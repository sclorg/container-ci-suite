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
from typing import Dict


import container_ci_suite.utils as utils


class HelmChartsAPI:

    def __init__(self, path: str, package_name: str, version: str, namespace: str = "default"):
        self.path = path
        self.version = version
        self.package_name = package_name
        self.namespace = namespace

    @staticmethod
    def run_helm_command(
        cmd, json_output: bool = True, return_output: bool = True, ignore_error: bool = False, shell: bool = True
    ):
        """
        Run docker command:
        """
        json_cmd = "-o json" if json_output else ""
        return utils.run_command(
            f"helm {cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    def helm_package(self) -> bool:
        """
        Package source to Helm Chart package
        """
        output = HelmChartsAPI.run_helm_command(f"package {self.path}", json_output=False)
        print(output)
        if "Successfully packaged chart" in output:
            print(self.get_tarball_name)
            if self.get_tarball_name in output:
                return True
        return False

    @property
    def get_tarball_name(self):
        return f"{self.package_name}-{self.version}.tgz"

    def check_installation(self):
        output = HelmChartsAPI.run_helm_command("list")
        json_output = json.loads(output)
        assert json_output["name"] == self.package_name
        assert json_output["chart"] == f"{self.package_name}-{self.version}"
        assert json_output["info"]["status"] == "deployed"
        assert json_output["namespace"] == self.namespace

    def get_install_package_json(self) -> Dict:
        output = HelmChartsAPI.run_helm_command(f"install {self.package_name} {self.get_tarball_name}")
        return json.loads(output)

    def helm_installation(self):
        json_output = self.get_install_package_json()
        assert json_output["name"] == self.package_name
        assert json_output["chart"]["metadata"]["version"] == self.version
        assert json_output["info"]["status"] == "deployed"
        assert json_output["namespace"] == self.namespace
        if not self.check_installation():
            return False
        return True

    def test_helm_chart(self, expected_str: str):
        output = HelmChartsAPI.run_helm_command(f"test {self.package_name}")
        assert f"NAME: {self.package_name}" in output
        assert "STATUS: deployed" in output
        assert "Succeeded" in output
        assert expected_str in output

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
            if tag["name"] == version and tag["from"]["name"] == registry:
                tag_found = True
                break
        return tag_found
