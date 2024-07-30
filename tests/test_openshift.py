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
from container_ci_suite.openshift_ops import OpenShiftOperations
from container_ci_suite.container import DockerCLIWrapper
from container_ci_suite import utils


class TestOpenShiftCISuite(object):
    def setup_method(self):
        self.oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    @pytest.mark.parametrize(
        "container,dir,filename,branch",
        [
            ("postgresql-container", "imagestreams", "postgres-rhel.json", "master"),
            ("mysql-container", "openshift/templates", "foo.json", "bar"),
        ]
    )
    def test_get_raw_url_for_json(self, container, dir, filename, branch):
        expected_output = f"https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir}/{filename}"
        assert utils.get_raw_url_for_json(
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
        flexmock(OpenShiftAPI).should_receive("docker_login_to_openshift").and_return("default_registry")
        flexmock(utils).should_receive("run_command").twice()
        assert self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")
