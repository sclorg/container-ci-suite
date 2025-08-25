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
import time
import subprocess
import shutil

from typing import List
from pathlib import Path
from tempfile import mkdtemp, mktemp

from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper
from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite import utils
from container_ci_suite.utils import cwd


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class S2IContainerImage:
    def __init__(self, image_name: str):
        self.image_name: str = image_name
        self.container_args: str = ""
        self.cid_file: Path = None
        self.cid_file_dir: Path = None
        logger.info(f"Image name to test: {image_name}")

    # Replacement for ct_s2i_usage
    def s2i_usage(self) -> str:
        return PodmanCLIWrapper.run_docker_command(
            f"run --rm {self.image_name} bash -c /usr/libexec/s2i/usage"
        )

    # Replacement for
    def is_image_available(self):
        return PodmanCLIWrapper.run_docker_command(f"inspect {self.image_name}")

    # Replacement for ct_s2i_build_as_df
    def s2i_build_as_df(self, app_path: str, src_image: str, dst_image: str, s2i_args: str = "--pull-policy=never"):
        named_tmp_dir = mkdtemp()
        tmp_dir = Path(named_tmp_dir)
        if tmp_dir.exists():
            logger.debug("Temporary Directory exists.")
        else:
            logger.debug("Temporary directory not exists.")
        with cwd(tmp_dir) as _:
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
                f.write(df_content)
            mount_options = utils.get_mount_options_from_s2i_args(s2i_args=s2i_args)
            # Run the build and tag the result
            build_cmd = f"build {mount_options} -f {df_name} --no-cache=true -t {dst_image}"
            print(build_cmd)
            try:
                PodmanCLIWrapper.run_docker_command(cmd=build_cmd)
            except subprocess.CalledProcessError as cpe:
                print(f"Building S2I Image failed: {cpe.stderr} with {cpe.output}")
                return None
            return S2IContainerImage(image_name=dst_image)

    # Replacement for ct_s2i_build_as_df_build_args
    def s2i_create_df(
        self, tmp_dir: Path, app_path: str, s2i_args: str, src_image, dst_image: str
    ) -> str:
        real_app_path = app_path.replace("file://", "")
        df_content: List = []
        local_scripts: Path = Path("upload/scripts")
        local_app: Path = Path("upload/src")

        if not PodmanCLIWrapper.docker_image_exists(src_image):
            if "pull-policy=never" not in s2i_args:
                PodmanCLIWrapper.run_docker_command(f"pull {src_image}")

        user = PodmanCLIWrapper.docker_get_user(src_image)
        print(f"User name from container {src_image} is {user}")
        if not user:
            user = "0"

        assert int(user)
        user_id = PodmanCLIWrapper.docker_get_user_id(src_image=src_image, user=user)
        if not user_id:
            logger.error(f"id of user {user} not found inside image {src_image}.")
            logger.error("Terminating s2i build.")
            return None

        incremental: bool = "--incremental" in s2i_args
        print(f"s2i_create_df: increamental is: {incremental}")
        if incremental:
            inc_tmp = Path(mktemp(dir=str(tmp_dir), prefix="incremental."))
            ContainerTestLibUtils.run_command(f"setfacl -m 'u:{user_id}:rwx' {inc_tmp}")
            # Check if the image exists, build should fail (for testing use case) if it does not
            if not PodmanCLIWrapper.docker_image_exists(src_image):
                return None
            # Run the original image with a mounted in volume and get the artifacts out of it
            cmd = (
                "if [ -s /usr/libexec/s2i/save-artifacts ];"
                ' then /usr/libexec/s2i/save-artifacts > "$inc_tmp/artifacts.tar";'
                ' else touch "$inc_tmp/artifacts.tar"; fi'
            )
            PodmanCLIWrapper.run_docker_command(
                f"run --rm -v {inc_tmp}:{inc_tmp}:Z {dst_image} bash -c {cmd}"
            )
            # Move the created content into the $tmpdir for the build to pick it up
            shutil.move(f"{inc_tmp}/artifacts.tar", tmp_dir.name)

        real_local_app = tmp_dir / local_app
        print(f"Real local app is: {real_local_app} and app_path: {real_app_path}")
        real_local_app.mkdir(parents=True, exist_ok=True)
        shutil.copytree(real_app_path + "/.", real_local_app)
        real_local_scripts = tmp_dir / local_scripts
        bin_dir = local_app / ".s2i" / "bin"
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
        env_content = utils.get_env_commands_from_s2i_args(s2i_args=s2i_args)
        df_content.extend(env_content)

        # Check if CA autority is present on host and add it into Dockerfile
        if utils.get_full_ca_file_path().exists():
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

        return '\n'.join(df_content)

    # Replacement for ct_clean_containers
    def cleanup_container(self):
        logger.info(f"Cleaning CID_FILE_DIR {self.cid_file_dir} is ongoing.")
        p = Path(self.cid_file_dir)
        cid_files = p.glob("*")
        for cid_file in cid_files:
            if not cid_file.exists():
                continue
            container_id = utils.get_file_content(cid_file)
            logger.info("Stopping container")
            PodmanCLIWrapper.run_docker_command(f"stop {container_id}")
            exit_code = PodmanCLIWrapper.docker_inspect(
                field="{{.State.ExitCode}}", src_image=container_id
            )
            if exit_code != 0:
                logs = PodmanCLIWrapper.run_docker_command(f"logs {container_id}")
                logger.info(logs)
            PodmanCLIWrapper.run_docker_command(f"rm -v {container_id}")
            # cid_file.unlink()
        os.rmdir(self.cid_file_dir)
        logger.info(f"Cleanning CID_FILE_DIR {self.cid_file_dir} is DONE.")

    # Replacement for ct_binary_found_from_df
    def binary_found_from_df(self, binary: str = "", binary_path: str = "^/opt/rh"):
        tempdir = mkdtemp(suffix=f"{self.image_name}_binary")
        dockerfile = Path(tempdir) / "Dockerfile"
        logger.info(f"Testing {binary} in build from Dockerfile")
        content: str = f"""FROM {self.image_name}
RUN which {binary} | grep {binary_path}
        """
        with open(dockerfile, "w") as f:
            f.write(content)
        if not PodmanCLIWrapper.run_docker_command(
            f"build -f {dockerfile} --no-cache {tempdir}", return_output=False
        ):
            logger.error(f"Failed to find {binary} in Dockerfile!")
            return False
        return True

    def doc_content_old(self, strings: List) -> bool:
        logger.info("Testing documentation in the container image")
        files_to_check = ["help.1"]
        for f in files_to_check:
            doc_content = PodmanCLIWrapper.docker_run_command(f'--rm {self.image_name} /bin/bash -c cat {f}')
            for term in strings:
                # test = re.search(f"{term}", doc_content)
                logger.info(f"ERROR: File /{f} does not contain '{term}'.")
                return False
            for term in ["TH", "PP", "SH"]:
                if term not in doc_content:
                    logger.info(f"ERROR: help.1 is probably not in troff or groff format, since {term} is missing")
                    return False
        return True

    def test_response(
            self, url: str = "",
            expected_code: int = 200, port: int = 8080,
            expected_output: str = "", max_tests: int = 20
    ) -> bool:
        url = f"{url}:{port}"
        print(f"URL address to get response from container: {url}")
        cmd_to_run = "curl --connect-timeout 10 -k -s -w '%{http_code}' " + f"{url}"
        # Check if application returns proper HTTP_CODE
        print("Check if HTTP_CODE is valid.")
        for count in range(max_tests):
            try:
                output_code = ContainerTestLibUtils.run_command(cmd=f"{cmd_to_run}", return_output=True)
                return_code = output_code[-3:]
                print(f"Output is: {output_code} and Return Code is: {return_code}")
                try:
                    int_ret_code = int(return_code)
                    if int_ret_code == expected_code:
                        print(f"HTTP_CODE is VALID {int_ret_code}")
                        break
                except ValueError:
                    logger.info(return_code)
                    time.sleep(1)
                    continue
                time.sleep(3)
                continue
            except subprocess.CalledProcessError as cpe:
                print(f"Error from {cmd_to_run} is {cpe.stderr}, {cpe.stdout}")
                time.sleep(3)

        cmd_to_run = "curl --connect-timeout 10 -k -s " + f"{url}"
        # Check if application returns proper output
        for count in range(max_tests):
            output_code = ContainerTestLibUtils.run_command(cmd=f"{cmd_to_run}", return_output=True)
            print(f"Check if expected output {expected_output} is in {cmd_to_run}.")
            if expected_output in output_code:
                print(f"Expected output '{expected_output}' is present.")
                return True
            print(
                f"check_response_inside_cluster:"
                f"expected_output {expected_output} not found in output of {cmd_to_run} command. See {output_code}"
            )
            time.sleep(5)
        return False
