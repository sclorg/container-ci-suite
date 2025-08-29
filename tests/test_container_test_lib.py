"""
Unit tests for ContainerTestLib class.
"""

import os
from pathlib import Path
from unittest.mock import patch
from subprocess import CalledProcessError

from container_ci_suite.container_lib import ContainerTestLib
from container_ci_suite.engines.container import ContainerImage


class TestContainerTestLibUtilities:
    """Test utility functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_random_string_default_length(self):
        """Test random string generation with default length."""
        random_str = self.lib.random_string()
        assert len(random_str) == 10
        assert random_str.isalnum()

    def test_random_string_custom_length(self):
        """Test random string generation with custom length."""
        random_str = self.lib.random_string(15)
        assert len(random_str) == 15
        assert random_str.isalnum()

    def test_timestamp_s(self):
        """Test timestamp generation."""
        timestamp = self.lib.timestamp_s()
        assert isinstance(timestamp, int)
        assert timestamp > 0

    def test_timestamp_pretty(self):
        """Test pretty timestamp generation."""
        timestamp = self.lib.timestamp_pretty()
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

    def test_timestamp_diff(self):
        """Test timestamp difference calculation."""
        start = 1000
        end = 1065  # 65 seconds later
        diff = self.lib.timestamp_diff(start, end)
        assert diff == "00:01:05"

    def test_path_append_new_variable(self, clean_environment):
        """Test appending to a new path variable."""
        self.lib.path_append('TEST_PATH', '/usr/local/bin')
        assert os.environ['TEST_PATH'] == '/usr/local/bin'

    def test_path_append_existing_variable(self, clean_environment):
        """Test appending to an existing path variable."""
        os.environ['TEST_PATH'] = '/usr/bin'
        self.lib.path_append('TEST_PATH', '/usr/local/bin')
        assert os.environ['TEST_PATH'] == '/usr/local/bin:/usr/bin'


class TestRegistryFunctions:
    """Test registry and image name functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_registry_from_os_rhel(self):
        """Test registry mapping for RHEL."""
        registry = self.lib.registry_from_os("rhel8")
        assert registry == "registry.redhat.io"

        registry = self.lib.registry_from_os("rhel9")
        assert registry == "registry.redhat.io"

        registry = self.lib.registry_from_os("rhel10")
        assert registry == "registry.redhat.io"

    def test_registry_from_os_other(self):
        """Test registry mapping for non-RHEL."""
        registry = self.lib.registry_from_os("fedora")
        assert registry == "quay.io"

    def test_get_public_image_name_rhel8(self):
        """Test public image name generation for RHEL8."""
        image_name = self.lib.get_public_image_name("rhel8", "nodejs", "16")
        assert image_name == "registry.redhat.io/rhel8/nodejs-16"

    def test_get_public_image_name_rhel9(self):
        """Test public image name generation for RHEL9."""
        image_name = self.lib.get_public_image_name("rhel9", "python", "3.9")
        assert image_name == "registry.redhat.io/rhel9/python-39"

    def test_get_public_image_name_c9s(self):
        """Test public image name generation for CentOS Stream 9."""
        image_name = self.lib.get_public_image_name("c9s", "nodejs", "16")
        assert image_name == "quay.io/sclorg/nodejs-16-c9s"


class TestCommandAssertions:
    """Test command assertion functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_assert_cmd_success_with_success(self, mock_docker_commands):
        """Test successful command assertion."""
        result = self.lib.assert_cmd_success('true')
        assert result is True

    def test_assert_cmd_success_with_failure(self, mock_docker_commands):
        """Test failed command assertion."""
        result = self.lib.assert_cmd_success('false')
        assert result is False

    def test_assert_cmd_failure_with_success(self, mock_docker_commands):
        """Test command failure assertion with successful command."""
        result = self.lib.assert_cmd_failure('true')
        assert result is False

    def test_assert_cmd_failure_with_failure(self, mock_docker_commands):
        """Test command failure assertion with failing command."""
        result = self.lib.assert_cmd_failure('false')
        assert result is True


class TestContainerOperations:
    """Test container-related operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_container_exists_false(self):
        """Test container exists check when container doesn't exist."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = ""
            result = ContainerImage.is_container_exists("test_container")
            assert result is False

    def test_get_cid(self, mock_file_operations):
        """Test getting container ID from file."""
        mock_file_operations[str(self.lib.cid_file_dir / "test")] = "container123"
        cid = self.lib.get_cid("test")
        assert cid == "container123"

    def test_get_cip(self, mock_docker_commands, mock_file_operations):
        """Test getting container IP address."""
        self.lib.image_name = "test:latest"

        # Mock the CID file creation
        mock_file_operations[str(self.lib.cid_file_dir / "test")] = "container123"
        cid = self.lib.get_cid("test")
        assert cid == "container123"

        ip = self.lib.get_cip("test")
        assert ip == "172.27.0.2"


class TestImageOperations:
    """Test image-related operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_pull_image_success(self, mock_docker_commands):
        """Test successful image pull."""
        result = self.lib.pull_image("test:latest")
        assert result is True

    def test_pull_image_already_exists(self, mock_docker_commands):
        """Test image pull when image already exists locally."""
        result = self.lib.pull_image("test:latest")
        assert result is True

    def test_pull_image_failure(self):
        """Test image pull failure."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = [
                "",  # docker images -q (not found)
                CalledProcessError(1, "docker pull")  # pull fails
            ]
            result = self.lib.pull_image("nonexistent:latest", loops=1)
            assert result is False

    def test_build_image_and_parse_id_success(self, mock_docker_commands):
        """Test successful image build."""
        result = self.lib.build_image_and_parse_id("Dockerfile", ".")
        assert result is True
        assert hasattr(self.lib, 'app_image_id')

    def test_build_image_and_parse_id_failure(self):
        """Test failed image build."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker build")
            result = self.lib.build_image_and_parse_id("Dockerfile", ".")
            assert result is False


class TestEnvironmentChecks:
    """Test environment variable checking functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_check_envs_set_success(self):
        """Test successful environment variable checking."""
        env_filter = "PATH"
        check_envs = "PATH=/usr/bin:/bin"
        loop_envs = "PATH=/usr/bin"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is True

    def test_check_envs_set_missing_var(self):
        """Test environment variable checking with missing variable."""
        env_filter = "MISSING"
        check_envs = "PATH=/usr/bin:/bin"
        loop_envs = "MISSING=/some/path"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False

    # TODO SUPPRESS FOR NOW
    def test_check_envs_set_missing_value(self):
        """Test environment variable checking with missing value."""
        env_filter = "PATH"
        check_envs = "PATH=/usr/bin"
        loop_envs = "PATH=/usr/bin:/missing/path"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is True


class TestFileOperations:
    """Test file and directory operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_obtain_input_local_file(self, temp_dir):
        """Test obtaining input from local file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        result = self.lib.obtain_input(str(test_file))
        assert result is not None
        assert Path(result).exists()

        # Cleanup
        Path(result).unlink()

    def test_obtain_input_local_directory(self, temp_dir):
        """Test obtaining input from local directory."""
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        result = self.lib.obtain_input(str(test_dir))
        assert result is not None
        assert Path(result).exists()
        assert Path(result).is_dir()

        # Cleanup
        import shutil
        shutil.rmtree(result)

    def test_obtain_input_nonexistent(self, ):
        """Test obtaining input from nonexistent path."""
        result = self.lib.obtain_input("/nonexistent/path")
        assert result is None


class TestWaitFunctions:
    """Test wait and timing functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_wait_for_cid_success(self, temp_dir):
        """Test successful wait for CID file."""
        cid_file = temp_dir / "test.cid"
        cid_file.write_text("container123")

        result = ContainerImage.wait_for_cid(cid_file, max_attempts=1)
        assert result is True

    def test_wait_for_cid_failure(self, temp_dir):
        """Test failed wait for CID file."""
        cid_file = temp_dir / "nonexistent.cid"

        result = ContainerImage.wait_for_cid(cid_file, max_attempts=1, sleep_time=1)
        assert result is False

    def test_wait_for_cid_empty_file(self, temp_dir):
        """Test wait for empty CID file."""
        cid_file = temp_dir / "empty.cid"
        cid_file.touch()  # Create empty file

        result = ContainerImage.wait_for_cid(cid_file, max_attempts=1)
        assert result is False


class TestImageSizeFunctions:
    """Test image size calculation functions."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_get_image_size_uncompressed_success(self, ):
        """Test getting uncompressed image size."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "1048576000"  # 1GB in bytes
            size = self.lib.get_image_size_uncompressed("test:latest")
            assert size == "1000MB"

    def test_get_image_size_uncompressed_error(self, ):
        """Test getting uncompressed image size with error."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker inspect")
            size = self.lib.get_image_size_uncompressed("test:latest")
            assert size == "Unknown"

    def test_get_image_size_compressed_success(self, ):
        """Test getting compressed image size."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "524288000"  # 500MB in bytes
            size = self.lib.get_image_size_compressed("test:latest")
            assert size == "500MB"

    def test_get_image_size_compressed_error(self, ):
        """Test getting compressed image size with error."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker save")
            size = self.lib.get_image_size_compressed("test:latest")
            assert size == "Unknown"
