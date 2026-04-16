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

from container_ci_suite.compare_images import ContainerCompareClass
from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper


class TestGetImageSizeUncompressed:
    """Tests for ContainerCompareClass.get_image_size_uncompressed."""

    def test_returns_parsed_int_from_inspect_output(self):
        """
        Test that the function returns the parsed int from the inspect output.
        """
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").with_args(
            cmd="inspect myimg:latest -f '{{.Size}}'",
            return_output=True,
        ).and_return("  1048576  \n").once()

        assert (
            ContainerCompareClass.get_image_size_uncompressed("myimg:latest") == 1048576
        )

    def test_returns_zero_on_called_process_error(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_raise(
            subprocess.CalledProcessError(1, "podman")
        )

        assert ContainerCompareClass.get_image_size_uncompressed("x:latest") == 0

    def test_returns_zero_on_non_integer_output(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "not-a-number"
        )

        assert ContainerCompareClass.get_image_size_uncompressed("x:latest") == 0


class TestGetImageSizeCompressed:
    """Tests for ContainerCompareClass.get_image_size_compressed."""

    def test_returns_parsed_int_from_save_pipeline(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").with_args(
            cmd="save myimg:latest | gzip - | wc --bytes",
            return_output=True,
        ).and_return("500000\n").once()

        assert ContainerCompareClass.get_image_size_compressed("myimg:latest") == 500000

    def test_returns_zero_on_error(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_raise(
            subprocess.CalledProcessError(1, "podman")
        )

        assert ContainerCompareClass.get_image_size_compressed("x:latest") == 0


class TestIsUncompressedImageSmallerThanOfficialImage:
    """Tests for ContainerCompareClass.is_uncompressed_image_smaller_than_official_image."""

    def test_true_when_built_smaller_and_official_exists(self):
        flexmock(PodmanCLIWrapper).should_receive("podman_image_exists").with_args(
            "official:latest"
        ).and_return(True).once()
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "100\n"
        ).and_return("200\n").times(2)

        assert ContainerCompareClass.is_uncompressed_image_smaller(
            "built:latest", "official:latest"
        )

    def test_false_when_built_not_smaller(self):
        flexmock(PodmanCLIWrapper).should_receive("podman_image_exists").with_args(
            "official:latest"
        ).and_return(True)
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "300\n"
        ).and_return("200\n").times(2)

        assert not ContainerCompareClass.is_uncompressed_image_smaller(
            "built:latest", "official:latest"
        )

    def test_pulls_official_when_missing_then_compares(self):
        flexmock(PodmanCLIWrapper).should_receive("podman_image_exists").with_args(
            "official:latest"
        ).and_return(False)
        flexmock(PodmanCLIWrapper).should_receive("podman_pull_image").with_args(
            "official:latest"
        ).and_return(True).once()
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "50\n"
        ).and_return("100\n").times(2)

        assert ContainerCompareClass.is_uncompressed_image_smaller(
            "built:latest", "official:latest"
        )

    def test_false_when_official_missing_and_pull_fails(self):
        flexmock(PodmanCLIWrapper).should_receive("podman_image_exists").with_args(
            "official:latest"
        ).and_return(False)
        flexmock(PodmanCLIWrapper).should_receive("podman_pull_image").with_args(
            "official:latest"
        ).and_return(False).once()
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "100\n"
        ).once()

        assert not ContainerCompareClass.is_uncompressed_image_smaller(
            "built:latest", "official:latest"
        )


class TestIsCompressedImageSmallerThanOfficialImage:
    """Tests for ContainerCompareClass.is_compressed_image_smaller_than_official_image."""

    def test_true_when_compressed_smaller(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "1000\n"
        ).and_return("2000\n").times(2)

        assert ContainerCompareClass.is_compressed_image_smaller(
            "mine:latest", "official:latest"
        )

    def test_false_when_compressed_not_smaller(self):
        flexmock(PodmanCLIWrapper).should_receive("call_podman_command").and_return(
            "5000\n"
        ).and_return("2000\n").times(2)

        assert not ContainerCompareClass.is_compressed_image_smaller(
            "mine:latest", "official:latest"
        )
