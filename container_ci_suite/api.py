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

from os import getenv
from pathlib import Path
from tempfile import TemporaryDirectory

from container_ci_suite.utils import (
    run_docker_command,
    get_file_content,
    get_mount_ca_file,
    get_full_ca_file_path,
    get_os_environment,
)

test_dir = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger()

# TODO
# Do we want to import docker.py or libpod?
# Or directly call docker / podman commands


class ContainerCISuite(object):

    def __init__(self, image_name: str):
        self.image_name = image_name
        self.cid_file_dir = TemporaryDirectory(suffix=f"{self.image_name}_test_cid_files")
        self.cid_file: Path = None
        self.container_args: str = ""

    def s2i_usage(self):
        return run_docker_command(f"run --rm {self.image_name} bash -c /usr/libexec/s2i/usage")

    def is_image_available(self):
        return run_docker_command(f"inspect {self.image_name}")

    def build_dockerfile_from_s2i(self, app_path: str, s2i_args: str, src_image, dst_image: str):
        local_app = "upload/src"
        local_scripts = "upload/scripts"
        mount_options = ""
        incremental = False
        tmp_dir = TemporaryDirectory()
        df_name = Path(tmp_dir.name) / "Dockerfile.XXXXX"
        if not run_docker_command(f"docker images {src_image}"):
            if "pull-policy=never" not in s2i_args:
                run_docker_command(f"pull {src_image}")

        user = run_docker_command(f'inspect -f "{{.Config.User}}" {src_image}')
        if not user:
            user = 0

        assert int(user)
        user_id = run_docker_command(f"run --rm {src_image} bash -c 'id -u {user} 2>/dev/null")
        if not user_id:
            logger.error(f"id of user {user} not found inside image {src_image}.")
            logger.error("Terminating s2i build.")
            return 1
        else:
            user_id = user

        incremental = "--incremental" in s2i_args
        pass

    def scl_usage_old(self):
        pass

    def create_container(self, cid_file: str, container_args: str = "", *args):
        p = Path(self.cid_file_dir.name)
        self.cid_file = p / cid_file
        run_docker_command(f"run --cidfile={self.cid_file} -d {container_args} {self.image_name} {args}")
        if not self.wait_for_cid():
            return False
        logger.info(f"Created container {self.get_cid_file()}")

    def wait_for_cid(self):
        max_attempts: int = 10
        attempt: int = 1
        while attempt < max_attempts:
            if self.cid_file.exists():
                return True
            logger.info("Waiting for container to start.")
            attempt += 1
            time.sleep(1)
        return False

    def get_cip(self):
        container_id = self.get_cid_file()
        return run_docker_command(f"inspect --format='{{.NetworkSettings.IPAddress}}'"
                                  f"{container_id}")

    def check_envs_set(self):
        pass

    def get_cid_file(self, cid_file: Path = None):
        if cid_file is None:
            return get_file_content(self.cid_file)
        return get_file_content(cid_file)

    def check_image_availability(self, public_image_name: str):
        try:
            run_docker_command(f"pull {public_image_name}", return_output=False)
        except subprocess.CalledProcessError as cfe:
            logger.error(f"{public_image_name} could not be downloaded via 'docker'.")
            logger.error(cfe)
            return False
        return True

    def cleanup_container(self):
        logger.info(f"Cleaning CID_FILE_DIR {self.cid_file_dir.name} is ongoing.")
        p = Path(self.cid_file_dir.name)
        cid_files = p.glob("*")
        for cid_file in cid_files:
            container_id = get_file_content(cid_file)
            logger.info("Stopping container")
            run_docker_command(f"stop {container_id}")
            exit_code = run_docker_command(f"inspect -f '{{.State.ExitCode}}' {container_id}")
            if exit_code != 0:
                logs = run_docker_command(f"logs {container_id}")
                logger.info(logs)
            run_docker_command(f"rm -v {container_id}")
            cid_file.unlink()
        self.cid_file_dir.cleanup()
        logger.info(f"Cleanning CID_FILE_DIR {self.cid_file_dir.name} is DONE.")

    def assert_container_fails(self, cid_file: str, container_args: str):
        attempt: int = 1
        max_attempts: int = 10
        old_container_args = container_args
        if self.create_container(cid_file, container_args=container_args):
            cid = self.get_cid_file()
            cmd = f"inspect -f '{{.State.Running}}' {cid}"
            while run_docker_command(cmd) != True:
                time.sleep(2)
                attempt += 1
                if attempt > max_attempts:
                    run_docker_command("stop cid")
                    return True
            exit_code = run_docker_command(f"inspect -f '{{.State.ExitCode}}' {cid}")
            if exit_code == 0:
                return True
            run_docker_command(f"rm -v {cid}")
            self.cid_file.unlink()
        if old_container_args != "":
            self.container_args = old_container_args
        return False

    def npm_works(self):
        tempdir = TemporaryDirectory(suffix=f"{self.image_name}_npm_test")
        cid_file = Path(tempdir.name) / "cid_npm_test"
        try:
            run_docker_command(f"run --rm {self.image_name} /bin/bash -c 'npm --version'")
        except subprocess.CalledProcessError:
            logger.error(f"'npm --version' does not work inside the image {self.image_name}.")
            return False

        run_docker_command(f"run -d {get_mount_ca_file()} --rm"
                           f"--cidfile={cid_file} {self.image_name}-testapp")
        if not self.wait_for_cid():
            return False

        try:
            jquery_output = run_docker_command(
                f"exec {self.get_cid_file(cid_file)} "
                f"/bin/bash -c 'npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js'")
        except subprocess.CalledProcessError:
            logger.error(f"npm could not install jquery inside the image ${self.image_name}.")
            return False
        if getenv("NPM_REGISTRY") and get_full_ca_file_path().exists():
            if get_os_environment("NPM_REGISTRY") in jquery_output:
                logger.error("Internal repository is NOT set. Even it is requested.")
                return False

        if cid_file.exists():
            run_docker_command(f"stop {self.get_cid_file(cid_file)}")
            cid_file.unlink()
        logger.info("Npm works.")
        return True

    def binary_found_from_df(self, binary: str = "", binary_path: str = "^/opt/rh"):
        tempdir = TemporaryDirectory(suffix=f"{self.image_name}_binary")
        dockerfile = Path(tempdir.name) / "Dockerfile"
        logger.info(f"Testing {binary} in build from Dockerfile")
        content: str = f"""FROM {self.image_name}
RUN which {binary} | grep {binary_path}
        """
        with open(dockerfile, "w") as f:
            f.write(content)
        if not run_docker_command(f"build -f {dockerfile} --no-cache {tempdir.name}",
                                  return_output=False):
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
#         docker run --rm "${IMAGE_NAME}" / bin / bash -c "cat /${f}" > "${tmpdir}/$(basename "${f}")"
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
#     "ERROR: /help.1 is probably not in troff or groff format, since '${term}' is missing." > & 2
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
