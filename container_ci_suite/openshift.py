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


from typing import Dict


import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftAPI:

    def __init__(self, namespace: str = "default", create_prj: bool = True, delete_prj: bool = True):
        self.namespace = namespace
        self.create_prj = create_prj
        self.delete_prj = delete_prj

    @staticmethod
    def run_oc_command(
        cmd, json_output: bool = True, return_output: bool = True, ignore_error: bool = False, shell: bool = True,
            namespace: str = ""
    ):
        """
        Run docker command:
        """
        json_cmd = "-o json" if json_output else ""
        namespace_cmd = f"-n {namespace}" if namespace != "" else ""
        print(f"run_oc_command: oc {cmd} {namespace_cmd} {json_cmd}")

        return utils.run_command(
            f"oc {cmd} {namespace_cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    def create_project(self):
        if self.create_prj:
            OpenShiftAPI.run_oc_command(f"new-project {self.namespace}", json_output=False)
        return self.is_project_exits()

    def delete_project(self):
        if self.delete_prj:
            OpenShiftAPI.run_oc_command("project default", json_output=False)
            OpenShiftAPI.run_oc_command(f"delete project {self.namespace}", json_output=False)

    def is_project_exits(self) -> bool:
        output = OpenShiftAPI.run_oc_command("projects", json_output=False)
        if self.namespace in output:
            return True
        return False

    def oc_get_pod_status(self) -> Dict:
        output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        # print(f"oc get all: {output}")
        output = OpenShiftAPI.run_oc_command("get pods", json_output=True, namespace=self.namespace)
        # print(f" oc get pods: {output}")
        return json.loads(output)
