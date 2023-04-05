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

from tempfile import mkdtemp
from pathlib import Path

from container_ci_suite.api import ContainerCISuite
from container_ci_suite.container import DockerCLIWrapper

from tests.conftest import s2i_build_as_df_fedora_test_app
from tests.spellbook import DATA_DIR


class TestContainerCISuiteAPI(object):
    @pytest.mark.parametrize(
        "app_path,s2i_args,src_image,dest_image,df",
        [
            (
                f"file://{DATA_DIR}/test-app",
                "--pull-policy=never -e NODE_ENV=development",
                "quay.io/fedora/nodejs-16",
                "quay.io/fedora/nodejs-16-testapp",
                s2i_build_as_df_fedora_test_app(),
            )
        ],
    )
    def test_s2i_build_from_df(self, app_path, s2i_args, src_image, dest_image, df):
        ccs = ContainerCISuite(image_name=src_image)
        flexmock(DockerCLIWrapper).should_receive("docker_image_exists").with_args(
            src_image
        ).and_return(True)
        flexmock(DockerCLIWrapper).should_receive("docker_inspect").and_return(1001)
        flexmock(DockerCLIWrapper).should_receive("docker_get_user_id").and_return(1001)
        tmp_dir = Path(mkdtemp())
        generated_df = ccs.s2i_create_df(
            tmp_dir=tmp_dir,
            app_path=app_path,
            s2i_args=s2i_args,
            src_image=src_image,
            dst_image=dest_image,
        )
        assert generated_df == df

    def test_check_envs_set(self):
        run_envs = """MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
APP_ROOT=/opt/app-root
NODEJS_SCL=rh-nodejs14
X_SCLS=rh-nodejs14 rh-ruby26
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-ruby26/root/usr/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STI_SCRIPTS_URL=image:///usr/libexec/s2i
PWD=/opt/app-root/src
STI_SCRIPTS_PATH=/usr/libexec/s2i
IMAGE_NAME=rhscl/ruby-26-rhel7
HOME=/opt/app-root/src
RUBY_SCL=rh-ruby26
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
RUBY_VERSION=2.6"""
        exec_envs = """PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-ruby26/root/usr/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
SUMMARY=Platform for building and running Ruby 2.6 applications
STI_SCRIPTS_URL=image:///usr/libexec/s2i
STI_SCRIPTS_PATH=/usr/libexec/s2i
APP_ROOT=/opt/app-root
HOME=/opt/app-root/src
BASH_ENV=/opt/app-root/etc/scl_enable
ENV=/opt/app-root/etc/scl_enable
PROMPT_COMMAND=. /opt/app-root/etc/scl_enable
NODEJS_SCL=rh-nodejs14
RUBY_SCL=rh-ruby26
IMAGE_NAME=rhscl/ruby-26-rhel7
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
X_SCLS=rh-nodejs14 rh-ruby26
MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
"""
        ccs = ContainerCISuite(image_name="quay.io/fedora/nodejs-16")
        ccs.test_check_envs_set(env_filter="^X_SCLS=|/opt/rh|/opt/app-root", check_envs=exec_envs, loop_envs=run_envs)

    def test_check_envs_set_home_not_in_docker_exec(self):
        run_envs = """MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
APP_ROOT=/opt/app-root
X_SCLS=rh-nodejs14 rh-ruby26
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-ruby26/root/usr/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STI_SCRIPTS_URL=image:///usr/libexec/s2i
STI_SCRIPTS_PATH=/usr/libexec/s2i
HOME=/opt/app-root/src
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
RUBY_VERSION=2.6"""
        exec_envs = """PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-ruby26/root/usr/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STI_SCRIPTS_URL=image:///usr/libexec/s2i
STI_SCRIPTS_PATH=/usr/libexec/s2i
APP_ROOT=/opt/app-root
BASH_ENV=/opt/app-root/etc/scl_enable
ENV=/opt/app-root/etc/scl_enable
PROMPT_COMMAND=. /opt/app-root/etc/scl_enable
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
X_SCLS=rh-nodejs14 rh-ruby26
MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
"""
        ccs = ContainerCISuite(image_name="quay.io/fedora/nodejs-16")
        ret = ccs.test_check_envs_set(
            env_filter="^X_SCLS=|/opt/rh|/opt/app-root",
            check_envs=exec_envs,
            loop_envs=run_envs
        )
        assert not ret

    def test_check_envs_set_not_in_run_envs_not_path(self):
        run_envs = """MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
APP_ROOT=/opt/app-root
X_SCLS=rh-nodejs14 rh-ruby26
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-ruby26/root/usr/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STI_SCRIPTS_URL=image:///usr/libexec/s2i
STI_SCRIPTS_PATH=/usr/libexec/s2i
HOME=/opt/app-root/src
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
RUBY_VERSION=2.6"""
        exec_envs = """PATH=/opt/rh/rh-ruby26/root/usr/local/bin:/opt/rh/rh-nodejs14/root/usr/bin:/opt/app-root/src/bin:/opt/app-root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STI_SCRIPTS_URL=image:///usr/libexec/s2i
STI_SCRIPTS_PATH=/usr/libexec/s2i
APP_ROOT=/opt/app-root
BASH_ENV=/opt/app-root/etc/scl_enable
ENV=/opt/app-root/etc/scl_enable
PROMPT_COMMAND=. /opt/app-root/etc/scl_enable
LD_LIBRARY_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64:/opt/rh/rh-ruby26/root/usr/lib64:/opt/rh/rh-nodejs14/root/usr/lib64
X_SCLS=rh-nodejs14 rh-ruby26
HOME=/opt/app-root/src
MANPATH=/opt/rh/rh-ruby26/root/usr/local/share/man:/opt/rh/rh-ruby26/root/usr/share/man:/opt/rh/rh-nodejs14/root/usr/share/man:
XDG_DATA_DIRS=/opt/rh/rh-ruby26/root/usr/local/share:/opt/rh/rh-ruby26/root/usr/share:/usr/local/share:/usr/share
PKG_CONFIG_PATH=/opt/rh/rh-ruby26/root/usr/local/lib64/pkgconfig:/opt/rh/rh-ruby26/root/usr/lib64/pkgconfig
"""
        ccs = ContainerCISuite(image_name="quay.io/fedora/nodejs-16")
        ret = ccs.test_check_envs_set(
            env_filter="^X_SCLS=|/opt/rh|/opt/app-root",
            check_envs=exec_envs,
            loop_envs=run_envs
        )
        assert not ret

    # def test_doc_content_old(self):
    #     #flexmock(DockerCLIWrapper).should_receive("docker_run_command").and_return("")
    #     ccs = ContainerCISuite(image_name="quay.io/fedora/nodejs-16")
    #     ret = ccs.doc_content_old(['POSTGRESQL\\?_ADMIN\\?_PASSWORD'])
    #     assert ret
