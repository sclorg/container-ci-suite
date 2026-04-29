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

from pathlib import Path
from subprocess import CalledProcessError
from typing import Dict, Any

from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite.utils import (
    get_file_content,
    load_shared_credentials,
    get_shared_variable,
)
from container_ci_suite.exceptions import (
    OpenShiftGetPodStatusFailed,
    OpenShiftCommandFailed,
)


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenShiftOperations:
    """
    OpenShift Operations - Utility functions for OpenShift operations.
    """

    namespace: str = ""
    pod_json_data: Dict = {}

    def __init__(self, pod_name_prefix: str = ""):
        """
        Initialize the OpenShift Operations.
        Args:
            pod_name_prefix: The prefix for the pod name
        """
        self.pod_name_prefix = pod_name_prefix
        self.build_failed: bool = False

    def set_namespace(self, namespace: str):
        """
        Set the namespace.
        Args:
            namespace: The namespace to set
        """
        self.namespace = namespace

    def login_to_cluster(self, shared_cluster: bool = False):
        """
        Login to the cluster.
        Args:
            shared_cluster: Whether to use a shared cluster
        """
        if shared_cluster:
            token = load_shared_credentials("SHARED_CLUSTER_TOKEN")
            url = get_shared_variable("shared_cluster_url")
            if not all([token, url]):
                print(
                    "Important variables 'SHARED_CLUSTER_TOKEN,shared_cluster_url' are missing."
                )
                return None
            cmd = f"login --token={token} --server={url}"
        else:
            url = get_shared_variable("local_cluster_url")
            password = get_file_content(filename=Path("/root/.kube/ocp-kube")).strip()
            cmd = f"login -u kubeadmin -p {password} --server={url}"
        output = ContainerTestLibUtils.run_oc_command(cmd, json_output=False)
        logger.info("Output from 'oc login': %s", output)
        output = ContainerTestLibUtils.run_oc_command("version", json_output=False)
        logger.info("Output from 'oc version': %s", output)

    def get_pod_status(self, cycle_count: int = 10) -> Dict:
        """
        Get the pod status.
        Returns:
            The pod status
        """
        # output = OpenShiftAPI.run_oc_command("get all", json_output=False)
        # print(f"oc get all: {output}")
        for _ in range(cycle_count):
            try:
                output = ContainerTestLibUtils.run_oc_command(
                    "get pods", json_output=True, namespace=self.namespace
                )
                if output:
                    return json.loads(output)
            except (CalledProcessError, OpenShiftCommandFailed):
                pass
            time.sleep(3)
        raise OpenShiftGetPodStatusFailed("Failed to get pod status")

    def print_get_status(self):
        """
        Print the get all and status.
        """
        logger.info("Print get all and status:")
        try:
            logger.info(
                ContainerTestLibUtils.run_oc_command(
                    "get all",
                    namespace=self.namespace,
                    json_output=False,
                    ignore_error=True,
                )
            )
        except CalledProcessError:
            pass
        try:
            logger.info(
                ContainerTestLibUtils.run_oc_command(
                    "status --suggest",
                    namespace=self.namespace,
                    json_output=False,
                    ignore_error=True,
                )
            )
        except CalledProcessError:
            pass

    def print_pod_logs(self):
        """
        Print the pod logs.
        """
        self.pod_json_data = self.get_pod_status()
        logger.info("Print all pod logs")
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            logger.info("Logs from pod name %s:", pod_name)
            oc_logs = ContainerTestLibUtils.run_oc_command(
                f"logs pod/{pod_name}", json_output=False, ignore_error=True
            )
            logger.info("Output from 'oc logs': %s", oc_logs)

    def is_project_exists(self) -> bool:
        """
        Check if the project exists.
        Returns:
            True if the project exists, False otherwise
        """
        output = ContainerTestLibUtils.run_oc_command("projects", json_output=False)
        if self.namespace in output:
            return True
        return False

    def get_pod_count(self) -> int:
        """
        Get the pod count.
        Returns:
            The pod count
        """
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

    def get_logs(self, pod_name) -> str:
        """
        Get the logs for a pod.
        Args:
            pod_name: The name of the pod
        Returns:
            The logs for the pod
        """
        return ContainerTestLibUtils.run_oc_command(
            f"logs {pod_name}", namespace=self.namespace, json_output=False
        )

    def is_pod_running(self, pod_name_prefix: str = "", loops: int = 180) -> bool:
        """
        Check if the pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
            loops: The number of loops to check
        Returns:
            True if the pod is running, False otherwise
        """
        logger.info("Check for POD is running %s", pod_name_prefix)
        for _ in range(loops):
            self.pod_json_data = self.get_pod_status()
            if pod_name_prefix == "" and self.pod_name_prefix == "":
                logger.info(
                    "\nApplication pod name is not specified."
                    'Call: is_pod_running(pod_name_prefix="something").'
                )
                return False
            if pod_name_prefix != "":
                self.pod_name_prefix = pod_name_prefix
            # Only one running pod is allowed
            if self.get_pod_count() != 1:
                time.sleep(1)
                continue

            for item in self.pod_json_data["items"]:
                pod_name = item["metadata"]["name"]
                if self.pod_name_prefix not in pod_name:
                    continue
                status = item["status"]["phase"]
                if "deploy" in pod_name:
                    continue
                if status == "Running":
                    logger.info("\nPod with name %s is running %s.", pod_name, status)
                    output = self.get_logs(pod_name=pod_name)
                    logger.info("Output from 'oc logs': %s", output)
                    # Wait couple seconds for sure
                    time.sleep(3)
                    return True
                logger.debug("Pod %s is not running. Status: %s", pod_name, status)
                output = self.get_logs(pod_name=pod_name)
                logger.debug("Output from 'oc logs': %s", output)
                time.sleep(3)
            time.sleep(3)
        logger.info("is_pod_running failed. See logs for debugging.")
        self.print_get_status()
        self.print_pod_logs()
        return False

    def is_build_pod_present(self) -> bool:
        """
        Check if the build pod is present.
        Returns:
            True if the build pod is present, False otherwise
        """
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            if "build" in pod_name:
                return True
        return False

    def is_pod_finished(self, pod_suffix_name: str = "deploy") -> bool:
        """
        Check if the pod is finished.
        Args:
            pod_suffix_name: The suffix for the pod name
        Returns:
            True if the pod is finished, False otherwise
        """
        if not self.pod_json_data:
            self.pod_json_data = self.get_pod_status()
        for item in self.pod_json_data["items"]:
            pod_name = item["metadata"]["name"]
            if self.pod_name_prefix not in pod_name:
                continue
            status = item["status"]["phase"]
            if pod_suffix_name in pod_name and status == "Failed":
                logger.info(
                    "\nPod with %s finished with %s. See logs.", pod_suffix_name, status
                )
                self.build_failed = True
                self.print_pod_logs()
                self.print_get_status()
                return False
            if pod_suffix_name in pod_name and status != "Succeeded":
                continue
            if pod_suffix_name in pod_name and status == "Succeeded":
                logger.info("\nPod with suffix %s is finished", pod_suffix_name)
                return True
        return False

    def is_build_pod_finished(self, cycle_count: int = 180) -> bool:
        """
        Function return information if build pod is finished.
        The function waits for 180*3 seconds
        Returns:
            True if the build pod is finished, False otherwise
        """
        logger.info("Check if build pod is finished")
        for _ in range(cycle_count):
            try:
                self.pod_json_data = self.get_pod_status()
            except OpenShiftGetPodStatusFailed:
                time.sleep(1)
                continue
            if len(self.pod_json_data["items"]) == 0:
                time.sleep(1)
                continue
            if not self.is_build_pod_present():
                time.sleep(1)
                continue
            if not self.is_pod_finished(pod_suffix_name="build"):
                if self.build_failed:
                    return False
                time.sleep(3)
                continue
            logger.info("\nBuild pod is finished")
            return True
        return False

    def is_s2i_pod_running(
        self, pod_name_prefix: str = "", cycle_count: int = 180
    ) -> bool:
        """
        Check if the S2I build pod is running.
        Args:
            pod_name_prefix: The prefix for the pod name
            cycle_count: The number of loops to check
        Returns:
            True if the S2I build pod is running, False otherwise
        """
        self.pod_name_prefix = pod_name_prefix
        build_pod_finished = False
        logger.info("Check if S2I build pod is running")
        for _ in range(cycle_count):
            self.pod_json_data = self.get_pod_status()
            if len(self.pod_json_data["items"]) == 0:
                time.sleep(1)
                continue
            if not self.is_build_pod_present():
                time.sleep(1)
                continue
            if not self.is_pod_finished(pod_suffix_name="build"):
                time.sleep(3)
                continue
            build_pod_finished = True
            logger.info("\nBuild pod with name %s is finished.", pod_name_prefix)
            break
        if not build_pod_finished:
            logger.info("\nBuild pod with name %s was not finished.", pod_name_prefix)
            return False
        logger.info("Check if S2I pod is running.")
        for _ in range(cycle_count):
            if not self.is_pod_running():
                time.sleep(3)
                continue
            logger.info("\nPod is running")
            return True
        logger.info("is_s2i_pod_running failed. See logs for debugging.")
        self.print_get_status()
        self.print_pod_logs()
        return False

    def oc_get_services(self, service_name):
        """
        Get the services.
        Args:
            service_name: The name of the service
        Returns:
            The services
        """
        output = ContainerTestLibUtils.run_oc_command(
            f"get svc/{service_name}", json_output=True, namespace=self.namespace
        )
        json_output = json.loads(output)
        logger.info("Output from 'oc get services': %s", json_output)
        return json_output

    def get_service_ip(self, service_name) -> Any:
        """
        Get the service IP.
        Args:
            service_name: The name of the service
        Returns:
            The service IP
        """
        json_output = self.oc_get_services(service_name=service_name)
        if "clusterIP" not in json_output["spec"]:
            return None
        if not json_output["spec"]["clusterIP"]:
            return None
        return json_output["spec"]["clusterIP"]

    def is_imagestream_exist(self, name: str):
        """
        Check if the image stream exists.
        Args:
            name: The name of the image stream
        Returns:
            True if the image stream exists, False otherwise
        """
        try:
            for _ in range(3):
                json_output = self.oc_get_is(name=name)
                if (
                    json_output["kind"] == "ImageStream"
                    and json_output["metadata"]["name"] == name
                ):
                    return json_output
                time.sleep(1)
        except CalledProcessError:
            pass
        return None

    def get_routes(self):
        """
        Get the routes.
        Returns:
            The routes
        """
        output = ContainerTestLibUtils.run_oc_command(
            "get route",
            namespace=self.namespace,
            return_output=True,
            ignore_error=True,
            shell=True,
        )
        return json.loads(output)

    def oc_gel_all_is(self):
        """
        Get all the image streams.
        Returns:
            The image streams
        """
        output = ContainerTestLibUtils.run_oc_command(
            "get is", namespace=self.namespace
        )
        return json.loads(output)

    def oc_get_is(self, name: str):
        """
        Get the image stream.
        Args:
            name: The name of the image stream
        Returns:
            The image stream
        """
        output = ContainerTestLibUtils.run_oc_command(
            f"get is/{name}", namespace=self.namespace
        )
        return json.loads(output)

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

    def is_pod_ready(self, cycle_count: int = 180) -> bool:
        """
        Function checks if pod with specific name is really ready
        """
        logger.info("Check if pod is ready.")
        for _ in range(cycle_count):
            json_data = self.get_pod_status()
            if len(json_data["items"]) == 0:
                time.sleep(1)
                continue
            if not self.is_pod_finished(pod_suffix_name=self.pod_name_prefix):
                time.sleep(1)
                continue
            for item in json_data["items"]:
                pod_name = item["metadata"]["name"]
                status = item["status"]["phase"]
                if "deploy" in pod_name:
                    continue
                if item["status"]["phase"] == "Running":
                    logger.info("\nPod with name %s is running %s.", pod_name, status)
                    output = ContainerTestLibUtils.run_oc_command(
                        f"logs {pod_name}", namespace=self.namespace, json_output=False
                    )
                    logger.info("Output from 'oc logs': %s", output)
                    # Wait couple seconds for sure
                    time.sleep(5)
                    return True
                time.sleep(1)
        return False
