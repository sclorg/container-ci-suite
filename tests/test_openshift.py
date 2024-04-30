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

import pytest

from flexmock import flexmock

from container_ci_suite.openshift import OpenShiftAPI
from container_ci_suite.container import DockerCLIWrapper
from container_ci_suite import utils


class TestOpenShiftCISuite(object):
    def setup_method(self):
        self.oc_api = OpenShiftAPI(namespace="container-ci-suite-test")

    def test_check_is_version(self, oc_get_is_ruby_json):
        flexmock(OpenShiftAPI).should_receive("oc_get_is").and_return(oc_get_is_ruby_json)
        assert self.oc_api.check_is_exists("ruby", "2.5-ubi8")
        assert not self.oc_api.check_is_exists("ruby", "333-ubi9")

    # TODO variant with outputs
    def test_get_pod_count(self, oc_build_pod_finished_json):
        self.oc_api.pod_json_data = oc_build_pod_finished_json
        self.oc_api.pod_name_prefix = "python-311-testing"
        assert self.oc_api.get_pod_count() == 1

    def test_is_pod_running(self, oc_is_pod_running):
        flexmock(OpenShiftAPI).should_receive("get_pod_status").and_return(oc_is_pod_running)
        flexmock(OpenShiftAPI).should_receive("run_oc_command").once()
        assert self.oc_api.is_pod_running(pod_name_prefix="python-311", loops=1)

    def test_build_pod_not_finished(self, oc_build_pod_not_finished_json):
        flexmock(OpenShiftAPI).should_receive("get_pod_status").and_return(oc_build_pod_not_finished_json)
        assert not self.oc_api.is_build_pod_finished(cycle_count=2)

    def test_build_pod_finished(self, oc_build_pod_finished_json):
        flexmock(OpenShiftAPI).should_receive("get_pod_status").and_return(oc_build_pod_finished_json)
        assert self.oc_api.is_build_pod_finished(cycle_count=2)

    def test_is_s2i_pod_running(self):
        # self.oc_api.is_s2i_pod_running()
        pass

    @pytest.mark.parametrize(
        "container,dir,filename,branch",
        [
            ("postgresql-container", "imagestreams", "postgres-rhel.json", "master"),
            ("mysql-container", "openshift/templates", "foo.json", "bar"),
        ]
    )
    def test_get_raw_url_for_json(self, container, dir, filename, branch):
        expected_output = f"https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir}/{filename}"
        assert self.oc_api.get_raw_url_for_json(
            container=container, dir=dir, filename=filename, branch=branch
        ) == expected_output

    def test_upload_image_pull_failed(self):
        flexmock(DockerCLIWrapper).should_receive("docker_pull_image").and_return(False)
        assert not self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_upload_image_login_failed(self):
        flexmock(DockerCLIWrapper).should_receive("docker_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("docker_login_to_openshift").and_return(None)
        assert not self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_upload_image_success(self):
        flexmock(DockerCLIWrapper).should_receive("docker_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("docker_login_to_openshift").and_return("defualt_registry")
        flexmock(utils).should_receive("run_command").twice()
        assert self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_get_pod_status(self):
        # self.oc_api.get_pod_status()
        pass

    def test_get_service_ip(self, get_svc_ip):
        flexmock(OpenShiftAPI).should_receive("oc_get_services").and_return(get_svc_ip)
        assert self.oc_api.get_service_ip("python-testing") == "172.30.224.217"

    def test_get_service_ip_not_available(self, get_svc_ip_empty):
        flexmock(OpenShiftAPI).should_receive("oc_get_services").and_return(get_svc_ip_empty)
        assert self.oc_api.get_service_ip("python-testing") is None
