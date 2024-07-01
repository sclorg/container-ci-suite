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
import shutil
import subprocess
import re
import time
import random
import string
import requests
import tempfile
import yaml

from typing import List, Any
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


def get_registry_name(os_name: str) -> str:
    return "registry.redhat.io" if os_name.startswith("rhel") else "docker.io"


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


def download_template(template_name: str, dir_name: str = "/var/tmp") -> Any:
    ext = ""
    file_ext_field = template_name.split(".")
    if len(file_ext_field) > 1:
        ext = f".{file_ext_field[1]}"
    print(f"Local temporary file {template_name} with extension {ext}")
    print(f"Temporary file: download_template from {template_name}")
    random_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    path_name = f"{dir_name}/{random_text}{ext}"
    if Path(template_name).is_file():
        shutil.copy2(template_name, path_name)
        return str(path_name)
    if Path(template_name).is_dir():
        shutil.copytree(template_name, path_name, symlinks=True)
        return str(path_name)
    if template_name.startswith("http"):
        resp = requests.get(template_name, verify=False)
        resp.raise_for_status()
        if resp.status_code != 200:
            print(f"utils.download_template: {resp.status_code} and {resp.text}")
            return None
        with open(path_name, "wb") as fd:
            fd.write(resp.content)
        return str(path_name)
    if not Path(template_name).exists():
        print("File to download does not exist.")
        return None


def run_command(
    cmd,
    return_output: bool = True,
    ignore_error: bool = False,
    shell: bool = True,
    debug: bool = False,
    **kwargs,
):
    """
    Run provided command on host system using the same user as invoked this code.
    Raises subprocess.CalledProcessError if it fails.
    :param cmd: list or str
    :param return_output: bool, return output of the command
    :param ignore_error: bool, do not fail in case nonzero return code
    :param shell: bool, run command in shell
    :param debug: bool, print command in shell, default is suppressed
    :return: None or str
    """
    if debug:
        logger.debug(f"command: {cmd}")
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


def get_response_request(url_address: str, expected_str: str, response_code: int = 200, max_tests: int = 3) -> bool:
    for count in range(max_tests):
        try:
            resp = requests.get(url_address, timeout=10, verify=False)
            resp.raise_for_status()
            print(f"Response code is {resp.status_code} and expected should be {response_code}")
            if resp.status_code == response_code and expected_str in resp.text:
                return True
            return False
        except requests.exceptions.HTTPError:
            print("get_response_request: Service is not yet available. Let's wait some time")
            pass
        except requests.exceptions.ConnectTimeout:
            print("get_response_request: ConnectTimeout. Let's wait some time")
            pass
        time.sleep(10)
    return False


def save_command_yaml(image_name: str) -> str:
    cmd_yaml = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "command-app"
        },
        "spec": {
            "restartPolicy": "OnFailure",
            "containers": [
                {
                    "name": "command-container",
                    "image": image_name,
                    "command": ["sleep"],
                    "args": ["3h"]
                }
            ]
        }
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="command-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(cmd_yaml, fp)
    print(f"Pod command yaml file: {temp_file.name}")
    return temp_file.name


def get_tagged_image(image_name: str, version: str) -> Any:
    try:
        image_no_namespace = image_name.split('/')[1]
        image_no_tag = image_no_namespace.split(':')[0]
    except IndexError:
        return None

    return f"{image_no_tag}:{version}"


def get_service_image(image_name: str) -> Any:
    try:
        image_no_namespace = image_name.split('/')[1]
        image_no_tag = image_no_namespace.split(':')[0]
    except IndexError:
        return None
    return f"{image_no_tag}-testing"


def check_variables() -> bool:
    ret_value: bool = True
    if not os.getenv("IMAGE_NAME", None):
        print("Make sure IMAGE_NAME is defined")
        ret_value = False
    if not os.getenv("SINGLE_VERSION"):
        print("Make sure SINGLE_VERSION is defined")
        ret_value = False
    if not os.getenv("OS"):
        print("Make sure OS is defined")
        ret_value = False
    return ret_value
