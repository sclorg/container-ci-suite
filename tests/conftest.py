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
import json
import yaml
from pathlib import Path

import pytest

from container_ci_suite.constants import CA_FILE_PATH

from tests.spellbook import DATA_DIR


def create_ca_file():
    with open(CA_FILE_PATH, "w") as f:
        f.write("foobar")
    os.environ["NPM_REGISTRY"] = "foobar"


def delete_ca_file():
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
