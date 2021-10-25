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

from container_ci_suite.utils import (
    get_public_image_name,
    get_npm_variables,
    get_mount_ca_file,
    get_mount_options_from_s2i_args,
    get_env_commands_from_s2i_args,
)
from tests.conftest import create_ca_file, delete_ca_file


class TestContainerCISuiteUtils(object):
    @pytest.mark.parametrize(
        "os,base_image_name,version,expected_str",
        [
            ("rhel7", "nodejs", "12", "registry.redhat.io/rhscl/nodejs-12-rhel7"),
            ("rhel8", "nodejs", "14", "registry.redhat.io/rhel8/nodejs-14"),
            ("centos7", "nodejs", "10", "docker.io/centos/nodejs-10-centos7"),
        ],
    )
    def test_get_public_image_name(self, os, base_image_name, version, expected_str):
        name = get_public_image_name(
            os=os, base_image_name=base_image_name, version=version
        )
        assert name == expected_str

    def test_get_npm_variables_no_ca_file(self):
        assert get_npm_variables() == ""

    def test_get_mount_ca_file_no_ca_file(self):
        assert get_mount_ca_file() == ""

    def test_get_npm_variables(self):
        create_ca_file()
        assert get_npm_variables() == f"-e NPM_MIRROR=foobar {get_mount_ca_file()}"
        delete_ca_file()

    def test_get_mount_ca_file(self):
        create_ca_file()
        assert get_mount_ca_file() == f"{get_mount_ca_file()}"
        delete_ca_file()

    @pytest.mark.parametrize(
        "s2i_args,expected_output",
        [
            ("--pull-never", ""),
            (
                "--pull-never -v /some/foo/bar/file:/some/foo/bar/file:Z",
                "-v /some/foo/bar/file:/some/foo/bar/file:Z",
            ),
        ],
    )
    def test_mount_point(self, s2i_args, expected_output):
        create_ca_file()
        ret_value = get_mount_options_from_s2i_args(s2i_args=s2i_args)
        assert ret_value == expected_output
        delete_ca_file()

    @pytest.mark.parametrize(
        "s2i_args,expected_output",
        [
            ("--pull-never", []),
            ("--pull-never -e NODE=development", ["ENV NODE=development"]),
            (
                "-v mount_point:mount_point:Z -e FOO=bar --env TEST=deployment",
                ["ENV FOO=bar", "ENV TEST=deployment"],
            ),
            ("-v mount_point:mount_point:Z -e FOO=bar --env TEST", ["ENV FOO=bar"]),
        ],
    )
    def test_get_env_from_s2i_args(self, s2i_args, expected_output):
        assert get_env_commands_from_s2i_args(s2i_args=s2i_args) == expected_output
