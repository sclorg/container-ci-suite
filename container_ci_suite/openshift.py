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
from typing import Dict, Any, List

from container_ci_suite.engines.container import PodmanCLIWrapper
from container_ci_suite.engines.openshift import OpenShiftOperations
from container_ci_suite.utils import run_oc_command


import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftAPI:

    def __init__(
            self, namespace: str = "default",
            pod_name_prefix: str = "", create_prj: bool = True,
            delete_prj: bool = True,
            shared_cluster: bool = False,
            version: str = "",
            test_type: str = "ocp4"
    ):
        self.create_prj = create_prj
        self.delete_prj = delete_prj
        if not shared_cluster:
            self.shared_cluster = shared_cluster
        else:
            self.shared_cluster = utils.is_shared_cluster(test_type=test_type)
        self.pod_name_prefix = pod_name_prefix
        self.pod_json_data: Dict = {}
        self.version = version
        self.shared_random_name = ""
        self.config_tenant_name = "core-services-ocp--config"
        self.openshift_ops = OpenShiftOperations(pod_name_prefix=pod_name_prefix)
        print(f"Namespace is: {namespace} and shared cluster is: {self.shared_cluster}")
        if namespace == "default":
            self.create_project()
        else:
            self.namespace = namespace
            self.create_prj = False

    def create_project(self):
        print(f"Create project {self.create_prj} and {self.shared_cluster}")
        if self.create_prj:
            self.openshift_ops.login_to_cluster(shared_cluster=self.shared_cluster)
            if self.shared_cluster:
                self.shared_random_name = f"sclorg-{random.randrange(10000, 100000)}"
                self.namespace = f"core-services-ocp--{self.shared_random_name}"
                self.openshift_ops.set_namespace(self.namespace)
                if not self.prepare_tenant_namespace():
                    return False
            else:
                self.namespace = f"sclorg-{random.randrange(10000, 100000)}"
                self.openshift_ops.set_namespace(self.namespace)
                run_oc_command(f"new-project {self.namespace}", json_output=False, return_output=True)
                print(f"Project with the name '{self.namespace}' were created.")
        else:
            run_oc_command(f"project {self.namespace}", json_output=False)
        return self.openshift_ops.is_project_exits()

    def create_tenant_namespace(self) -> bool:
        tenant_yaml_file = utils.save_tenant_namespace_yaml(project_name=self.shared_random_name)
        try:
            tentant_output = run_oc_command(cmd=f"create -f {tenant_yaml_file}", json_output=False, return_output=True)
            print(tentant_output)
        except subprocess.CalledProcessError:
            print(f"Create tenant namespace with the name '{self.shared_random_name}' was not successful.")
            return False
        return True

    def create_egress_rules(self) -> bool:
        tenant_egress_file = utils.save_tenant_egress_yaml(project_name=self.shared_random_name)
        try:
            tentant_output = run_oc_command(cmd=f"apply -f {tenant_egress_file}", json_output=False, return_output=True)
            print(tentant_output)
        except subprocess.CalledProcessError as cpe:
            print(f"Apply egress rules to tenant namespace '{self.shared_random_name}' was not successful. {cpe}")
            return False
        return True

    def prepare_tenant_namespace(self):
        print(f"Prepare Tenant Namespace with name: '{self.shared_random_name}'")
        json_flag = False
        if not self.create_tenant_namespace():
            return False
        # Let's wait 3 seconds till project is not up
        time.sleep(3)
        self.create_egress_rules()
        run_oc_command(
            cmd=f"project {self.namespace}",
            json_output=json_flag,
            return_output=True
        )
        print("Tenant Namespace were created")

    def delete_tenant_namespace(self):
        json_flag = False
        namespace = run_oc_command(cmd="project -q", json_output=json_flag)
        if namespace == self.config_tenant_name:
            print(f"Deleting tenant '{self.config_tenant_name}' is not allowed.")
            return
        run_oc_command(f"project {self.config_tenant_name}", json_output=json_flag)
        if run_oc_command(
                f"delete tenantnamespace {self.shared_random_name}",
                json_output=json_flag
        ):
            print(f"TenantNamespace {self.shared_random_name} was deleted properly")
        else:
            print(f"!!!!! TenantNamespace ${self.shared_random_name} was not delete properly."
                  f"But it does not block CI.!!!!")

    def get_raw_url_for_json(self, container: str, dir: str, filename: str, branch: str = "master"):
        return utils.get_raw_url_for_json(container=container, dir=dir, filename=filename, branch=branch)

    def is_s2i_pod_running(self, pod_name_prefix: str):
        return self.openshift_ops.is_s2i_pod_running(pod_name_prefix=pod_name_prefix)

    def is_pod_running(self, pod_name_prefix: str):
        return self.openshift_ops.is_pod_running(pod_name_prefix=pod_name_prefix)

    def delete_project(self):
        if not self.delete_prj:
            print("Deleting project is SUPPRESSED.")
            # project is not deleted by request user
        else:
            if self.shared_cluster:
                print("Delete project on shared cluster")
                self.delete_tenant_namespace()
            else:
                print(f"Deleting project {self.namespace}")
                run_oc_command("project default", json_output=False)
                run_oc_command(
                    f"delete project {self.namespace} --grace-period=0 --force", json_output=False
                )

    def run_command_in_pod(self, pod_name, command: str = "") -> str:
        output = run_oc_command(f"exec {pod_name} -- \"{command}\"")
        print(output)
        return output

    def import_is(self, path: str, name: str, skip_check=False):
        if not skip_check:
            is_exists = self.openshift_ops.is_imagestream_exist(name=name)
            if is_exists:
                return is_exists
        output = run_oc_command(f"create -f {path}", namespace=self.namespace)
        # Let's wait 3 seconds till imagestreams are not uploaded
        time.sleep(3)
        return json.loads(output)

    def process_file(self, path: str):
        output = run_oc_command(f"process -f {path}", namespace=self.namespace)
        json_output = json.loads(output)
        print(json_output)
        return json_output

    def start_build(self, service_name: str, app_name: str = "") -> str:
        from_dir = utils.download_template(template_name=app_name)
        output = run_oc_command(f"start-build {service_name} --from-dir={from_dir}", json_output=False)
        return output

    def login_to_shared_cluster(self):
        self.openshift_ops.login_to_cluster(shared_cluster=True)
        output = run_oc_command("version", json_output=False)
        print(output)
        output = run_oc_command(f"project {self.config_tenant_name}", json_output=False)
        print(output)

    @staticmethod
    def login_external_registry() -> Any:
        registry_url = utils.get_shared_variable("registry_url")
        robot_token = utils.load_shared_credentials("ROBOT_TOKEN")
        robot_name = utils.get_shared_variable("robot_account")
        if not all([registry_url, robot_token, robot_name]):
            print(
                "Important variable ROBOT_TOKEN or variables in file /root/shared_cluster"
                " 'registry_url,robot_account' are missing."
            )
            return None
        cmd = f"podman login -u \"{robot_name}\" -p \"{robot_token}\" {registry_url}"
        output = utils.run_command(
            cmd=cmd,
            ignore_error=False,
            return_output=True
        )
        print(f"Output from podman login: {output}")
        return registry_url

    def upload_image_to_external_registry(self, source_image: str, tagged_image: str):
        register_url = OpenShiftAPI.login_external_registry()
        print(f"Registry_url: {register_url}")
        if not register_url:
            return None
        output_name = f"{register_url}/core-services-ocp/{tagged_image}"
        print(utils.run_command("podman images"))
        cmd = f"podman tag {source_image} {output_name}"
        output = utils.run_command(cmd, ignore_error=False, return_output=True)
        print(f"Output from podman tag command {output}")
        cmd = f"podman push {output_name}"
        output = utils.run_command(cmd, ignore_error=False, return_output=True)
        print(f"Output from podman push command {output}")
        ret = run_oc_command(
            f"import-image {tagged_image} --from={output_name} --confirm", json_output=False, return_output=True
        )
        print(ret)
        # Let's wait couple seconds
        time.sleep(3)
        return True

    def docker_login_to_openshift(self) -> Any:
        output = run_oc_command(cmd="get route default-route -n openshift-image-registry")
        jsou_output = json.loads(output)
        print(jsou_output["spec"]["host"])
        if not jsou_output["spec"]["host"]:
            print("Default route does not exist. Install OpenShift 4 cluster properly and expose default route.")
            return None
        ocp4_register = jsou_output["spec"]["host"]
        token_output = run_oc_command(cmd="whoami -t", json_output=False).strip()
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
        if not PodmanCLIWrapper.docker_pull_image(image_name=source_image, loops=3):
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
        output = run_oc_command(
            f"new-app {template_json} --name {name} -p NAMESPACE={self.namespace} {args}",
            json_output=False
        )
        print(output)
        return output

    def get_route_url(self, routes_name: str) -> Any:
        output = run_oc_command(f"get routes/{routes_name}")
        json_output = json.loads(output)
        if not json_output["spec"]["host"]:
            return None
        if routes_name != json_output["spec"]["to"]["name"]:
            return None
        return json_output["spec"]["host"]

    def get_openshift_args(self, oc_args: List[str]) -> str:
        return " -p ".join(oc_args)

    def template_deployed(self, name_in_template: str = "", timeout: int = 180) -> bool:
        if not self.openshift_ops.is_build_pod_finished(cycle_count=timeout):
            print("\nBuild pod does not finished in proper time")
            self.openshift_ops.print_get_status()
            return False
        if not self.openshift_ops.is_pod_running(pod_name_prefix=name_in_template):
            print("Pod is not running after time.")
            self.openshift_ops.print_get_status()
            return False
        return True

    def command_app_run(self, cmd: str, return_output: bool = True) -> str:
        cmd = f"exec command-app -- bash -c \"{cmd}\""
        print(f"command_app_run: {cmd}")
        cmd_out = run_oc_command(
            cmd=cmd, ignore_error=True, return_output=return_output, json_output=False
        )
        return cmd_out

    def create_deploy_command_app(self, image_name: str = "registry.access.redhat.com/ubi8/ubi") -> bool:
        cmd_file = utils.save_command_yaml(image_name=image_name)
        run_oc_command(f"create -f {cmd_file}")
        if not self.openshift_ops.is_pod_running(pod_name_prefix="command-app"):
            print("create_deploy_command_app: command-app pod is not running after time.")
            self.openshift_ops.print_get_status()
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
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(source_image=image_name, tagged_image=tagged_image):
                return False
        else:
            if not self.upload_image(source_image=image_name, tagged_image=tagged_image):
                return False
        return self.deploy_template_with_image(
            image_name=image_name, template=template_file, name_in_template=name_in_template,
            openshift_args=openshift_args
        )

    def deploy_s2i_app(self, image_name: str, app: str, context: str, service_name: str = "") -> bool:
        tagged_image = utils.get_tagged_image(image_name=image_name, version=self.version)
        print(f"Source image {image_name} was tagged as {tagged_image}")
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(source_image=image_name, tagged_image=tagged_image):
                return False
        else:
            if not self.upload_image(source_image=image_name, tagged_image=tagged_image):
                return False

        if service_name == "":
            service_name = utils.get_service_image(image_name)
        print(f"Service name in app is: {service_name}")
        app_param = app
        if Path(app).is_dir():
            app_param = utils.download_template(template_name=app)
        oc_cmd = f"new-app {tagged_image}~{app_param} --strategy=source --context-dir={context} --name={service_name}"
        try:
            output = run_oc_command(f"{oc_cmd}", json_output=False)
            print(output)
        except subprocess.CalledProcessError as cpe:
            print(cpe.output)
            return False

        time.sleep(3)
        if Path(app).is_dir():
            output = self.start_build(service_name=service_name, app_name=app)
            print(f"Output from start build: {output}")

        return True

    def update_template_example_file(self, file_name: str) -> dict:
        json_data = utils.get_json_data(file_name=Path(file_name))
        for object in json_data["objects"]:
            if object["kind"] != "PersistentVolumeClaim":
                continue
            if "annotations" not in object["metadata"]:
                annotations: Dict = {}
            else:
                annotations = object["metadata"]["annotations"]
            annotations["trident.netapp.io/reclaimPolicy"] = "Delete"
            object["metadata"]["annotations"] = annotations
            if "labels" not in object["metadata"]:
                labels: Dict = {}
            else:
                labels = object["metadata"]["labels"]
            labels["paas.redhat.com/appcode"] = utils.get_shared_variable("app_code")
            object["metadata"]["labels"] = labels
            object["spec"]["storageClassName"] = "netapp-nfs"
            object["spec"]["volumeMode"] = "Filesystem"
        utils.dump_json_data(json_data=json_data, file_name=Path(file_name))
        return json_data

    def deploy_image_stream_template(
            self, imagestream_file: str, template_file: str, app_name: str, openshift_args=None
    ) -> bool:
        local_is_file = utils.download_template(template_name=imagestream_file)
        local_template = utils.download_template(template_name=template_file)
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)
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
            output = run_oc_command(f"{oc_cmd}", json_output=False)
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
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)

        self.import_is(local_template, name="", skip_check=True)
        return self.deploy_s2i_app(image_name=image_name, app=app, context=context)

    def deploy_template_with_image(
            self, image_name: str, template: str, name_in_template: str = "", openshift_args=None
    ) -> bool:
        tagged_image = f"{name_in_template}:{self.version}"
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(source_image=image_name, tagged_image=tagged_image):
                return False
        else:
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
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)
        oc_cmd = f"new-app {local_template} --name {name_in_template} -p NAMESPACE={self.namespace} {openshift_args}"
        print(f"Deploy template by command: oc {oc_cmd}")
        try:
            output = run_oc_command(f"{oc_cmd}", json_output=False)
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
        ip_address = self.openshift_ops.get_service_ip(service_name=service_name)
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
        ip_address = self.openshift_ops.get_service_ip(service_name=name_in_template)
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
                time.sleep(1)
                continue
            time.sleep(3)
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
            time.sleep(5)
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
        for count in range(10):
            print(f"Let's try to get response from route {url} one more time {count}")
            response_status = utils.get_response_request(
                url_address=url, response_code=response_code, expected_str=expected_output
            )
            if not response_status:
                time.sleep(5)
                continue
            break

        # ct_os_service_image_info
        return response_status
