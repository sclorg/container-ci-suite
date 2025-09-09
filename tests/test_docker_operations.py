#!/usr/bin/env python3
"""
Comprehensive pytest suite for the DockerfileProcessor module.
This test suite covers all functionality of the dockerfile_processor module
including the replacement of sed commands with Python equivalents.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from container_ci_suite.dockerfile_processor import DockerfileProcessor


# Add the test directory to the Python path
TEST_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, str(TEST_DIR))


@pytest.mark.unit
@pytest.mark.dockerfile
class TestDockerfileProcessor:
    """Test suite for DockerfileProcessor class."""

    @pytest.fixture
    def sample_dockerfile_content(self):
        """Sample Dockerfile content for testing."""
        return """FROM registry.redhat.io/ubi8/ubi:latest

LABEL maintainer="Test Team <test@example.com>"

ENV NGINX_VERSION=1.20 \
    NGINX_SHORT_VER=120 \
    NAME=nginx \
    VERSION=0

# Install nginx
RUN yum install -y nginx-$NGINX_VERSION && \
    yum clean all

EXPOSE 8080

COPY ./s2i/bin/ $STI_SCRIPTS_PATH

USER 1001

CMD ["nginx", "-g", "daemon off;"]
"""

    @pytest.fixture
    def temp_dockerfile(self, sample_dockerfile_content):
        """Create a temporary Dockerfile for testing."""
        fd, temp_path = tempfile.mkstemp(suffix='.dockerfile', prefix='test_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(sample_dockerfile_content)
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix='dockerfile_test_')
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_dockerfile_processor_init_valid_file(self, temp_dockerfile):
        """Test DockerfileProcessor initialization with valid file."""
        processor = DockerfileProcessor(temp_dockerfile)
        assert processor.dockerfile_path == Path(temp_dockerfile)
        assert processor.dockerfile_path.exists()

    def test_dockerfile_processor_init_invalid_file(self):
        """Test DockerfileProcessor initialization with invalid file."""
        with pytest.raises(FileNotFoundError):
            DockerfileProcessor("/nonexistent/dockerfile")

    def test_process_nginx_version_env_replacement(self, temp_dockerfile):
        """Test replacement of ENV NGINX_VERSION line."""
        processor = DockerfileProcessor(temp_dockerfile)
        result = processor.process_nginx_version("1.24")

        # Check that ENV NGINX_VERSION was replaced
        assert "ENV NGINX_VERSION=1.24" in result
        assert "ENV NGINX_VERSION=1.20" not in result

    def test_process_nginx_version_variable_replacement(self, temp_dockerfile):
        """Test replacement of $NGINX_VERSION variables."""
        processor = DockerfileProcessor(temp_dockerfile)
        result = processor.process_nginx_version("1.24")

        # Check that $NGINX_VERSION was replaced
        assert "nginx-1.24" in result
        assert "nginx-$NGINX_VERSION" not in result

    def test_process_nginx_version_with_output_file(self, temp_dockerfile, temp_dir):
        """Test processing with output file."""
        processor = DockerfileProcessor(temp_dockerfile)
        output_path = Path(temp_dir) / "output.dockerfile"

        result = processor.process_nginx_version("1.26", output_path)

        # Check that output file was created
        assert output_path.exists()

        # Check content of output file
        with open(output_path, 'r') as f:
            content = f.read()

        assert content == result
        assert "ENV NGINX_VERSION=1.26" in content
        assert "nginx-1.26" in content

    def test_create_temp_dockerfile(self, temp_dockerfile):
        """Test creation of temporary Dockerfile."""
        processor = DockerfileProcessor(temp_dockerfile)
        temp_path = processor.create_temp_dockerfile("1.22")

        try:
            assert os.path.exists(temp_path)
            assert temp_path.endswith('.dockerfile')

            with open(temp_path, 'r') as f:
                content = f.read()

            assert "ENV NGINX_VERSION=1.22" in content
            assert "nginx-1.22" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.parametrize("version", [
        "1.20",
        "1.22",
        "1.24",
        "1.26",
        "1.22-micro",
        "1.24-micro"
    ])
    def test_process_different_versions(self, temp_dockerfile, version):
        """Test processing with different version formats."""
        processor = DockerfileProcessor(temp_dockerfile)
        result = processor.process_nginx_version(version)

        expected_env = f"ENV NGINX_VERSION={version}"
        expected_var = f"nginx-{version}"

        assert expected_env in result
        assert expected_var in result

    def test_validate_dockerfile_syntax_valid(self):
        """Test validation with valid Dockerfile content."""
        processor = DockerfileProcessor.__new__(DockerfileProcessor)  # Create without calling __init__

        valid_content = """FROM ubuntu:20.04
RUN apt-get update
ENV TEST=value
EXPOSE 80
CMD ["nginx"]
"""
        assert processor.validate_dockerfile_syntax(valid_content) is True

    def test_validate_dockerfile_syntax_invalid_no_from(self):
        """Test validation with invalid Dockerfile (no FROM)."""
        processor = DockerfileProcessor.__new__(DockerfileProcessor)

        invalid_content = """RUN apt-get update
ENV TEST=value
"""
        assert processor.validate_dockerfile_syntax(invalid_content) is False

    def test_validate_dockerfile_syntax_invalid_instruction(self):
        """Test validation with invalid instruction."""
        processor = DockerfileProcessor.__new__(DockerfileProcessor)

        invalid_content = """FROM ubuntu:20.04
INVALID_INSTRUCTION something
"""
        assert processor.validate_dockerfile_syntax(invalid_content) is False

    def test_validate_dockerfile_syntax_with_comments(self):
        """Test validation with comments and empty lines."""
        processor = DockerfileProcessor.__new__(DockerfileProcessor)

        content_with_comments = """# This is a comment
FROM ubuntu:20.04

# Another comment
RUN apt-get update
ENV TEST=value

# Final comment
CMD ["nginx"]
"""
        assert processor.validate_dockerfile_syntax(content_with_comments) is True

    def test_static_replace_version_in_file(self, temp_dockerfile, temp_dir):
        """Test static method for version replacement."""
        output_path = Path(temp_dir) / "static_output.dockerfile"

        DockerfileProcessor.replace_version_in_file(temp_dockerfile, "1.28", output_path)

        assert output_path.exists()

        with open(output_path, 'r') as f:
            content = f.read()

        assert "ENV NGINX_VERSION=1.28" in content
        assert "nginx-1.28" in content

    def test_process_preserves_other_content(self, temp_dockerfile):
        """Test that processing preserves other Dockerfile content."""
        processor = DockerfileProcessor(temp_dockerfile)
        result = processor.process_nginx_version("1.24")

        # Check that other content is preserved
        assert "FROM registry.redhat.io/ubi8/ubi:latest" in result
        assert "LABEL maintainer" in result
        assert "EXPOSE 8080" in result
        assert "USER 1001" in result
        assert "CMD [\"nginx\"" in result

    def test_multiple_env_nginx_version_lines(self, temp_dir):
        """Test handling of multiple ENV NGINX_VERSION lines."""
        content = """FROM ubuntu:20.04
ENV NGINX_VERSION=1.20
RUN some command
ENV NGINX_VERSION=1.22
CMD ["nginx"]
"""

        dockerfile_path = Path(temp_dir) / "multi_env.dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(content)

        processor = DockerfileProcessor(dockerfile_path)
        result = processor.process_nginx_version("1.26")

        # Both lines should be replaced
        assert result.count("ENV NGINX_VERSION=1.26") == 2
        assert "ENV NGINX_VERSION=1.20" not in result
        assert "ENV NGINX_VERSION=1.22" not in result

    def test_no_nginx_version_lines(self, temp_dir):
        """Test handling when no NGINX_VERSION lines exist."""
        content = """FROM ubuntu:20.04
ENV OTHER_VAR=value
RUN some command
CMD ["nginx"]
"""

        dockerfile_path = Path(temp_dir) / "no_nginx.dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(content)

        processor = DockerfileProcessor(dockerfile_path)
        result = processor.process_nginx_version("1.26")

        # Content should be unchanged except no $NGINX_VERSION to replace
        assert "ENV OTHER_VAR=value" in result
        assert "ENV NGINX_VERSION" not in result

    def test_edge_case_empty_file(self, temp_dir):
        """Test handling of empty Dockerfile."""
        dockerfile_path = Path(temp_dir) / "empty.dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write("")

        processor = DockerfileProcessor(dockerfile_path)
        result = processor.process_nginx_version("1.26")

        assert result == ""

    def test_edge_case_version_in_comments(self, temp_dir):
        """Test that versions in comments are not replaced."""
        content = """FROM ubuntu:20.04
# This uses NGINX_VERSION=1.20 but should not be replaced
ENV NGINX_VERSION=1.22
# Another comment with $NGINX_VERSION
RUN nginx-$NGINX_VERSION
"""

        dockerfile_path = Path(temp_dir) / "comments.dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(content)

        processor = DockerfileProcessor(dockerfile_path)
        result = processor.process_nginx_version("1.26")

        # ENV line should be replaced
        assert "ENV NGINX_VERSION=1.26" in result
        # Variable should be replaced
        assert "nginx-1.26" in result
        # Comments should remain unchanged
        assert "# This uses NGINX_VERSION=1.20 but should not be replaced" in result
        assert "# Another comment with $NGINX_VERSION" in result


@pytest.mark.integration
@pytest.mark.dockerfile
class TestDockerfileProcessorIntegration:
    """Integration tests that simulate the actual use case from the shell script."""

    @pytest.fixture
    def example_dockerfile_content(self):
        """Content similar to the actual examples/Dockerfile."""
        return """FROM registry.redhat.io/ubi8/s2i-base:1

ENV NGINX_VERSION=1.20 \
    NGINX_SHORT_VER=120 \
    NAME=nginx \
    VERSION=0

LABEL summary="Platform for running nginx or building nginx-based application" \
      description="Nginx $NGINX_VERSION available as container is a web server and a reverse proxy server."

RUN yum install -y centos-release-scl && \
    INSTALL_PKGS="nginx116 nginx116-nginx nginx116-nginx-mod-stream" && \
    yum install -y --setopt=tsflags=nodocs $INSTALL_PKGS && \
    yum clean all

COPY ./s2i/bin/ $STI_SCRIPTS_PATH
COPY ./root/ /

RUN /usr/libexec/s2i/assemble

USER 1001

EXPOSE 8080

CMD $STI_SCRIPTS_PATH/run
"""

    @pytest.fixture
    def example_dockerfile(self, example_dockerfile_content, temp_dir):
        """Create example Dockerfile for integration testing."""
        dockerfile_path = Path(temp_dir) / "Dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(example_dockerfile_content)
        return dockerfile_path

    def test_integration_sed_replacement_equivalent(self, example_dockerfile, temp_dir):
        """Test that our Python replacement produces equivalent results to sed command."""
        # Test with version that would be used in actual script
        test_version = "1.24"

        processor = DockerfileProcessor(example_dockerfile)
        result = processor.process_nginx_version(test_version)

        # Verify the exact transformations that sed would do
        assert f"ENV NGINX_VERSION={test_version}" in result
        assert "ENV NGINX_VERSION=1.20" not in result
        assert f"Nginx {test_version} available" in result
        assert "Nginx $NGINX_VERSION available" not in result

    def test_integration_micro_version(self, example_dockerfile):
        """Test with micro version as used in the actual script."""
        test_version = "1.22-micro"

        processor = DockerfileProcessor(example_dockerfile)
        result = processor.process_nginx_version(test_version)

        assert f"ENV NGINX_VERSION={test_version}" in result
        assert f"Nginx {test_version} available" in result

    def test_integration_dockerfile_s2i(self, temp_dir):
        """Test with Dockerfile.s2i content."""
        s2i_content = """FROM registry.redhat.io/ubi8/s2i-base:1

ENV NGINX_VERSION=1.20

LABEL io.k8s.description="Nginx $NGINX_VERSION" \
      io.k8s.display-name="Nginx $NGINX_VERSION"

USER 1001
"""

        dockerfile_path = Path(temp_dir) / "Dockerfile.s2i"
        with open(dockerfile_path, 'w') as f:
            f.write(s2i_content)

        processor = DockerfileProcessor(dockerfile_path)
        result = processor.process_nginx_version("1.26")

        assert "ENV NGINX_VERSION=1.26" in result
        assert "Nginx 1.26" in result
        # Should appear twice in the labels
        assert result.count("1.26") == 3  # ENV + 2 labels

    @pytest.mark.parametrize("dockerfile_name", ["Dockerfile", "Dockerfile.s2i"])
    def test_integration_both_dockerfile_types(self, temp_dir, dockerfile_name):
        """Test both Dockerfile types as used in the actual script."""
        content = """FROM registry.redhat.io/ubi8/s2i-base:1
ENV NGINX_VERSION=1.20
RUN echo "Installing nginx-$NGINX_VERSION"
"""

        dockerfile_path = Path(temp_dir) / dockerfile_name
        with open(dockerfile_path, 'w') as f:
            f.write(content)

        # Simulate the actual script usage
        output_path = Path(temp_dir) / f"processed_{dockerfile_name}"
        DockerfileProcessor.replace_version_in_file(dockerfile_path, "1.24", output_path)

        with open(output_path, 'r') as f:
            result = f.read()

        assert "ENV NGINX_VERSION=1.24" in result
        assert "Installing nginx-1.24" in result


@pytest.mark.unit
@pytest.mark.dockerfile
class TestDockerfileProcessorCommandLine:
    """Test the command-line interface."""

    def test_main_function_success(self, temp_dir):
        """Test successful command-line execution."""
        # Create input dockerfile
        input_content = "FROM ubuntu:20.04\nENV NGINX_VERSION=1.20\n"
        input_path = Path(temp_dir) / "input.dockerfile"
        output_path = Path(temp_dir) / "output.dockerfile"

        with open(input_path, 'w') as f:
            f.write(input_content)

        # Mock sys.argv
        test_args = ['dockerfile_processor.py', str(input_path), '1.24', str(output_path)]

        with patch('sys.argv', test_args):
            with patch('sys.exit') as mock_exit:
                from dockerfile_processor import main
                main()
                mock_exit.assert_not_called()

        # Verify output
        assert output_path.exists()
        with open(output_path, 'r') as f:
            content = f.read()
        assert "ENV NGINX_VERSION=1.24" in content

    def test_main_function_wrong_args(self):
        """Test command-line with wrong number of arguments."""
        with patch('sys.argv', ['dockerfile_processor.py', 'arg1']):
            with patch('sys.exit') as mock_exit:
                with patch('builtins.print') as mock_print:
                    from dockerfile_processor import main
                    main()
                    mock_exit.assert_called_with(1)
                    mock_print.assert_called_with(
                        "Usage: python dockerfile_processor.py <dockerfile_path> <version> <output_path>")


@pytest.mark.unit
@pytest.mark.dockerfile
class TestDockerfileProcessorErrorHandling:
    """Test error handling scenarios."""

    def test_file_permission_error(self, temp_dir):
        """Test handling of file permission errors."""
        dockerfile_path = Path(temp_dir) / "test.dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write("FROM ubuntu:20.04\n")

        # Make file read-only
        os.chmod(dockerfile_path, 0o444)

        processor = DockerfileProcessor(dockerfile_path)

        # Try to write to a read-only directory
        readonly_output = Path(temp_dir) / "readonly"
        readonly_output.mkdir()
        os.chmod(readonly_output, 0o444)

        with pytest.raises(PermissionError):
            processor.process_nginx_version("1.24", readonly_output / "output.dockerfile")

    def test_invalid_utf8_content(self, temp_dir):
        """Test handling of files with invalid UTF-8 content."""
        dockerfile_path = Path(temp_dir) / "invalid.dockerfile"

        # Write invalid UTF-8 content
        with open(dockerfile_path, 'wb') as f:
            f.write(b"FROM ubuntu:20.04\n\xff\xfe\n")

        processor = DockerfileProcessor(dockerfile_path)

        # Should handle gracefully or raise appropriate exception
        with pytest.raises(UnicodeDecodeError):
            processor.process_nginx_version("1.24")
