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

import subprocess

from flexmock import flexmock
from unittest.mock import patch

from container_ci_suite.openshift import OpenShiftAPI
from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite import utils


class TestDeployImageStreamTemplate(object):
    """
    Tests for OpenShiftAPI.deploy_image_stream_template.
    """

    def test_deploy_image_stream_template_returns_false_when_project_not_created(self):
        """
        Short-circuits when project_created is False.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = False
        assert (
            oc_api.deploy_image_stream_template("is.json", "tpl.json", "app") is False
        )

    def test_deploy_image_stream_template_returns_false_when_import_is_fails(self):
        """
        Returns False when import_is yields a falsy JSON payload.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("download_template").with_args(
            template_name="is.json"
        ).and_return("/tmp/is.json")
        flexmock(utils).should_receive("download_template").with_args(
            template_name="tpl.json"
        ).and_return("/tmp/tpl.json")
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/is.json", name="", skip_check=True
        ).and_return({})

        assert (
            oc_api.deploy_image_stream_template("is.json", "tpl.json", "app") is False
        )

    @patch("container_ci_suite.openshift.time.sleep")
    def test_deploy_image_stream_template_returns_false_when_new_app_raises(
        self, mock_sleep
    ):
        """
        CalledProcessError from oc new-app returns False (after successful import_is).
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("download_template").with_args(
            template_name="is.json"
        ).and_return("/tmp/is.json")
        flexmock(utils).should_receive("download_template").with_args(
            template_name="tpl.json"
        ).and_return("/tmp/tpl.json")
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/is.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").and_raise(
            subprocess.CalledProcessError(1, "oc", output=b"fail")
        )

        assert (
            oc_api.deploy_image_stream_template("is.json", "tpl.json", "myapp")
            is False
        )
        mock_sleep.assert_not_called()

    @patch("container_ci_suite.openshift.time.sleep")
    def test_deploy_image_stream_template_success_without_openshift_args(
        self, mock_sleep
    ):
        """
        Downloads templates, imports IS, runs new-app with NAMESPACE, then sleeps 3s.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("download_template").with_args(
            template_name="imagestreams/httpd.json"
        ).and_return("/tmp/httpd-is.json")
        flexmock(utils).should_receive("download_template").with_args(
            template_name="templates/httpd.json"
        ).and_return("/tmp/httpd-tpl.json")
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/httpd-is.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        expected_cmd = (
            "new-app -f /tmp/httpd-tpl.json --name=httpd-app "
            "-p NAMESPACE=ns-test "
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            expected_cmd,
            json_output=False,
        ).and_return("created").once()

        assert (
            oc_api.deploy_image_stream_template(
                "imagestreams/httpd.json",
                "templates/httpd.json",
                "httpd-app",
            )
            is True
        )
        mock_sleep.assert_called_once_with(3)

    @patch("container_ci_suite.openshift.time.sleep")
    def test_deploy_image_stream_template_success_with_openshift_args(self, mock_sleep):
        """
        Passes openshift_args through get_openshift_args into the new-app command.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("download_template").with_args(
            template_name="is.json"
        ).and_return("/tmp/is.json")
        flexmock(utils).should_receive("download_template").with_args(
            template_name="tpl.json"
        ).and_return("/tmp/tpl.json")
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/is.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        # get_openshift_args joins with " -p "; outer f-string adds leading "-p "
        expected_cmd = (
            "new-app -f /tmp/tpl.json --name=app1 -p NAMESPACE=ns-test "
            "-p MEMORY_LIMIT=512Mi -p FOO=bar"
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            expected_cmd,
            json_output=False,
        ).and_return("created").once()

        assert (
            oc_api.deploy_image_stream_template(
                "is.json",
                "tpl.json",
                "app1",
                openshift_args=["MEMORY_LIMIT=512Mi", "FOO=bar"],
            )
            is True
        )
        mock_sleep.assert_called_once_with(3)

    @patch("container_ci_suite.openshift.time.sleep")
    def test_deploy_image_stream_template_shared_cluster_updates_template(
        self, mock_sleep
    ):
        """
        On shared cluster, update_template_example_file runs on the local template path.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = True
        flexmock(utils).should_receive("download_template").with_args(
            template_name="is.json"
        ).and_return("/tmp/is.json")
        flexmock(utils).should_receive("download_template").with_args(
            template_name="tpl.json"
        ).and_return("/tmp/tpl.json")
        flexmock(OpenShiftAPI).should_receive("update_template_example_file").with_args(
            file_name="/tmp/tpl.json"
        ).and_return({}).once()
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/is.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "new-app -f /tmp/tpl.json --name=app2 -p NAMESPACE=ns-test ",
            json_output=False,
        ).and_return("ok").once()

        assert (
            oc_api.deploy_image_stream_template("is.json", "tpl.json", "app2") is True
        )
        mock_sleep.assert_called_once_with(3)
