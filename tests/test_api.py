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
import flexmock

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
                "f32/nodejs:12",
                "f32/nodejs:12-testapp",
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
