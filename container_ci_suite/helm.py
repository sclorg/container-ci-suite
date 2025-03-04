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

from container_ci_suite.openshift import OpenShiftAPI
from container_ci_suite.engines.openshift import OpenShiftOperations

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HelmChartsAPI:

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
            create_prj=self.create_prj, delete_prj=self.delete_prj, shared_cluster=self.shared_cluster, test_type="helm"
        )
        self.pod_json_data: dict = {}
        self.pod_name_prefix: str = ""
        self.namespace = self.set_namespace()
        self.cloned_dir = ""

    @staticmethod
    def run_helm_command(
        cmd, json_output: bool = True, return_output: bool = True, ignore_error: bool = False, shell: bool = True
    ):
        """
        Run docker command:
        """
        json_cmd = "-o json" if json_output else ""
        print(f"run_helm_command: helm {cmd} {json_cmd}")

        return utils.run_command(
            f"helm {cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    def set_namespace(self):
        return self.oc_api.namespace

    def delete_project(self):
        self.oc_api.delete_project()
        if self.cloned_dir != "" and Path(self.cloned_dir).exists():
            shutil.rmtree(self.cloned_dir)

    @property
    def full_package_dir(self) -> Path:
        return Path(self.path) / self.package_name / "src"

    @property
    def get_tarball_name(self):
        return f"{self.package_name}-{self.version}.tgz"

    @property
    def get_full_tarball_path(self):
        return self.tarball_dir / self.get_tarball_name

    def clone_helm_chart_repo(self, repo_url: str, repo_name: str, subdir: str = ""):
        temp_dir = utils.temporary_dir()
        self.cloned_dir = temp_dir
        cmd_clone = f"git clone {repo_url} {temp_dir}/{repo_name}"
        print(f"Clone charts repo by command: {cmd_clone}")
        clone_output = utils.run_command(cmd_clone, return_output=True)
        print(clone_output)
        if subdir != "":
            self.path = Path(temp_dir) / repo_name / subdir
        else:
            self.path = Path(temp_dir) / repo_name

    def get_version_from_chart_yaml(self) -> Any:
        chart_dict = utils.get_yaml_data(self.full_package_dir / "Chart.yaml")
        if "appVersion" in chart_dict:
            return chart_dict["appVersion"]
        return None

    def is_registry_in_values_yaml(self) -> bool:
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "registry" in chart_dict:
            return True
        return False

    def is_pvc_in_values_yaml(self) -> bool:
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "pvc" in chart_dict:
            return True
        return False

    def get_name_from_values_yaml(self) -> Any:
        chart_dict = utils.get_yaml_data(self.full_package_dir / "values.yaml")
        if "name" in chart_dict:
            return chart_dict["name"]
        return None

    def set_version(self, version: str):
        self.version = version

    def is_chart_yaml_present(self):
        if (self.full_package_dir / "Chart.yaml") .exists():
            return True
        return False

    def is_s2i_pod_running(self, pod_name_prefix: str, timeout: int = 180):
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        return oc_ops.is_s2i_pod_running(pod_name_prefix=pod_name_prefix, cycle_count=timeout)

    def is_pod_running(self, pod_name_prefix: str, loops: int = 180):
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        return oc_ops.is_pod_running(pod_name_prefix=pod_name_prefix, loops=loops)

    def helm_package(self) -> bool:
        """
        Package source to Helm Chart package
        """
        if not self.is_chart_yaml_present():
            print(f"Chart.yaml file is not present in directory {self.full_package_dir}")
            return False
        self.version = self.get_version_from_chart_yaml()
        print(f"Helm package command is: helm package {self.full_package_dir}")
        output = HelmChartsAPI.run_helm_command(f"package {self.full_package_dir}", json_output=False)
        print(output)
        if "Successfully packaged chart" in output:
            print(self.get_tarball_name)
            if self.get_tarball_name in output:
                return True
        return False

    def get_helm_json_output(self, command: str) -> Dict:
        try:
            output = HelmChartsAPI.run_helm_command(cmd=command)
        except subprocess.CalledProcessError as cpe:
            print(f"Helm command {command} failed. See {cpe.output}")
            return {}
        # Remove debug wrong output
        new_output = []
        for line in output.split('\n'):
            if line.startswith("W"):
                continue
            new_output.append(line)
        # output = [x for x in output.split('\n') if not x.startswith("W")]
        # print(output)
        return json.loads(''.join(new_output))

    def check_helm_installation(self):
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
        json_output = self.get_helm_json_output(command="list")
        for out in json_output:
            if out["name"] == self.package_name:
                return True
        return False

    def helm_uninstallation(self):
        output = HelmChartsAPI.run_helm_command(
            f"uninstall {self.package_name} -n {self.oc_api.namespace}", json_output=False
        )
        print(output)

    def helm_installation(self, values: Dict = None):
        self.version = self.get_version_from_chart_yaml()
        if not self.version:
            return False
        if self.is_helm_package_installed():
            self.helm_uninstallation()
        command_values = ""
        if values:
            command_values += " " + ' '.join([f"--set {key}={value}" for key, value in values.items()])
        if self.shared_cluster:
            if self.is_registry_in_values_yaml():
                if self.shared_cluster:
                    command_values += " " + ' '.join(
                        [f"--set {key}={value}" for key, value in utils.shared_cluster_variables().items()]
                    )
            if self.is_pvc_in_values_yaml():
                command_values += (f" --set pvc.netapp_nfs=true "
                                   f"--set pvc.app_code={utils.get_shared_variable('app_code')}")
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
            print("Installation has failed. Let's uninstall it and try one more time.")
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
        check_list = [
            f"NAME: {self.package_name}",
            "STATUS: deployed",
            "Succeeded"
        ]
        if isinstance(expected_str, str):
            print("Function expects list of strings to check.")
            return False
        check_list.extend(expected_str)
        print(f"Strings to check in helm output log: {check_list}")
        result_list = [x in ''.join(output) for x in check_list]
        if False in result_list:
            return False
        return True

    def test_helm_chart(self, expected_str: List[str]) -> bool:
        for count in range(60):
            time.sleep(2)
            try:
                output = HelmChartsAPI.run_helm_command(
                    f"test {self.package_name} --logs", json_output=False
                )
                print(f"Helm test output: {output}")
            except subprocess.CalledProcessError:
                print(f"Helm test command `test {self.package_name} --logs` failed. Let's try more time.")
                continue
            if self.check_test_output(output, expected_str=expected_str):
                return True
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        oc_ops.print_get_status()
        return False

    def get_route_name(self, route_name: str):
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
        Returns JSON output
        """
        oc_ops = OpenShiftOperations()
        oc_ops.set_namespace(namespace=self.oc_api.namespace)
        json_output = oc_ops.oc_gel_all_is()
        for tag in json_output["items"][0]["spec"]["tags"]:
            tag_name = tag["name"]
            tag_registry = tag["from"]["name"]
            print(f"Important tags: {version}={tag_name}, {registry}={tag_registry}")
            if tag_name == version and tag_registry == registry:
                print("Imagestream tag exists.")
                return True
        return False

    def test_helm_curl_output(
            self, route_name: str, expected_str: str, port: int = None, schema: str = "http://",
            range_count: int = 10
    ) -> bool:
        # Let's get some time to start application
        time.sleep(3)
        host_name = self.get_route_name(route_name=route_name)
        print(f"test_helm_curl_output: Route name is: {host_name}")
        if not host_name:
            return False
        url_address = f"{schema}{host_name}"
        if port:
            url_address = f"{url_address}:{port}"
        valid_request: bool = False
        for count in range(range_count):
            try:
                print(f"test_helm_curl_output: requests.get {url_address}")
                resp = requests.get(url_address, verify=False)
                resp.raise_for_status()
                if resp.status_code != 200:
                    print(f"test_helm_curl_output response is different from 200: {resp.text}, {resp.status_code}")
                    continue
                print(f"test_helm_curl_output: text: {resp.text}")
                if expected_str not in resp.text:
                    print(f"{expected_str} is not in the output")
                    continue
                return True
            except requests.exceptions.HTTPError:
                print("test_helm_curl_output: Service is not yet available. Let's wait some time")
                time.sleep(3)
                continue
            except requests.exceptions.ConnectTimeout:
                print("test_helm_curl_output: Service is not yet available. Connection Timeout")
                time.sleep(3)
                continue
            except urllib3.exceptions.MaxRetryError:
                print("test_helm_curl_output: MaxRetryError. Let's wait some time")
                time.sleep(3)
                continue
        if not valid_request:
            print("test_helm_curl_output: Service was not available")
            return False
        return False
