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
import json
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
    """
    Get the content of a file.
    Args:
        filename: The path to the file
    Returns:
        The content of the file
    """
    with open(str(filename)) as f:
        return f.read()


def save_file_content(content: str, filename: Path):
    """
    Save the content of a file.
    Args:
        content: The content to save
        filename: The path to the file
    """
    with open(str(filename), "w") as f:
        f.write(content)


def get_full_ca_file_path() -> Path:
    """
    Get the full CA file path.
    Returns:
        The full CA file path
    """
    return Path(CA_FILE_PATH)


# Replacement for ct_mount_ca_file
def get_mount_ca_file() -> str:
    if os.getenv("NPM_REGISTRY") and get_full_ca_file_path().exists():
        return f"-v {CA_FILE_PATH}:{CA_FILE_PATH}:Z"
    return ""


# Replacement for ct_mount_ca_file
def get_npm_variables():
    """
    Get the NPM variables.
    Returns:
        The NPM variables
    """
    npm_registry = os.getenv("NPM_REGISTRY")
    if npm_registry and get_full_ca_file_path().exists():
        return f"-e NPM_MIRROR={npm_registry} {get_mount_ca_file()}"
    return ""


def get_registry_name(os_name: str, stage_registry: bool = False) -> str:
    """
    Get the registry name.
    Args:
        os_name: The operating system name
        stage_registry: Whether to use the stage registry
    Returns:
        The registry name
    """
    if stage_registry:
        return "registry.stage.redhat.io" if os_name.startswith("rhel") else "quay.io"
    return "registry.redhat.io" if os_name.startswith("rhel") else "docker.io"


def get_mount_options_from_s2i_args(s2i_args: str) -> str:
    """
    Get the mount options from the S2I arguments.
    Args:
        s2i_args: The S2I arguments
    Returns:
        The mount options
    """
    # Check if -v parameter is present in s2i_args and add it into docker build command
    searchObj = re.search(r"(-v \.*\S*)", s2i_args)
    logger.debug("Search object: %s", searchObj)
    if not searchObj:
        return ""

    logger.debug(searchObj.group(1))
    mount_options = searchObj.group()

    logger.debug("Mount options: %s", mount_options)
    return searchObj.group()


def get_env_commands_from_s2i_args(s2i_args: str) -> List:
    """
    Get the environment commands from the S2I arguments.
    Args:
        s2i_args: The S2I arguments
    Returns:
        The environment commands
    """
    matchObj = re.findall(r"(-e|--env)=?\s*(\S*)=(\S*)", s2i_args)
    logger.debug(matchObj)
    env_content: List = []
    if matchObj:
        for obj in matchObj:
            if obj[1] == "":
                continue
            env_content.append(f"ENV {obj[1]}={obj[2]}")
        logger.debug(env_content)
        return env_content
    return env_content


def get_previous_os_version(os_name: str) -> str:
    """
    Get the previous OS version.
    Args:
        os_name: The operating system name
    Returns:
        The previous OS version
    """
    m = re.search(r"\d+", os_name)
    if not m:
        return os_name  # or raise ValueError("No number found")
    num = int(m.group())
    bumped = str(num - 1)
    return os_name[: m.start()] + bumped + os_name[m.end() :]


def get_public_image_name(
    os_name: str, base_image_name: str, version: str, stage_registry: bool = False
) -> str:
    """
    Get the public image name.
    Args:
        os: The operating system
        base_image_name: The base image name
        version: The version
        stage_registry: Whether to use the stage registry
    Returns:
        The public image name
    """
    registry = get_registry_name(os_name, stage_registry)
    if os_name.startswith("rhel"):
        return f"{registry}/{os_name}/{base_image_name}-{version}"
    return f"{registry}/sclorg/{base_image_name}-{version}-{os_name}"


def download_template(
    template_name: str, dir_name: str = "/var/tmp", file_name: str = ""
) -> Any:
    """
    Download a template file.
    Args:
        template_name: The name of the template to download
        dir_name: The directory to download the template to
        file_name: The name of the file to download the template to
    Returns:
        The path to the downloaded template
    """
    ext = ""
    file_ext_field = template_name.split(".")
    if len(file_ext_field) > 1:
        ext = f".{file_ext_field[1]}"
    logger.debug("Local temporary file %s with extension %s", template_name, ext)
    logger.debug("Temporary file: download_template from %s", template_name)
    random_text = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    path_name = f"{random_text}{ext}"
    if Path(template_name).is_file():
        shutil.copy2(template_name, path_name)
        return str(path_name)
    if Path(template_name).is_dir():
        shutil.copytree(template_name, path_name, symlinks=True)
        return str(path_name)
    if template_name.startswith("http"):
        if file_name:
            path_name = f"{dir_name}/{file_name}"
        resp = requests.get(template_name, verify=False)
        resp.raise_for_status()
        if resp.status_code != 200:
            logger.error(
                "utils.download_template: %s and %s", resp.status_code, resp.text
            )
            return None
        with open(path_name, "wb") as fd:
            fd.write(resp.content)
        logger.debug("utils.download_template: %s", path_name)
        return str(path_name)
    if not Path(template_name).exists():
        logger.error("utils.download_template: File to download does not exist.")
        return None


class ContainerTestLibUtils:
    """
    Container Test Library Utilities - Utility functions for container testing.
    """

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
            logger.debug("command: %s", cmd)
        try:
            if return_output:
                return subprocess.check_output(
                    cmd,
                    stderr=stderr,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=shell,
                    **kwargs,
                )
            else:
                return subprocess.check_call(cmd, shell=shell, **kwargs)
        except subprocess.CalledProcessError as cpe:
            logger.error("Exception: %s", cpe)
            if ignore_error:
                if return_output:
                    return cpe.output
                else:
                    logger.error("failed with output %s", cpe.output)
                    return cpe.returncode
            else:
                logger.error(
                    "failed with code %s and output:\n%s", cpe.returncode, cpe.output
                )
                raise cpe

    @staticmethod
    def run_oc_command(
        cmd,
        json_output: bool = True,
        return_output: bool = True,
        ignore_error: bool = False,
        shell: bool = True,
        namespace: str = "",
        debug: bool = False,
    ):
        """
        Run docker command:
        Args:
            cmd: The command to run
            json_output: Whether to return the output as JSON
            return_output: Whether to return the output
            ignore_error: Whether to ignore errors
            shell: Whether to run the command in a shell
            namespace: The namespace to run the command in
            debug: Whether to print the command
        Returns:
            The output of the command
        """
        json_cmd = "-o json" if json_output else ""
        namespace_cmd = f"-n {namespace}" if namespace != "" else ""

        return ContainerTestLibUtils.run_command(
            f"oc {cmd} {namespace_cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
            debug=debug,
        )

    @staticmethod
    def commands_to_run(commands_to_run: List[str]) -> bool:
        """
        Run the commands.
        Args:
            commands_to_run: The commands to run
        Returns:
            True if the commands were successful, False otherwise
        """
        command_failed: bool = True
        for cmd in commands_to_run:
            try:
                logger.debug("ContainerTestLibUtils: commands_to_run: %s", cmd)
                output = ContainerTestLibUtils.run_command(
                    cmd=cmd, return_output=True, ignore_error=False
                )
                if output:
                    logger.debug("Output is '%s'", output)
            except subprocess.CalledProcessError as cpe:
                logger.error("ContainerTestLibUtils: cmd %s failed '%s'", cmd, cpe)
                command_failed = False
        return command_failed

    @staticmethod
    def check_files_are_present(dir_name: str, file_name_to_check: List[str]) -> bool:
        """
        Check if the files are present in the directory.
        Args:
            dir_name: The directory name
            file_name_to_check: The files to check
        Returns:
            True if the files are present, False otherwise
        """
        file_present: bool = True
        for f in file_name_to_check:
            if not (Path(dir_name) / f).exists():
                logger.error(
                    "ContainerTestLibUtils(check_logs_are_present): File '%s/%s' does not exist.",
                    dir_name,
                    f,
                )
                file_present = False
        return file_present

    @staticmethod
    def update_dockerfile(dockerfile: str, original_string, string_to_replace) -> Any:
        """
        Update the Dockerfile.
        Args:
            dockerfile: The Dockerfile
            original_string: The original string
            string_to_replace: The string to replace
        Returns:
            The path to the temporary file
        """
        local_temp_file = tempfile.NamedTemporaryFile(
            prefix="new_dockerfile", dir="/tmp", delete=False
        ).name
        if not Path(dockerfile).exists():
            logger.error("ERROR: Dockerfile '%s' do not exists", dockerfile)
            return None
        with open(dockerfile, "r") as f:
            content = f.read()

        content = re.sub(
            original_string, string_to_replace, content, flags=re.MULTILINE
        )
        with open(local_temp_file, "w") as f:
            f.write(content)
        return local_temp_file


def get_response_request(
    url_address: str, expected_str: str, response_code: int = 200, max_tests: int = 3
) -> bool:
    """
    Get the response from a URL.
    Args:
        url_address: The URL address
        expected_str: The expected string
        response_code: The response code
        max_tests: The maximum number of tests
    Returns:
        True if the response is successful, False otherwise
    """
    for _ in range(max_tests):
        try:
            resp = requests.get(url_address, timeout=10, verify=False)
            resp.raise_for_status()
            logger.debug(
                "Response code is %s and expected should be %s",
                resp.status_code,
                response_code,
            )
            if resp.status_code == response_code and expected_str in resp.text:
                return True
            return False
        except requests.exceptions.HTTPError:
            logger.debug(
                "get_response_request: Service is not yet available. Let's wait some time"
            )
            pass
        except requests.exceptions.ConnectTimeout:
            logger.debug("get_response_request: ConnectTimeout. Let's wait some time")
            pass
        time.sleep(10)
    return False


def temporary_dir(prefix: str = "helm-chart") -> str:
    """
    Create a temporary directory.
    Args:
        prefix: The prefix for the temporary directory
    Returns:
        The path to the temporary directory
    """
    temp_file = tempfile.TemporaryDirectory(prefix=prefix)
    logger.debug("Temporary dir name: %s", temp_file.name)
    return temp_file.name


def save_command_yaml(image_name: str) -> str:
    """
    Save the command YAML file.
    Args:
        image_name: The image name
    Returns:
        The path to the command YAML file
    """
    cmd_yaml = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "command-app"},
        "spec": {
            "restartPolicy": "OnFailure",
            "containers": [
                {
                    "name": "command-container",
                    "image": image_name,
                    "command": ["sleep"],
                    "args": ["3h"],
                }
            ],
        },
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="command-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(cmd_yaml, fp)
    logger.debug("Pod command yaml file: %s", temp_file.name)
    return temp_file.name


def save_tenant_namespace_yaml(project_name: str) -> str:
    """
    Save the tenant namespace YAML file.
    Args:
        project_name: The project name
    Returns:
        The path to the tenant namespace YAML file
    """
    cmd_yaml = {
        "apiVersion": "tenant.paas.redhat.com/v1alpha1",
        "kind": "TenantNamespace",
        "metadata": {
            "labels": {
                "tenant.paas.redhat.com/namespace-type": "build",
                "tenant.paas.redhat.com/tenant": "core-services-ocp",
            },
            "name": f"{project_name}",
            "namespace": "core-services-ocp--config",
        },
        "spec": {
            "type": "build",
            "roles": ["namespace-admin", "tenant-egress-admin"],
            "network": {"security-zone": "internal"},
        },
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-namespace-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(cmd_yaml, fp)
    logger.debug("TenantNamespace yaml file: %s", temp_file.name)
    return temp_file.name


def save_tenant_egress_yaml(project_name: str, rules: List[str] = []) -> str:
    """
    Save the tenant egress YAML file.
    Args:
        project_name: The project name
        rules: The rules to save
    Returns:
        The path to the tenant egress YAML file
    """
    if not rules:
        rules = [
            "github.com",
            "api.github.com",
            "codeload.github.com",
            "pypi.org",
            "www.cpan.org",
            "registry.npmjs.org",
            "npmjs.org",
            "npmjs.com",
            "rubygems.org",
            "repo.packagist.org",
            "backpan.perl.org",
            "www.metacpan.org",
            "files.pythonhosted.org",
            "getcomposer.org",
        ]
    generated_yaml = []
    for rule in rules:
        generated_yaml.append({"to": {"dnsName": f"{rule}"}, "type": "Allow"})
    for rule in [
        "172.0.0.0/8",
        "10.0.0.0/9",
        "52.218.128.0/17",
        "52.92.128.0/17",
        "52.216.0.0/15",
    ]:
        generated_yaml.append({"to": {"cidrSelector": f"{rule}"}, "type": "Allow"})
    generated_yaml.append({"to": {"cidrSelector": "0.0.0.0/0"}, "type": "Deny"})
    tenant_egress_yaml = {
        "apiVersion": "tenant.paas.redhat.com/v1alpha1",
        "kind": "TenantEgress",
        "metadata": {
            "name": "default",
            "namespace": f"core-services-ocp--{project_name}",
        },
        "spec": {"egress": generated_yaml},
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-egress-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(tenant_egress_yaml, fp)
    logger.debug("TenantNamespaceEgress yaml file: %s", temp_file.name)
    return temp_file.name


def save_tenant_limit_yaml() -> str:
    """
    Save the tenant limit YAML file.
    Returns:
        The path to the tenant limit YAML file
    """
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
                    "max": {"cpu": "8", "memory": "8Gi"},
                    "min": {"cpu": "4", "memory": "2Gi"},
                },
                {
                    "type": "Container",
                    "max": {"cpu": "8", "memory": "8Gi"},
                    "min": {"cpu": "2", "memory": "2Gi"},
                },
            ]
        },
    }
    temp_file = tempfile.NamedTemporaryFile(prefix="tenant-limit-yml", delete=False)
    with open(temp_file.name, "w") as fp:
        yaml.dump(tenant_limit_yaml, fp)
    logger.debug("TenantNamespaceLimits yaml file: %s", temp_file.name)
    return temp_file.name


def get_tagged_image(image_name: str, version: str) -> Any:
    """
    Get the tagged image name.
    Args:
        image_name: The image name
        version: The version
    Returns:
        The tagged image name
    """
    try:
        image_no_namespace = image_name.split("/")[1]
        image_no_tag = image_no_namespace.split(":")[0]
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
        if "@" in app_url:
            git_url_parts = app_url.split("@")
            git_url = git_url_parts[0]
            branch = git_url_parts[1]
            cmd = f"git clone --branch {branch} {git_url} {app_dir}"
        else:
            cmd = f"git clone {app_url} {app_dir}"
        ContainerTestLibUtils.run_command(cmd, return_output=False)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git clone failed: %s", e)
        return False


def get_service_image(image_name: str) -> Any:
    """
    Get the service image name.
    Args:
        image_name: The image name
    Returns:
        The service image name
    """
    try:
        image_no_namespace = image_name.split("/")[1]
        image_no_tag = image_no_namespace.split(":")[0]
    except IndexError:
        return None
    return f"{image_no_tag}-testing"


def check_variables() -> bool:
    """
    Check if the variables are defined.
    Returns:
        True if the variables are defined, False otherwise
    """
    ret_value: bool = True
    if not os.getenv("VERSION"):
        logger.error("Make sure VERSION is defined")
        ret_value = False
    if not os.getenv("OS"):
        logger.error("Make sure OS is defined")
        ret_value = False
    if not os.getenv("IMAGE_NAME"):
        logger.error("Make sure IMAGE_NAME is defined")
    return ret_value


def get_image_name(path: str) -> Any:
    """
    Get the image name from a file.
    Args:
        path: The path to the file
    Returns:
        The image name
    """
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
    """
    Load shared credentials from the environment.
    Args:
        credential: The credential name
    Returns:
        The credential value
    """
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
    """
    Get the JSON data from a file.
    Args:
        file_name: The path to the file
    Returns:
        The JSON data
    """
    if not file_name.exists():
        logger.error("File %s does not exist.", file_name)
        return {}
    json_data: dict = {}
    with open(file_name) as fd:
        json_data = json.loads(fd.read())
    return json_data


def dump_json_data(
    json_data: dict, file_name: Path = Path("/root/shared_cluster.json")
):
    """
    Dump JSON data to a file.
    Args:
        json_data: The JSON data to dump
        file_name: The path to the file
    """
    with open(file_name, "w") as fd:
        json.dump(json_data, fd)


def get_yaml_data(filename_path: Path) -> dict:
    """
    Get the YAML data from a file.
    Args:
        filename_path: The path to the file
    Returns:
        The YAML data
    """
    if not filename_path.exists():
        return {}
    with open(filename_path) as fd_chart:
        lines = fd_chart.read()
    return yaml.safe_load(lines)


def is_shared_cluster(test_type: str = "ocp4"):
    """
    Check if the test is running on a shared cluster.
    Args:
        test_type: The type of test
    Returns:
        True if the test is running on a shared cluster, False otherwise
    """
    json_data = get_json_data()
    if test_type not in json_data:
        logger.error(
            "Variable %s is not present in file /root/shared_cluster.json", test_type
        )
        return False
    value = json_data[test_type]
    if isinstance(value, bool) and value is True:
        logger.debug("Shared cluster allowed for %s", test_type)
        return True
    if isinstance(value, str) and value in ["true", "True", "y", "Y", "1"]:
        logger.debug("Shared cluster allowed for %s", test_type)
        return True
    logger.debug(
        "\nShared cluster is not allowed.\nTo allow it add 'true' to file /root/shared_cluster.json."
    )
    return False


def get_shared_variable(variable: str) -> Any:
    """
    Get a shared variable from the shared cluster JSON file.
    Args:
        variable: The variable name
    Returns:
        The value of the variable
    """
    json_data = get_json_data()
    if variable not in json_data:
        logger.error(
            "Variable %s is not present in file /root/shared_cluster.json", variable
        )
        return None
    return json_data[variable]


def get_raw_url_for_json(
    container: str, dir: str, filename: str, branch: str = "master"
) -> str:
    """
    Get the raw URL for a JSON file.
    Args:
        container: The container name
        dir: The directory name
        filename: The filename
        branch: The branch name
    Returns:
        The raw URL for a JSON file
    """
    RAW_SCL_JSON_URL: str = (
        "https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir}/{filename}"
    )
    return RAW_SCL_JSON_URL.format(
        container=container, branch=branch, dir=dir, filename=filename
    )


def shared_cluster_variables() -> dict:
    """
    Get the shared cluster variables.
    Returns:
        The shared cluster variables
    """
    shared_cluster_data = {
        "registry.enabled": "true",
        "registry.name": get_shared_variable("registry_url"),
        "registry.namespace": "core-services-ocp",
        "registry.push_secret": get_shared_variable("push_secret"),
    }
    return shared_cluster_data


def get_datetime_string() -> str:
    """
    Get the current date and time as a string.
    Returns:
        The current date and time as a string
    """
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


def redact_secrets(value: str) -> str:
    """
    Redact secrets from a string.
    Args:
        value: The string to redact secrets from
    Returns:
        The string with secrets redacted
    """
    return re.sub(
        r"(?i)(\b(?:PASSWORD|PASS|TOKEN|SECRET|KEY)\b[=\s:]*)(\"[^\"]*\"|'[^']*'|[^\s]+)",
        r"\1***",
        value,
    )
