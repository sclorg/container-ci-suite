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

import os
import logging

from pathlib import Path
from tempfile import TemporaryDirectory

from container_ci_suite.utils import run_command

test_dir = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger()

# TODO
# Do we want to import docker.py or libpod?
# Or directly call docker / podman commands


class ContainerCISuite(object):

    def __init__(self, image_name: str):
        self.image_name = image_name

    def test_response(self):
        pass

    def test_s2i_image(self):
        return run_command(f"docker run --rm {self.image_name} bash -c /usr/libexec/s2i/usage")

    def is_image_available(self):
        return run_command(f"docker inspect {self.image_name}")

    def check_image_availability(self):
        pass

    def build_dockerfile_from_s2i(self, app_path: str, s2i_args: str, src_image, dst_image: str):
        local_app = "upload/src"
        local_scripts = "upload/scripts"
        mount_options = ""
        incremental = False
        tmp_dir = TemporaryDirectory()
        df_name = Path(tmp_dir.name) / "Dockerfile.XXXXX"
        if not run_command(f"docker images {src_image}"):
            if "pull-policy=never" not in s2i_args:
                run_command(f"docker pull {src_image}")

        user = run_command(f'docker inspect -f "{{.Config.User}}" {src_image}')
        if not user:
            user = 0

        assert int(user)
        user_id = run_command(f"docker run --rm {src_image} bash -c 'id -u {user} 2>/dev/null")
        if not user_id:
            logger.error(f"id of user {user} not found inside image {src_image}.")
            logger.error("Terminating s2i build.")
            return 1
        else:
            user_id = user

        incremental = "--incremental" in s2i_args
        pass

    def npm_works(self):
        pass

    def scl_usage_old(self):
        pass

    def create_container(self):
        pass

    def wait_for_cid(self):
        pass

    def get_cip(self):
        pass

    def check_envs_set(self):
        pass

    def cleanup_container(self):
        pass
