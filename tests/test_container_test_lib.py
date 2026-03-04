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
        """Set up the test environment."""
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
        self.lib.path_append("TEST_PATH", "/usr/local/bin")
        assert os.environ["TEST_PATH"] == "/usr/local/bin"

    def test_path_append_existing_variable(self, clean_environment):
        """Test appending to an existing path variable."""
        os.environ["TEST_PATH"] = "/usr/bin"
        self.lib.path_append("TEST_PATH", "/usr/local/bin")
        assert os.environ["TEST_PATH"] == "/usr/local/bin:/usr/bin"


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

    def test_get_public_image_name_rhel10(self):
        """Test public image name generation for RHEL10."""
        image_name = self.lib.get_public_image_name("rhel10", "nodejs", "20")
        assert image_name == "registry.redhat.io/rhel10/nodejs-20"

    def test_get_public_image_name_c10s(self):
        """Test public image name generation for CentOS Stream 10."""
        image_name = self.lib.get_public_image_name("c10s", "python", "3.12")
        assert image_name == "quay.io/sclorg/python-312-c10s"

    def test_get_public_image_name_other_os(self):
        """Test public image name generation for other OS (e.g. fedora)."""
        image_name = self.lib.get_public_image_name("fedora", "nodejs", "16")
        assert image_name == "quay.io/sclorg/nodejs-16"


class TestCommandAssertions:
    """Test command assertion functions."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_assert_cmd_success_with_success(self, mock_docker_commands):
        """Test successful command assertion."""
        result = self.lib.assert_cmd_success("true")
        assert result is True

    def test_assert_cmd_success_with_failure(self, mock_docker_commands):
        """Test failed command assertion."""
        result = self.lib.assert_cmd_success("false")
        assert result is False

    def test_assert_cmd_failure_with_success(self, mock_docker_commands):
        """Test command failure assertion with successful command."""
        result = self.lib.assert_cmd_failure("true")
        assert result is False

    def test_assert_cmd_failure_with_failure(self, mock_docker_commands):
        """Test command failure assertion with failing command."""
        result = self.lib.assert_cmd_failure("false")
        assert result is True


class TestContainerOperations:
    """Test container-related operations."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_container_exists_false(self):
        """Test container exists check when container doesn't exist."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
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

    def test_get_cid_cip(self, mock_docker_commands, mock_file_operations):
        """Test getting container ID from file."""
        mock_file_operations[str(self.lib.cid_file_dir / "test")] = "container123"
        cip, cid = self.lib.get_cip_cid("test")
        assert cid == "container123"
        assert cip == "172.27.0.2"


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
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
            mock_cmd.side_effect = [
                "",  # docker images -q (not found)
                CalledProcessError(1, "docker pull"),  # pull fails
            ]
            result = self.lib.pull_image("nonexistent:latest", loops=1)
            assert result is False

    def test_build_image_and_parse_id_success(self, mock_docker_commands):
        """Test successful image build."""
        result = self.lib.build_image_and_parse_id("Dockerfile", ".")
        assert result is True
        assert hasattr(self.lib, "app_image_id")

    def test_build_image_and_parse_id_failure(self):
        """Test failed image build."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
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

    def test_check_envs_set_empty_loop_envs(self):
        """Test environment variable checking with empty loop_envs."""
        result = self.lib.check_envs_set("PATH", "PATH=/usr/bin", "")
        assert result is True

    def test_check_envs_set_pwd_skipped(self):
        """Test that PWD= lines are skipped."""
        env_filter = "PWD"
        check_envs = ""
        loop_envs = "PWD=/home/user"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is True

    def test_check_envs_set_multiple_vars_success(self):
        """Test environment variable checking with multiple variables."""
        env_filter = r"PATH|X_SCLS"
        check_envs = "PATH=/usr/bin:/bin\nX_SCLS=nodejs16"
        loop_envs = "PATH=/usr/bin\nX_SCLS=nodejs16"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is True

    def test_check_envs_set_value_missing_in_check_envs(self):
        """Test when a value in loop_envs is not present in check_envs."""
        env_filter = r"/opt|/usr"
        check_envs = "PATH=/usr/bin"
        loop_envs = "PATH=/usr/bin:/opt/custom"

        result = self.lib.check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False

    def test_check_envs_set_custom_env_format(self):
        """Test environment variable checking with custom env_format."""
        check_envs = "X_SCLS=nodejs16"
        loop_envs = "X_SCLS=nodejs16"

        result = self.lib.check_envs_set(
            "nodejs", check_envs, loop_envs, env_format="*VALUE*"
        )
        assert result is True


class TestSclUsageOld:
    """Test scl_usage_old function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    def test_scl_usage_old_success(self, mock_get_cid, mock_podman):
        """Test scl_usage_old when all three checks pass."""
        mock_get_cid.return_value = "container123"
        mock_podman.return_value = "nodejs16 python38"

        result = self.lib.scl_usage_old(
            cid_file_name="app",
            command="scl enable nodejs16 -- node --version",
            expected="nodejs16",
        )

        assert result is True
        assert mock_podman.call_count == 3

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_scl_usage_old_run_fails_expected_missing(self, mock_podman):
        """Test scl_usage_old when docker run output lacks expected string."""
        mock_podman.return_value = "unexpected output"

        result = self.lib.scl_usage_old(
            cid_file_name="app",
            command="scl enable nodejs16 -- node --version",
            expected="nodejs16",
            image_name="test:latest",
        )

        assert result is False
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    def test_scl_usage_old_exec_bash_fails(self, mock_get_cid, mock_podman):
        """Test scl_usage_old when exec with bash fails."""
        mock_get_cid.return_value = "container123"
        mock_podman.side_effect = [
            "nodejs16 python38",  # run succeeds
            "wrong output",  # exec bash - expected not in output
        ]

        result = self.lib.scl_usage_old(
            cid_file_name="app",
            command="scl enable nodejs16 -- node --version",
            expected="nodejs16",
        )

        assert result is False
        assert mock_podman.call_count == 2

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    def test_scl_usage_old_exec_sh_fails(self, mock_get_cid, mock_podman):
        """Test scl_usage_old when exec with sh fails."""
        mock_get_cid.return_value = "container123"
        mock_podman.side_effect = [
            "nodejs16 python38",  # run succeeds
            "nodejs16 python38",  # exec bash succeeds
            "wrong output",  # exec sh - expected not in output
        ]

        result = self.lib.scl_usage_old(
            cid_file_name="app",
            command="scl enable nodejs16 -- node --version",
            expected="nodejs16",
        )

        assert result is False
        assert mock_podman.call_count == 3

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_scl_usage_old_run_command_error(self, mock_podman):
        """Test scl_usage_old when docker run raises CalledProcessError."""
        mock_podman.side_effect = CalledProcessError(1, "podman run", "error")

        result = self.lib.scl_usage_old(
            cid_file_name="app",
            command="scl enable nodejs16 -- node --version",
            expected="nodejs16",
            image_name="test:latest",
        )

        assert result is False
        mock_podman.assert_called_once()


class TestDocContentOld:
    """Test doc_content_old function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_doc_content_old_success(self, mock_podman):
        """Test doc_content_old when all strings found and format is correct."""
        content = ".TH MANUAL 1\n.PP\nSome text\n.SH NAME\nrequired_string"
        mock_podman.return_value = content

        result = self.lib.doc_content_old(
            strings=["required_string"], image_name="test:latest"
        )

        assert result is True
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_doc_content_old_missing_string(self, mock_podman):
        """Test doc_content_old when required string is not in content."""
        content = ".TH MANUAL 1\n.PP\nSome text\n.SH NAME"
        mock_podman.return_value = content

        result = self.lib.doc_content_old(
            strings=["missing_string"], image_name="test:latest"
        )

        assert result is False
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_doc_content_old_missing_format(self, mock_podman):
        """Test doc_content_old when content lacks troff/groff format."""
        content = "plain text without .TH or .PP or .SH"
        mock_podman.return_value = content

        result = self.lib.doc_content_old(strings=["plain"], image_name="test:latest")

        assert result is False
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_doc_content_old_command_error(self, mock_podman):
        """Test doc_content_old when podman run raises CalledProcessError."""
        mock_podman.side_effect = CalledProcessError(1, "podman run", "error")

        result = self.lib.doc_content_old(
            strings=["required"], image_name="test:latest"
        )

        assert result is False
        mock_podman.assert_called_once()


class TestBuildS2iNpmVariables:
    """Test build_s2i_npm_variables function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_s2i_npm_variables_with_registry_and_ca(
        self, mock_ca_path, clean_environment, temp_dir
    ):
        """Test build_s2i_npm_variables when NPM_REGISTRY and CA file exist."""
        os.environ["NPM_REGISTRY"] = "https://registry.example.com"
        ca_file = temp_dir / "ca.pem"
        ca_file.write_text("")
        mock_ca_path.return_value = ca_file

        with patch.object(
            self.lib, "mount_ca_file", return_value="-v /tmp/ca.pem:/tmp/ca.pem:Z"
        ):
            result = self.lib.build_s2i_npm_variables()

        assert "NPM_MIRROR=https://registry.example.com" in result
        assert "-v /tmp/ca.pem:/tmp/ca.pem:Z" in result

    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_s2i_npm_variables_no_registry(self, mock_ca_path, clean_environment):
        """Test build_s2i_npm_variables when NPM_REGISTRY is not set."""
        if "NPM_REGISTRY" in os.environ:
            del os.environ["NPM_REGISTRY"]
        mock_path = Path("/tmp/ca.pem")
        mock_path.touch()
        mock_ca_path.return_value = mock_path

        result = self.lib.build_s2i_npm_variables()

        assert result == ""

    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_s2i_npm_variables_no_ca_file(self, mock_ca_path, clean_environment):
        """Test build_s2i_npm_variables when CA file does not exist."""
        os.environ["NPM_REGISTRY"] = "https://registry.example.com"
        mock_path = Path("/nonexistent/ca.pem")
        mock_ca_path.return_value = mock_path

        result = self.lib.build_s2i_npm_variables()

        assert result == ""


class TestNpmWorks:
    """Test npm_works function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.utils.get_file_content")
    @patch("container_ci_suite.container_lib.ContainerImage.wait_for_cid")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_npm_works_success(
        self, mock_ca_path, mock_podman, mock_wait, mock_get_file
    ):
        """Test npm_works when all steps succeed."""
        mock_ca_path.return_value = Path("/tmp/nonexistent")  # No CA
        mock_podman.return_value = ""
        mock_wait.return_value = True
        mock_get_file.return_value = "container123"

        result = self.lib.npm_works(image_name="test:latest")

        assert result is True

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_npm_works_version_fails(self, mock_podman):
        """Test npm_works when npm --version raises CalledProcessError."""
        mock_podman.side_effect = CalledProcessError(1, "npm --version", "error")

        result = self.lib.npm_works(image_name="test:latest")

        assert result is False
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.ContainerImage.wait_for_cid")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_npm_works_container_start_fails(self, mock_podman, mock_wait):
        """Test npm_works when container start fails."""
        mock_podman.side_effect = [
            "8.19.2",  # npm --version succeeds
            CalledProcessError(1, "podman run", "error"),  # run -d fails
        ]

        result = self.lib.npm_works(image_name="test:latest")

        assert result is False

    @patch("container_ci_suite.container_lib.ContainerImage.wait_for_cid")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_npm_works_wait_for_cid_fails(self, mock_podman, mock_wait):
        """Test npm_works when wait_for_cid returns False."""
        mock_podman.return_value = ""
        mock_wait.return_value = False

        result = self.lib.npm_works(image_name="test:latest")

        assert result is False

    @patch("container_ci_suite.container_lib.utils.get_file_content")
    @patch("container_ci_suite.container_lib.ContainerImage.wait_for_cid")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_npm_works_install_fails(self, mock_podman, mock_wait, mock_get_file):
        """Test npm_works when npm install raises CalledProcessError."""
        mock_podman.side_effect = [
            "8.19.2",  # npm --version succeeds
            "",  # run -d succeeds
            CalledProcessError(1, "npm install", "error"),  # exec npm install fails
        ]
        mock_wait.return_value = True
        mock_get_file.return_value = "container123"

        result = self.lib.npm_works(image_name="test:latest")

        assert result is False


class TestFileOperations:
    """Test file and directory operations."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.tempfile.mktemp")
    def test_obtain_input_local_file(self, mock_mktemp, temp_dir):
        """Test obtaining input from local file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        dest_file = temp_dir / "test-input-file12345.txt"
        mock_mktemp.return_value = str(dest_file)

        result = self.lib.obtain_input(str(test_file))

        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_text() == "test content"

    @patch("container_ci_suite.container_lib.tempfile.mktemp")
    def test_obtain_input_local_directory(self, mock_mktemp, temp_dir):
        """Test obtaining input from local directory."""
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        dest_dir = temp_dir / "test-input-dir12345"
        mock_mktemp.return_value = str(dest_dir)

        result = self.lib.obtain_input(str(test_dir))

        assert result is not None
        assert Path(result).exists()
        assert Path(result).is_dir()
        assert (Path(result) / "file.txt").read_text() == "content"

    def test_obtain_input_nonexistent(
        self,
    ):
        """Test obtaining input from nonexistent path."""
        result = self.lib.obtain_input("/nonexistent/path")
        assert result is None

    @patch("container_ci_suite.container_lib.urllib.request.urlretrieve")
    @patch("container_ci_suite.container_lib.tempfile.mktemp")
    def test_obtain_input_url_success(self, mock_mktemp, mock_urlretrieve, temp_dir):
        """Test obtaining input from URL."""
        temp_file = temp_dir / "test-input-url12345.txt"
        mock_mktemp.return_value = str(temp_file)

        result = self.lib.obtain_input("https://example.com/file.txt")

        assert result == str(temp_file)
        mock_urlretrieve.assert_called_once_with(
            "https://example.com/file.txt", str(temp_file)
        )

    @patch("container_ci_suite.container_lib.urllib.request.urlretrieve")
    @patch("container_ci_suite.container_lib.tempfile.mktemp")
    def test_obtain_input_url_download_fails(self, mock_mktemp, mock_urlretrieve):
        """Test obtain_input when URL download fails."""
        mock_mktemp.return_value = "/var/tmp/test-input-url12345.txt"
        mock_urlretrieve.side_effect = OSError("Connection refused")

        result = self.lib.obtain_input("https://example.com/file.txt")

        assert result is None

    def test_obtain_input_unknown_type(self):
        """Test obtain_input with path that is not file, dir, or URL."""
        result = self.lib.obtain_input("ftp://example.com/file")
        assert result is None


class TestS2iUsage:
    """Test s2i_usage function."""

    def setup_method(self):
        self.lib = ContainerTestLib(image_name="test:latest")

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_s2i_usage_success(self, mock_podman):
        """Test s2i_usage when command succeeds."""
        mock_podman.return_value = "Usage: s2i build <source> <image> [options]"

        result = self.lib.s2i_usage()

        assert result == "Usage: s2i build <source> <image> [options]"
        mock_podman.assert_called_once()

    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_s2i_usage_command_error(self, mock_podman):
        """Test s2i_usage when podman run raises CalledProcessError."""
        mock_podman.side_effect = CalledProcessError(1, "podman run", "error")

        result = self.lib.s2i_usage()

        assert result == ""
        mock_podman.assert_called_once()


class TestShowResources:
    """Test show_resources function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.ContainerTestLibUtils.run_command")
    def test_show_resources_success(self, mock_run):
        """Test show_resources when all commands succeed."""
        mock_run.return_value = "mock output"

        self.lib.show_resources()

        # free -h, df -h, lscpu, get_image_size_uncompressed, get_image_size_compressed
        assert mock_run.call_count == 5

    @patch("container_ci_suite.container_lib.ContainerTestLibUtils.run_command")
    def test_show_resources_some_fail(self, mock_run):
        """Test show_resources when some commands fail."""
        mock_run.side_effect = [
            "memory output",
            CalledProcessError(1, "df -h", "error"),
            "cpu output",
            "1048576000",  # get_image_size_uncompressed (1GB)
            "524288000",  # get_image_size_compressed (500MB)
        ]

        self.lib.show_resources()

        assert mock_run.call_count == 5


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

    def test_get_image_size_uncompressed_success(
        self,
    ):
        """Test getting uncompressed image size."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
            mock_cmd.return_value = "1048576000"  # 1GB in bytes
            size = self.lib.get_image_size_uncompressed("test:latest")
            assert size == "1000MB"

    def test_get_image_size_uncompressed_error(
        self,
    ):
        """Test getting uncompressed image size with error."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker inspect")
            size = self.lib.get_image_size_uncompressed("test:latest")
            assert size == "Unknown"

    def test_get_image_size_compressed_success(
        self,
    ):
        """Test getting compressed image size."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
            mock_cmd.return_value = "524288000"  # 500MB in bytes
            size = self.lib.get_image_size_compressed("test:latest")
            assert size == "500MB"

    def test_get_image_size_compressed_error(
        self,
    ):
        """Test getting compressed image size with error."""
        with patch(
            "container_ci_suite.utils.ContainerTestLibUtils.run_command"
        ) as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker save")
            size = self.lib.get_image_size_compressed("test:latest")
            assert size == "Unknown"


class TestContainerCreationAssertions:
    """Test container creation assertion functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lib = ContainerTestLib(image_name="test:latest")

    @patch("container_ci_suite.engines.container.ContainerImage.is_container_running")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_basic(
        self, mock_create, mock_get_cid, mock_podman, mock_running
    ):
        """Test assert_container_creation_succeeds with basic arguments."""
        # Setup mocks
        mock_create.return_value = True
        mock_get_cid.return_value = "container123"
        mock_running.return_value = True

        # Test
        result = self.lib.assert_container_creation_succeeds(
            container_args="-e TEST=value"
        )

        assert result is True
        mock_create.assert_called_once()
        mock_get_cid.assert_called_once()
        mock_running.assert_called_once_with("container123")

    @patch("container_ci_suite.engines.container.ContainerImage.is_container_running")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_with_list_args(
        self, mock_create, mock_get_cid, mock_podman, mock_running
    ):
        """Test assert_container_creation_succeeds with list arguments."""
        # Setup mocks
        mock_create.return_value = True
        mock_get_cid.return_value = "container123"
        mock_running.return_value = True

        # Test with list
        result = self.lib.assert_container_creation_succeeds(
            container_args=["-e", "TEST=value", "-e", "ANOTHER=test"]
        )

        assert result is True
        mock_create.assert_called_once()

    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_empty_args(self, mock_create):
        """Test assert_container_creation_succeeds with empty arguments."""
        result = self.lib.assert_container_creation_succeeds(container_args="")

        assert result is False
        mock_create.assert_not_called()

    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_creation_fails(self, mock_create):
        """Test assert_container_creation_succeeds when creation fails."""
        mock_create.return_value = False

        result = self.lib.assert_container_creation_succeeds(
            container_args="-e TEST=value"
        )

        assert result is False

    @patch("container_ci_suite.engines.container.ContainerImage.is_container_running")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_not_running(
        self, mock_create, mock_get_cid, mock_podman, mock_running
    ):
        """Test assert_container_creation_succeeds when container is not running."""
        # Setup mocks
        mock_create.return_value = True
        mock_get_cid.return_value = "container123"
        mock_running.return_value = False
        mock_podman.return_value = "1"  # Exit code

        result = self.lib.assert_container_creation_succeeds(
            container_args="-e TEST=value"
        )

        assert result is False

    @patch("container_ci_suite.engines.container.ContainerImage.is_container_running")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_with_connection_test(
        self, mock_create, mock_get_cid, mock_podman, mock_running
    ):
        """Test assert_container_creation_succeeds with connection test."""
        # Setup mocks
        mock_create.return_value = True
        mock_get_cid.return_value = "container123"
        mock_running.return_value = True

        # Create a mock connection test function
        def mock_test_connection(cid_file, params):
            return params.get("should_succeed", True)

        # Test with successful connection
        result = self.lib.assert_container_creation_succeeds(
            container_args="-e TEST=value",
            test_connection_func=mock_test_connection,
            connection_params={"should_succeed": True},
        )

        assert result is True

    @patch("container_ci_suite.engines.container.ContainerImage.is_container_running")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_cid")
    @patch("container_ci_suite.container_lib.ContainerTestLib.create_container")
    def test_assert_container_creation_succeeds_with_command(
        self, mock_create, mock_get_cid, mock_podman, mock_running
    ):
        """Test assert_container_creation_succeeds with custom command."""
        # Setup mocks
        mock_create.return_value = True
        mock_get_cid.return_value = "container123"
        mock_running.return_value = True

        # Test with command
        result = self.lib.assert_container_creation_succeeds(
            container_args="-e TEST=value", command="bash -c 'sleep 100'"
        )

        assert result is True
        # Verify command was passed to create_container
        call_args = mock_create.call_args
        assert call_args[1]["command"] == "bash -c 'sleep 100'"
