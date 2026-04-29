#!/bin/env python3

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
import subprocess
from pathlib import Path

import pytest
from flexmock import flexmock
from unittest.mock import patch

import container_ci_suite.engines.openshift as openshift_engine
from container_ci_suite.engines.openshift import OpenShiftOperations
from container_ci_suite.exceptions import (
    OpenShiftCommandFailed,
    OpenShiftGetPodStatusFailed,
)
from container_ci_suite.utils import ContainerTestLibUtils


class TestOpenShiftOpsSuite(object):
    def setup_method(self):
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    def test_check_is_version(self, oc_get_is_ruby_json):
        flexmock(OpenShiftOperations).should_receive("oc_get_is").and_return(
            oc_get_is_ruby_json
        )
        assert self.oc_ops.check_is_exists("ruby", "2.5-ubi8")
        assert not self.oc_ops.check_is_exists("ruby", "333-ubi9")

    # TODO variant with outputs
    def test_get_pod_count(self, oc_build_pod_finished_json):
        self.oc_ops.pod_json_data = oc_build_pod_finished_json
        self.oc_ops.pod_name_prefix = "python-311-testing"
        assert self.oc_ops.get_pod_count() == 1

    def test_is_pod_running(self, oc_is_pod_running):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_is_pod_running
        )
        flexmock(OpenShiftOperations).should_receive("get_pod_count").and_return(1)
        flexmock(OpenShiftOperations).should_receive("get_logs").and_return("something")
        assert self.oc_ops.is_pod_running(pod_name_prefix="python-311", loops=2)

    def test_build_pod_not_finished(self, oc_build_pod_not_finished_json):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_build_pod_not_finished_json
        )
        assert not self.oc_ops.is_build_pod_finished(cycle_count=2)

    def test_build_pod_finished(self, oc_build_pod_finished_json):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_build_pod_finished_json
        )
        assert self.oc_ops.is_build_pod_finished(cycle_count=2)

    def test_get_service_ip(self, get_svc_ip):
        flexmock(OpenShiftOperations).should_receive("oc_get_services").and_return(
            get_svc_ip
        )
        assert self.oc_ops.get_service_ip("python-testing") == "172.30.224.217"

    def test_get_service_ip_not_available(self, get_svc_ip_empty):
        flexmock(OpenShiftOperations).should_receive("oc_get_services").and_return(
            get_svc_ip_empty
        )
        assert self.oc_ops.get_service_ip("python-testing") is None

    def test_get_pod_status_success(self):
        output = json.dumps({"items": [{"metadata": {"name": "pod-1"}}]})
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get pods",
            json_output=True,
            namespace="container-ci-suite-test",
        ).and_return(output).once()

        assert self.oc_ops.get_pod_status() == {"items": [{"metadata": {"name": "pod-1"}}]}

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_get_pod_status_retries_on_openshift_error(self, mock_sleep):
        output = json.dumps({"items": [{"metadata": {"name": "pod-1"}}]})
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get pods",
            json_output=True,
            namespace="container-ci-suite-test",
        ).and_raise(OpenShiftCommandFailed("oc failed")).and_return(output).times(2)

        assert self.oc_ops.get_pod_status(cycle_count=2) == {
            "items": [{"metadata": {"name": "pod-1"}}]
        }
        mock_sleep.assert_called_once_with(3)

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_get_pod_status_raises_when_retry_count_exhausted(self, mock_sleep):
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get pods",
            json_output=True,
            namespace="container-ci-suite-test",
        ).and_raise(subprocess.CalledProcessError(1, "oc get pods")).times(2)

        with pytest.raises(OpenShiftGetPodStatusFailed):
            self.oc_ops.get_pod_status(cycle_count=2)
        assert mock_sleep.call_count == 2

    def test_print_get_status_success(self):
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get all",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_return("all resources").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "status --suggest",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_return("status output").once()

        self.oc_ops.print_get_status()

    def test_print_get_status_ignores_called_process_error_for_get_all(self):
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get all",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_raise(subprocess.CalledProcessError(1, "oc get all")).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "status --suggest",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_return("status output").once()

        self.oc_ops.print_get_status()

    def test_print_get_status_ignores_called_process_error_for_status(self):
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "get all",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_return("all resources").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "status --suggest",
            namespace="container-ci-suite-test",
            json_output=False,
            ignore_error=True,
        ).and_raise(subprocess.CalledProcessError(1, "oc status --suggest")).once()

        self.oc_ops.print_get_status()

class TestIsS2iPodRunning(object):
    """Tests for OpenShiftOperations.is_s2i_pod_running (engines/openshift.py)."""

    def setup_method(self):
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_s2i_pod_running_success_after_build(
        self, mock_sleep, oc_build_pod_finished_json
    ):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_build_pod_finished_json
        )
        flexmock(OpenShiftOperations).should_receive("is_pod_running").and_return(True)

        assert (
            self.oc_ops.is_s2i_pod_running(
                pod_name_prefix="python-311-testing", cycle_count=3
            )
            is True
        )

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_s2i_pod_running_false_when_build_never_finishes(self, mock_sleep):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            {"items": []}
        )

        assert (
            self.oc_ops.is_s2i_pod_running(pod_name_prefix="myapp", cycle_count=2)
            is False
        )

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_s2i_pod_running_false_when_no_build_pod_in_list(self, mock_sleep):
        pod_json = {
            "items": [
                {
                    "metadata": {"name": "other-1"},
                    "status": {"phase": "Running"},
                }
            ]
        }
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            pod_json
        )

        assert (
            self.oc_ops.is_s2i_pod_running(pod_name_prefix="myapp", cycle_count=2)
            is False
        )

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_s2i_pod_running_false_when_app_never_ready(
        self, mock_sleep, oc_build_pod_finished_json
    ):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_build_pod_finished_json
        )
        flexmock(OpenShiftOperations).should_receive("is_pod_running").and_return(False)
        flexmock(OpenShiftOperations).should_receive("print_get_status").once()
        flexmock(OpenShiftOperations).should_receive("print_pod_logs").once()

        assert (
            self.oc_ops.is_s2i_pod_running(
                pod_name_prefix="python-311-testing", cycle_count=2
            )
            is False
        )


class TestLoginToCluster(object):
    """Tests for OpenShiftOperations.login_to_cluster (engines/openshift.py)."""

    def setup_method(self):
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    def test_login_to_cluster_shared_cluster_success(self):
        flexmock(openshift_engine).should_receive("load_shared_credentials").with_args(
            "SHARED_CLUSTER_TOKEN"
        ).and_return("secret-token")
        flexmock(openshift_engine).should_receive("get_shared_variable").with_args(
            "shared_cluster_url"
        ).and_return("https://api.shared.example:6443")
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "login --token=secret-token --server=https://api.shared.example:6443",
            json_output=False,
        ).and_return("Logged in").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "version",
            json_output=False,
        ).and_return("Client Version: 4.14").once()

        assert self.oc_ops.login_to_cluster(shared_cluster=True) is None

    def test_login_to_cluster_shared_cluster_missing_credentials_returns_none(self):
        flexmock(openshift_engine).should_receive("load_shared_credentials").and_return(
            None
        )
        flexmock(openshift_engine).should_receive("get_shared_variable").and_return(None)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").never()

        assert self.oc_ops.login_to_cluster(shared_cluster=True) is None

    def test_login_to_cluster_shared_cluster_partial_credentials_returns_none(self):
        flexmock(openshift_engine).should_receive("load_shared_credentials").and_return(
            "only-token"
        )
        flexmock(openshift_engine).should_receive("get_shared_variable").with_args(
            "shared_cluster_url"
        ).and_return(None)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").never()

        assert self.oc_ops.login_to_cluster(shared_cluster=True) is None

    def test_login_to_cluster_local_cluster_success(self):
        flexmock(openshift_engine).should_receive("get_shared_variable").with_args(
            "local_cluster_url"
        ).and_return("https://api.local.test:6443")
        flexmock(openshift_engine).should_receive("get_file_content").with_args(
            filename=Path("/root/.kube/ocp-kube")
        ).and_return("local-pass\n")
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "login -u kubeadmin -p local-pass --server=https://api.local.test:6443",
            json_output=False,
        ).and_return("Logged in").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "version",
            json_output=False,
        ).and_return("Client Version: 4.14").once()

        assert self.oc_ops.login_to_cluster(shared_cluster=False) is None


class TestPrintPodLogs(object):
    """Tests for OpenShiftOperations.print_pod_logs (engines/openshift.py)."""

    def setup_method(self):
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    def test_print_pod_logs_fetches_logs_for_each_pod(self):
        pod_json = {
            "items": [
                {"metadata": {"name": "app-build-1"}},
                {"metadata": {"name": "myapp-1-abcde"}},
            ]
        }
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(pod_json)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "logs pod/app-build-1",
            json_output=False,
            ignore_error=True,
        ).and_return("build log").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "logs pod/myapp-1-abcde",
            json_output=False,
            ignore_error=True,
        ).and_return("app log").once()

        self.oc_ops.print_pod_logs()

    def test_print_pod_logs_no_pods(self):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            {"items": []}
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").never()

        self.oc_ops.print_pod_logs()


class TestIsPodRunningExtended(object):
    """Additional coverage for OpenShiftOperations.is_pod_running."""

    def setup_method(self):
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    def test_is_pod_running_requires_prefix(self):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            {"items": []}
        )

        assert self.oc_ops.is_pod_running(pod_name_prefix="", loops=1) is False

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_pod_running_exhaustion_calls_print_get_status_and_print_pod_logs(
        self, mock_sleep
    ):
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            {"items": []}
        )
        flexmock(OpenShiftOperations).should_receive("print_get_status").once()
        flexmock(OpenShiftOperations).should_receive("print_pod_logs").once()

        assert self.oc_ops.is_pod_running(pod_name_prefix="python-311", loops=1) is False

    @patch("container_ci_suite.engines.openshift.time.sleep")
    def test_is_pod_running_success_path(self, mock_sleep, oc_is_pod_running):
        self.oc_ops.pod_name_prefix = "python-311-testing"
        flexmock(OpenShiftOperations).should_receive("get_pod_status").and_return(
            oc_is_pod_running
        )
        flexmock(OpenShiftOperations).should_receive("get_pod_count").and_return(1)
        flexmock(OpenShiftOperations).should_receive("get_logs").and_return(
            "container started"
        )

        assert self.oc_ops.is_pod_running(pod_name_prefix="python-311", loops=2) is True
        assert mock_sleep.called
