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

from flexmock import flexmock

from container_ci_suite.openshift import OpenShiftAPI


class TestDeployTemplateWithImage(object):
    """
    Tests for OpenShiftAPI.deploy_template_with_image.
    """

    def test_deploy_template_with_image_returns_false_when_project_not_created(self):
        """
        Short-circuits when project_created is False.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = False
        assert (
            oc_api.deploy_template_with_image(
                "quay.io/foo",
                "templates/app.json",
                name_in_template="app",
            )
            is False
        )

    def test_deploy_template_with_image_returns_false_when_upload_image_fails(self):
        """
        Non-shared cluster: upload_image failure returns False before deploy_template.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        oc_api.version = "14"
        flexmock(OpenShiftAPI).should_receive("upload_image").with_args(
            source_image="quay.io/foo",
            tagged_image="app:14",
        ).and_return(False)
        flexmock(OpenShiftAPI).should_receive("deploy_template").never()

        assert (
            oc_api.deploy_template_with_image(
                "quay.io/foo",
                "templates/app.json",
                name_in_template="app",
            )
            is False
        )

    def test_deploy_template_with_image_returns_false_when_upload_external_fails(self):
        """
        Shared cluster: upload_image_to_external_registry failure returns False.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = True
        oc_api.version = ""
        flexmock(OpenShiftAPI).should_receive("upload_image_to_external_registry").with_args(
            source_image="registry.io/img:latest",
            tagged_image="svc:",
        ).and_return(False)
        flexmock(OpenShiftAPI).should_receive("upload_image").never()
        flexmock(OpenShiftAPI).should_receive("deploy_template").never()

        assert (
            oc_api.deploy_template_with_image(
                "registry.io/img:latest",
                "templates/t.json",
                name_in_template="svc",
            )
            is False
        )

    def test_deploy_template_with_image_non_shared_calls_deploy_template(self):
        """
        After a successful upload_image, delegates to deploy_template with expected_output=''.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        oc_api.version = "1"
        flexmock(OpenShiftAPI).should_receive("upload_image").with_args(
            source_image="img",
            tagged_image="name:1",
        ).and_return(True)
        flexmock(OpenShiftAPI).should_receive("deploy_template").with_args(
            template="tpl.json",
            name_in_template="name",
            openshift_args=["MEMORY=512Mi"],
            expected_output="",
        ).and_return(True)

        assert (
            oc_api.deploy_template_with_image(
                "img",
                "tpl.json",
                name_in_template="name",
                openshift_args=["MEMORY=512Mi"],
            )
            is True
        )

    def test_deploy_template_with_image_shared_cluster_calls_external_upload(self):
        """
        Shared cluster uses upload_image_to_external_registry with the same tagged name.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = True
        oc_api.version = "v2"
        flexmock(OpenShiftAPI).should_receive("upload_image_to_external_registry").with_args(
            source_image="src-img",
            tagged_image="appname:v2",
        ).and_return(True)
        flexmock(OpenShiftAPI).should_receive("upload_image").never()
        flexmock(OpenShiftAPI).should_receive("deploy_template").with_args(
            template="t.json",
            name_in_template="appname",
            openshift_args=None,
            expected_output="",
        ).and_return(True)

        assert (
            oc_api.deploy_template_with_image("src-img", "t.json", name_in_template="appname")
            is True
        )

    def test_deploy_template_with_image_returns_deploy_template_result(self):
        """
        Return value is whatever deploy_template returns.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("deploy_template").and_return(False)

        assert (
            oc_api.deploy_template_with_image("img", "tpl.json", name_in_template="n")
            is False
        )
