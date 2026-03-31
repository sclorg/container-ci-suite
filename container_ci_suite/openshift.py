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
import shlex
import time
import random
import subprocess


from pathlib import Path
from time import sleep
from typing import Dict, Any, List

from container_ci_suite.engines.container import PodmanCLIWrapper
from container_ci_suite.engines.openshift import OpenShiftOperations
from container_ci_suite.utils import ContainerTestLibUtils


import container_ci_suite.utils as utils

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftAPI:
    """
    OpenShift API - Utility functions for OpenShift operations.
    """

    def __init__(
        self,
        namespace: str = "default",
        pod_name_prefix: str = "",
        create_prj: bool = True,
        delete_prj: bool = True,
        shared_cluster: bool = False,
        version: str = "",
        test_type: str = "ocp4",
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
        self.project_created: bool = False
        if namespace == "default":
            self.create_project()
        else:
            self.namespace = namespace
            self.create_prj = False
        logger.debug(
            "Namespace is: %s and shared cluster is: %s", namespace, self.shared_cluster
        )

    def _create_openshift_project(self) -> bool:
        """
        Create an OpenShift project.
        Returns:
            True if the project was created, False otherwise
        """
        logger.debug("Trying to create project with the name '%s'", self.namespace)
        try:
            ContainerTestLibUtils.run_oc_command(
                f"new-project {self.namespace}",
                json_output=False,
                return_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            logger.error(
                "Project with the name '%s' were not created.",
                self.namespace,
                exc_info=True,
            )
            return False

    def create_project(self):
        """
        Create a project.
        """
        logger.debug("Create project %s and %s", self.create_prj, self.shared_cluster)
        if self.create_prj:
            self.openshift_ops.login_to_cluster(shared_cluster=self.shared_cluster)
            if self.shared_cluster:
                self.shared_random_name = f"sclorg-{random.randrange(10000, 100000)}"
                self.namespace = f"core-services-ocp--{self.shared_random_name}"
                self.openshift_ops.set_namespace(self.namespace)
                if not self.prepare_tenant_namespace():
                    return False
            else:
                for _ in range(3):
                    self.namespace = f"sclorg-{random.randrange(10000, 100000)}"
                    self.openshift_ops.set_namespace(self.namespace)
                    if not self._create_openshift_project():
                        sleep(3)
                        continue
                    break
                else:
                    logger.error(
                        "Project with the name '%s' were not created after 3 attempts.",
                        self.namespace,
                    )
                    return False
                logger.debug("Project with the name '%s' were created.", self.namespace)
        else:
            ContainerTestLibUtils.run_oc_command(
                f"project {self.namespace}", json_output=False
            )
        self.project_created = True
        return self.openshift_ops.is_project_exists()

    def create_tenant_namespace(self) -> bool:
        """
        Create a tenant namespace.
        Returns:
            True if the tenant namespace was created, False otherwise
        """
        tenant_yaml_file = utils.save_tenant_namespace_yaml(
            project_name=self.shared_random_name
        )
        tentant_output = ContainerTestLibUtils.run_oc_command(
            cmd=f"create -f {tenant_yaml_file}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        )
        if tentant_output != 0:
            logger.error(
                "Create tenant namespace with the name '%s' was not successful.%s",
                self.shared_random_name,
                tentant_output,
            )
            return False
        return True

    def is_tenant_namespace_created(self) -> bool:
        """
        Check if the tenant namespace was created.
        Returns:
            True if the tenant namespace was created, False otherwise
        """
        is_tenant_namespace_created = False
        logger.debug(
            "Check if TenantNamespace %s really exists", self.shared_random_name
        )
        for _ in range(5):
            logger.debug("Waiting for TenantNamespace creation...")
            if not self.openshift_ops.is_project_exists():
                sleep(5)
                continue
            is_tenant_namespace_created = True
            break
        if not is_tenant_namespace_created:
            logger.error(
                "\nTenantNamespace %s was not created properly.",
                self.shared_random_name,
            )
        return is_tenant_namespace_created

    def apply_tenant_egress_rules(self) -> bool:
        """
        Apply the tenant egress rules.
        Returns:
            True if the tenant egress rules were applied, False otherwise
        """
        tenant_egress_file = utils.save_tenant_egress_yaml(
            project_name=self.shared_random_name
        )
        is_applied = False
        for _ in range(10):
            tentant_output = ContainerTestLibUtils.run_oc_command(
                cmd=f"apply -f {tenant_egress_file}",
                json_output=False,
                ignore_error=True,
                return_output=False,
                debug=True,
            )
            if tentant_output != 0:
                logger.error(
                    "Apply egress rules to tenant namespace '%s' was not successful.%s. Let's try one more tine",
                    self.shared_random_name,
                    tentant_output,
                )
                sleep(5)
                continue
            is_applied = True
            break
        return is_applied

    def create_limit_ranges(self) -> bool:
        """
        Create the limit ranges.
        Returns:
            True if the limit ranges were created, False otherwise
        """
        tenant_limit_file = utils.save_tenant_limit_yaml()
        is_applied = False
        for _ in range(10):
            tentant_output = ContainerTestLibUtils.run_oc_command(
                cmd=f"apply -f {tenant_limit_file}",
                json_output=False,
                ignore_error=True,
                return_output=False,
                debug=True,
            )
            if tentant_output != 0:
                logger.error(
                    "create limit ranges to tenant namespace '%s' was not successful.%s. Let's try one more tine",
                    self.shared_random_name,
                    tentant_output,
                )
                sleep(5)
                continue
            is_applied = True
            break
        return is_applied

    def prepare_tenant_namespace(self):
        """
        Prepare the tenant namespace.
        """
        logger.info("Prepare Tenant Namespace with name: '%s'", self.shared_random_name)
        json_flag = False
        try:
            namespace = ContainerTestLibUtils.run_oc_command(
                cmd="project -q", json_output=json_flag
            ).strip()
            logger.debug("The current namespace is '%s'", namespace)
            if namespace != self.config_tenant_name:
                ContainerTestLibUtils.run_oc_command(
                    f"project {self.config_tenant_name}", json_output=json_flag
                )
        except subprocess.CalledProcessError:
            ContainerTestLibUtils.run_oc_command(
                f"project {self.config_tenant_name}", json_output=json_flag
            )
        if not self.create_tenant_namespace():
            return False
        # Let's wait 5 seconds till project is not up
        time.sleep(10)
        if not self.is_tenant_namespace_created():
            return False
        if not self.apply_tenant_egress_rules():
            return False
        self.project_created = True
        ContainerTestLibUtils.run_oc_command(
            cmd=f"project {self.namespace}", json_output=json_flag, return_output=True
        )
        # if not self.create_limit_ranges():
        #     return False
        logger.info("Tenant Namespace were created")

    def delete_tenant_namespace(self):
        """
        Delete the tenant namespace.
        """
        json_flag = False
        namespace = ContainerTestLibUtils.run_oc_command(
            cmd="project -q", json_output=json_flag
        )
        if namespace == self.config_tenant_name:
            logger.error(
                "Deleting tenant '%s' is not allowed.", self.config_tenant_name
            )
            return
        ContainerTestLibUtils.run_oc_command(
            f"project {self.config_tenant_name}", json_output=json_flag
        )
        if ContainerTestLibUtils.run_oc_command(
            f"delete tenantnamespace {self.shared_random_name}", json_output=json_flag
        ):
            logger.info(
                "TenantNamespace %s was deleted properly",
                self.shared_random_name,
            )
        else:
            logger.error(
                "!!!!! TenantNamespace %s was not delete properly. But it does not block CI.!!!!",
                self.shared_random_name,
            )

    def get_raw_url_for_json(
        self, container: str, dir: str, filename: str, branch: str = "master"
    ):
        """
        Get the raw URL for the JSON.
        Args:
            container: The container
            dir: The directory
            filename: The filename
            branch: The branch
        Returns:
            The raw URL for the JSON
        """
        return utils.get_raw_url_for_json(
            container=container, dir=dir, filename=filename, branch=branch
        )

    def is_s2i_pod_running(self, pod_name_prefix: str, cycle_count: int = 180):
        """
        Check if the S2I pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
            cycle_count: The number of loops to check
        Returns:
            True if the S2I pod is running, False otherwise
        """
        return self.openshift_ops.is_s2i_pod_running(
            pod_name_prefix=pod_name_prefix, cycle_count=cycle_count
        )

    def is_pod_running(self, pod_name_prefix: str):
        """
        Check if the pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
        Returns:
            True if the pod is running, False otherwise
        """
        return self.openshift_ops.is_pod_running(pod_name_prefix=pod_name_prefix)

    def delete_project(self):
        """
        Delete the project.
        """
        if not self.delete_prj:
            logger.info("Deleting project is SUPPRESSED.")
            # project is not deleted by request user
        else:
            if self.shared_cluster:
                logger.info("Delete project on shared cluster")
                self.delete_tenant_namespace()
            else:
                logger.info("Deleting project %s", self.namespace)
                ContainerTestLibUtils.run_oc_command(
                    "project default", json_output=False
                )
                ContainerTestLibUtils.run_oc_command(
                    f"delete project {self.namespace} --grace-period=0 --force",
                    json_output=False,
                )

    def run_command_in_pod(self, pod_name, command: str = "") -> str:
        """
        Run a command in a pod.
        Args:
            pod_name: The name of the pod
            command: The command to run
        Returns:
            The output of the command
        """
        output = ContainerTestLibUtils.run_oc_command(f'exec {pod_name} -- "{command}"')
        logger.debug("%s", output)
        return output

    def import_is(self, path: str, name: str, skip_check=False):
        """
        Import an image stream.
        Args:
            path: The path to the image stream
            name: The name of the image stream
            skip_check: Whether to skip the check
        Returns:
            The output of the command
        """
        if not skip_check:
            is_exists = self.openshift_ops.is_imagestream_exist(name=name)
            if is_exists:
                return is_exists
        output = ContainerTestLibUtils.run_oc_command(
            f"create -f {path}", namespace=self.namespace
        )
        # Let's wait 3 seconds till imagestreams are not uploaded
        time.sleep(3)
        return json.loads(output)

    def process_file(self, path: str):
        """
        Process a file.
        Args:
            path: The path to the file
        Returns:
            The output of the command
        """
        output = ContainerTestLibUtils.run_oc_command(
            f"process -f {path}", namespace=self.namespace
        )
        json_output = json.loads(output)
        logger.debug(json_output)
        return json_output

    def start_build(self, service_name: str, app_name: str = "") -> str:
        """
        Start a build.
        Args:
            service_name: The name of the service
            app_name: The name of the app
        Returns:
            The output of the command
        """
        from_dir = utils.download_template(template_name=app_name)
        output = ContainerTestLibUtils.run_oc_command(
            f"start-build {service_name} --from-dir={from_dir}", json_output=False
        )
        return output

    def login_to_shared_cluster(self):
        """
        Login to the shared cluster.
        """
        self.openshift_ops.login_to_cluster(shared_cluster=True)
        output = ContainerTestLibUtils.run_oc_command("version", json_output=False)
        logger.debug(output)
        output = ContainerTestLibUtils.run_oc_command(
            f"project {self.config_tenant_name}", json_output=False
        )
        logger.debug("%s", output)

    @staticmethod
    def login_external_registry() -> Any:
        """
        Login to the external registry.
        Returns:
            The registry URL
        """
        registry_url = utils.get_shared_variable("registry_url")
        robot_token = utils.load_shared_credentials("ROBOT_TOKEN")
        robot_name = utils.get_shared_variable("robot_account")
        if not all([registry_url, robot_token, robot_name]):
            logger.error(
                "Important variable ROBOT_TOKEN or variables in file /root/shared_cluster"
                " 'registry_url,robot_account' are missing."
            )
            return None
        cmd = f'podman login -u "{robot_name}" -p "{robot_token}" {registry_url}'
        output = ContainerTestLibUtils.run_command(
            cmd=cmd, ignore_error=False, return_output=True
        )
        logger.debug("Output from podman login: %s", output)
        return registry_url

    def upload_image_to_external_registry(self, source_image: str, tagged_image: str):
        """
        Upload an image to the external registry.
        Args:
            source_image: The source image
            tagged_image: The tagged image
        Returns:
            The output of the command
        """
        register_url = OpenShiftAPI.login_external_registry()
        logger.debug("Registry_url: %s", register_url)
        if not register_url:
            return None
        output_name = f"{register_url}/core-services-ocp/{tagged_image}"
        logger.debug("%s", ContainerTestLibUtils.run_command("podman images"))
        cmd = f"podman tag {source_image} {output_name}"
        output = ContainerTestLibUtils.run_command(
            cmd, ignore_error=False, return_output=True
        )
        logger.debug("Output from podman tag command %s", output)
        cmd = f"podman push {output_name}"
        output = ContainerTestLibUtils.run_command(
            cmd, ignore_error=False, return_output=True
        )
        logger.debug("Output from podman push command %s", output)
        ret = ContainerTestLibUtils.run_oc_command(
            f"import-image {tagged_image} --from={output_name} --confirm",
            json_output=False,
            return_output=True,
        )
        logger.debug("%s", ret)
        # Let's wait couple seconds
        time.sleep(3)
        return True

    def podman_login_to_openshift(self) -> Any:
        """
        Login to the OpenShift.
        Returns:
            The OpenShift URL
        """
        output = ContainerTestLibUtils.run_oc_command(
            cmd="get route default-route -n openshift-image-registry"
        )
        jsou_output = json.loads(output)
        logger.debug(jsou_output["spec"]["host"])
        if not jsou_output["spec"]["host"]:
            logger.error(
                "Default route does not exist. Install OpenShift 4 cluster properly and expose default route."
            )
            return None
        ocp4_register = jsou_output["spec"]["host"]
        token_output = ContainerTestLibUtils.run_oc_command(
            cmd="whoami -t", json_output=False
        ).strip()
        cmd = f"podman login -u kubeadmin -p {token_output} {ocp4_register}"
        output = ContainerTestLibUtils.run_command(
            cmd=cmd, ignore_error=False, return_output=True
        )
        logger.debug("Output from podman login: %s", output)
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
        if not PodmanCLIWrapper.podman_pull_image(image_name=source_image, loops=3):
            return False
        try:
            ocp4_register = self.podman_login_to_openshift()
            if not ocp4_register:
                return False
        except subprocess.CalledProcessError:
            return False
        output_name = f"{ocp4_register}/{self.namespace}/{tagged_image}"
        cmd = f"podman tag {source_image} {output_name}"
        logger.debug("Tag podman image %s", cmd)
        output = ContainerTestLibUtils.run_command(cmd=cmd, ignore_error=False)
        logger.debug("Upload_image tagged %s", output)
        output = ContainerTestLibUtils.run_command(
            cmd=f"podman push {output_name}", ignore_error=False
        )
        logger.debug("Upload_image push %s", output)
        return True

    def create_new_app_with_template(
        self, name: str, template_json: str, template_args: Dict = None
    ):
        """
        Function creates a new application in OpenShift 4 environment
        :param name: str - Template name
        :param template_json: str - Template path to file
        :param template_args: Dict - Arguments that will be passed to oc new-app
        :return json toutput
        """
        if not self.project_created:
            return False
        # Let's wait couple seconds till is fully loaded
        time.sleep(3)
        args = [""]
        if template_args:
            args = [f"-p {key}={val}" for key, val in template_args]
        output = ContainerTestLibUtils.run_oc_command(
            f"new-app {template_json} --name {name} -p NAMESPACE={self.namespace} {args}",
            json_output=False,
        )
        logger.debug("%s", output)
        return output

    def get_route_url(self, routes_name: str) -> Any:
        """
        Get the route URL.
        Args:
            routes_name: The name of the routes
        Returns:
            The route URL
        """
        output = ContainerTestLibUtils.run_oc_command(f"get routes/{routes_name}")
        json_output = json.loads(output)
        if not json_output["spec"]["host"]:
            return None
        if routes_name != json_output["spec"]["to"]["name"]:
            return None
        return json_output["spec"]["host"]

    def get_openshift_args(self, oc_args: List[str]) -> str:
        """
        Get the OpenShift arguments.
        Args:
            oc_args: The OpenShift arguments
        Returns:
            The OpenShift arguments
        """
        return " -p ".join(oc_args)

    def is_template_deployed(
        self, name_in_template: str = "", timeout: int = 180
    ) -> bool:
        """
        Check if the template was deployed properly.
        Args:
            name_in_template: The name of the template
            timeout: The timeout
        Returns:
            True if the template was deployed properly, False otherwise
        """
        logger.info("Check if template was deployed properly")
        if not self.openshift_ops.is_build_pod_finished(cycle_count=timeout):
            logger.error("\nBuild pod does not finished in proper time")
            self.openshift_ops.print_get_status()
            return False
        if not self.openshift_ops.is_pod_running(pod_name_prefix=name_in_template):
            logger.error("Pod is not running after time.")
            self.openshift_ops.print_get_status()
            return False
        return True

    def command_app_run(self, cmd: str, return_output: bool = True) -> str:
        """
        Run a command in the command app.
        Args:
            cmd: The command to run
            return_output: Whether to return the output
        Returns:
            The output of the command
        """
        safe_cmd = shlex.quote(cmd)
        cmd = f"exec command-app -- bash -c {safe_cmd}"
        logger.debug("command_app_run: %s", cmd)
        cmd_out = ContainerTestLibUtils.run_oc_command(
            cmd=cmd, ignore_error=True, return_output=return_output, json_output=False
        )
        return cmd_out

    def create_deploy_command_app(
        self, image_name: str = "registry.access.redhat.com/ubi8/ubi"
    ) -> bool:
        """
        Create a deploy command app.
        Args:
            image_name: The name of the image
        Returns:
            True if the deploy command app was created, False otherwise
        """
        cmd_file = utils.save_command_yaml(image_name=image_name)
        ContainerTestLibUtils.run_oc_command(f"create -f {cmd_file}")
        if not self.openshift_ops.is_pod_running(pod_name_prefix="command-app"):
            logger.error(
                "create_deploy_command_app: command-app pod is not running after time."
            )
            self.openshift_ops.print_get_status()
            return False
        output_cmd = self.command_app_run("echo $((11*11))")
        if "121" not in output_cmd:
            return False
        return True

    def imagestream_quickstart(
        self,
        imagestream_file: str,
        template_file: str,
        image_name: str,
        name_in_template: str,
        openshift_args=None,
    ) -> bool:
        """
        Deploy an imagestream quickstart.
        Args:
            imagestream_file: The path to the imagestream file
            template_file: The path to the template file
            image_name: The name of the image
            name_in_template: The name of the template
            openshift_args: The OpenShift arguments
        Returns:
            True if the imagestream quickstart was deployed, False otherwise
        """
        if not self.project_created:
            return False
        local_imagestream_file = utils.download_template(imagestream_file)
        self.import_is(local_imagestream_file, name="", skip_check=True)
        tagged_image = utils.get_tagged_image(
            image_name=image_name, version=self.version
        )
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False
        else:
            if not self.upload_image(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False
        return self.deploy_template_with_image(
            image_name=image_name,
            template=template_file,
            name_in_template=name_in_template,
            openshift_args=openshift_args,
        )

    def deploy_s2i_app(
        self, image_name: str, app: str, context: str, service_name: str = ""
    ) -> bool:
        """
        Deploy an S2I app.
        Args:
            image_name: The name of the image
            app: The path to the app
            context: The context of the app
            service_name: The name of the service
        Returns:
            True if the S2I app was deployed, False otherwise
        """
        if not self.project_created:
            return False
        tagged_image = utils.get_tagged_image(
            image_name=image_name, version=self.version
        )
        logger.info("Source image %s was tagged as %s", image_name, tagged_image)
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False
        else:
            if not self.upload_image(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False

        if service_name == "":
            service_name = utils.get_service_image(image_name)
        logger.info("Service name in app is: %s", service_name)
        app_param = app
        if Path(app).is_dir():
            app_param = utils.download_template(template_name=app)
        oc_cmd = f"new-app {tagged_image}~{app_param} --strategy=source --context-dir={context} --name={service_name}"
        logger.debug("Command for deploying application is: %s", oc_cmd)
        try:
            output = ContainerTestLibUtils.run_oc_command(
                f"{oc_cmd}", json_output=False
            )
            logger.debug("%s", output)
        except subprocess.CalledProcessError as cpe:
            logger.error(cpe.output)
            return False

        time.sleep(3)
        if Path(app).is_dir():
            output = self.start_build(service_name=service_name, app_name=app)
            logger.info("Output from start build: %s", output)

        return True

    def update_template_example_file(self, file_name: str) -> dict:
        """
        Update the template example file.
        Args:
            file_name: The name of the file
        Returns:
            The JSON data
        """
        json_data = utils.get_json_data(file_name=Path(file_name))
        if "objects" not in json_data:
            return json_data
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
        self,
        imagestream_file: str,
        template_file: str,
        app_name: str,
        openshift_args=None,
    ) -> bool:
        """
        Deploy an image stream template.
        Args:
            imagestream_file: The path to the imagestream file
            template_file: The path to the template file
            app_name: The name of the app
            openshift_args: The OpenShift arguments
        Returns:
            True if the image stream template was deployed, False otherwise
        """
        if not self.project_created:
            return False
        local_is_file = utils.download_template(template_name=imagestream_file)
        local_template = utils.download_template(template_name=template_file)
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)
        json_output = self.import_is(local_is_file, name="", skip_check=True)
        if not json_output:
            logger.error("deploy_image_stream_template: import_is failed")
            return False
        if openshift_args is None:
            openshift_args = ""
        else:
            openshift_args = f"-p {self.get_openshift_args(oc_args=openshift_args)}"
        logger.info(
            "========\nCreating a new-app with name %s in namespace %s with args %s\n========",
            app_name,
            self.namespace,
            openshift_args,
        )
        oc_cmd = f"new-app -f {local_template} --name={app_name} -p NAMESPACE={self.namespace} {openshift_args}"
        logger.info("Deploy template by command: oc %s", oc_cmd)
        try:
            output = ContainerTestLibUtils.run_oc_command(
                f"{oc_cmd}", json_output=False
            )
            logger.info("%s", output)
        except subprocess.CalledProcessError:
            return False
        # Let's wait couple seconds to deployment can start
        time.sleep(3)
        return True

    def deploy_imagestream_s2i(
        self,
        imagestream_file: str,
        image_name: str,
        app: str,
        context: str,
        service_name: str,
    ) -> bool:
        """
        Function deploys imagestreams as s2i application
        In case of failure check if imagestream_file really exist
        :param imagestream_file: imagestream file that is imported to OCP4
        :param image_name: image name that is used for testing
        :param app: the app reference that is used in template like https://github.com/sclorg/httpd-ex.git
        :param context: specify context of in source git repository
        :param service_name: specify service name to check in pods
        :return True: application was properly deployed
                False: application was not properly deployed
        """
        if not self.project_created:
            return False
        imagestream_file = re.sub(r"[0-9]", "", imagestream_file)
        local_template = utils.download_template(template_name=imagestream_file)
        if not local_template:
            return False
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)

        self.import_is(local_template, name="", skip_check=True)
        return self.deploy_s2i_app(
            image_name=image_name, app=app, context=context, service_name=service_name
        )

    def deploy_template_with_image(
        self,
        image_name: str,
        template: str,
        name_in_template: str = "",
        openshift_args=None,
    ) -> bool:
        """
        Deploy a template with an image.
        Args:
            image_name: The name of the image
            template: The path to the template
            name_in_template: The name of the template
            openshift_args: The OpenShift arguments
        Returns:
            True if the template was deployed, False otherwise
        """
        if not self.project_created:
            return False
        tagged_image = f"{name_in_template}:{self.version}"
        logger.debug(
            "deploy_template_with_image: %s and %s", tagged_image, self.shared_cluster
        )
        if self.shared_cluster:
            if not self.upload_image_to_external_registry(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False
        else:
            if not self.upload_image(
                source_image=image_name, tagged_image=tagged_image
            ):
                return False

        return self.deploy_template(
            template=template,
            name_in_template=name_in_template,
            openshift_args=openshift_args,
            expected_output="",
        )

    def deploy_template(
        self,
        template: str,
        name_in_template: str,
        expected_output: str,
        port: int = 8080,
        protocol: str = "http",
        response_code: int = 200,
        openshift_args=None,
        other_images=None,
    ) -> bool:
        """
        Deploy a template.
        Args:
            template: The path to the template
            name_in_template: The name of the template
            expected_output: The expected output
            port: The port
            protocol: The protocol
            response_code: The response code
            openshift_args: The OpenShift arguments
            other_images: The other images
        Returns:
            True if the template was deployed, False otherwise
        """
        if not self.project_created:
            return False
        if other_images is None:
            other_images = ""
        if openshift_args is None:
            openshift_args = ""
        else:
            openshift_args = f"-p {self.get_openshift_args(openshift_args)}"
        logger.info(
            "========\nCreating a new-app with name %s in namespace %s with args %s\n========",
            name_in_template,
            self.namespace,
            openshift_args,
        )
        local_template = utils.download_template(template_name=template)
        if not local_template:
            return False
        if self.shared_cluster:
            self.update_template_example_file(file_name=local_template)
        oc_cmd = f"new-app {local_template} --name {name_in_template} -p NAMESPACE={self.namespace} {openshift_args}"
        logger.info("Deploy template by command: oc %s", oc_cmd)
        try:
            output = ContainerTestLibUtils.run_oc_command(
                f"{oc_cmd}", json_output=False
            )
            logger.info("%s", output)
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
        timeout: int = 120,
    ) -> bool:
        """
        Check the command internal.
        Args:
            image_name: The name of the image
            service_name: The name of the service
            cmd: The command to run
            expected_output: The expected output
            timeout: The timeout
        Returns:
            True if the command internal was checked, False otherwise
        """
        if not self.create_deploy_command_app(image_name=image_name):
            return False
        ip_address = self.openshift_ops.get_service_ip(service_name=service_name)
        cmd = cmd.replace("<IP>", ip_address)
        for _ in range(timeout):
            output = self.command_app_run(cmd=cmd, return_output=True)
            if expected_output in output:
                return True
            logger.info(
                "Output %s in NOT present in the output of `%s`",
                expected_output,
                cmd,
            )
            time.sleep(3)
        return False

    def check_response_inside_cluster(
        self,
        cmd_to_run: str = None,
        name_in_template: str = "",
        expected_output: str = "",
        port: int = 8080,
        protocol: str = "http",
        response_code: int = 200,
        max_tests: int = 20,
    ) -> bool:
        """
        Check the response inside the cluster.
        Args:
            cmd_to_run: The command to run
            name_in_template: The name of the template
            expected_output: The expected output
            port: The port
            protocol: The protocol
            response_code: The response code
            max_tests: The maximum number of tests
        Returns:
            True if the response inside the cluster was checked, False otherwise
        """
        ip_address = self.openshift_ops.get_service_ip(service_name=name_in_template)
        url = f"{protocol}://{ip_address}:{port}/"
        logger.info("URL address to get internal response is: %s", url)
        if not self.create_deploy_command_app():
            return False
        if cmd_to_run is None:
            cmd_to_run = "curl --connect-timeout 10 -k -s -w '%{http_code}' " + f"{url}"
        # Check if application returns proper HTTP_CODE
        logger.info("Check if HTTP_CODE is valid.")
        for _ in range(max_tests):
            output_code = self.command_app_run(cmd=f"{cmd_to_run}", return_output=True)
            return_code = output_code[-3:]
            try:
                int_ret_code = int(return_code)
                if int_ret_code == response_code:
                    logger.info("HTTP_CODE is VALID %s", int_ret_code)
                    break
            except ValueError:
                logger.info("%s", return_code)
                time.sleep(1)
                continue
            time.sleep(3)
            continue

        cmd_to_run = "curl --connect-timeout 10 -k -s " + f"{url}"
        # Check if application returns proper output
        for count in range(max_tests):
            output_code = self.command_app_run(cmd=f"{cmd_to_run}", return_output=True)
            logger.info(
                "Check if expected output %s is in %s.", expected_output, cmd_to_run
            )
            if expected_output in output_code:
                logger.info("Expected output '%s' is present.", expected_output)
                return True
            logger.info(
                "check_response_inside_cluster: expected_output %s not found in output of %s command. See %s",
                expected_output,
                cmd_to_run,
                output_code,
            )
            time.sleep(5)
        return False

    def check_response_outside_cluster(
        self,
        name_in_template: str = "",
        expected_output: str = "",
        port: int = None,
        protocol: str = "http",
        response_code: int = 200,
    ) -> bool:
        """
        Check the response outside the cluster.
        Args:
            name_in_template: The name of the template
            expected_output: The expected output
            port: The port
            protocol: The protocol
            response_code: The response code
        Returns:
            True if the response outside the cluster was checked, False otherwise
        """
        route_name = self.get_route_url(routes_name=name_in_template)
        logger.info("Route name is %s", route_name)
        url = f"{protocol}://{route_name}"
        for count in range(10):
            logger.info(
                "Let's try to get response from route %s one more time %s", url, count
            )
            response_status = utils.get_response_request(
                url_address=url,
                response_code=response_code,
                expected_str=expected_output,
            )
            if not response_status:
                time.sleep(5)
                continue
            break

        return response_status
