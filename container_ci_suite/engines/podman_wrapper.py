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
import subprocess
import time
import json

from typing import Any

from container_ci_suite.utils import ContainerTestLibUtils


class PodmanCLIWrapper(object):
    @staticmethod
    def call_podman_command(
        cmd,
        return_output: bool = True,
        ignore_error: bool = False,
        shell: bool = True,
        debug: bool = False,
        stderr=subprocess.STDOUT,
    ):
        """
        Run docker command:
        """
        return ContainerTestLibUtils.run_command(
            f"podman {cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
            debug=debug,
            stderr=stderr,
        )

    @staticmethod
    def podman_image_exists(image_name: str) -> bool:
        """
        Check if docker image exists or not
        :param image_name: image to check
        :return True: In case if image is present
                False: In case if image is not present
        """
        output = PodmanCLIWrapper.call_podman_command(
            f"images -q {image_name}", ignore_error=True, return_output=True
        )
        return True if output != "" else False

    @staticmethod
    def podman_inspect(field: str, src_image: str) -> str:
        return PodmanCLIWrapper.call_podman_command(f"inspect -f '{field}' {src_image}")

    @staticmethod
    def podman_run_command(cmd):
        return PodmanCLIWrapper.call_podman_command(f"run {cmd}")

    @staticmethod
    def podman_exec_shell_command(
        cid_file_name: str,
        cmd: str,
        used_shell: str = "/bin/bash",
        return_output: bool = True,
        debug: bool = False,
    ):
        """
        Function executes shell command if image_name is present in system.
        :param cid_file_name: image to check specified by cid_file_name
        :param cmd: command that will be executed in image
        :param used_shell: which shell will be used /bin/bash or /bin/sh
        :return True: In case if image is present
                False: In case if image is not present
        """
        cmd = f'exec {cid_file_name} {used_shell} -c "{cmd}"'
        print(f"podman exec command is: {cmd}")
        try:
            output = PodmanCLIWrapper.call_podman_command(
                cmd=cmd, return_output=return_output, debug=debug
            )
        except subprocess.CalledProcessError as cpe:
            print(f"podman exec command {cmd} failed. See '{cpe}'")
            return False
        print(f"Output cmd is {output}")
        return output

    @staticmethod
    def podman_run_command_and_remove(
        cid_file_name: str,
        cmd: str,
        return_output: bool = True,
        debug: bool = False,
        ignore_error: bool = False,
    ):
        """
        Function run shell command if image_name is present in system.
        Calling is `podman run --rm {cid_file_name} /bin/bash -c "{cmd}"
        :param cid_file_name: image to check specified by cid_file_name
        :param cmd: command that will be executed in image
        :return True: In case if image is present
                False: In case if image is not present
        """
        cmd = f'run --rm {cid_file_name} /bin/bash -c "{cmd}"'
        print(f"podman exec command is: {cmd}")
        try:
            output = PodmanCLIWrapper.call_podman_command(
                cmd=cmd,
                return_output=return_output,
                ignore_error=ignore_error,
                debug=debug,
            )
        except subprocess.CalledProcessError as cpe:
            print(f"podman exec command {cmd} failed. See '{cpe}'")
            return False
        print(f"Output cmd is {output}")
        return output

    @staticmethod
    def podman_get_user_id(src_image, user):
        return PodmanCLIWrapper.call_podman_command(
            f"--rm {src_image} /bin/bash -c 'id -u {user}' 2>/dev/null"
        ).strip()

    @staticmethod
    def podman_pull_image(image_name: str, loops: int = 10) -> bool:
        """
        Function checks if image_name is present in system.
        In case it isn't, try to pull it for specific count of loops
        Default is 10.
        """
        if PodmanCLIWrapper.podman_image_exists(image_name=image_name):
            print("Pulled image already exists.")
            return True
        for loop in range(loops):
            ret_val = PodmanCLIWrapper.call_podman_command(
                cmd=f"pull {image_name}", return_output=False
            )
            if ret_val == 0 and PodmanCLIWrapper.podman_image_exists(
                image_name=image_name
            ):
                return True
            PodmanCLIWrapper.call_podman_command("images", return_output=True)
            print(
                f"Pulling of image {image_name} failed. Let's wait {loop * 5} seconds and try again."
            )
            time.sleep(loop * 5)
        return False

    @staticmethod
    def podman_inspect_ip_address(container_id: str) -> Any:
        output = PodmanCLIWrapper.call_podman_command(f"inspect {container_id}")

        json_output = json.loads(output)
        if len(json_output) == 0:
            return None
        if "NetworkSettings" not in json_output[0]:
            return None
        return json_output[0]["NetworkSettings"]["IPAddress"]

    @staticmethod
    def podman_exit_status(image_name: str) -> str:
        return PodmanCLIWrapper.call_podman_command(
            cmd=f"inspect --format='{{{{.State.ExitCode}}}}' {image_name}",
            return_output=True,
        ).strip()

    @staticmethod
    def podman_get_user(image_name: str) -> Any:
        output = PodmanCLIWrapper.call_podman_command(f"inspect {image_name}")

        json_output = json.loads(output)
        if len(json_output) == 0:
            return None
        if "Config" not in json_output[0]:
            return None
        return json_output[0]["Config"]["User"]

    @staticmethod
    def podman_get_file_content(cid_file_name: str, filename: str) -> str:
        return PodmanCLIWrapper.call_podman_command(
            cmd=f"exec {cid_file_name} cat {filename}"
        )
