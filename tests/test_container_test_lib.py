"""
Unit tests for ContainerTestLib class.
"""

import os
from pathlib import Path
from unittest.mock import patch
from subprocess import CalledProcessError

from container_ci_suite.container_test_lib import ContainerTestLib


class TestContainerTestLibInit:
    """Test initialization and basic setup."""

    def test_init_creates_instance(self, container_test_lib):
        """Test that ContainerTestLib can be instantiated."""
        assert isinstance(container_test_lib, ContainerTestLib)
        assert container_test_lib.app_id_file_dir is None
        assert container_test_lib.cid_file_dir is None
        assert isinstance(container_test_lib.unstable_tests, list)

    def test_ct_init_creates_directories(self, container_test_lib):
        """Test that ct_init creates necessary directories."""
        container_test_lib.ct_init()

        assert container_test_lib.app_id_file_dir is not None
        assert container_test_lib.cid_file_dir is not None
        assert container_test_lib.app_id_file_dir.exists()
        assert container_test_lib.cid_file_dir.exists()
        assert container_test_lib.cleanup_enabled is True

        # Cleanup
        container_test_lib.ct_cleanup()

    def test_unstable_tests_from_environment(self, clean_environment):
        """Test that unstable tests are loaded from environment."""
        os.environ['UNSTABLE_TESTS'] = 'test1 test2 test3'
        ct_lib = ContainerTestLib()
        assert ct_lib.unstable_tests == ['test1', 'test2', 'test3']


class TestContainerTestLibUtilities:
    """Test utility functions."""

    def test_ct_random_string_default_length(self, container_test_lib):
        """Test random string generation with default length."""
        random_str = container_test_lib.ct_random_string()
        assert len(random_str) == 10
        assert random_str.isalnum()

    def test_ct_random_string_custom_length(self, container_test_lib):
        """Test random string generation with custom length."""
        random_str = container_test_lib.ct_random_string(15)
        assert len(random_str) == 15
        assert random_str.isalnum()

    def test_ct_timestamp_s(self, container_test_lib):
        """Test timestamp generation."""
        timestamp = container_test_lib.ct_timestamp_s()
        assert isinstance(timestamp, int)
        assert timestamp > 0

    def test_ct_timestamp_pretty(self, container_test_lib):
        """Test pretty timestamp generation."""
        timestamp = container_test_lib.ct_timestamp_pretty()
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

    def test_ct_timestamp_diff(self, container_test_lib):
        """Test timestamp difference calculation."""
        start = 1000
        end = 1065  # 65 seconds later
        diff = container_test_lib.ct_timestamp_diff(start, end)
        assert diff == "00:01:05"

    def test_ct_path_append_new_variable(self, container_test_lib, clean_environment):
        """Test appending to a new path variable."""
        container_test_lib.ct_path_append('TEST_PATH', '/usr/local/bin')
        assert os.environ['TEST_PATH'] == '/usr/local/bin'

    def test_ct_path_append_existing_variable(self, container_test_lib, clean_environment):
        """Test appending to an existing path variable."""
        os.environ['TEST_PATH'] = '/usr/bin'
        container_test_lib.ct_path_append('TEST_PATH', '/usr/local/bin')
        assert os.environ['TEST_PATH'] == '/usr/local/bin:/usr/bin'


class TestRegistryFunctions:
    """Test registry and image name functions."""

    def test_ct_registry_from_os_rhel(self, container_test_lib):
        """Test registry mapping for RHEL."""
        registry = container_test_lib.ct_registry_from_os("rhel8")
        assert registry == "registry.redhat.io"

        registry = container_test_lib.ct_registry_from_os("rhel9")
        assert registry == "registry.redhat.io"

    def test_ct_registry_from_os_other(self, container_test_lib):
        """Test registry mapping for non-RHEL."""
        registry = container_test_lib.ct_registry_from_os("fedora")
        assert registry == "quay.io"

        registry = container_test_lib.ct_registry_from_os("centos")
        assert registry == "quay.io"

    def test_ct_get_public_image_name_rhel8(self, container_test_lib):
        """Test public image name generation for RHEL8."""
        image_name = container_test_lib.ct_get_public_image_name("rhel8", "nodejs", "16")
        assert image_name == "registry.redhat.io/rhel8/nodejs-16"

    def test_ct_get_public_image_name_rhel9(self, container_test_lib):
        """Test public image name generation for RHEL9."""
        image_name = container_test_lib.ct_get_public_image_name("rhel9", "python", "3.9")
        assert image_name == "registry.redhat.io/rhel9/python-39"

    def test_ct_get_public_image_name_c9s(self, container_test_lib):
        """Test public image name generation for CentOS Stream 9."""
        image_name = container_test_lib.ct_get_public_image_name("c9s", "nodejs", "16")
        assert image_name == "quay.io/sclorg/nodejs-16-c9s"


class TestCommandAssertions:
    """Test command assertion functions."""

    def test_ct_assert_cmd_success_with_success(self, container_test_lib, mock_docker_commands):
        """Test successful command assertion."""
        result = container_test_lib.ct_assert_cmd_success('true')
        assert result is True

    def test_ct_assert_cmd_success_with_failure(self, container_test_lib, mock_docker_commands):
        """Test failed command assertion."""
        result = container_test_lib.ct_assert_cmd_success('false')
        assert result is False

    def test_ct_assert_cmd_failure_with_success(self, container_test_lib, mock_docker_commands):
        """Test command failure assertion with successful command."""
        result = container_test_lib.ct_assert_cmd_failure('true')
        assert result is False

    def test_ct_assert_cmd_failure_with_failure(self, container_test_lib, mock_docker_commands):
        """Test command failure assertion with failing command."""
        result = container_test_lib.ct_assert_cmd_failure('false')
        assert result is True


class TestContainerOperations:
    """Test container-related operations."""

    def test_ct_container_running_true(self, container_test_lib, mock_docker_commands):
        """Test container running check when container is running."""
        result = container_test_lib.ct_container_running("test_container")
        assert result is True

    def test_ct_container_running_false(self, container_test_lib):
        """Test container running check when container is not running."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "false"
            result = container_test_lib.ct_container_running("test_container")
            assert result is False

    def test_ct_container_exists_true(self, container_test_lib, mock_docker_commands):
        """Test container exists check when container exists."""
        result = container_test_lib.ct_container_exists("test_container")
        assert result is True

    def test_ct_container_exists_false(self, container_test_lib):
        """Test container exists check when container doesn't exist."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = ""
            result = container_test_lib.ct_container_exists("test_container")
            assert result is False

    def test_ct_get_cid(self, initialized_container_test_lib, mock_file_operations):
        """Test getting container ID from file."""
        mock_file_operations[str(initialized_container_test_lib.cid_file_dir / "test")] = "container123"
        cid = initialized_container_test_lib.ct_get_cid("test")
        assert cid == "container123"

    def test_ct_get_cip(self, initialized_container_test_lib, mock_docker_commands, mock_file_operations):
        """Test getting container IP address."""
        mock_file_operations[str(initialized_container_test_lib.cid_file_dir / "test")] = "container123"
        ip = initialized_container_test_lib.ct_get_cip("test")
        assert ip == "172.17.0.2"


class TestImageOperations:
    """Test image-related operations."""

    def test_ct_pull_image_success(self, container_test_lib, mock_docker_commands):
        """Test successful image pull."""
        result = container_test_lib.ct_pull_image("test:latest")
        assert result is True

    def test_ct_pull_image_already_exists(self, container_test_lib, mock_docker_commands):
        """Test image pull when image already exists locally."""
        result = container_test_lib.ct_pull_image("test:latest")
        assert result is True

    def test_ct_pull_image_failure(self, container_test_lib):
        """Test image pull failure."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = [
                "",  # docker images -q (not found)
                CalledProcessError(1, "docker pull")  # pull fails
            ]
            result = container_test_lib.ct_pull_image("nonexistent:latest", loops=1)
            assert result is False

    def test_ct_build_image_and_parse_id_success(self, container_test_lib, mock_docker_commands):
        """Test successful image build."""
        result = container_test_lib.ct_build_image_and_parse_id("Dockerfile", ".")
        assert result is True
        assert hasattr(container_test_lib, 'app_image_id')

    def test_ct_build_image_and_parse_id_failure(self, container_test_lib):
        """Test failed image build."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker build")
            result = container_test_lib.ct_build_image_and_parse_id("Dockerfile", ".")
            assert result is False


class TestEnvironmentChecks:
    """Test environment variable checking functions."""

    def test_ct_check_envs_set_success(self, container_test_lib):
        """Test successful environment variable checking."""
        env_filter = "PATH"
        check_envs = "PATH=/usr/bin:/bin"
        loop_envs = "PATH=/usr/bin"

        result = container_test_lib.ct_check_envs_set(env_filter, check_envs, loop_envs)
        assert result is True

    def test_ct_check_envs_set_missing_var(self, container_test_lib):
        """Test environment variable checking with missing variable."""
        env_filter = "MISSING"
        check_envs = "PATH=/usr/bin:/bin"
        loop_envs = "MISSING=/some/path"

        result = container_test_lib.ct_check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False

    def test_ct_check_envs_set_missing_value(self, container_test_lib):
        """Test environment variable checking with missing value."""
        env_filter = "PATH"
        check_envs = "PATH=/usr/bin"
        loop_envs = "PATH=/usr/bin:/missing/path"

        result = container_test_lib.ct_check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False


class TestFileOperations:
    """Test file and directory operations."""

    def test_ct_obtain_input_local_file(self, container_test_lib, temp_dir):
        """Test obtaining input from local file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        result = container_test_lib.ct_obtain_input(str(test_file))
        assert result is not None
        assert Path(result).exists()

        # Cleanup
        Path(result).unlink()

    def test_ct_obtain_input_local_directory(self, container_test_lib, temp_dir):
        """Test obtaining input from local directory."""
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        result = container_test_lib.ct_obtain_input(str(test_dir))
        assert result is not None
        assert Path(result).exists()
        assert Path(result).is_dir()

        # Cleanup
        import shutil
        shutil.rmtree(result)

    def test_ct_obtain_input_nonexistent(self, container_test_lib):
        """Test obtaining input from nonexistent path."""
        result = container_test_lib.ct_obtain_input("/nonexistent/path")
        assert result is None


class TestWaitFunctions:
    """Test wait and timing functions."""

    def test_ct_wait_for_cid_success(self, container_test_lib, temp_dir):
        """Test successful wait for CID file."""
        cid_file = temp_dir / "test.cid"
        cid_file.write_text("container123")

        result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=1)
        assert result is True

    def test_ct_wait_for_cid_failure(self, container_test_lib, temp_dir):
        """Test failed wait for CID file."""
        cid_file = temp_dir / "nonexistent.cid"

        result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=1, sleep_time=0.1)
        assert result is False

    def test_ct_wait_for_cid_empty_file(self, container_test_lib, temp_dir):
        """Test wait for empty CID file."""
        cid_file = temp_dir / "empty.cid"
        cid_file.touch()  # Create empty file

        result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=1)
        assert result is False


class TestTestResults:
    """Test result tracking and display functions."""

    def test_ct_update_test_result(self, container_test_lib):
        """Test updating test results."""
        container_test_lib.ct_update_test_result("[PASSED]", "myapp", "test_basic", "00:01:30")

        expected = "[PASSED] for 'myapp' test_basic (00:01:30)\n"
        assert container_test_lib.test_summary == expected

    def test_ct_check_testcase_result_success(self, container_test_lib):
        """Test checking successful test case result."""
        result = container_test_lib.ct_check_testcase_result(0, "test:latest")
        assert result == 0
        assert container_test_lib.testsuite_result == 0

    def test_ct_check_testcase_result_failure(self, container_test_lib):
        """Test checking failed test case result."""
        result = container_test_lib.ct_check_testcase_result(1, "test:latest")
        assert result == 1
        assert container_test_lib.testsuite_result == 1

    def test_ct_show_results(self, container_test_lib, capsys):
        """Test showing test results."""
        container_test_lib.test_summary = "[PASSED] test1\n[FAILED] test2\n"
        container_test_lib.testsuite_result = 1

        container_test_lib.ct_show_results("test:latest")

        captured = capsys.readouterr()
        assert "Tests were run for image test:latest" in captured.out
        assert "[PASSED] test1" in captured.out
        assert "[FAILED] test2" in captured.out
        assert "Tests for test:latest failed." in captured.out


class TestCleanupOperations:
    """Test cleanup and resource management."""

    def test_ct_enable_cleanup(self, container_test_lib):
        """Test enabling cleanup handlers."""
        container_test_lib.ct_enable_cleanup()
        assert container_test_lib.cleanup_enabled is True

    def test_ct_cleanup_no_directories(self, container_test_lib, capsys):
        """Test cleanup when directories don't exist."""
        container_test_lib.ct_cleanup()
        captured = capsys.readouterr()
        assert "Cleaning of testing containers and images started." in captured.out


class TestImageSizeFunctions:
    """Test image size calculation functions."""

    def test_ct_get_image_size_uncompressed_success(self, container_test_lib):
        """Test getting uncompressed image size."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "1048576000"  # 1GB in bytes
            size = container_test_lib.ct_get_image_size_uncompressed("test:latest")
            assert size == "1000MB"

    def test_ct_get_image_size_uncompressed_error(self, container_test_lib):
        """Test getting uncompressed image size with error."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker inspect")
            size = container_test_lib.ct_get_image_size_uncompressed("test:latest")
            assert size == "Unknown"

    def test_ct_get_image_size_compressed_success(self, container_test_lib):
        """Test getting compressed image size."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "524288000"  # 500MB in bytes
            size = container_test_lib.ct_get_image_size_compressed("test:latest")
            assert size == "500MB"

    def test_ct_get_image_size_compressed_error(self, container_test_lib):
        """Test getting compressed image size with error."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker save")
            size = container_test_lib.ct_get_image_size_compressed("test:latest")
            assert size == "Unknown"
