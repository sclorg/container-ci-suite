#!/bin/env python3

# MIT License
#
# Copyright (c) 2018-2019 Red Hat, Inc.

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

import pytest
import subprocess

from unittest.mock import patch
from flexmock import flexmock

from container_ci_suite.openshift import OpenShiftAPI
from container_ci_suite.engines.openshift import OpenShiftOperations
from container_ci_suite.engines.container import PodmanCLIWrapper
from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite import utils
from tests.spellbook import DATA_DIR


class TestCreateOpenshiftProject(object):
    """
    Tests for OpenShiftAPI._create_openshift_project.
    """

    @pytest.mark.parametrize(
        "namespace", ["sclorg-12345", "core-services-ocp--sclorg-99999"]
    )
    def test_create_openshift_project_success(self, namespace):
        """
        _create_openshift_project returns True when oc new-project succeeds.
        """
        oc_api = OpenShiftAPI(namespace=namespace)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            f"new-project {namespace}",
            json_output=False,
            return_output=True,
        ).and_return("Now using project").once()

        assert oc_api._create_openshift_project() is True

    def test_create_openshift_project_called_process_error_returns_false(self):
        """
        _create_openshift_project returns False when oc new-project raises CalledProcessError.
        """
        oc_api = OpenShiftAPI(namespace="sclorg-fail")
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "new-project sclorg-fail",
            json_output=False,
            return_output=True,
        ).and_raise(subprocess.CalledProcessError(1, "oc")).once()

        assert oc_api._create_openshift_project() is False


class TestCreateProject(object):
    """
    Tests for OpenShiftAPI.create_project.
    """

    @pytest.mark.parametrize("project_exists", [True, False])
    def test_create_project_when_create_prj_false(self, project_exists):
        """
        When create_prj is False, run oc project and return is_project_exists().
        """
        namespace = "container-ci-suite-test"
        oc_api = OpenShiftAPI(namespace=namespace)
        assert oc_api.create_prj is False
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            f"project {namespace}",
            json_output=False,
        ).once()
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            project_exists
        )
        assert oc_api.create_project() is project_exists
        assert oc_api.project_created

    def test_create_project_non_shared_first_attempt_succeeds(self):
        """
        Non-shared cluster: login, new-project succeeds on first try, then is_project_exists.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = False
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").with_args(
            shared_cluster=False
        ).and_return(True)
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("_create_openshift_project").and_return(
            True
        ).once()
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            True
        )

        assert oc_api.create_project() is True
        assert oc_api.project_created

    def test_create_project_non_shared_is_project_exists_false(self):
        """
        Non-shared: project creation succeeds but is_project_exists returns False.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = False
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").and_return(
            True
        )
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("_create_openshift_project").and_return(
            True
        )
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            False
        )

        assert oc_api.create_project() is False
        assert oc_api.project_created

    @patch("container_ci_suite.openshift.sleep")
    def test_create_project_non_shared_retries_then_succeeds(self, mock_sleep):
        """
        Non-shared: _create_openshift_project fails twice, succeeds on third attempt.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = False
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").and_return(
            True
        )
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("_create_openshift_project").and_return(
            False
        ).and_return(False).and_return(True)
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            True
        )

        assert oc_api.create_project() is True
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(3)

    @patch("container_ci_suite.openshift.sleep")
    def test_create_project_non_shared_retries_exhausted_returns_false(self, mock_sleep):
        """
        Non-shared: all three new-project attempts fail; returns False.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = False
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").and_return(
            True
        )
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("_create_openshift_project").and_return(
            False
        ).times(3)
        assert oc_api.create_project() is False
        assert not oc_api.project_created
        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(3)

    def test_create_project_shared_cluster_prepare_tenant_fails(self):
        """
        Shared cluster: prepare_tenant_namespace failure stops create_project.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = True
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").with_args(
            shared_cluster=True
        ).and_return(True)
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("prepare_tenant_namespace").and_return(
            False
        )

        assert oc_api.create_project() is False
        assert not oc_api.project_created

    def test_create_project_shared_cluster_success(self):
        """
        Shared cluster: prepare_tenant_namespace succeeds, then is_project_exists.
        """
        oc_api = OpenShiftAPI(namespace="ignored")
        oc_api.create_prj = True
        oc_api.shared_cluster = True
        flexmock(OpenShiftOperations).should_receive("login_to_cluster").with_args(
            shared_cluster=True
        ).and_return(True)
        flexmock(OpenShiftOperations).should_receive("set_namespace").and_return(None)
        flexmock(OpenShiftAPI).should_receive("prepare_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            True
        )

        assert oc_api.create_project() is True
        assert oc_api.project_created


class TestOpenShiftCISuite(object):
    """
    Test OpenShift API suite.
    """

    oc_api = None
    oc_ops = None

    def setup_method(self):
        """
        Setup the test environment.
        """
        self.oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        self.oc_ops = OpenShiftOperations()
        self.oc_ops.set_namespace(namespace="container-ci-suite-test")

    @pytest.mark.parametrize(
        "container,dir_name,filename,branch",
        [
            ("postgresql-container", "imagestreams", "postgres-rhel.json", "master"),
            ("mysql-container", "openshift/templates", "foo.json", "bar"),
        ],
    )
    def test_get_raw_url_for_json(self, container, dir_name, filename, branch):
        """
        Test getting the raw URL for a JSON file.
        """
        expected_output = f"https://raw.githubusercontent.com/sclorg/{container}/{branch}/{dir_name}/{filename}"
        assert (
            utils.get_raw_url_for_json(
                container=container, dir=dir_name, filename=filename, branch=branch
            )
            == expected_output
        )

    def test_upload_image_pull_failed(self):
        """
        Test uploading an image pull failed.
        """
        flexmock(PodmanCLIWrapper).should_receive("podman_pull_image").and_return(False)
        assert not self.oc_api.upload_image(
            source_image="foobar", tagged_image="foobar:latest"
        )

    def test_upload_image_login_failed(self):
        """
        Test uploading an image login failed.
        """
        flexmock(PodmanCLIWrapper).should_receive("podman_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("podman_login_to_openshift").and_return(
            None
        )
        assert not self.oc_api.upload_image(
            source_image="foobar", tagged_image="foobar:latest"
        )

    def test_upload_image_success(self):
        """
        Test uploading an image success.
        """
        flexmock(PodmanCLIWrapper).should_receive("podman_pull_image").and_return(True)
        flexmock(OpenShiftAPI).should_receive("podman_login_to_openshift").and_return(
            "default_registry"
        )
        flexmock(ContainerTestLibUtils).should_receive("run_command").twice()
        assert self.oc_api.upload_image(
            source_image="foobar", tagged_image="foobar:latest"
        )

    def test_update_template_example_file_without_pvc(self, get_ephemeral_template):
        """
        Test updating a template example file without PVC.
        """
        flexmock(utils).should_receive("get_json_data").and_return(
            get_ephemeral_template
        )
        json_data = self.oc_api.update_template_example_file(
            file_name=f"{DATA_DIR}/example_ephemeral_template.json"
        )
        assert json_data
        assert "PersistentVolumeClaim" not in json_data["objects"][0]["kind"]

    def test_update_template_example_file_with_pvc(self, get_persistent_template):
        """
        Test updating a template example file with PVC.
        """
        flexmock(utils).should_receive("get_json_data").and_return(
            get_persistent_template
        )
        flexmock(utils).should_receive("get_shared_variable").and_return(
            "SOMETHING-001"
        )
        json_data = self.oc_api.update_template_example_file(
            file_name=f"{DATA_DIR}/example_persistent_template.json"
        )
        assert json_data
        assert json_data["objects"][0]["kind"] == "PersistentVolumeClaim"
        metadata = json_data["objects"][0]["metadata"]
        assert "annotations" in metadata
        assert "trident.netapp.io/reclaimPolicy" in metadata["annotations"]
        assert metadata["annotations"]["trident.netapp.io/reclaimPolicy"] == "Delete"
        assert "labels" in metadata
        assert "paas.redhat.com/appcode" in metadata["labels"]
        assert metadata["labels"]["paas.redhat.com/appcode"] == "SOMETHING-001"
        assert json_data["objects"][0]["spec"]["storageClassName"] == "netapp-nfs"
        assert json_data["objects"][0]["spec"]["volumeMode"] == "Filesystem"

    def test_update_template_without_modification(self, postgresql_json):
        """
        Test updating a template without modification.
        """
        flexmock(utils).should_receive("get_json_data").and_return(postgresql_json)
        flexmock(utils).should_receive("get_shared_variable").and_return(
            "SOMETHING-001"
        )
        json_data = self.oc_api.update_template_example_file(
            file_name=f"{DATA_DIR}/postgresql_imagestreams.json"
        )
        assert json_data
        assert "objects" not in json_data

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_success(self, mock_sleep):
        """
        Test prepare_tenant_namespace when all steps succeed.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_return("core-services-ocp--config ")
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("is_tenant_namespace_created").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("apply_tenant_egress_rules").and_return(
            True
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project core-services-ocp--sclorg-12345",
            json_output=False,
            return_output=True,
        ).and_return(None)

        self.oc_api.prepare_tenant_namespace()

        assert self.oc_api.project_created
        mock_sleep.assert_called_once_with(10)

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_switches_project_when_different_namespace(
        self, mock_sleep
    ):
        """
        Test prepare_tenant_namespace switches to config project when current namespace differs.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_return("default ")
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "project core-services-ocp--config", json_output=False
        ).and_return(None)
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("is_tenant_namespace_created").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("apply_tenant_egress_rules").and_return(
            True
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project core-services-ocp--sclorg-12345",
            json_output=False,
            return_output=True,
        ).and_return(None)

        self.oc_api.prepare_tenant_namespace()

        assert self.oc_api.project_created

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_create_tenant_fails(self, mock_sleep):
        """
        Test prepare_tenant_namespace returns False when create_tenant_namespace fails.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").and_return(
            "core-services-ocp--config "
        )
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            False
        )

        result = self.oc_api.prepare_tenant_namespace()

        assert result is False
        assert not self.oc_api.project_created
        mock_sleep.assert_not_called()

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_is_tenant_created_fails(self, mock_sleep):
        """
        Test prepare_tenant_namespace returns False when is_tenant_namespace_created fails.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").and_return(
            "core-services-ocp--config "
        )
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("is_tenant_namespace_created").and_return(
            False
        )

        result = self.oc_api.prepare_tenant_namespace()

        assert result is False
        assert not self.oc_api.project_created
        mock_sleep.assert_called_once_with(10)

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_apply_egress_fails(self, mock_sleep):
        """
        Test prepare_tenant_namespace returns False when apply_tenant_egress_rules fails.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").and_return(
            "core-services-ocp--config "
        )
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("is_tenant_namespace_created").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("apply_tenant_egress_rules").and_return(
            False
        )

        result = self.oc_api.prepare_tenant_namespace()

        assert result is False
        assert not self.oc_api.project_created

    @patch("container_ci_suite.openshift.time.sleep")
    def test_prepare_tenant_namespace_handles_called_process_error(self, mock_sleep):
        """
        Test prepare_tenant_namespace handles CalledProcessError when getting current project.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.namespace = "core-services-ocp--sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_raise(subprocess.CalledProcessError(1, "oc"))
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "project core-services-ocp--config", json_output=False
        ).and_return(None)
        flexmock(OpenShiftAPI).should_receive("create_tenant_namespace").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("is_tenant_namespace_created").and_return(
            True
        )
        flexmock(OpenShiftAPI).should_receive("apply_tenant_egress_rules").and_return(
            True
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project core-services-ocp--sclorg-12345",
            json_output=False,
            return_output=True,
        ).and_return(None)

        self.oc_api.prepare_tenant_namespace()

        assert self.oc_api.project_created

    def test_delete_tenant_namespace_skipped_when_in_config_namespace(self):
        """
        Test delete_tenant_namespace returns early when current project is config tenant.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_return("core-services-ocp--config").once()

        self.oc_api.delete_tenant_namespace()

        # Only project -q should be called, no delete or project switch

    def test_delete_tenant_namespace_success(self):
        """
        Test delete_tenant_namespace when delete succeeds.
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_return("some-other-namespace ").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "project core-services-ocp--config", json_output=False
        ).and_return(None).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "delete tenantnamespace sclorg-12345", json_output=False
        ).and_return("tenantnamespace deleted").once()

        self.oc_api.delete_tenant_namespace()

    def test_delete_tenant_namespace_delete_returns_falsy(self):
        """
        Test delete_tenant_namespace when delete command returns falsy (e.g. empty string).
        """
        self.oc_api.shared_random_name = "sclorg-12345"
        self.oc_api.config_tenant_name = "core-services-ocp--config"

        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd="project -q", json_output=False
        ).and_return("some-other-namespace ").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "project core-services-ocp--config", json_output=False
        ).and_return(None).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "delete tenantnamespace sclorg-12345", json_output=False
        ).and_return("").once()

        self.oc_api.delete_tenant_namespace()
