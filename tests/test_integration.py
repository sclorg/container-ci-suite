"""
Integration tests for ContainerTestLib class.
These tests require Docker to be available and may be slower.
"""

import pytest

from unittest.mock import patch
from subprocess import CalledProcessError

from container_ci_suite.container_lib import ContainerTestLib
from container_ci_suite.engines.container import ContainerImage


@pytest.mark.integration
class TestContainerIntegration:
    """Integration tests for container operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_create_container_success(
            self, mock_docker_commands, mock_file_operations
    ):
        """Test successful container creation."""
        self.lib.image_name = "test:latest"

        # Mock the CID file creation
        cid_file_path = str(self.lib.cid_file_dir / "test_container")
        mock_file_operations[cid_file_path] = "container123"

        with patch.object(ContainerImage, 'wait_for_cid', return_value=True):
            result = self.lib.create_container("test_container", "sleep 60")
            assert result is True

    def test_ct_create_container_failure(self):
        """Test failed container creation."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker run")
            result = self.lib.create_container("test_container", "sleep 60")
            assert result is False

    def test_ct_assert_container_creation_fails_success(
            self, mock_docker_commands, mock_file_operations
    ):
        """Test assertion that container creation should fail."""

        # Mock container that exits with non-zero status
        with patch.object(self.lib, 'create_container', return_value=True), \
             patch.object(self.lib, 'get_cid', return_value="container123"), \
             patch.object(ContainerImage, 'is_container_running', return_value=False), \
             patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:

            # Mock exit status check
            mock_cmd.return_value = "1"  # Non-zero exit code

            result = self.lib.assert_container_creation_fails("--invalid-arg")
            assert result is True


@pytest.mark.integration
class TestImageIntegration:
    """Integration tests for image operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_image_build_and_cleanup(
            self, temp_dir, sample_dockerfile_content
    ):
        """Test building image and cleanup."""

        # Create a test Dockerfile
        dockerfile = temp_dir / "Dockerfile"
        dockerfile.write_text(sample_dockerfile_content)

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "Successfully built abc123\nabc123"

            result = self.lib.build_image_and_parse_id(str(dockerfile), str(temp_dir))
            assert result is True
            assert self.lib.app_image_id == "abc123"

    def test_binary_found_from_dockerfile(self):
        """Test binary availability check from Dockerfile."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "Successfully built def456\ndef456"

            result = self.lib.binary_found_from_df("node", "/usr/bin")
            assert result is True


@pytest.mark.integration
class TestS2IIntegration:
    """Integration tests for S2I operations."""

    def test_s2i_usage(self, mock_docker_commands):
        """Test S2I usage command."""
        lib = ContainerTestLib(image_name="test:latest")
        result = lib.s2i_usage()
        assert result == ""  # Mocked to return empty string


@pytest.mark.integration
class TestEnvironmentIntegration:
    """Integration tests for environment checking."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_check_exec_env_vars_success(
            self, sample_environment_vars
                                            ):
        """Test environment variable checking between run and exec."""
        self.lib.image_name = "test:latest"

        env_output = "\n".join([f"{k}={v}" for k, v in sample_environment_vars.items()])

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd, \
             patch.object(self.lib, 'create_container', return_value=True), \
             patch.object(self.lib, 'get_cid', return_value="container123"):

            mock_cmd.return_value = env_output

            result = self.lib.check_exec_env_vars()
            assert result is True

    def test_ct_check_scl_enable_vars_success(
            self, sample_environment_vars
    ):
        """Test SCL environment variable checking."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            # Mock X_SCLS output
            mock_cmd.side_effect = [
                "nodejs16",  # X_SCLS value
                "\n".join([f"{k}={v}" for k, v in sample_environment_vars.items()]),  # env output
                "\n".join([f"{k}={v}{v}" for k, v in sample_environment_vars.items()])  # scl enable env
            ]

            result = self.lib.check_scl_enable_vars()
            assert result is True


@pytest.mark.integration
@pytest.mark.network
class TestNetworkIntegration:
    """Integration tests requiring network access."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_test_response_success(self):
        """Test HTTP response testing."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "Welcome to the app200"

            result = self.lib.test_response(
                "http://localhost:8080",
                200,
                "Welcome",
                max_attempts=1
            )
            assert result is True

    def test_test_response_failure(self):
        """Test HTTP response testing with failure."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = "Error404"

            result = self.lib.test_response(
                "http://localhost:8080",
                200,
                "Welcome",
                max_attempts=1
            )
            assert result is False


@pytest.mark.integration
class TestNpmIntegration:
    """Integration tests for NPM functionality."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_npm_works_success(self, temp_dir):
        """Test NPM functionality check."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd, \
                patch.object(ContainerImage, 'wait_for_cid', return_value=True), \
                patch('container_ci_suite.utils.get_file_content', return_value="container123"):
            mock_cmd.side_effect = [
                "8.19.2",  # npm --version
                "",  # docker run for test container
                "npm install success",  # npm install jquery
                ""  # docker stop
            ]

            result = self.lib.npm_works()
            assert result is True

    def test_ct_npm_works_version_failure(self):
        """Test NPM functionality check with version failure."""
        self.lib.image_name = "test:latest"

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "npm --version")

            result = self.lib.npm_works()
            assert result is False


@pytest.mark.integration
class TestDocumentationIntegration:
    """Integration tests for documentation checking."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_doc_content_old_success(self):
        """Test documentation content checking."""
        doc_content = """.TH NODEJS 1 "nodejs container"
.PP
This is a nodejs container
.SH DESCRIPTION
Node.js runtime for applications
"""

        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = self.lib.doc_content_old(["nodejs", "container"])
            assert result is True

    def test_doc_content_old_missing_string(self):
        """Test documentation content checking with missing string."""
        doc_content = """.TH NODEJS 1 "nodejs container"
.PP
This is a nodejs container
"""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = self.lib.doc_content_old(["missing_string"])
            assert result is False

    def test_doc_content_old_invalid_format(self):
        """Test documentation content checking with invalid format."""
        doc_content = "This is not a proper troff format"
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = self.lib.doc_content_old(["nodejs"])
            assert result is False


@pytest.mark.integration
class TestCertificateIntegration:
    """Integration tests for certificate operations."""
    def setup_method(self):
        self.lib = ContainerTestLib()

    def test_gen_self_signed_cert_pem(self, temp_dir):
        """Test self-signed certificate generation."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.return_value = ""  # Successful command execution

            result = self.lib.gen_self_signed_cert_pem(str(temp_dir), "test")
            assert result is True

            # Check that openssl commands were called
            assert mock_cmd.call_count >= 2

    def test_gen_self_signed_cert_pem_failure(self, temp_dir):
        """Test self-signed certificate generation failure."""
        with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "openssl")

            result = self.lib.gen_self_signed_cert_pem(str(temp_dir), "test")
            assert result is False
