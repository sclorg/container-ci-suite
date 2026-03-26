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
import json
import shutil

import logging
import time
import requests
import subprocess

from typing import Dict, List, Any
from pathlib import Path

import urllib3

import container_ci_suite.utils as utils

from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite.openshift import OpenShiftAPI
from container_ci_suite.engines.openshift import OpenShiftOperations

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HelmChartsAPI:
    """
    Helm Charts API - API for Helm charts.
    """

    def __init__(
        self,
        path: Path,
        package_name: str,
        tarball_dir: Path,
        delete_prj: bool = True,
        shared_cluster: bool = False,
    ):
        self.path: Path = path
        self.version: str = ""
        self.package_name: str = package_name
        self.tarball_dir = tarball_dir
        self.delete_prj: bool = delete_prj
        if not shared_cluster:
            self.shared_cluster = shared_cluster
        else:
            self.shared_cluster = utils.is_shared_cluster(test_type="helm")
        self.create_prj: bool = True
        self.oc_api = OpenShiftAPI(
            create_prj=self.create_prj,
            delete_prj=self.delete_prj,
            shared_cluster=self.shared_cluster,
            test_type="helm",
        )
        self.pod_json_data: dict = {}
        self.pod_name_prefix: str = ""
        self.namespace = self.set_namespace()
        self.cloned_dir = ""

    @staticmethod
    def run_helm_command(
        cmd,
        json_output: bool = True,
        return_output: bool = True,
        ignore_error: bool = False,
        shell: bool = True,
    ):
        """
        Run docker command:
        """
        json_cmd = "-o json" if json_output else ""
        logger.debug("run_helm_command: helm %s %s", cmd, json_cmd)

        return ContainerTestLibUtils.run_command(
            f"helm {cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    def set_namespace(self) -> str:
        """
        Set the namespace.
        Returns:
            The namespace
        """
        return self.oc_api.namespace

    def delete_project(self):
        """
        Delete the project.
        """
        self.oc_api.delete_project()
        if self.cloned_dir != "" and Path(self.cloned_dir).exists():
            shutil.rmtree(self.cloned_dir)

    @property
    def full_package_dir(self) -> Path:
        """
        Get the full path of the package directory.
        Returns:
            The full path of the package directory
        """
        return Path(self.path) / self.package_name / "src"

    @property
    def get_tarball_name(self) -> str:
        """
        Get the name of the tarball.
        Returns:
            The name of the tarball
        """
        return f"{self.package_name}-{self.version}.tgz"

    @property
    def get_full_tarball_path(self) -> Path:
        """
        Get the full path of the tarball.
        Returns:
            The full path of the tarball
        """
        return self.tarball_dir / self.get_tarball_name

    def clone_helm_chart_repo(self, repo_url: str, repo_name: str, subdir: str = ""):
        """
        Clone the Helm chart repository.
        Args:
            repo_url: The URL of the repository to clone
            repo_name: The name of the repository to clone
            subdir: The subdirectory of the repository to clone
        """
        temp_dir = utils.temporary_dir()
        self.cloned_dir = temp_dir
        cmd_clone = f"git clone {repo_url} {temp_dir}/{repo_name}"
        logger.info("Clone charts repo by command: %s", cmd_clone)
        clone_output = ContainerTestLibUtils.run_command(cmd_clone, return_output=True)
        logger.debug("Clone output: %s", clone_output)
        if subdir != "":
            self.path = Path(temp_dir) / repo_name / subdir
        else:
            self.path = Path(temp_dir) / repo_name

    def get_version_from_chart_yaml(self) -> Any:
        """
        Get the version from the Chart.yaml file.
        Returns:
            The version from the Chart.yaml file
        """
        chart_dict = utils.get_yaml_data(self.full_package_dir / "Chart.yaml")
        if "appVersion" in chart_dict:
            return chart_dict["appVersion"]
        return None

    def is_registry_in_values_yaml(self) -> bool:
        """
        Check if the registry is in the values.yaml file.
        Returns:
            True if the registry is in the values.yaml file, False otherwise
        """
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "registry" in chart_dict:
            return True
        return False

    def is_pvc_in_values_yaml(self) -> bool:
        """
        Check if the PVC is in the values.yaml file.
        Returns:
            True if the PVC is in the values.yaml file, False otherwise
        """
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "pvc" in chart_dict:
            return True
        return False

    def get_name_from_values_yaml(self) -> Any:
        """
        Get the name from the values.yaml file.
        Returns:
            The name from the values.yaml file
        """
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "name" in chart_dict:
            return chart_dict["name"]
        return None

    def set_version(self, version: str) -> None:
        """
        Set the version.
        Args:
            version: The version to set
        """
        self.version = version

    def is_chart_yaml_present(self) -> bool:
        """
        Check if the Chart.yaml file is present.
        Returns:
            True if the Chart.yaml file is present, False otherwise
        """
        if (self.full_package_dir / "Chart.yaml").exists():
            return True
        return False

    def is_s2i_pod_running(self, pod_name_prefix: str, timeout: int = 180) -> bool:
        """
        Check if the S2I pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
            timeout: The timeout in seconds
        Returns:
            True if the S2I pod is running, False otherwise
        """
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        return oc_ops.is_s2i_pod_running(
            pod_name_prefix=pod_name_prefix, cycle_count=timeout
        )

    def is_pod_running(self, pod_name_prefix: str, loops: int = 180) -> bool:
        """
        Check if the pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
            loops: The number of loops to check
        Returns:
            True if the pod is running, False otherwise
        """
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        return oc_ops.is_pod_running(pod_name_prefix=pod_name_prefix, loops=loops)

    def helm_package(self) -> bool:
        """
        Package source to Helm Chart package
        Returns:
            True if the Helm chart is packaged successfully, False otherwise
        """
        if not self.is_chart_yaml_present():
            logger.debug(
                "Chart.yaml file is not present in directory %s", self.full_package_dir
            )
            return False
        self.version = self.get_version_from_chart_yaml()
        logger.info("Helm package command is: helm package %s", self.full_package_dir)
        output = HelmChartsAPI.run_helm_command(
            f"package {self.full_package_dir}", json_output=False
        )
        logger.info("Helm package output: %s", output)
        if "Successfully packaged chart" in output:
            logger.info("Helm package tarball name: %s", self.get_tarball_name)
            if self.get_tarball_name in output:
                return True
        return False

    def get_helm_json_output(self, command: str) -> Dict:
        """
        Get the JSON output of the Helm command.
        Args:
            command: The command to run
        Returns:
            The JSON output of the Helm command
        """
        try:
            output = HelmChartsAPI.run_helm_command(cmd=command)
        except subprocess.CalledProcessError as cpe:
            logger.error("Helm command %s failed. See %s", command, cpe.output)
            return {}
        # Remove debug wrong output
        new_output = []
        for line in output.split("\n"):
            if line.startswith("W"):
                continue
            new_output.append(line)
        # output = [x for x in output.split('\n') if not x.startswith("W")]
        # print(output)
        return json.loads("".join(new_output))

    def check_helm_installation(self) -> bool:
        """
        Check if the Helm chart is installed.
        Returns:
            True if the Helm chart is installed, False otherwise
        """
        # Let's check that pod is really running
        json_output = self.get_helm_json_output(command="list")
        for out in json_output:
            if out["name"] != self.package_name:
                continue
            assert out["name"] == self.package_name
            assert out["chart"] == f"{self.package_name}-{self.version}"
            assert out["status"] == "deployed"
            return True
        return False

    def is_helm_package_installed(self):
        """
        Check if the Helm package is installed.
        Returns:
            True if the Helm package is installed, False otherwise
        """
        json_output = self.get_helm_json_output(command="list")
        for out in json_output:
            if out["name"] == self.package_name:
                return True
        return False

    def helm_uninstallation(self):
        """
        Uninstall the Helm chart.
        """
        output = HelmChartsAPI.run_helm_command(
            f"uninstall {self.package_name} -n {self.oc_api.namespace}",
            json_output=False,
        )
        logger.info("Helm uninstallation output: %s", output)

    def helm_installation(self, values: Dict = None):
        """
        Install the Helm chart.
        Args:
            values: The values to set
        Returns:
            True if the Helm chart is installed successfully, False otherwise
        """
        self.version = self.get_version_from_chart_yaml()
        if not self.version:
            return False
        if self.is_helm_package_installed():
            self.helm_uninstallation()
        command_values = ""
        if values:
            command_values += " " + " ".join(
                [f"--set {key}={value}" for key, value in values.items()]
            )
        if self.shared_cluster:
            if self.is_registry_in_values_yaml():
                if self.shared_cluster:
                    command_values += " " + " ".join(
                        [
                            f"--set {key}={value}"
                            for key, value in utils.shared_cluster_variables().items()
                        ]
                    )
            if self.is_pvc_in_values_yaml():
                command_values += (
                    f" --set pvc.netapp_nfs=true "
                    f"--set pvc.app_code={utils.get_shared_variable('app_code')}"
                )
        install_success: bool = False
        json_output: Dict = {}
        for count in range(3):
            json_output = self.get_helm_json_output(
                f"install {self.package_name} {self.get_full_tarball_path} {command_values}"
            )
            if json_output:
                install_success = True
                break
            time.sleep(3)
        # Let's wait couple seconds, till it is not really imported
        time.sleep(3)
        if not install_success:
            return False
        assert json_output["name"] == self.package_name
        assert json_output["chart"]["metadata"]["version"] == self.version
        assert json_output["info"]["status"] == "deployed"
        if not self.check_helm_installation():
            logger.error(
                "Installation has failed. Let's uninstall it and try one more time."
            )
            return False
        return True

    def check_test_output(self, output, expected_str: List[str]):
        """
        Expected output from helm test is e.g.:
        NAME: postgresql-persistent
        LAST DEPLOYED: Wed Apr 12 08:08:20 2023
        NAMESPACE: helm-sclorg-7072
        STATUS: deployed
        REVISION: 1
        TEST SUITE:     postgresql-persistent-connection-test
        Last Started:   Wed Apr 12 08:08:52 2023
        Last Completed: Wed Apr 12 08:08:56 2023
        Phase:          Succeeded

        POD LOGS: postgresql-persistent-connection-test
        postgresql-testing:5432 - accepting connections
        """
        check_list = [f"NAME: {self.package_name}", "STATUS: deployed", "Succeeded"]
        if isinstance(expected_str, str):
            logger.error("Function expects list of strings to check.")
            return False
        check_list.extend(expected_str)
        logger.info("Strings to check in helm output log: %s", check_list)
        result_list = [x in "".join(output) for x in check_list]
        if False in result_list:
            return False
        return True

    def test_helm_chart(self, expected_str: List[str]) -> bool:
        """
        Test the Helm chart.
        Args:
            expected_str: The expected strings in the output
        Returns:
            True if the Helm chart is tested successfully, False otherwise
        """
        for count in range(60):
            time.sleep(2)
            try:
                output = HelmChartsAPI.run_helm_command(
                    f"test {self.package_name} --logs", json_output=False
                )
                logger.info("Helm test output: %s", output)
            except subprocess.CalledProcessError:
                logger.error(
                    "Helm test command `test %s --logs` failed. Let's try more time.",
                    self.package_name,
                )
                continue
            if self.check_test_output(output, expected_str=expected_str):
                return True
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        oc_ops.print_get_status()
        return False

    def get_route_name(self, route_name: str):
        """
        Get the route name.
        Args:
            route_name: The name of the route to get
        Returns:
            The route name
        """
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        json_data = oc_ops.get_routes()
        if len(json_data["items"]) == 0:
            return None
        for item in json_data["items"]:
            if item["metadata"]["namespace"] != self.oc_api.namespace:
                continue
            if item["metadata"]["name"] != route_name:
                continue
            if item["spec"]["to"]["name"] != route_name:
                continue
            return item["spec"]["host"]
        return None

    def check_imagestreams(self, version: str, registry: str) -> bool:
        """
        Check if the image streams exist.
        Args:
            version: The version of the image stream
            registry: The registry of the image stream
        Returns:
            True if the image streams exist, False otherwise
        """
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        json_output = oc_ops.oc_gel_all_is()
        for tag in json_output["items"][0]["spec"]["tags"]:
            tag_name = tag["name"]
            tag_registry = tag["from"]["name"]
            logger.debug(
                "Important tags: %s=%s, %s=%s",
                version,
                tag_name,
                registry,
                tag_registry,
            )
            if tag_name == version and tag_registry == registry:
                logger.debug("Imagestream tag exists.")
                return True
        return False

    def test_helm_curl_output(
        self,
        route_name: str,
        expected_str: str,
        port: int = None,
        schema: str = "http://",
        range_count: int = 10,
    ) -> bool:
        """
        Test the output of the Helm chart.
        Args:
            route_name: The name of the route to test
            expected_str: The expected string in the output
            port: The port to test
            schema: The schema to use
            range_count: The number of attempts to test
        Returns:
            True if the output is as expected, False otherwise
        """
        time.sleep(3)
        host_name = self.get_route_name(route_name=route_name)
        logger.debug("test_helm_curl_output: Route name is: %s", host_name)
        if not host_name:
            return False
        url_address = f"{schema}{host_name}"
        if port:
            url_address = f"{url_address}:{port}"
        valid_request: bool = False
        for count in range(range_count):
            try:
                logger.debug("test_helm_curl_output: requests.get %s", url_address)
                resp = requests.get(url_address, verify=False)
                resp.raise_for_status()
                if resp.status_code != 200:
                    logger.error(
                        "test_helm_curl_output response is different from 200: %s, %s",
                        resp.text,
                        resp.status_code,
                    )
                    continue
                logger.debug("test_helm_curl_output: text: %s", resp.text)
                if expected_str not in resp.text:
                    logger.error("%s is not in the output", expected_str)
                    continue
                return True
            except requests.exceptions.HTTPError:
                logger.error(
                    "test_helm_curl_output: Service is not yet available. Let's wait some time"
                )
                time.sleep(3)
                continue
            except requests.exceptions.ConnectTimeout:
                logger.error(
                    "test_helm_curl_output: Service is not yet available. Connection Timeout"
                )
                time.sleep(3)
                continue
            except urllib3.exceptions.MaxRetryError:
                logger.error(
                    "test_helm_curl_output: MaxRetryError. Let's wait some time"
                )
                time.sleep(3)
                continue
        if not valid_request:
            logger.error("test_helm_curl_output: Service was not available")
            return False
        return False
