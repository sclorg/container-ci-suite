# MIT License
#
# Copyright (c) 2018-2019 Red Hat, Inc.
import json
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
import contextlib

from typing import List, Any
from pathlib import Path
from datetime import datetime


from container_ci_suite.constants import CA_FILE_PATH

logger = logging.getLogger(__name__)


def get_file_content(filename: Path) -> str:
    with open(str(filename)) as f:
        return f.read()


def save_file_content(content: str, filename: Path):
    with open(str(filename), "w") as f:
        f.write(content)


def get_full_ca_file_path() -> Path:
    return Path(CA_FILE_PATH)


def get_os_environment(variable: str) -> str:
    return os.getenv(variable)


# Replacement for ct_mount_ca_file
def get_mount_ca_file() -> str:
    if get_os_environment("NPM_REGISTRY") and get_full_ca_file_path().exists():
        return f"-v {CA_FILE_PATH}:{CA_FILE_PATH}:Z"
    return ""


# Replacement for ct_mount_ca_file
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
    if os == "rhel8":
        return f"{registry}/rhel8/{base_image_name}-{version}"
    if os == "rhel9":
        return f"{registry}/rhel9/{base_image_name}-{version}"
    if os == "rhel10":
        return f"{registry}/rhel10/{base_image_name}-{version}"
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


class ContainerTestLibUtils:
    @staticmethod
    def run_command(
        cmd,
        return_output: bool = True,
        ignore_error: bool = False,
        shell: bool = True,
        debug: bool = False,
        stderr=subprocess.STDOUT,
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
        :param stderr: bool, print command in shell, default is suppressed
        :return: None or str
        """
        if debug:
            print(f"command: {cmd}")
        try:
            if return_output:
                return subprocess.check_output(
                    cmd,
                    stderr=stderr,
                    universal_newlines=True,
                    shell=shell,
                    **kwargs,
                )
            else:
                return subprocess.check_call(cmd, shell=shell, **kwargs)
        except subprocess.CalledProcessError as cpe:
            print(f"Exception: {cpe}")
            if ignore_error:
                if return_output:
                    return cpe.output
                else:
                    print(f"failed with output {cpe.output}")
                    return cpe.returncode
            else:
                print(f"failed with code {cpe.returncode} and output:\n{cpe.output}")
                raise cpe

    @staticmethod
    def run_oc_command(
        cmd, json_output: bool = True, return_output: bool = True, ignore_error: bool = False, shell: bool = True,
            namespace: str = "", debug: bool = False
    ):
        """
        Run docker command:
        """
        json_cmd = "-o json" if json_output else ""
        namespace_cmd = f"-n {namespace}" if namespace != "" else ""

        return ContainerTestLibUtils.run_command(
            f"oc {cmd} {namespace_cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
            debug=debug
        )

    @staticmethod
    def check_regexp_output(regexp_to_check: str, logs_to_check: str):
        return re.search(regexp_to_check, logs_to_check)

    @staticmethod
    def create_local_temp_dir(dir_name: str) -> str:
        return tempfile.mkdtemp(prefix=dir_name)

    @staticmethod
    def create_local_temp_file(filename: str) -> str:
        return tempfile.mktemp(prefix=filename)

    @staticmethod
    def commands_to_run(commands_to_run: List[str]) -> bool:
        command_failed: bool = True
        for cmd in commands_to_run:
            try:
                print(f"ContainerTestLibUtils: commands_to_run: {cmd}")
                output = ContainerTestLibUtils.run_command(cmd=cmd, return_output=True, ignore_error=False)
                if output:
                    print(f"Output is '{output}'")
            except subprocess.CalledProcessError as cpe:
                print(f"ContainerTestLibUtils: cmd {cmd} failed '{cpe}'")
                command_failed = False
        return command_failed

    @staticmethod
    def check_files_are_present(dir_name: str, file_name_to_check: List[str]) -> bool:
        file_present: bool = True
        for f in file_name_to_check:
            if not (Path(dir_name) / f).exists():
                print(f"ContainerTestLibUtils(check_logs_are_present): File {dir_name}/{f} does not exist.")
                file_present = False
        return file_present

    @staticmethod
    def update_dockerfile(dockerfile: str, original_string, string_to_replace) -> Any:
        local_temp_dir = Path(ContainerTestLibUtils.create_local_temp_file(filename="new_dockerfile"))
        if not Path(dockerfile).exists():
            print(f"ERROR: Dockerfile '{dockerfile}' do not exists")
            return None
        with open(dockerfile, "r") as f:
            content = f.read()

        content = re.sub(original_string, string_to_replace, content, flags=re.MULTILINE)
        with open(local_temp_dir, "w") as f:
            f.write(content)
        return True


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


def temporary_dir(prefix: str = "helm-chart") -> str:
    temp_file = tempfile.TemporaryDirectory(prefix=prefix)
    print(f"Temporary dir name: {temp_file.name}")
    return temp_file.name


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


def save_tenant_namespace_yaml(project_name: str) -> str:
    cmd_yaml = {
        "apiVersion": "tenant.paas.redhat.com/v1alpha1",
        "kind": "TenantNamespace",
        "metadata": {
            "labels": {
                "tenant.paas.redhat.com/namespace-type": "build",
                "tenant.paas.redhat.com/tenant": "core-services-ocp"
            },
            "name": f"{project_name}",
            "namespace": "core-services-ocp--config"
        },
        "spec": {
            "type": "build",
            "roles": [
                    "namespace-admin",
                    "tenant-egress-admin"
            ],
            "network": {
                "security-zone": "internal"
            }

        }
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-namespace-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(cmd_yaml, fp)
    print(f"TenantNamespace yaml file: {temp_file.name}")
    return temp_file.name


def save_tenant_egress_yaml(project_name: str, rules: List[str] = []) -> str:
    if not rules:
        rules = [
            "github.com", "api.github.com", "codeload.github.com", "pypi.org", "www.cpan.org",
            "registry.npmjs.org", "npmjs.org", "npmjs.com", "rubygems.org", "repo.packagist.org",
            "backpan.perl.org", "www.metacpan.org", "files.pythonhosted.org", "getcomposer.org",
        ]
    generated_yaml = []
    for rule in rules:
        generated_yaml.append({
            "to": {
                "dnsName": f"{rule}"
            },
            "type": "Allow"
        })
    for rule in ["172.0.0.0/8", "10.0.0.0/9", "52.218.128.0/17", "52.92.128.0/17", "52.216.0.0/15"]:
        generated_yaml.append({
            "to": {
                "cidrSelector": f"{rule}"
            },
            "type": "Allow"
        })
    generated_yaml.append({
        "to": {
            "cidrSelector": "0.0.0.0/0"
        },
        "type": "Deny"
    })
    tenant_egress_yaml = {
        "apiVersion": "tenant.paas.redhat.com/v1alpha1",
        "kind": "TenantEgress",
        "metadata": {
            "name": "default",
            "namespace": f"core-services-ocp--{project_name}"
        },
        "spec": {
            "egress": generated_yaml
        }
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-egress-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(tenant_egress_yaml, fp)
    print(f"TenantNamespaceEgress yaml file: {temp_file.name}")
    return temp_file.name


def save_tenant_limit_yaml() -> str:
    tenant_limit_yaml = {
        "apiVersion": "v1",
        "kind": "LimitRange",
        "metadata": {
            "name": "limits",
        },
        "spec": {
            "limits": [
                {
                    "type": "Pod",
                    "max": {
                        "cpu": "8",
                        "memory": "8Gi"
                    },
                    "min": {
                        "cpu": "4",
                        "memory": "2Gi"
                    }
                },
                {
                    "type": "Container",
                    "max": {
                        "cpu": "8",
                        "memory": "8Gi"
                    },
                    "min": {
                        "cpu": "2",
                        "memory": "2Gi"
                    }
                }
            ]
        }
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-limit-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(tenant_limit_yaml, fp)
    print(f"TenantNamespaceLimits yaml file: {temp_file.name}")
    return temp_file.name


def get_tagged_image(image_name: str, version: str) -> Any:
    try:
        image_no_namespace = image_name.split('/')[1]
        image_no_tag = image_no_namespace.split(':')[0]
    except IndexError:
        return None

    return f"{image_no_tag}:{version}"


def clone_git_repository(app_url: str, app_dir: str) -> bool:
    """
    Clone git repository.
    This is the Python equivalent of ct_clone_git_repository.
    Args:
        app_url: Git URI pointing to a repository, supports "@" to indicate a different branch
        app_dir: Name of the directory to clone the repository into
    Returns:
        True if clone successful, False otherwise
    """
    try:
        # If app_url contains @, the string after @ is considered
        # as a name of a branch to clone instead of the main/master branch
        if '@' in app_url:
            git_url_parts = app_url.split('@')
            git_url = git_url_parts[0]
            branch = git_url_parts[1]
            cmd = f"git clone --branch {branch} {git_url} {app_dir}"
        else:
            cmd = f"git clone {app_url} {app_dir}"
        ContainerTestLibUtils.run_command(cmd, return_output=False)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed: {e}")
        return False


def get_service_image(image_name: str) -> Any:
    try:
        image_no_namespace = image_name.split('/')[1]
        image_no_tag = image_no_namespace.split(':')[0]
    except IndexError:
        return None
    return f"{image_no_tag}-testing"


def check_variables() -> bool:
    ret_value: bool = True
    if not os.getenv("VERSION"):
        print("Make sure VERSION is defined")
        ret_value = False
    if not os.getenv("OS"):
        print("Make sure OS is defined")
        ret_value = False
    return ret_value


def get_image_name(path: str) -> Any:
    image_id_file = Path(path, ".image-id")
    if not image_id_file.exists():
        return None
    image_id = get_file_content(image_id_file).strip()
    inspect_name = 'docker inspect -f "{{.Config.Labels.name}}" ' + image_id
    name = ContainerTestLibUtils.run_command(cmd=inspect_name).strip()
    inspect_version = 'docker inspect -f "{{.Config.Labels.version}}" ' + image_id
    version = ContainerTestLibUtils.run_command(cmd=inspect_version).strip()
    return f"{name}:{version}"


def load_shared_credentials(credential: str) -> Any:
    cread_path = os.environ.get(credential, None)
    if not cread_path:
        return None
    cred = ""
    with open(cread_path) as f:
        cred = f.read().strip()
    if cred == "":
        return None
    return cred


def get_json_data(file_name: Path = Path("/root/shared_cluster.json")) -> dict:
    if not file_name.exists():
        print("File /root/shared_cluster.json does not exist.")
        return {}
    json_data: dict = {}
    with open(file_name) as fd:
        json_data = json.loads(fd.read())
    return json_data


def dump_json_data(json_data: dict, file_name: Path = Path("/root/shared_cluster.json")):
    with open(file_name, "w") as fd:
        json.dump(json_data, fd)


def get_yaml_data(filename_path: Path) -> dict:
    if not filename_path.exists():
        return {}
    with open(filename_path) as fd_chart:
        lines = fd_chart.read()
    return yaml.safe_load(lines)


def is_shared_cluster(test_type: str = "ocp4"):
    json_data = get_json_data()
    if test_type not in json_data:
        print(f"Variable {test_type} is not present in file /root/shared_cluster.json")
        return False
    value = json_data[test_type]
    if isinstance(value, bool) and value is True:
        print(f"Shared cluster allowed for {test_type}")
        return True
    if isinstance(value, str) and value in ["true", "True", "y", "Y", "1"]:
        print(f"Shared cluster allowed for {test_type}")
        return True
    print("\nShared cluster is not allowed.\nTo allow it add 'true' to file /root/shared_cluster.json.")
    return False


def get_shared_variable(variable: str) -> Any:
    json_data = get_json_data()
    if variable not in json_data:
        print(f"\nVariable {variable} is not present in file /root/shared_cluster.json")
        return None
    return json_data[variable]


def get_raw_url_for_json(container: str, dir: str, filename: str, branch: str = "master") -> str:
    RAW_SCL_JSON_URL: str = "https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir}/{filename}"
    return RAW_SCL_JSON_URL.format(container=container, branch=branch, dir=dir, filename=filename)


def shared_cluster_variables() -> dict:
    shared_cluster_data = {
        "registry.enabled": "true",
        "registry.name": get_shared_variable("registry_url"),
        "registry.namespace": "core-services-ocp",
        "registry.push_secret": get_shared_variable("push_secret"),
    }
    return shared_cluster_data


def get_datetime_string() -> str:
    now = datetime.now()
    return now.strftime("%Y%m%d-%H%M%S")


@contextlib.contextmanager
def cwd(path):
    """
    Changes CWD to the temporary directory.
    Yields the temporary directory.
    """
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
