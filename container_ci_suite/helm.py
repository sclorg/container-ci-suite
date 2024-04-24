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
import yaml
import logging
import random
import time
import requests
import subprocess

from typing import Dict, List, Any
from pathlib import Path

import container_ci_suite.utils as utils
from container_ci_suite.openshift import OpenShiftAPI

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HelmChartsAPI:

    def __init__(
            self, path: Path, package_name: str, tarball_dir: Path,
            namespace: str = "helm-default", delete_prj: bool = True
    ):
        self.path: Path = path
        self.version: str = ""
        self.package_name: str = package_name
        self.tarball_dir = tarball_dir
        self.delete_prj: bool = delete_prj
        self.create_prj: bool = True
        if namespace == "helm-default":
            self.namespace = f"helm-sclorg-{random.randrange(10000, 100000)}"
        else:
            self.namespace = namespace
            self.create_prj = False
        self.oc_api = OpenShiftAPI(namespace=self.namespace, create_prj=self.create_prj, delete_prj=self.delete_prj)
        self.oc_api.create_prj = self.create_prj
        self.oc_api.create_project()
        self.pod_json_data: dict = {}
        self.pod_name_prefix: str = ""

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

    def delete_project(self):
        self.oc_api.delete_project()

    @property
    def full_package_dir(self):
        return self.path / self.package_name / "src"

    @property
    def get_tarball_name(self):
        return f"{self.package_name}-{self.version}.tgz"

    @property
    def get_full_tarball_path(self):
        return self.tarball_dir / self.get_tarball_name

    def get_version_from_chart_yaml(self) -> Any:
        chart_yaml = self.full_package_dir / "Chart.yaml"
        if not chart_yaml.exists():
            return False
        with open(chart_yaml) as fd_chart:
            lines = fd_chart.read()
        chart_dict = yaml.safe_load(lines)
        if "appVersion" in chart_dict:
            return chart_dict["appVersion"]
        return None

    def set_version(self, version: str):
        self.version = version

    def is_chart_yaml_present(self):
        if (self.full_package_dir / "Chart.yaml") .exists():
            return True
        return False

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
        output = HelmChartsAPI.run_helm_command(cmd=command)
        print(output)
        # Remove debug wrong output
        new_output = []
        for line in output.split('\n'):
            print(line)
            if line.startswith("W"):
                continue
            new_output.append(line)
        # output = [x for x in output.split('\n') if not x.startswith("W")]
        # print(output)
        return json.loads(''.join(new_output))

    def is_pod_finished(self, pod_suffix_name: str = "deploy") -> bool:
        if not self.pod_json_data:
            self.pod_json_data = self.oc_api.get_pod_status()
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            if self.pod_name_prefix not in pod_name:
                continue
            status = item["status"]["phase"]
            print(f"is_pod_finished for {pod_suffix_name}: {pod_name} and status: {status}.")
            if pod_suffix_name in pod_name and status != "Succeeded":
                continue
            if pod_suffix_name in pod_name and status == "Succeeded":
                print(f"Pod with suffix {pod_suffix_name} is finished")
                return True
        return False

    def is_build_pod_present(self) -> bool:
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            print(f"is_build_pod_present: {pod_name}.")
            if "build" in pod_name:
                return True
        return False

    def is_s2i_pod_running(self, pod_name_prefix: str = "") -> bool:
        self.pod_name_prefix = pod_name_prefix
        build_pod_finished = False
        for count in range(180):
            print(f"Cycle for checking s2i build pod status: {count}.")
            self.pod_json_data = self.oc_api.get_pod_status()
            if len(self.pod_json_data["items"]) == 0:
                time.sleep(3)
                continue
            if not self.is_build_pod_present():
                print("Build pod is not present.")
                time.sleep(3)
                continue
            print("Build pod is present.")
            if not self.is_pod_finished(pod_suffix_name="build"):
                print("Build pod is not yet finished")
                time.sleep(3)
                continue
            print("Build pod is finished")
            build_pod_finished = True
        if not build_pod_finished:
            print("Build pod was not finished.")
            return False
        for count in range(60):
            if not self.is_pod_running():
                print("Running pod is not yet finished")
                time.sleep(3)
                continue
            print("Pod is running")
            return True
        return False

    def get_pod_count(self) -> int:
        count: int = 0
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            print(f"get_pod_count: {pod_name} and {self.pod_name_prefix}.")
            if self.pod_name_prefix not in pod_name:
                continue
            if "deploy" in pod_name:
                continue
            if "build" in pod_name:
                continue
            count += 1
        print(f"get_pod_count: {count}")
        return count

    def is_pod_running(self, pod_name_prefix: str = "") -> bool:
        for count in range(60):
            print(f"Cycle for checking pod status: {count}.")
            self.pod_json_data = self.oc_api.get_pod_status()
            if pod_name_prefix == "" and self.pod_name_prefix == "":
                print("Application pod name is not specified. Call: is_pod_running(pod_name_prefix=\"something\").")
                return False
            if pod_name_prefix != "":
                self.pod_name_prefix = pod_name_prefix
            # Only one running pod is allowed
            if self.get_pod_count() != 1:
                time.sleep(3)
                continue

            for item in self.pod_json_data["items"]:
                pod_name = item["metadata"]["name"]
                if self.pod_name_prefix not in pod_name:
                    continue
                status = item["status"]["phase"]
                print(f"Pod Name: {pod_name} and status: {status}.")
                if "deploy" in pod_name:
                    continue
                if item["status"]["phase"] == "Running":
                    print(f"Pod with name {pod_name} is running {status}.")
                    output = OpenShiftAPI.run_oc_command(
                        f"logs {pod_name}", namespace=self.namespace, json_output=False
                    )
                    print(output)
                    # Wait couple seconds for sure
                    time.sleep(3)
                    return True
            time.sleep(3)

        return False

    def check_helm_installation(self):
        # Let's check that pod is really running
        output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        print(output)
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
        output = HelmChartsAPI.run_helm_command(f"uninstall {self.package_name} -n {self.namespace}", json_output=False)
        print(output)

    def helm_installation(self, values: Dict = None):
        self.version = self.get_version_from_chart_yaml()
        if not self.version:
            return False
        if self.is_helm_package_installed():
            self.helm_uninstallation()
        command_values = ""
        if values:
            command_values = ' '.join([f"--set {key}={value}" for key, value in values.items()])
        json_output = self.get_helm_json_output(
            f"install {self.package_name} {self.get_full_tarball_path} {command_values}"
        )
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
        result_list = [x in ''.join(output) for x in check_list]
        if False in result_list:
            return False
        return True

    def test_helm_chart(self, expected_str: List[str]) -> bool:
        for count in range(40):
            time.sleep(3)
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
        output = OpenShiftAPI.run_oc_command("status", json_output=False)
        print(output)
        output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        print(output)
        return False

    def get_is_json(self):
        output = OpenShiftAPI.run_oc_command(
            "get is", namespace=self.namespace, return_output=True, ignore_error=True, shell=True
        )
        return json.loads(output)

    def get_routes(self):
        output = OpenShiftAPI.run_oc_command(
            "get route",
            namespace=self.namespace, return_output=True, ignore_error=True, shell=True
        )
        return json.loads(output)

    def get_route_name(self, route_name: str):
        json_data = self.get_routes()
        if len(json_data["items"]) == 0:
            return None
        for item in json_data["items"]:
            if item["metadata"]["namespace"] != self.namespace:
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
        tag_found = False
        json_output = self.get_is_json()
        for tag in json_output["items"][0]["spec"]["tags"]:
            print(f"TAG: {tag}")
            if tag["name"] == version and tag["from"]["name"] == registry:
                tag_found = True
                break
        return tag_found

    def test_helm_curl_output(
            self, route_name: str, expected_str: str, port: int = None, schema: str = "http://"
    ) -> bool:
        # Let's get some time to start application
        time.sleep(10)
        host_name = self.get_route_name(route_name=route_name)
        print(f"test_helm_curl_output: Route name is: {host_name}")
        if not host_name:
            return False
        url_address = f"{schema}{host_name}"
        if port:
            url_address = f"{url_address}:{port}"
        print(f"test_helm_curl_output: to {url_address}")
        valid_request: bool = False
        for count in range(20):
            try:
                resp = requests.get(url_address, verify=False)
                resp.raise_for_status()
                valid_request = True
                if resp.status_code != 200:
                    print(f"test_helm_curl_output: {resp.text}, {resp.status_code}")
                    return False
                print(f"test_helm_curl_output: {resp.text}")
                if expected_str not in resp.text:
                    print(resp.text)
                    return False
                return True
            except requests.exceptions.HTTPError:
                print("test_helm_curl_output: Service is not yet available. Let's wait some time")
                time.sleep(3)
                pass
        if not valid_request:
            print("test_helm_curl_output: Service was not available")
            return False
        return False
