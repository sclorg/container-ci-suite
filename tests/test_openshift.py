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


class TestOpenShiftCISuite(object):
    def setup_method(self):
        self.oc_api = OpenShiftAPI()

    def test_check_is_version(self, oc_get_is_ruby_json):
        flexmock(OpenShiftAPI).should_receive("oc_get_is").and_return(oc_get_is_ruby_json)
        assert self.oc_api.check_is_exists("ruby", "2.5-ubi8")
        assert not self.oc_api.check_is_exists("ruby", "333-ubi9")

    # TODO variant with outputs
    def test_get_pod_count(self):
        # self.oc_api.get_pod_count()
        pass

    def test_is_pod_running(self):
        # self.oc_api.is_pod_running()
        pass

    def test_is_build_pod_finished(self):
        # self.oc_api.is_build_pod_finished()
        pass

    def test_is_s2i_pod_running(self):
        # self.oc_api.is_s2i_pod_running()
        pass

    # Parametrized
    def test_get_raw_url_for_json(self):
        # self.oc_api.get_raw_url_for_json()
        pass

    def test_get_pod_status(self):
        # self.oc_api.get_pod_status()
        pass

    def test_is_pod_finished(self):
        # self.oc_api.is_pod_finished()
        pass

    def test_get_service_ip(self):
        # self.oc_api.get_service_ip()
        pass
