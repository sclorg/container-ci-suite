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
from container_ci_suite.engines.openshift import OpenShiftOperations
from container_ci_suite.engines.container import PodmanCLIWrapper
from container_ci_suite import utils
from tests.spellbook import DATA_DIR


class TestOpenShiftCISuite(object):
    def setup_method(self):
        self.oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    @pytest.mark.parametrize(
        "container,dir_name,filename,branch",
        [
            ("postgresql-container", "imagestreams", "postgres-rhel.json", "master"),
            ("mysql-container", "openshift/templates", "foo.json", "bar"),
        ]
    )
    def test_get_raw_url_for_json(self, container, dir_name, filename, branch):
        expected_output = f"https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir_name}/{filename}"
        assert utils.get_raw_url_for_json(
            container=container, dir=dir_name, filename=filename, branch=branch
        ) == expected_output

    def test_upload_image_pull_failed(self):
        flexmock(PodmanCLIWrapper).should_receive("docker_pull_image").and_return(False)
        assert not self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_upload_image_login_failed(self):
        flexmock(PodmanCLIWrapper).should_receive("docker_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("docker_login_to_openshift").and_return(None)
        assert not self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_upload_image_success(self):
        flexmock(PodmanCLIWrapper).should_receive("docker_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("docker_login_to_openshift").and_return("default_registry")
        flexmock(utils).should_receive("run_command").twice()
        assert self.oc_api.upload_image(source_image="foobar", tagged_image="foobar:latest")

    def test_update_template_example_file_without_pvc(self, get_ephemeral_template):
        flexmock(utils).should_receive("get_json_data").and_return(get_ephemeral_template)
        json_data = self.oc_api.update_template_example_file(file_name=f"{DATA_DIR}/example_ephemeral_template.json")
        assert json_data
        assert "PersistentVolumeClaim" not in json_data["objects"][0]["kind"]

    def test_update_template_example_file_with_pvc(self, get_persistent_template):
        flexmock(utils).should_receive("get_json_data").and_return(get_persistent_template)
        flexmock(utils).should_receive("get_shared_variable").and_return("SOMETHING-001")
        json_data = self.oc_api.update_template_example_file(file_name=f"{DATA_DIR}/example_persistent_template.json")
        assert json_data
        assert json_data["objects"][0]["kind"] == "PersistentVolumeClaim"
        metadata = json_data["objects"][0]["metadata"]
        assert "annotations" in metadata
        assert "trident.netapp.io/reclaimPolicy" in metadata["annotations"]
        assert metadata["annotations"]["trident.netapp.io/reclaimPolicy"] == "Delete"
        assert "labels" in metadata
        assert "paas.redhat.com/appcode" in metadata["labels"]
        assert metadata["labels"]["paas.redhat.com/appcode"] == "SOMETHING-001"
        assert json_data["objects"][0]["spec"]["storageClassName"] == "netapp-nfs"
        assert json_data["objects"][0]["spec"]["volumeMode"] == "Filesystem"
