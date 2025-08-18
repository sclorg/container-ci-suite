"""
Pytest configuration and fixtures for Container Test Library tests.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from container_test_lib import ContainerTestLib


@pytest.fixture
def container_test_lib():
    """Create a ContainerTestLib instance for testing."""
    return ContainerTestLib()


@pytest.fixture
def initialized_container_test_lib():
    """Create and initialize a ContainerTestLib instance for testing."""
    ct_lib = ContainerTestLib()
    ct_lib.ct_init()
    yield ct_lib
    # Cleanup after test
    try:
        ct_lib.ct_cleanup()
    except Exception:
        pass  # Ignore cleanup errors in tests


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_run_command():
    """Mock the run_command function."""
    with patch('container_test_lib.run_command') as mock:
        yield mock


@pytest.fixture
def mock_podman_wrapper():
    """Mock the PodmanCLIWrapper."""
    with patch('container_test_lib.PodmanCLIWrapper') as mock:
        yield mock


@pytest.fixture
def sample_dockerfile_content():
    """Sample Dockerfile content for testing."""
    return """FROM registry.redhat.io/rhel8/nodejs-16
RUN npm install -g express
COPY . /app
WORKDIR /app
CMD ["node", "server.js"]
"""


@pytest.fixture
def sample_environment_vars():
    """Sample environment variables for testing."""
    return {
        'X_SCLS': 'nodejs16',
        'PATH': '/opt/rh/nodejs16/bin:/usr/local/bin:/usr/bin:/bin',
        'LD_LIBRARY_PATH': '/opt/rh/nodejs16/lib64',
        'NODEJS_VERSION': '16'
    }


@pytest.fixture
def mock_docker_commands():
    """Mock common docker commands."""
    def mock_command(cmd, return_output=True, ignore_error=False, **kwargs):
        if 'docker images -q' in cmd:
            return "sha256:abc123" if return_output else 0
        elif 'docker inspect' in cmd and 'State.Running' in cmd:
            return "true" if return_output else 0
        elif 'docker inspect' in cmd and 'State.ExitCode' in cmd:
            return "0" if return_output else 0
        elif 'docker inspect' in cmd and 'NetworkSettings.IPAddress' in cmd:
            return "172.17.0.2" if return_output else 0
        elif 'docker ps -q -a' in cmd:
            return "container123" if return_output else 0
        elif 'docker pull' in cmd:
            return "Successfully pulled" if return_output else 0
        elif 'docker build' in cmd:
            return "Successfully built abc123\nabc123" if return_output else 0
        elif 'docker run' in cmd and 'env' in cmd:
            return "PATH=/usr/bin\nX_SCLS=nodejs16" if return_output else 0
        elif 'docker run' in cmd and 'npm --version' in cmd:
            return "8.19.2" if return_output else 0
        elif 'curl' in cmd:
            return "Welcome to the app200" if return_output else 0
        elif cmd in ['true']:
            return "" if return_output else 0
        elif cmd in ['false']:
            if ignore_error:
                return "" if return_output else 1
            else:
                from subprocess import CalledProcessError
                raise CalledProcessError(1, cmd)
        else:
            return "" if return_output else 0
    
    with patch('container_test_lib.run_command', side_effect=mock_command) as mock:
        yield mock


@pytest.fixture
def mock_file_operations():
    """Mock file operations for testing."""
    mock_files = {}
    
    def mock_get_file_content(filename):
        path_str = str(filename)
        if path_str in mock_files:
            return mock_files[path_str]
        elif 'cid' in path_str:
            return "container123"
        else:
            return "mock_content"
    
    def mock_file_exists(self):
        return str(self) in mock_files or 'test' in str(self)
    
    with patch('container_test_lib.get_file_content', side_effect=mock_get_file_content), \
         patch('pathlib.Path.exists', mock_file_exists), \
         patch('pathlib.Path.is_file', lambda self: True), \
         patch('pathlib.Path.is_dir', lambda self: False):
        yield mock_files


@pytest.fixture
def clean_environment():
    """Clean environment variables for testing."""
    original_env = os.environ.copy()
    # Remove test-related environment variables
    test_vars = ['UNSTABLE_TESTS', 'NPM_REGISTRY', 'DEBUG', 'IGNORE_UNSTABLE_TESTS']
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_subprocess_error():
    """Mock subprocess.CalledProcessError for testing."""
    from subprocess import CalledProcessError
    return CalledProcessError(1, "mock_command", "mock_output")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires docker)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )
