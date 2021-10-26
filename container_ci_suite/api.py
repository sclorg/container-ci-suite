#!/bin/env python3

# MIT License
#
# Copyright (c) 2018-2019 Red Hat, Inc.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import logging
import re
import time
import subprocess
import shutil

from typing import List
from os import getenv
from pathlib import Path
from tempfile import mkdtemp, mktemp

from container_ci_suite.container import DockerCLIWrapper
from container_ci_suite.utils import (
    run_command,
    get_file_content,
    get_mount_ca_file,
    get_full_ca_file_path,
    get_os_environment,
    get_mount_options_from_s2i_args,
    get_env_commands_from_s2i_args,
)

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ContainerCISuite(object):
    def __init__(self, image_name: str):
        self.image_name: str = image_name
        self.container_args: str = ""
        self.cid_file: Path = None
        self.cid_file_dir: Path = None
        logger.info(f"Image name to test: {image_name}")

    def s2i_usage(self):
        return DockerCLIWrapper.run_docker_command(
            f"run --rm {self.image_name} bash -c /usr/libexec/s2i/usage"
        )

    def is_image_available(self):
        return DockerCLIWrapper.run_docker_command(f"inspect {self.image_name}")

    def s2i_build_as_df(self, app_path: str, s2i_args: str, src_image, dst_image: str):
        named_tmp_dir = mkdtemp()
        tmp_dir = Path(named_tmp_dir)
        if tmp_dir.exists():
            logger.debug("Temporary Directory exists.")
        else:
            logger.debug("Temporary directory not exists.")
        ntf = mktemp(dir=str(tmp_dir), prefix="Dockerfile.")
        df_name = Path(ntf)
        df_content = self.s2i_create_df(
            tmp_dir=tmp_dir,
            app_path=app_path,
            s2i_args=s2i_args,
            src_image=src_image,
            dst_image=dst_image,
        )
        with open(df_name, mode="w") as f:
            f.writelines(df_content)
        mount_options = get_mount_options_from_s2i_args(s2i_args=s2i_args)
        # Run the build and tag the result
        DockerCLIWrapper.run_docker_command(
            f"build {mount_options} -f {df_name} --no-cache=true -t {dst_image}"
        )

    def s2i_create_df(
        self, tmp_dir: Path, app_path: str, s2i_args: str, src_image, dst_image: str
    ) -> List[str]:
        real_app_path = app_path.replace("file://", "")
        df_content: List = []
        local_scripts: str = "upload/scripts"
        local_app: str = "upload/src"
        os.chdir(tmp_dir)
        if not DockerCLIWrapper.docker_image_exists(src_image):
            if "pull-policy=never" not in s2i_args:
                DockerCLIWrapper.run_docker_command(f"pull {src_image}")

        user = DockerCLIWrapper.docker_inspect(
            field="{{.Config.User}}", src_image=src_image
        )
        if not user:
            user = "0"

        assert int(user)
        user_id = DockerCLIWrapper.docker_get_user_id(src_image=src_image, user=user)
        if not user_id:
            logger.error(f"id of user {user} not found inside image {src_image}.")
            logger.error("Terminating s2i build.")
            return None
        else:
            user_id = user

        incremental: bool = "--incremental" in s2i_args
        if incremental:
            inc_tmp = Path(mktemp(dir=str(tmp_dir), prefix="incremental."))
            run_command(f"setfacl -m 'u:{user_id}:rwx' {inc_tmp}")
            # Check if the image exists, build should fail (for testing use case) if it does not
            if not DockerCLIWrapper.docker_image_exists(src_image):
                return None
            # Run the original image with a mounted in volume and get the artifacts out of it
            cmd = (
                "if [ -s /usr/libexec/s2i/save-artifacts ];"
                ' then /usr/libexec/s2i/save-artifacts > "$inc_tmp/artifacts.tar";'
                ' else touch "$inc_tmp/artifacts.tar"; fi'
            )
            DockerCLIWrapper.run_docker_command(
                f"run --rm -v {inc_tmp}:{inc_tmp}:Z {dst_image} bash -c {cmd}"
            )
            # Move the created content into the $tmpdir for the build to pick it up
            shutil.move(f"{inc_tmp}/artifacts.tar", tmp_dir.name)
        real_local_app = tmp_dir / local_app
        real_local_scripts = tmp_dir / local_scripts
        os.makedirs(real_local_app.parent)
        shutil.copytree(real_app_path, real_local_app)
        bin_dir = real_local_app / ".s2i" / "bin"
        if bin_dir.exists():
            shutil.move(bin_dir, real_local_scripts)
        df_content.extend(
            [
                f"FROM {src_image}",
                f"LABEL io.openshift.s2i.build.image={src_image} "
                f"io.openshift.s2i.build.source-location={app_path}",
                "USER root",
                f"COPY {local_app}/ /tmp/src",
            ]
        )
        if real_local_scripts.exists():
            df_content.append(f"COPY {local_scripts} /tmp/scripts")
            df_content.append(f"RUN chown -R {user_id}:0 /tmp/scripts")
        df_content.append(f"RUN chown -R {user_id}:0 /tmp/src")

        # Check for custom environment variables inside .s2i/ folder
        env_file = Path(real_local_app / ".s2i" / "environment")
        if env_file.exists():
            with open(env_file) as fd:
                env_content = fd.readlines()
            # Remove any comments and add the contents as ENV commands to the Dockerfile
            env_content = [f"ENV {x}" for x in env_content if not x.startswith("#")]
            df_content.extend(env_content)

        # Filter out env var definitions from $s2i_args
        # and create Dockerfile ENV commands out of them
        env_content = get_env_commands_from_s2i_args(s2i_args=s2i_args)
        df_content.extend(env_content)

        # Check if CA autority is present on host and add it into Dockerfile
        if get_full_ca_file_path().exists():
            df_content.append(
                "RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract"
            )
        # Add in artifacts if doing an incremental build
        if incremental:
            df_content.extend(
                [
                    "RUN mkdir /tmp/artifacts",
                    "RUN artifacts.tar /tmp/artifacts",
                    f"RUN chown -R {user_id}:0 /tmp/artifacts",
                ]
            )
        df_content.append(f"USER {user_id}")
        # If exists, run the custom assemble script, else default to /usr/libexec/s2i/assemble
        if (real_local_scripts / "assemble").exists():
            df_content.append("RUN /tmp/scripts/assemble")
        else:
            df_content.append("RUN /usr/libexec/s2i/assemble")
        # If exists, set the custom run script as CMD, else default to /usr/libexec/s2i/run
        if Path(real_local_scripts / "run").exists():
            df_content.append("CMD /tmp/scripts/run")
        else:
            df_content.append("CMD /usr/libexec/s2i/run")

        logger.error(df_content)
        return df_content

    def scl_usage_old(self):
        pass

    def create_container(self, cid_file: str, container_args: str = "", *args):
        self.cid_file_dir = Path(mkdtemp(suffix=".test_cid_files"))
        p = Path(self.cid_file_dir)
        self.cid_file = p / cid_file
        DockerCLIWrapper.run_docker_command(
            f"run --cidfile={self.cid_file} -d {container_args} {self.image_name} {args}"
        )
        if not self.wait_for_cid():
            return False
        logger.info(f"Created container {self.get_cid_file()}")

    def wait_for_cid(self):
        max_attempts: int = 10
        attempt: int = 1
        while attempt < max_attempts:
            if self.cid_file.exists():
                with open(self.cid_file) as f:
                    logger.debug(f"{self.cid_file} contains:")
                    logger.info(f.readlines())
                return True
            logger.info("Waiting for container to start.")
            attempt += 1
            time.sleep(1)
        return False

    def get_cip(self):
        container_id = self.get_cid_file()
        return DockerCLIWrapper.run_docker_command(
            f"inspect --format='{{.NetworkSettings.IPAddress}}' {container_id}"
        )

    def check_envs_set(self):
        pass

    def get_cid_file(self, cid_file: Path = None):
        if cid_file is None:
            return get_file_content(self.cid_file)
        return get_file_content(cid_file)

    def check_image_availability(self, public_image_name: str):
        try:
            DockerCLIWrapper.run_docker_command(
                f"pull {public_image_name}", return_output=False
            )
        except subprocess.CalledProcessError as cfe:
            logger.error(f"{public_image_name} could not be downloaded via 'docker'.")
            logger.error(cfe)
            return False
        return True

    def cleanup_container(self):
        logger.info(f"Cleaning CID_FILE_DIR {self.cid_file_dir} is ongoing.")
        p = Path(self.cid_file_dir)
        cid_files = p.glob("*")
        for cid_file in cid_files:
            container_id = get_file_content(cid_file)
            logger.info("Stopping container")
            DockerCLIWrapper.run_docker_command(f"stop {container_id}")
            exit_code = DockerCLIWrapper.docker_inspect(
                field="{{.State.ExitCode}}", src_image=container_id
            )
            if exit_code != 0:
                logs = DockerCLIWrapper.run_docker_command(f"logs {container_id}")
                logger.info(logs)
            DockerCLIWrapper.run_docker_command(f"rm -v {container_id}")
            cid_file.unlink()
        os.rmdir(self.cid_file_dir)
        logger.info(f"Cleanning CID_FILE_DIR {self.cid_file_dir} is DONE.")

    def assert_container_fails(self, cid_file: str, container_args: str):
        attempt: int = 1
        max_attempts: int = 10
        old_container_args = container_args
        if self.create_container(cid_file, container_args=container_args):
            cid = self.get_cid_file()
            while not DockerCLIWrapper.docker_inspect(
                field="{{.State.Running}}", src_image=cid
            ):
                time.sleep(2)
                attempt += 1
                if attempt > max_attempts:
                    DockerCLIWrapper.run_docker_command("stop cid")
                    return True
            exit_code = DockerCLIWrapper.docker_inspect(
                field="{{.State.ExitCode}}", src_image=cid
            )
            if exit_code == 0:
                return True
            DockerCLIWrapper.run_docker_command(f"rm -v {cid}")
            self.cid_file.unlink()
        if old_container_args != "":
            self.container_args = old_container_args
        return False

    def npm_works(self):
        tempdir = mkdtemp(suffix="npm_test")
        self.cid_file = Path(tempdir) / "cid_npm_test"
        try:
            DockerCLIWrapper.run_docker_command(
                f'run --rm {self.image_name} /bin/bash -c "npm --version"'
            )
        except subprocess.CalledProcessError:
            logger.error(
                f"'npm --version' does not work inside the image {self.image_name}."
            )
            return False

        # TODO
        # Add {self.iamge_name}-testapp as soon as function `s2i_create_df` is ready.
        DockerCLIWrapper.run_docker_command(
            f"run -d {get_mount_ca_file()} --rm --cidfile={self.cid_file} {self.image_name}"
        )
        if not self.wait_for_cid():
            logger.error("Container did not create cidfile.")
            return False

        try:
            jquery_output = DockerCLIWrapper.run_docker_command(
                f"exec {self.get_cid_file(self.cid_file)} "
                f"/bin/bash -c "
                f"'npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js'"
            )
        except subprocess.CalledProcessError:
            logger.error(
                f"npm could not install jquery inside the image ${self.image_name}."
            )
            return False
        if getenv("NPM_REGISTRY") and get_full_ca_file_path().exists():
            if get_os_environment("NPM_REGISTRY") in jquery_output:
                logger.error("Internal repository is NOT set. Even it is requested.")
                return False

        if self.cid_file.exists():
            DockerCLIWrapper.run_docker_command(
                f"stop {self.get_cid_file(self.cid_file)}"
            )
            self.cid_file.unlink()
        logger.info("Npm works.")
        return True

    def binary_found_from_df(self, binary: str = "", binary_path: str = "^/opt/rh"):
        tempdir = mkdtemp(suffix=f"{self.image_name}_binary")
        dockerfile = Path(tempdir) / "Dockerfile"
        logger.info(f"Testing {binary} in build from Dockerfile")
        content: str = f"""FROM {self.image_name}
RUN which {binary} | grep {binary_path}
        """
        with open(dockerfile, "w") as f:
            f.write(content)
        if not DockerCLIWrapper.run_docker_command(
            f"build -f {dockerfile} --no-cache {tempdir}", return_output=False
        ):
            logger.error(f"Failed to find {binary} in Dockerfile!")
            return False
        return True

    def check_latest_imagestreams(self):
        pass

    #     local latest_version=
    #     local test_lib_dir=
    #
    #     # Check only lines which starts with VERSIONS
    #     latest_version=$(grep '^VERSIONS' Makefile | rev | cut -d ' ' -f 1 | rev )
    #     test_lib_dir=$(dirname "$(readlink -f "$0")")
    #     python3 "${test_lib_dir}/check_imagestreams.py" "$latest_version"
    #

    def doc_content_old(self):
        pass

    #         # ct_doc_content_old [strings]
    #         # --------------------
    #         # Looks for occurence of stirngs in the documentation files and checks
    #         # the format of the files. Files examined: help.1
    #         # Argument: strings - strings expected to appear in the documentation
    #         # Uses: $IMAGE_NAME - name of the image being tested
    #         function
    #         ct_doc_content_old()
    #         {
    #             local
    #         tmpdir
    #         tmpdir =$(mktemp - d)
    #         local
    #         f
    #         : "  Testing documentation in the container image"
    #         # Extract the help files from the container
    #         # shellcheck disable=SC2043
    #         for f in help.1; do
    #         docker run --rm "${IMAGE_NAME}" / bin / bash -c "cat /${f}" >
    #         "${tmpdir}/$(basename "${f}")"
    #         # Check whether the files contain some important information
    #         for term in "$@"; do
    #         if ! grep -F -q -e "${term}" "${tmpdir}/$(basename "${f}")"; then
    #         echo "ERROR: File /${f} does not include '${term}'." > & 2
    #         return 1
    #         fi
    #
    #     done
    #     # Check whether the files use the correct format
    #     for term in TH PP SH; do
    #     if ! grep -q "^\.${term}" "${tmpdir}/help.1"; then
    #     echo
    #     "ERROR: /help.1 is probably not in troff or groff format, since
    #     '${term}' is missing." > & 2
    #     return 1
    #
    #
    # fi
    # done
    # done
    # : "  Success!"
    # }

    def test_response(self):
        pass

    def test_check_exec_env_vars(self, env_filter: str = "^X_SCLS=|/opt/rh|/opt/app-root"):
        check_envs = DockerCLIWrapper.docker_run_command(f'--rm {self.image_name} /bin/bash -c env')
        logger.debug(f"Run envs {check_envs}")
        self.create_container(cid_file="exec_env_vars", container_args="bash -c 'sleep 1000'")
        loop_envs = DockerCLIWrapper.run_docker_command(f"exec {self.get_cid_file(self.cid_file)} env")
        self.test_check_envs_set(env_filter=env_filter, check_envs=check_envs, loop_envs=loop_envs)

    def test_check_envs_set(self, env_filter: str, check_envs: str, loop_envs: str, env_format="VALUE"):
        fields_to_check: List = [
            x for x in loop_envs.split('\n') if re.findall(env_filter, x) and not x.startswith("PWD=")
        ]
        for field in fields_to_check:
            var_name, stripped = field.split('=', 2)
            filtered_envs = [x for x in check_envs.split('\n') if x.startswith(f"{var_name}=")]
            if not filtered_envs:
                logger.error(f"{var_name} not found during 'docker exec'")
                return False
            filter_envs = ''.join(filtered_envs)
            for value in stripped.split(':'):
                # If the value checked does not go through env_filter we do not care about it
                ret = re.findall(env_filter, value)
                if not ret:
                    continue
                new_env = env_format.replace('VALUE', value)
                find_env = re.findall(rf"{new_env}", filter_envs)
                if not find_env:
                    logger.error(f"Value {value} is missing from variable {var_name}")
                    logger.error(filtered_envs)
                    return False
        return True
