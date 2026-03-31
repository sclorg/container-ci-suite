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
from container_ci_suite import utils


class TestDeployImagestreamS2i(object):
    """
    Tests for OpenShiftAPI.deploy_imagestream_s2i.
    """

    def test_deploy_imagestream_s2i_returns_false_when_project_not_created(self):
        """
        Short-circuits when project_created is False.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = False
        assert (
            oc_api.deploy_imagestream_s2i(
                "imagestreams/httpd.json",
                "quay.io/httpd",
                "https://github.com/sclorg/httpd-ex.git",
                ".",
                "httpd",
            )
            is False
        )

    def test_deploy_imagestream_s2i_returns_false_when_download_returns_empty(self):
        """
        Returns False when download_template yields a falsy path.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        flexmock(utils).should_receive("download_template").with_args(
            template_name="imagestreams/httpd.json"
        ).and_return("")

        assert (
            oc_api.deploy_imagestream_s2i(
                "imagestreams/httpd.json",
                "quay.io/httpd",
                "https://github.com/x.git",
                "src",
                "svc",
            )
            is False
        )

    def test_deploy_imagestream_s2i_strips_digits_before_download(self):
        """
        All digits are removed from imagestream_file before download_template.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        # "my2template3.json" -> "mytemplate.json"
        flexmock(utils).should_receive("download_template").with_args(
            template_name="mytemplate.json"
        ).and_return("/tmp/mytemplate.json")
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/tmp/mytemplate.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        flexmock(OpenShiftAPI).should_receive("deploy_s2i_app").with_args(
            image_name="img:1",
            app="https://github.com/app.git",
            context="sub",
            service_name="mysvc",
        ).and_return(True)

        assert (
            oc_api.deploy_imagestream_s2i(
                "my2template3.json",
                "img:1",
                "https://github.com/app.git",
                "sub",
                "mysvc",
            )
            is True
        )

    def test_deploy_imagestream_s2i_shared_cluster_updates_template(self):
        """
        On shared cluster, update_template_example_file runs on the downloaded path.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = True
        flexmock(utils).should_receive("download_template").with_args(
            template_name="imagestreams/httpd.json"
        ).and_return("/local/httpd.json")
        flexmock(OpenShiftAPI).should_receive("update_template_example_file").with_args(
            file_name="/local/httpd.json"
        ).and_return({}).once()
        flexmock(OpenShiftAPI).should_receive("import_is").with_args(
            "/local/httpd.json", name="", skip_check=True
        ).and_return({"kind": "List"})
        flexmock(OpenShiftAPI).should_receive("deploy_s2i_app").and_return(True)

        assert (
            oc_api.deploy_imagestream_s2i(
                "imagestreams/httpd.json",
                "quay.io/httpd",
                "https://github.com/sclorg/httpd-ex.git",
                ".",
                "httpd",
            )
            is True
        )

    def test_deploy_imagestream_s2i_returns_deploy_s2i_app_result(self):
        """
        Return value comes from deploy_s2i_app.
        """
        oc_api = OpenShiftAPI(namespace="ns-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("download_template").and_return("/t.json")
        flexmock(OpenShiftAPI).should_receive("import_is").and_return({"kind": "List"})
        flexmock(OpenShiftAPI).should_receive("deploy_s2i_app").and_return(False)

        assert (
            oc_api.deploy_imagestream_s2i(
                "is.json",
                "image",
                "app",
                "ctx",
                "name",
            )
            is False
        )
