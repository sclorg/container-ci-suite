"""
Error handling and edge case tests for ContainerTestLib class.
"""

import pytest
import os
from unittest.mock import patch
from subprocess import CalledProcessError

from container_ci_suite.container_lib import ContainerTestLib
from container_ci_suite.engines.container import ContainerImage


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_build_image_timeout(self):
        """Test image build with timeout."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(124, "timeout")  # timeout exit code

            result = self.lib.build_image_and_parse_id("Dockerfile", ".")
            assert result is False

    def test_container_running_with_invalid_id(self, container_test_lib):
        """Test container running check with invalid container ID."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker inspect")

            result = ContainerImage.is_container_running("invalid_id")
            assert result is False

    def test_get_cid_with_missing_file(self):
        """Test getting CID when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            self.lib.get_cid("nonexistent")

    def test_pull_image_with_network_error(self):
        """Test image pull with network errors."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = [
                "",  # docker images -q (not found)
                CalledProcessError(1, "docker pull", "network error")
            ]

            result = self.lib.pull_image("test:latest", loops=1)
            assert result is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_path_append_empty_directory(self, clean_environment):
        """Test path append with empty directory string."""
        self.lib.path_append('TEST_PATH', '')
        assert os.environ['TEST_PATH'] == ''

    def test_check_envs_set_empty_inputs(self):
        """Test environment checking with empty inputs."""
        result = self.lib.check_envs_set("", "", "")
        assert result is True  # Should succeed with empty inputs

    def test_check_envs_set_malformed_env(self):
        """Test environment checking with malformed environment strings."""
        env_filter = "TEST"
        check_envs = "MALFORMED_LINE_WITHOUT_EQUALS"
        loop_envs = "TEST=value"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False

    def test_wait_for_cid_with_zero_attempts(self, temp_dir):
        """Test wait for CID with zero max attempts."""
        cid_file = temp_dir / "test.cid"

        result = ContainerImage.wait_for_cid(cid_file, max_attempts=0)
        assert result is False

    def test_get_public_image_name_unknown_os(self):
        """Test public image name generation with unknown OS."""
        image_name = self.lib.get_public_image_name("unknown", "nodejs", "16")
        assert image_name == "quay.io/sclorg/nodejs-16"  # Should default to quay.io


class TestInputValidation:
    """Test input validation and sanitization."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_pull_image_invalid_name(self):
        """Test pulling image with invalid name."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(
                1, "docker pull", "invalid repository name"
            )

            result = self.lib.pull_image("invalid/image/name/too/long", loops=1)
            assert result is False

    def test_create_container_invalid_args(self):
        """Test container creation with invalid arguments."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker run", "invalid argument")

            result = self.lib.create_container("test", "--invalid-flag")
            assert result is False

    def test_test_response_invalid_url(self):
        """Test HTTP response testing with invalid URL."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "curl", "Could not resolve host")

            result = self.lib.test_response("http://invalid-host:8080", max_attempts=1)
            assert result is False

    def test_registry_from_os_empty_string(self):
        """Test registry mapping with empty OS string."""
        registry = self.lib.registry_from_os("")
        assert registry == "quay.io"  # Should default to quay.io

    def test_get_public_image_name_empty_inputs(self):
        """Test public image name generation with empty inputs."""
        image_name = self.lib.get_public_image_name("", "", "")
        assert image_name == "quay.io/sclorg/-"  # Should handle empty inputs gracefully
