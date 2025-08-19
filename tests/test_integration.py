"""
Integration tests for ContainerTestLib class.
These tests require Docker to be available and may be slower.
"""

import pytest
from unittest.mock import patch
from subprocess import CalledProcessError


@pytest.mark.integration
class TestContainerIntegration:
    """Integration tests for container operations."""

    def test_ct_create_container_success(
            self, initialized_container_test_lib, mock_docker_commands, mock_file_operations
    ):
        """Test successful container creation."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        # Mock the CID file creation
        cid_file_path = str(ct_lib.cid_file_dir / "test_container")
        mock_file_operations[cid_file_path] = "container123"

        with patch.object(ct_lib, 'ct_wait_for_cid', return_value=True):
            result = ct_lib.ct_create_container("test_container", "sleep 60")
            assert result is True

    def test_ct_create_container_failure(self, initialized_container_test_lib):
        """Test failed container creation."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker run")
            result = ct_lib.ct_create_container("test_container", "sleep 60")
            assert result is False

    def test_ct_assert_container_creation_fails_success(
            self, initialized_container_test_lib, mock_docker_commands, mock_file_operations
    ):
        """Test assertion that container creation should fail."""
        ct_lib = initialized_container_test_lib

        # Mock container that exits with non-zero status
        with patch.object(ct_lib, 'ct_create_container', return_value=True), \
             patch.object(ct_lib, 'ct_get_cid', return_value="container123"), \
             patch.object(ct_lib, 'ct_container_running', return_value=False), \
             patch('container_test_lib.run_command') as mock_cmd:

            # Mock exit status check
            mock_cmd.return_value = "1"  # Non-zero exit code

            result = ct_lib.ct_assert_container_creation_fails("--invalid-arg")
            assert result is True

    def test_container_lifecycle(
            self, initialized_container_test_lib, mock_docker_commands, mock_file_operations
    ):
        """Test complete container lifecycle."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        # Mock CID file
        cid_file_path = str(ct_lib.cid_file_dir / "lifecycle_test")
        mock_file_operations[cid_file_path] = "container123"

        with patch.object(ct_lib, 'wait_for_cid', return_value=True):
            # Create container
            assert ct_lib.ct_create_container("lifecycle_test", "sleep 60") is True

            # Check if running
            assert ct_lib.ct_container_running("container123") is True

            # Check if exists
            assert ct_lib.ct_container_exists("container123") is True

            # Get IP
            ip = ct_lib.ct_get_cip("lifecycle_test")
            assert ip == "172.17.0.2"


@pytest.mark.integration
class TestImageIntegration:
    """Integration tests for image operations."""

    def test_image_build_and_cleanup(
            self, initialized_container_test_lib, temp_dir, sample_dockerfile_content
    ):
        """Test building image and cleanup."""
        ct_lib = initialized_container_test_lib

        # Create a test Dockerfile
        dockerfile = temp_dir / "Dockerfile"
        dockerfile.write_text(sample_dockerfile_content)

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "Successfully built abc123\nabc123"

            result = ct_lib.ct_build_image_and_parse_id(str(dockerfile), str(temp_dir))
            assert result is True
            assert ct_lib.app_image_id == "abc123"

    def test_binary_found_from_dockerfile(self, initialized_container_test_lib):
        """Test binary availability check from Dockerfile."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "Successfully built def456\ndef456"

            result = ct_lib.ct_binary_found_from_df("node", "/usr/bin")
            assert result is True


@pytest.mark.integration
class TestS2IIntegration:
    """Integration tests for S2I operations."""

    def test_ct_s2i_usage(self, container_test_lib, mock_docker_commands):
        """Test S2I usage command."""
        result = container_test_lib.ct_s2i_usage("test:latest")
        assert result == ""  # Mocked to return empty string


@pytest.mark.integration
class TestEnvironmentIntegration:
    """Integration tests for environment checking."""

    def test_ct_check_exec_env_vars_success(
            self, initialized_container_test_lib, sample_environment_vars
                                            ):
        """Test environment variable checking between run and exec."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        env_output = "\n".join([f"{k}={v}" for k, v in sample_environment_vars.items()])

        with patch('container_test_lib.run_command') as mock_cmd, \
             patch.object(ct_lib, 'ct_create_container', return_value=True), \
             patch.object(ct_lib, 'ct_get_cid', return_value="container123"):

            mock_cmd.return_value = env_output

            result = ct_lib.ct_check_exec_env_vars()
            assert result is True

    def test_ct_check_scl_enable_vars_success(
            self, initialized_container_test_lib, sample_environment_vars
    ):
        """Test SCL environment variable checking."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        with patch('container_test_lib.run_command') as mock_cmd:
            # Mock X_SCLS output
            mock_cmd.side_effect = [
                "nodejs16",  # X_SCLS value
                "\n".join([f"{k}={v}" for k, v in sample_environment_vars.items()]),  # env output
                "\n".join([f"{k}={v}{v}" for k, v in sample_environment_vars.items()])  # scl enable env
            ]

            result = ct_lib.ct_check_scl_enable_vars()
            assert result is True


@pytest.mark.integration
@pytest.mark.network
class TestNetworkIntegration:
    """Integration tests requiring network access."""

    def test_ct_test_response_success(self, container_test_lib):
        """Test HTTP response testing."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "Welcome to the app200"

            result = container_test_lib.ct_test_response(
                "http://localhost:8080",
                200,
                "Welcome",
                max_attempts=1
            )
            assert result is True

    def test_ct_test_response_failure(self, container_test_lib):
        """Test HTTP response testing with failure."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "Error404"

            result = container_test_lib.ct_test_response(
                "http://localhost:8080",
                200,
                "Welcome",
                max_attempts=1
            )
            assert result is False


@pytest.mark.integration
class TestNpmIntegration:
    """Integration tests for NPM functionality."""

    def test_ct_npm_works_success(self, initialized_container_test_lib, temp_dir):
        """Test NPM functionality check."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        with patch('container_test_lib.run_command') as mock_cmd, \
             patch.object(ct_lib, 'ct_wait_for_cid', return_value=True), \
             patch('container_test_lib.get_file_content', return_value="container123"):

            mock_cmd.side_effect = [
                "8.19.2",  # npm --version
                "",  # docker run for test container
                "npm install success",  # npm install jquery
                ""  # docker stop
            ]

            result = ct_lib.ct_npm_works()
            assert result is True

    def test_ct_npm_works_version_failure(self, initialized_container_test_lib):
        """Test NPM functionality check with version failure."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "npm --version")

            result = ct_lib.ct_npm_works()
            assert result is False


@pytest.mark.integration
class TestDocumentationIntegration:
    """Integration tests for documentation checking."""

    def test_doc_content_old_success(self, container_test_lib):
        """Test documentation content checking."""
        doc_content = """.TH NODEJS 1 "nodejs container"
.PP
This is a nodejs container
.SH DESCRIPTION
Node.js runtime for applications
"""

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = container_test_lib.ct_doc_content_old(["nodejs", "container"])
            assert result is True

    def test_doc_content_old_missing_string(self, container_test_lib):
        """Test documentation content checking with missing string."""
        doc_content = """.TH NODEJS 1 "nodejs container"
.PP
This is a nodejs container
"""

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = container_test_lib.ct_doc_content_old(["missing_string"])
            assert result is False

    def test_doc_content_old_invalid_format(self, container_test_lib):
        """Test documentation content checking with invalid format."""
        doc_content = "This is not a proper troff format"

        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = doc_content

            result = container_test_lib.ct_doc_content_old(["nodejs"])
            assert result is False


@pytest.mark.integration
class TestCertificateIntegration:
    """Integration tests for certificate operations."""

    def test_ct_gen_self_signed_cert_pem(self, container_test_lib, temp_dir):
        """Test self-signed certificate generation."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = ""  # Successful command execution

            result = container_test_lib.gen_self_signed_cert_pem(str(temp_dir), "test")
            assert result is True

            # Check that openssl commands were called
            assert mock_cmd.call_count >= 2

    def test_ct_gen_self_signed_cert_pem_failure(self, container_test_lib, temp_dir):
        """Test self-signed certificate generation failure."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "openssl")

            result = container_test_lib.gen_self_signed_cert_pem(str(temp_dir), "test")
            assert result is False
