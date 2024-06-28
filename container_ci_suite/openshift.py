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
import re
import time
import random
import subprocess

from pathlib import Path
from subprocess import CalledProcessError
from typing import Dict, Any, List

from container_ci_suite.container import DockerCLIWrapper

import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftAPI:

    def __init__(
            self, namespace: str = "default",
            pod_name_prefix: str = "", create_prj: bool = True,
            delete_prj: bool = True,
            version: str = ""
    ):
        self.namespace = namespace
        self.create_prj = create_prj
        self.delete_prj = delete_prj
        self.pod_name_prefix = pod_name_prefix
        self.pod_json_data: Dict = {}
        self.version = version
        self.build_failed: bool = False
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

        return utils.run_command(
            f"oc {cmd} {namespace_cmd} {json_cmd}",
            return_output=return_output,
            ignore_error=ignore_error,
            shell=shell,
        )

    def create_project(self):
        if self.create_prj:
            OpenShiftAPI.run_oc_command(f"new-project {self.namespace}", json_output=False, return_output=True)
        else:
            OpenShiftAPI.run_oc_command(f"project {self.namespace}", json_output=False)
        return self.is_project_exits()

    def delete_project(self):
        if self.delete_prj:
            OpenShiftAPI.run_oc_command("project default", json_output=False)
            OpenShiftAPI.run_oc_command(f"delete project {self.namespace} --grace-period=0 --force", json_output=False)

    def is_project_exits(self) -> bool:
        output = OpenShiftAPI.run_oc_command("projects", json_output=False)
        if self.namespace in output:
            return True
        return False

    def get_pod_count(self) -> int:
        count: int = 0
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            if self.pod_name_prefix not in pod_name:
                continue
            if "deploy" in pod_name:
                continue
            if "build" in pod_name:
                continue
            count += 1
        return count

    def is_pod_running(self, pod_name_prefix: str = "", loops: int = 60) -> bool:
        print(f"Check for POD is running {pod_name_prefix}")
        for count in range(loops):
            print(".", sep="", end="")
            self.pod_json_data = self.get_pod_status()
            if pod_name_prefix == "" and self.pod_name_prefix == "":
                print("\nApplication pod name is not specified. Call: is_pod_running(pod_name_prefix=\"something\").")
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
                if "deploy" in pod_name:
                    print(".", sep="", end="")
                    continue
                if item["status"]["phase"] == "Running":
                    print(f"\nPod with name {pod_name} is running {status}.")
                    output = OpenShiftAPI.run_oc_command(
                        f"logs {pod_name}", namespace=self.namespace, json_output=False
                    )
                    print(output)
                    # Wait couple seconds for sure
                    time.sleep(3)
                    return True
            time.sleep(3)
        return False

    def is_build_pod_finished(self, cycle_count: int = 180) -> bool:
        """
        Function return information if build pod is finished.
        The function waits for 180*3 seconds
        """
        print("Check if build pod is finished")
        for count in range(cycle_count):
            print(".", sep="", end="")
            self.pod_json_data = self.get_pod_status()
            if len(self.pod_json_data["items"]) == 0:
                time.sleep(3)
                continue
            if not self.is_build_pod_present():
                print(".", sep="", end="")
                time.sleep(3)
                continue
            if not self.is_pod_finished(pod_suffix_name="build"):
                print(".", sep="", end="")
                if self.build_failed:
                    return False
                time.sleep(3)
                continue
            print("\nBuild pod is finished")
            return True
        return False

    def is_s2i_pod_running(self, pod_name_prefix: str = "", cycle_count: int = 180) -> bool:
        self.pod_name_prefix = pod_name_prefix
        build_pod_finished = False
        print("Check if S2I build pod is running")
        for count in range(cycle_count):
            print(".", sep="", end="")
            self.pod_json_data = self.get_pod_status()
            if len(self.pod_json_data["items"]) == 0:
                time.sleep(3)
                continue
            if not self.is_build_pod_present():
                time.sleep(3)
                continue
            if not self.is_pod_finished(pod_suffix_name="build"):
                time.sleep(3)
                continue
            build_pod_finished = True
            print(f"\nBuild pod with name {pod_name_prefix} is finished.")
        if not build_pod_finished:
            print(f"\nBuild pod with name {pod_name_prefix} was not finished.")
            return False
        print("Check if S2I pod is running.")
        for count in range(cycle_count):
            print(".", sep="", end="")
            if not self.is_pod_running():
                time.sleep(3)
                continue
            print("\nPod is running")
            return True
        return False

    @staticmethod
    def get_raw_url_for_json(container: str, dir: str, filename: str, branch: str = "master") -> str:
        RAW_SCL_JSON_URL: str = "https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir}/{filename}"
        return RAW_SCL_JSON_URL.format(container=container, branch=branch, dir=dir, filename=filename)

    def get_pod_status(self) -> Dict:
        # output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        # print(f"oc get all: {output}")
        output = OpenShiftAPI.run_oc_command("get pods", json_output=True, namespace=self.namespace)
        # print(f" oc get pods: {output}")
        return json.loads(output)

    def is_build_pod_present(self) -> bool:
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            if "build" in pod_name:
                return True
        return False

    def print_get_status(self):
        print("Print get all and status:")
        print(OpenShiftAPI.run_oc_command("get all", namespace=self.namespace, json_output=False))
        print(OpenShiftAPI.run_oc_command("status", namespace=self.namespace, json_output=False))
        print(OpenShiftAPI.run_oc_command("status --suggest", namespace=self.namespace, json_output=False))

    def print_pod_logs(self):
        self.pod_json_data = self.get_pod_status()
        print("Print all pod logs")
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            print(f"Logs from pod name {pod_name}:")
            oc_logs = OpenShiftAPI.run_oc_command(f"logs pod/{pod_name}", json_output=False)
            print(oc_logs)

    def is_pod_finished(self, pod_suffix_name: str = "deploy") -> bool:
        if not self.pod_json_data:
            self.pod_json_data = self.get_pod_status()
        for item in self.pod_json_data["items"]:
            print(".", sep="", end="")
            pod_name = item["metadata"]["name"]
            if self.pod_name_prefix not in pod_name:
                print(".", sep="", end="")
                continue
            status = item["status"]["phase"]
            if pod_suffix_name in pod_name and status == "Failed":
                print(f"\nPod with {pod_suffix_name} finished with {status}. See logs.")
                self.build_failed = True
                self.print_pod_logs()
                self.print_get_status()
                return False
            if pod_suffix_name in pod_name and status != "Succeeded":
                print(".", sep="", end="")
                continue
            if pod_suffix_name in pod_name and status == "Succeeded":
                print(f"\nPod with suffix {pod_suffix_name} is finished")
                return True
        return False

    def run_command_in_pod(self, pod_name, command: str = "") -> str:
        output = OpenShiftAPI.run_oc_command(f"exec {pod_name} -- \"{command}\"")
        print(output)
        return output

    def oc_get_services(self, service_name):
        output = OpenShiftAPI.run_oc_command(f"get svc/{service_name}", json_output=True, namespace=self.namespace)
        json_output = json.loads(output)
        print(json_output)
        return json_output

    def get_service_ip(self, service_name) -> Any:
        json_output = self.oc_get_services(service_name=service_name)
        if "clusterIP" not in json_output["spec"]:
            return None
        if not json_output["spec"]["clusterIP"]:
            return None
        return json_output["spec"]["clusterIP"]

    def is_imagestream_exist(self, name: str):
        try:
            json_output = self.oc_get_is(name=name)
            if json_output["kind"] == "ImageStream" and json_output["metadata"]["name"] == name:
                return json_output
        except CalledProcessError:
            pass
        return None

    def import_is(self, path: str, name: str, skip_check=False):
        if not skip_check:
            is_exists = self.is_imagestream_exist(name=name)
            if is_exists:
                return is_exists

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

    def start_build(self, service_name: str, app_name: str = "") -> str:
        from_dir = utils.download_template(template_name=app_name)
        output = OpenShiftAPI.run_oc_command(f"start-build {service_name} --from-dir={from_dir}", json_output=False)
        return output

    def docker_login_to_openshift(self) -> Any:
        output = OpenShiftAPI.run_oc_command(cmd="get route default-route -n openshift-image-registry")
        jsou_output = json.loads(output)
        print(jsou_output["spec"]["host"])
        if not jsou_output["spec"]["host"]:
            print("Default route does not exist. Install OpenShift 4 cluster properly and expose default route.")
            return None
        ocp4_register = jsou_output["spec"]["host"]
        token_output = OpenShiftAPI.run_oc_command(cmd="whoami -t", json_output=False).strip()
        cmd = f"docker login -u kubeadmin -p {token_output} {ocp4_register}"
        output = utils.run_command(
            cmd=cmd,
            ignore_error=False,
            return_output=True
        )
        print(f"Output from docker login: {output}")
        return ocp4_register

    def upload_image(self, source_image: str, tagged_image: str) -> bool:
        """
        Function pull the image specified by parameter source_image
        and tagged it into OpenShift environment as tagged_image
        :param source_image: image that is pulled and uploaded to OpenShift
        :param tagged_image: image uploaded to OpenShift and tagged by this parameter
        :return True: image was properly uploaded to OpenShift
                False: image was not either pulled or uploading failed
        """
        if not DockerCLIWrapper.docker_pull_image(image_name=source_image, loops=3):
            return False
        try:
            ocp4_register = self.docker_login_to_openshift()
            if not ocp4_register:
                return False
        except subprocess.CalledProcessError:
            return False
        output_name = f"{ocp4_register}/{self.namespace}/{tagged_image}"
        cmd = f"docker tag {source_image} {output_name}"
        print(f"Tag docker image {cmd}")
        output = utils.run_command(
            cmd=cmd,
            ignore_error=False
        )
        print(f"Upload_image tagged {output}")
        output = utils.run_command(
            cmd=f"docker push {output_name}",
            ignore_error=False
        )
        print(f"Upload_image push {output}")
        return True

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

    def is_pod_ready(self, cycle_count: int = 60) -> bool:
        """
        Function checks if pod with specific name is really ready
        """
        print("Check if pod is ready.")
        for count in range(cycle_count):
            print(".", end="")
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
                if "deploy" in pod_name:
                    continue
                if item["status"]["phase"] == "Running":
                    print(f"\nPod with name {pod_name} is running {status}.")
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
            print("\nBuild pod does not finished in proper time")
            self.print_get_status()
            return False
        if not self.is_pod_running(pod_name_prefix=name_in_template):
            print("Pod is not running after time.")
            self.print_get_status()
            return False
        return True

    def command_app_run(self, cmd: str, return_output: bool = True) -> str:
        cmd = f"exec command-app -- bash -c \"{cmd}\""
        print(f"command_app_run: {cmd}")
        cmd_out = self.run_oc_command(
            cmd=cmd, ignore_error=True, return_output=return_output, json_output=False
        )
        return cmd_out

    def create_deploy_command_app(self, image_name: str = "registry.access.redhat.com/ubi8/ubi") -> bool:
        cmd_file = utils.save_command_yaml(image_name=image_name)
        self.run_oc_command(f"create -f {cmd_file}")
        if not self.is_pod_running(pod_name_prefix="command-app"):
            print("create_deploy_command_app: command-app pod is not running after time.")
            self.print_get_status()
            return False
        output_cmd = self.command_app_run("echo $((11*11))")
        if "121" not in output_cmd:
            return False
        return True

    def imagestream_quickstart(
            self, imagestream_file: str, template_file: str,
            image_name: str, name_in_template: str, openshift_args=None
    ) -> bool:
        local_imagestream_file = utils.download_template(imagestream_file)
        self.import_is(local_imagestream_file, name="", skip_check=True)
        tagged_image = utils.get_tagged_image(image_name=image_name, version=self.version)
        if not self.upload_image(source_image=image_name, tagged_image=tagged_image):
            return False
        return self.deploy_template_with_image(
            image_name=image_name, template=template_file, name_in_template=name_in_template,
            openshift_args=openshift_args
        )

    def deploy_s2i_app(self, image_name: str, app: str, context: str, service_name: str = "") -> bool:
        tagged_image = utils.get_tagged_image(image_name=image_name, version=self.version)
        print(f"Source image {image_name} was tagged as {tagged_image}")
        self.upload_image(source_image=image_name, tagged_image=tagged_image)
        if service_name == "":
            service_name = utils.get_service_image(image_name)
        print(f"Service name in app is: {service_name}")
        app_param = app
        if Path(app).is_dir():
            app_param = utils.download_template(template_name=app)
        oc_cmd = f"new-app {tagged_image}~{app_param} --strategy=source --context-dir={context} --name={service_name}"
        try:
            output = self.run_oc_command(f"{oc_cmd}", json_output=False)
            print(output)
        except subprocess.CalledProcessError:
            return False

        time.sleep(5)
        if Path(app).is_dir():
            output = self.start_build(service_name=service_name, app_name=app)
            print(f"Output from start build: {output}")

        return True

    def deploy_image_stream_template(
            self, imagestream_file: str, template_file: str, app_name: str, openshift_args=None
    ) -> bool:
        local_is_file = utils.download_template(template_name=imagestream_file)
        local_template = utils.download_template(template_name=template_file)
        json_output = self.import_is(local_is_file, name="", skip_check=True)
        if not json_output:
            print("deploy_image_stream_template: import_is failed")
            return False
        if openshift_args is None:
            openshift_args = ""
        else:
            openshift_args = f"-p {self.get_openshift_args(oc_args=openshift_args)}"
        print(f"========\n"
              f"Creating a new-app with name {app_name} in "
              f"namespace {self.namespace} with args {openshift_args}\n"
              f"========")
        oc_cmd = f"new-app -f {local_template} --name={app_name} -p NAMESPACE={self.namespace} {openshift_args}"
        print(f"Deploy template by command: oc {oc_cmd}")
        try:
            output = self.run_oc_command(f"{oc_cmd}", json_output=False)
            print(output)
        except subprocess.CalledProcessError:
            return False
        # Let's wait couple seconds to deployment can start
        time.sleep(3)
        return True

    def deploy_imagestream_s2i(
            self, imagestream_file: str, image_name: str, app: str, context: str
    ) -> bool:
        """
        Function deploys imagestreams as s2i application
        In case of failure check if imagestream_file really exist
        :param imagestream_file: imagestream file that is imported to OCP4
        :param image_name: image name that is used for testing
        :param app: the app reference that is used in template like https://github.com/sclorg/httpd-ex.git
        :param context: specify context of in source git repository
        :return True: application was properly deployed
                False: application was not properly deployed
        """
        imagestream_file = re.sub(r"[0-9]", "", imagestream_file)
        local_template = utils.download_template(template_name=imagestream_file)
        if not local_template:
            return False
        self.import_is(local_template, name="", skip_check=True)
        return self.deploy_s2i_app(image_name=image_name, app=app, context=context)

    def deploy_template_with_image(
            self, image_name: str, template: str, name_in_template: str = "", openshift_args=None
    ) -> bool:
        tagged_image = f"{name_in_template}:{self.version}"
        if not self.upload_image(source_image=image_name, tagged_image=tagged_image):
            return False
        return self.deploy_template(
            template=template, name_in_template=name_in_template, openshift_args=openshift_args, expected_output=""
        )

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
            openshift_args = f"-p {self.get_openshift_args(openshift_args)}"
        print(f"========\n"
              f"Creating a new-app with name {name_in_template} in "
              f"namespace {self.namespace} with args ${openshift_args}\n"
              f"========")
        local_template = utils.download_template(template_name=template)
        if not local_template:
            return False
        oc_cmd = f"new-app {local_template} --name {name_in_template} -p NAMESPACE={self.namespace} {openshift_args}"
        print(f"Deploy template by command: oc {oc_cmd}")
        try:
            output = self.run_oc_command(f"{oc_cmd}", json_output=False)
            print(output)
        except subprocess.CalledProcessError:
            return False
        # Let's wait couple seconds to deployment can start
        time.sleep(3)
        return True

    def check_command_internal(
            self,
            image_name: str,
            service_name: str,
            cmd: str,
            expected_output: str,
            timeout: int = 120
    ) -> bool:
        if not self.create_deploy_command_app(image_name=image_name):
            return False
        ip_address = self.get_service_ip(service_name=service_name)
        cmd = cmd.replace("<IP>", ip_address)
        for count in range(timeout):
            output = self.command_app_run(cmd=cmd, return_output=True)
            if expected_output in output:
                return True
            print(f"Output {expected_output} in NOT present in the output of `{cmd}`")
            time.sleep(3)
        return False

    def check_response_inside_cluster(
            self, cmd_to_run: str = None, name_in_template: str = "",
            expected_output: str = "",
            port: int = 8080,
            protocol: str = "http",
            response_code: int = 200,
            max_tests: int = 20
    ) -> bool:
        ip_address = self.get_service_ip(service_name=name_in_template)
        url = f"{protocol}://{ip_address}:{port}/"
        print(f"URL address to get internal response is: {url}")
        if not self.create_deploy_command_app():
            return False
        if cmd_to_run is None:
            cmd_to_run = "curl --connect-timeout 10 -k -s -w '%{http_code}' " + f"{url}"
        # Check if application returns proper HTTP_CODE
        print("Check if HTTP_CODE is valid.")
        for count in range(max_tests):
            output_code = self.command_app_run(cmd=f"{cmd_to_run}", return_output=True)
            return_code = output_code[-3:]
            try:
                int_ret_code = int(return_code)
                if int_ret_code == response_code:
                    print(f"HTTP_CODE is VALID {int_ret_code}")
                    break
            except ValueError:
                print(return_code)
                time.sleep(3)
                continue
            time.sleep(5)
            continue

        cmd_to_run = "curl --connect-timeout 10 -k -s " + f"{url}"
        # Check if application returns proper output
        for count in range(max_tests):
            output_code = self.command_app_run(cmd=f"{cmd_to_run}", return_output=True)
            print(f"Check if expected output {expected_output} is in {cmd_to_run}.")
            if expected_output in output_code:
                print(f"Expected output '{expected_output}' is present.")
                return True
            print(
                f"check_response_inside_cluster:"
                f"expected_output {expected_output} not found in output of {cmd_to_run} command. See {output_code}"
            )
            time.sleep(10)
        return False

    def check_response_outside_cluster(
            self, name_in_template: str = "",
            expected_output: str = "",
            port: int = None,
            protocol: str = "http",
            response_code: int = 200,
    ) -> bool:

        route_name = self.get_route_url(routes_name=name_in_template)
        print(f"Route name is {route_name}")
        url = f"{protocol}://{route_name}"
        for count in range(3):
            print(f"Let's try to get response from route {url} one more time {count}")
            response_status = utils.get_response_request(
                url_address=url, response_code=response_code, expected_str=expected_output
            )
            if not response_status:
                time.sleep(10)
                continue
            break

        # ct_os_service_image_info
        return response_status
