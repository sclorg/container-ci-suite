# MIT License
#
# Copyright (c) 2020 SCL team at Red Hat
#
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
import tempfile
import shutil
import json
import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

from container_ci_suite.container_lib import ContainerTestLib

from tests.spellbook import DATA_DIR


def create_ca_file():
    CA_FILE_PATH = "/tmp/CA_FILE_PATH"
    with open(CA_FILE_PATH, "w") as f:
        f.write("foobar")
    os.environ["NPM_REGISTRY"] = "foobar"


def delete_ca_file():
    CA_FILE_PATH = "/tmp/CA_FILE_PATH"
    p = Path(CA_FILE_PATH)
    p.unlink()
    os.unsetenv("NPM_REGISTRY")


def s2i_build_as_df_fedora_test_app():
    return [
        "FROM quay.io/fedora/nodejs-16",
        f"LABEL io.openshift.s2i.build.image=quay.io/fedora/nodejs-16 "
        f"io.openshift.s2i.build.source-location=file://{DATA_DIR}/test-app",
        "USER root",
        "COPY upload/src/ /tmp/src",
        "RUN chown -R 1001:0 /tmp/src",
        "ENV NODE_ENV=development",
        "USER 1001",
        "RUN /usr/libexec/s2i/assemble",
        "CMD /usr/libexec/s2i/run",
    ]


@pytest.fixture
def postgresql_json():
    return json.loads((DATA_DIR / "postgresql_imagestreams.json").read_text())


@pytest.fixture
def package_installation_json():
    return json.loads((DATA_DIR / "postgresql_package_installation.json").read_text())


@pytest.fixture
def helm_package_success():
    with open(DATA_DIR / "helm_package_successful.txt") as fd:
        lines = fd.readline()
    return lines


@pytest.fixture
def helm_package_failed():
    with open(DATA_DIR / "helm_package_failed.txt") as fd:
        lines = fd.readline()
    return lines


@pytest.fixture
def helm_list_json():
    return json.loads((DATA_DIR / "helm_list.json").read_text())


@pytest.fixture()
def oc_get_is_ruby_json():
    return json.loads((DATA_DIR / "oc_get_is_ruby.json").read_text())


@pytest.fixture()
def oc_build_pod_not_finished_json():
    return json.loads((DATA_DIR / "oc_build_pod_not_finished.json").read_text())


@pytest.fixture()
def oc_build_pod_finished_json():
    return json.loads((DATA_DIR / "oc_build_pod_finished.json").read_text())


@pytest.fixture()
def oc_is_pod_running():
    return json.loads((DATA_DIR / "oc_is_pod_running.json").read_text())


@pytest.fixture()
def get_chart_yaml():
    return yaml.safe_load((DATA_DIR / "Chart.yaml").read_text())


@pytest.fixture()
def get_svc_ip():
    return json.loads((DATA_DIR / "oc_get_svc.json").read_text())


@pytest.fixture()
def get_svc_ip_empty():
    return json.loads((DATA_DIR / "oc_get_svc_empty.json").read_text())


@pytest.fixture()
def get_ephemeral_template():
    return json.loads((DATA_DIR / "example_ephemeral_template.json").read_text())


@pytest.fixture()
def get_persistent_template():
    return json.loads((DATA_DIR / "example_persistent_template.json").read_text())


@pytest.fixture
def container_test_lib():
    """Create a ContainerTestLib instance for testing."""
    return ContainerTestLib()


@pytest.fixture
def initialized_container_test_lib():
    """Create and initialize a ContainerTestLib instance for testing."""
    ct_lib = ContainerTestLib()
    yield ct_lib
    # Cleanup after test
    try:
        ct_lib.cleanup()
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
    with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command') as mock:
        yield mock


@pytest.fixture
def mock_podman_wrapper():
    """Mock the PodmanCLIWrapper."""
    with patch('container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper') as mock:
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
        if 'podman images -q' in cmd:
            return "sha256:abc123" if return_output else 0
        elif 'podman inspect' in cmd and 'State.Running' in cmd:
            return "true" if return_output else 0
        elif 'podman inspect' in cmd and 'State.ExitCode' in cmd:
            return "0" if return_output else 0
        elif 'podman inspect' in cmd and 'NetworkSettings.IPAddress' in cmd:
            return "172.27.0.2" if return_output else 0
        elif 'podman ps -q -a' in cmd:
            return "container123" if return_output else 0
        elif 'podman pull' in cmd:
            return "Successfully pulled" if return_output else 0
        elif 'podman build' in cmd:
            return "Successfully built abc123\nabc123" if return_output else 0
        elif 'podman run' in cmd and 'env' in cmd:
            return "PATH=/usr/bin\nX_SCLS=nodejs16" if return_output else 0
        elif 'podman run' in cmd and 'npm --version' in cmd:
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

    with patch('container_ci_suite.utils.ContainerTestLibUtils.run_command', side_effect=mock_command) as mock:
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

    with patch('container_ci_suite.utils.get_file_content', side_effect=mock_get_file_content), \
         patch('pathlib.Path.exists', mock_file_exists), \
         patch('pathlib.Path.is_file', lambda self: True), \
         patch('pathlib.Path.is_dir', lambda self: False):
        yield mock_files


@pytest.fixture
def clean_environment():
    """Clean environment variables for testing."""
    original_env = os.environ.copy()
    # Remove test-related environment variables
    test_vars = ['NPM_REGISTRY', 'DEBUG', 'IGNORE_UNSTABLE_TESTS']
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
