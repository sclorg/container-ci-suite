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
import subprocess
import re

from typing import List
from pathlib import Path

from container_ci_suite.constants import CA_FILE_PATH

logger = logging.getLogger(__name__)


def get_file_content(filename: Path) -> str:
    with open(str(filename)) as f:
        return f.read()


def get_full_ca_file_path() -> Path:
    return Path(CA_FILE_PATH)


def get_os_environment(variable: str) -> str:
    return os.getenv(variable)


def get_mount_ca_file() -> str:
    if get_os_environment("NPM_REGISTRY") and get_full_ca_file_path().exists():
        return f"-v {CA_FILE_PATH}:{CA_FILE_PATH}:Z"
    return ""


def get_npm_variables():
    npm_registry = get_os_environment("NPM_REGISTRY")
    if npm_registry and get_full_ca_file_path().exists():
        return f"-e NPM_MIRROR={npm_registry} {get_mount_ca_file()}"
    return ""


def get_registry_name(os: str) -> str:
    return "registry.redhat.io" if os.startswith("rhel") else "docker.io"


def get_mount_options_from_s2i_args(s2i_args: str) -> str:
    # Check if -v parameter is present in s2i_args and add it into docker build command
    searchObj = re.search(r"(-v \.*\S*)", s2i_args)
    logger.debug(searchObj)
    if not searchObj:
        return ""

    logger.debug(searchObj.group(1))
    mount_options = searchObj.group()

    logger.info(f"Mount options: {mount_options}")
    return searchObj.group()


def get_env_commands_from_s2i_args(s2i_args: str) -> List:
    matchObj = re.findall(r"(-e|--env)\s*(\S*)=(\S*)", s2i_args)
    logger.debug(matchObj)
    env_content: List = []
    if matchObj:
        env_content.extend([f"ENV {x[1]}={x[2]}" for x in matchObj])
        logger.debug(env_content)
        return env_content
    return env_content


def get_public_image_name(os: str, base_image_name: str, version: str) -> str:
    registry = get_registry_name(os)
    if os == "rhel7":
        return f"{registry}/rhscl/{base_image_name}-{version}-rhel7"
    elif os == "rhel8":
        return f"{registry}/rhel8/{base_image_name}-{version}"
    else:
        return f"{registry}/centos/{base_image_name}-{version}-centos7"


def run_command(
    cmd,
    return_output: bool = True,
    ignore_error: bool = False,
    shell: bool = True,
    **kwargs,
):
    """
    Run provided command on host system using the same user as invoked this code.
    Raises subprocess.CalledProcessError if it fails.
    :param cmd: list or str
    :param return_output: bool, return output of the command
    :param ignore_error: bool, do not fail in case nonzero return code
    :param shell: bool, run command in shell
    :return: None or str
    """
    logger.debug("command: %r", cmd)
    try:
        if return_output:
            return subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=shell,
                **kwargs,
            )
        else:
            return subprocess.check_call(cmd, shell=shell, **kwargs)
    except subprocess.CalledProcessError as cpe:
        if ignore_error:
            if return_output:
                return cpe.output
            else:
                return cpe.returncode
        else:
            logger.error(f"failed with code {cpe.returncode} and output:\n{cpe.output}")
            raise cpe
