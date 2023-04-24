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
import logging
import random
import time

from typing import Dict
from pathlib import Path

import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HelmChartsAPI:

    def __init__(self, path: Path, package_name: str, tarball_dir: Path,  namespace: str = "default"):
        self.path: Path = path
        self.version: str = ""
        self.package_name: str = package_name
        self.tarball_dir = tarball_dir
        if namespace == "default":
            self.namespace = f"helm-sclorg-{random.randrange(10000, 100000)}"
        else:
            self.namespace = namespace
        self.create_project()

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

    @property
    def full_package_dir(self):
        return self.path / self.package_name / "src"

    @property
    def get_tarball_name(self):
        return f"{self.package_name}-{self.version}.tgz"

    @property
    def get_full_tarball_path(self):
        return self.tarball_dir / self.get_tarball_name

    def set_version(self, version: str):
        self.version = version

    def oc_project_exists(self):
        output = utils.run_command("oc projects")
        if self.namespace in output:
            return True
        return False

    def create_project(self):
        utils.run_command(f"oc new-project {self.namespace}")
        return self.oc_project_exists()

    def delete_project(self):
        utils.run_command("oc project default")
        utils.run_command(f"oc delete project {self.namespace}")

    def is_chart_yaml_present(self):
        if (self.full_package_dir / "Chart.yaml") .exists():
            return True
        return False

    def oc_get_pod_status(self) -> Dict:
        output = utils.run_command("oc project")
        # print(f"oc project: {output}")
        output = utils.run_command("oc get all")
        # print(f"oc get all: {output}")
        output = utils.run_command(f"oc get pods -n {self.namespace} -o json")
        # print(f" oc get pods: {output}")
        return json.loads(output)

    def helm_package(self) -> bool:
        """
        Package source to Helm Chart package
        """
        if not self.is_chart_yaml_present():
            print(f"Chart.yaml file is not present in directory {self.full_package_dir}")
            return False
        output = HelmChartsAPI.run_helm_command(f"package {self.full_package_dir}", json_output=False)
        if "Successfully packaged chart" in output:
            if self.get_tarball_name in output:
                return True
        return False

    def get_helm_json_output(self, command: str) -> Dict:
        output = HelmChartsAPI.run_helm_command(cmd=command)
        return json.loads(output)

    def is_pod_running(self):
        for count in range(10):
            print(f"Cycle for checking pod status: {count}.")
            json_data = self.oc_get_pod_status()
            output = utils.run_command("oc status --suggest")
            print(output)
            if len(json_data["items"]) == 0:
                time.sleep(3)
                continue
            for item in json_data["items"]:
                pod_name = item["metadata"]["name"]
                status = item["status"]["phase"]
                print(f"Pod Name: {pod_name} and status: {status}.")
                if "deploy" in pod_name and status != "Succeeded":
                    continue
                if not pod_name.startswith(self.namespace):
                    continue
                # Deployment is finished
                if item["status"]["phase"] == "Running":
                    print(f"Pod with name {pod_name} is running {status}.")
                    output = utils.run_command(f"oc logs {pod_name} -n {self.namespace}")
                    print(output)
                    # Wait couple seconds for sure
                    time.sleep(10)
                    return True
            time.sleep(3)

        return False

    def check_helm_installation(self):
        # Let's check that pod is really running
        output = utils.run_command("oc status")
        # print(output)
        output = utils.run_command("oc status --suggest")
        # print(output)
        output = utils.run_command("oc get all")
        print(output)
        json_output = self.get_helm_json_output(command="list")
        for out in json_output:
            if out["name"] != self.package_name:
                continue
            assert out["name"] == self.package_name
            assert out["chart"] == f"{self.package_name}-{self.version}"
            assert out["status"] == "deployed"
            assert out["namespace"] == self.namespace
            return True
        return False

    def helm_uninstallation(self):
        output = HelmChartsAPI.run_helm_command(f"uninstall {self.package_name} -n {self.namespace}", json_output=False)
        print(output)

    def helm_installation(self, values: Dict = None):
        command_values = ""
        if values:
            command_values = ' '.join([f"--set {key}={value}" for key, value in values.items()])
        json_output = self.get_helm_json_output(
            f"install {self.package_name} {self.get_full_tarball_path} {command_values}"
        )
        assert json_output["name"] == self.package_name
        assert json_output["chart"]["metadata"]["version"] == self.version
        assert json_output["info"]["status"] == "deployed"
        assert json_output["namespace"] == self.namespace
        if not self.check_helm_installation():
            logger.error("Installation has failed. Let's uninstall it and try one more time.")
            return False
        return True

    def check_test_output(self, output, expected_str: str):
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
            f"NAMESPACE: {self.namespace}",
            "Succeeded",
            expected_str,

        ]
        result_list = [x in ''.join(output) for x in check_list]
        if False in result_list:
            return False
        return True

    def test_helm_chart(self, expected_str: str):
        output = HelmChartsAPI.run_helm_command(
            f"test {self.package_name} -n {self.namespace} --logs", json_output=False
        )
        print(f"Helm test output: {output}")
        if self.check_test_output(output, expected_str=expected_str):
            return True
        output = utils.run_command("oc status")
        print(output)
        output = utils.run_command("oc get all")
        print(output)
        return False

    def get_is_json(self):
        output = utils.run_command("oc get is -o json", return_output=True, ignore_error=True, shell=True)
        return json.loads(output)

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
