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
import time
import random
import subprocess

from subprocess import CalledProcessError
from typing import Dict, Any, List


import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftAPI:

    def __init__(
            self, namespace: str = "default",
            pod_name_prefix: str = "", create_prj: bool = True,
            delete_prj: bool = True
    ):
        self.namespace = namespace
        self.create_prj = create_prj
        self.delete_prj = delete_prj
        self.pod_name_prefix = pod_name_prefix
        self.pod_json_data: Dict = {}
        if namespace == "default":
            self.namespace = f"sclorg-{random.randrange(10000, 100000)}"
            self.create_project()
        else:
            self.namespace = namespace
            self.create_prj = False

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
        else:
            OpenShiftAPI.run_oc_command(f"project {self.namespace}", json_output=False)
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
            self.pod_json_data = self.get_pod_status()
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

    def is_build_pod_finished(self) -> bool:
        """
        Function return information if build pod is finished.
        The function waits for 180*3 seconds
        """
        for count in range(180):
            self.pod_json_data = self.get_pod_status()
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
            return True
        return False

    def is_s2i_pod_running(self, pod_name_prefix: str = "") -> bool:
        self.pod_name_prefix = pod_name_prefix
        build_pod_finished = False
        for count in range(180):
            print(f"Cycle for checking s2i build pod status: {count}.")
            self.pod_json_data = self.get_pod_status()
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

    @staticmethod
    def get_raw_url_for_json(container: str, dir: str, filename: str) -> str:
        RAW_SCL_JSON_URL: str = "https://raw.githubusercontent.com/sclorg/{container}/master/{dir}/{filename}"
        return RAW_SCL_JSON_URL.format(container=container, dir=dir, filename=filename)

    def get_pod_status(self) -> Dict:
        # output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        # print(f"oc get all: {output}")
        output = OpenShiftAPI.run_oc_command("get pods", json_output=True, namespace=self.namespace)
        # print(f" oc get pods: {output}")
        return json.loads(output)

    def is_build_pod_present(self) -> bool:
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            print(f"is_build_pod_present: {pod_name}.")
            if "build" in pod_name:
                return True
        return False

    def print_get_status(self):
        print(OpenShiftAPI.run_oc_command("get all", namespace=self.namespace))
        print(OpenShiftAPI.run_oc_command("get status", namespace=self.namespace))
        print(OpenShiftAPI.run_oc_command("get status --suggest", namespace=self.namespace))

    def print_pod_logs(self):
        self.pod_json_data = self.get_pod_status()
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            print(OpenShiftAPI.run_oc_command(f"logs {pod_name}"))

    def is_pod_finished(self, pod_suffix_name: str = "deploy") -> bool:
        if not self.pod_json_data:
            self.pod_json_data = self.get_pod_status()
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

    def run_command_in_pod(self, pod_name, command: str = ""):
        output = OpenShiftAPI.run_oc_command(f"exec {pod_name} -- \"{command}\"")
        print(output)

    def get_service_ip(self, service_name) -> Any:
        output = OpenShiftAPI.run_oc_command(f"get svc/{service_name}", json_output=True, namespace=self.namespace)
        json_output = json.loads(output)
        if not json_output["spec"]["clusterIP"]:
            return None
        return json_output["spec"]["clusterIP"]

    def import_is(self, path: str, name: str):
        try:
            json_output = self.oc_get_is(name=name)
            if json_output["kind"] == "ImageStream" and json_output["metadata"]["name"] == name:
                return json_output
        except CalledProcessError:
            pass
        output = OpenShiftAPI.run_oc_command(f"create -f {path}", namespace=self.namespace)
        # Let's wait 3 seconds till imagestreams are not uploaded
        time.sleep(3)
        return json.loads(output)

    def process_file(self, path: str):
        output = OpenShiftAPI.run_oc_command(f"process -f {path}", namespace=self.namespace)
        json_output = json.loads(output)
        print(json_output)
        return json_output

    def oc_get_is(self, name: str):
        output = OpenShiftAPI.run_oc_command(f"get is/{name}", namespace=self.namespace)
        return json.loads(output)

    def start_build(self, name: str):
        output = OpenShiftAPI.run_oc_command(f"start-build {name}", json_output=False)
        return output

    def check_is_exists(self, is_name, version_to_check: str) -> bool:
        """
        Function checks if it exists in OpenShift 4 environment
        Exact version has to be the same
        :return:    True if tag was found
                    False if tag does not exist
        """
        json_output = self.oc_get_is(name=is_name)
        if "tags" not in json_output["spec"]:
            return False
        tag_found: bool = False
        for tag in json_output["spec"]["tags"]:
            if "name" not in tag:
                continue
            if version_to_check not in tag["name"]:
                continue
            tag_found = True
        return tag_found

    def create_new_app_with_template(self, name: str, template_json: str, template_args: Dict = None):
        """
        Function creates a new application in OpenShift 4 environment
        :param name: str - Template name
        :param template_json: str - Template path to file
        :param template_args: Dict - Arguments that will be passed to oc new-app
        :return json toutput
        """

        # Let's wait couple seconds till is fully loaded
        time.sleep(3)
        args = [""]
        if template_args:
            args = [f"-p {key}={val}" for key, val in template_args]
        print(args)
        output = OpenShiftAPI.run_oc_command(
            f"new-app {template_json} --name {name} -p NAMESPACE={self.namespace} {args}",
            json_output=False
        )
        print(output)
        return output

    def get_route_url(self, routes_name: str) -> Any:
        output = OpenShiftAPI.run_oc_command(f"get routes/{routes_name}")
        json_output = json.loads(output)
        if not json_output["spec"]["host"]:
            return None
        if routes_name != json_output["spec"]["to"]["name"]:
            return None
        return json_output["spec"]["host"]

    def is_pod_ready(self) -> bool:
        """
        Function checks if pod with specific name is really ready
        """

        for count in range(60):
            print(f"Cycle for checking pod status: {count}.")
            json_data = self.get_pod_status()
            if len(json_data["items"]) == 0:
                time.sleep(3)
                continue
            if not self.is_pod_finished(pod_suffix_name=self.pod_name_prefix):
                time.sleep(3)
                continue
            for item in json_data["items"]:
                pod_name = item["metadata"]["name"]
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
                    time.sleep(10)
                    return True
                time.sleep(3)
        return False

    def get_openshift_args(self, oc_args: List[str]) -> str:
        return " -p ".join(oc_args)

    def template_deployed(self, name_in_template: str = "") -> bool:
        if not self.is_build_pod_finished():
            print("deploy_template: Build pod does not finished in proper time")
            self.print_get_status()
            return False
        if not self.is_pod_running(pod_name_prefix=name_in_template):
            print("deploy_template: Pod is not running after time.")
            self.print_get_status()
            return False
        return True
    #
    # def create_deploy_cmd_image(self):
    #     cmd_file = utils.save_command_yaml(image_name="registry.access.redhat.com/ubi7/ubi")
    #     OpenShiftAPI.run_oc_command(f"create -f {cmd_file}")

    def deploy_template(
            self, template: str,
            name_in_template: str,
            expected_output: str,
            port: int = 8080,
            protocol: str = "http",
            response_code: int = 200,
            openshift_args=None,
            other_images=None
    ) -> bool:

        if other_images is None:
            other_images = ""
        if openshift_args is None:
            openshift_args = ""
        else:
            openshift_args = self.get_openshift_args(openshift_args)
        print(f"========"
              f"Creating a new-app with name ${name_in_template} in "
              f"namespace ${self.namespace} with args ${openshift_args}."
              f"========")
        local_template = utils.download_template(template_name=template)
        oc_cmd = f"new-app {local_template} --name {name_in_template} -p NAMESPACE={self.namespace} -p {openshift_args}"
        print(f"Deploy template by command: oc {oc_cmd}")
        try:
            output = self.run_oc_command(f"{oc_cmd}", json_output=False)
            print(output)
        except subprocess.CalledProcessError:
            return False
        # Let's wait couple seconds to deployment can start
        time.sleep(3)
        return True

    def check_response_outside_cluster(
            self, name_in_template: str = "",
            expected_output: str = "",
            port: int = None,
            protocol: str = "http",
            response_code: int = 200
    ) -> bool:

        ip_address = self.get_service_ip(service_name=name_in_template)
        route_name = self.get_route_url(routes_name=name_in_template)
        url = f"{protocol}://{ip_address}/"
        if port:
            url = f"{protocol}://{ip_address}:{port}/"
        # "ct_os_test_response_internal '${protocol}://<IP>:${port}' '${response_code}' '${expected_output}'"
        print(f"URL address to get response is: {url}")
        print(f"Route name is {route_name}")
        response_status = utils.get_response_request(
            url_address=url, response_code=response_code, expected_str=expected_output
        )
        print(f"Response status from {url} is {response_status}")
        if not response_status:
            url = f"{protocol}://{route_name}"
            print(f"Let's try to get response from route {url}")
            response_status = utils.get_response_request(
                url_address=url, response_code=response_code, expected_str=expected_output
            )

        # ct_os_service_image_info
        return response_status
