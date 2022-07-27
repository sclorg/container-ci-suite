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

from container_ci_suite.utils import run_command


class DockerCLIWrapper(object):
    @staticmethod
    def run_docker_command(
        cmd, return_output: bool = True, ignore_error: bool = False, shell: bool = True
    ):
        """
        Run docker command:
        """
        return run_command(
            f"docker {cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    @staticmethod
    def docker_image_exists(image_name: str) -> bool:
        """
        Check if docker image exists or not
        """
        output = DockerCLIWrapper.run_docker_command(
            f"images {image_name}", ignore_error=True
        )
        if image_name in output:
            return True
        return False

    @staticmethod
    def docker_inspect(field: str, src_image: str) -> str:
        return DockerCLIWrapper.run_docker_command(
            f"docker inspect -f '{field}' {src_image}"
        )

    @staticmethod
    def docker_run_command(cmd):
        return DockerCLIWrapper.run_docker_command(f"run {cmd}")

    @staticmethod
    def docker_get_user_id(src_image, user):
        return DockerCLIWrapper.docker_run_command(
            f"--rm {src_image} bash -c 'id -u {user} 2>/dev/null"
        )
