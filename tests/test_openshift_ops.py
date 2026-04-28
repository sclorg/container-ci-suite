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

import pytest
from flexmock import flexmock
from unittest.mock import patch

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

    def test_is_s2i_pod_running(self):
        # self.oc_api.is_s2i_pod_running()
        pass
