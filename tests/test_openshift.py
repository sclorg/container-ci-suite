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
import shlex
import subprocess

from unittest.mock import MagicMock, patch
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


class TestCreateTenantNamespace(object):
    """
    Tests for OpenShiftAPI.create_tenant_namespace.
    """

    def _make_api(self, shared_random_name: str = "sclorg-54321"):
        oc_api = OpenShiftAPI(namespace="test-tenant-ns")
        oc_api.shared_random_name = shared_random_name
        return oc_api

    def test_create_tenant_namespace_success(self):
        """
        Returns True when oc create -f exits with code 0.
        """
        yaml_path = "/tmp/tenant-namespace-yml-abc123.yaml"
        oc_api = self._make_api()
        flexmock(utils).should_receive("save_tenant_namespace_yaml").with_args(
            project_name="sclorg-54321"
        ).and_return(yaml_path).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=f"create -f {yaml_path}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        ).and_return(0).once()

        assert oc_api.create_tenant_namespace() is True

    @pytest.mark.parametrize("exit_code", [1, 2, 255])
    def test_create_tenant_namespace_nonzero_exit_returns_false(self, exit_code):
        """
        Returns False when oc create -f reports a non-zero exit (ignore_error path).
        """
        yaml_path = f"/tmp/tenant-namespace-fail-{exit_code}.yaml"
        oc_api = self._make_api(shared_random_name="sclorg-99999")
        flexmock(utils).should_receive("save_tenant_namespace_yaml").with_args(
            project_name="sclorg-99999"
        ).and_return(yaml_path).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=f"create -f {yaml_path}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        ).and_return(exit_code).once()

        assert oc_api.create_tenant_namespace() is False


class TestIsTenantNamespaceCreated(object):
    """
    Tests for OpenShiftAPI.is_tenant_namespace_created.
    """

    def _make_api(self, shared_random_name: str = "sclorg-54321"):
        oc_api = OpenShiftAPI(namespace="test-tenant-ns")
        oc_api.shared_random_name = shared_random_name
        return oc_api

    def test_is_tenant_namespace_created_true_on_first_check(self):
        """
        Returns True when is_project_exists is True on the first iteration.
        """
        oc_api = self._make_api()
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            True
        ).once()

        assert oc_api.is_tenant_namespace_created() is True

    @patch("container_ci_suite.openshift.sleep")
    def test_is_tenant_namespace_created_true_after_waiting(self, mock_sleep):
        """
        Retries until is_project_exists becomes True, sleeping 5s between checks.
        """
        oc_api = self._make_api()
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            False
        ).and_return(False).and_return(True)

        assert oc_api.is_tenant_namespace_created() is True
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(5)

    @patch("container_ci_suite.openshift.sleep")
    def test_is_tenant_namespace_created_false_when_never_exists(self, mock_sleep):
        """
        Returns False when is_project_exists stays False for all iterations.
        """
        oc_api = self._make_api()
        flexmock(OpenShiftOperations).should_receive("is_project_exists").and_return(
            False
        ).times(5)

        assert oc_api.is_tenant_namespace_created() is False
        assert mock_sleep.call_count == 5
        mock_sleep.assert_called_with(5)


class TestCreateLimitRanges(object):
    """
    Tests for OpenShiftAPI.create_limit_ranges.
    """

    def _make_api(self, shared_random_name: str = "sclorg-54321"):
        oc_api = OpenShiftAPI(namespace="test-tenant-ns")
        oc_api.shared_random_name = shared_random_name
        return oc_api

    def test_create_limit_ranges_success_first_attempt(self):
        """
        Returns True when oc apply -f exits with code 0 on the first try.
        """
        yaml_path = "/tmp/tenant-limit-yml-abc.yaml"
        oc_api = self._make_api()
        flexmock(utils).should_receive("save_tenant_limit_yaml").and_return(
            yaml_path
        ).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=f"apply -f {yaml_path}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        ).and_return(0).once()

        assert oc_api.create_limit_ranges() is True

    @patch("container_ci_suite.openshift.sleep")
    def test_create_limit_ranges_success_after_retry(self, mock_sleep):
        """
        Retries apply when oc returns non-zero, then succeeds on the second attempt.
        """
        yaml_path = "/tmp/tenant-limit-retry.yaml"
        oc_api = self._make_api()
        flexmock(utils).should_receive("save_tenant_limit_yaml").and_return(
            yaml_path
        ).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=f"apply -f {yaml_path}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        ).and_return(1).and_return(0)

        assert oc_api.create_limit_ranges() is True
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(5)

    @patch("container_ci_suite.openshift.sleep")
    def test_create_limit_ranges_false_when_all_attempts_fail(self, mock_sleep):
        """
        Returns False when every apply attempt returns a non-zero exit code.
        """
        yaml_path = "/tmp/tenant-limit-fail.yaml"
        oc_api = self._make_api()
        flexmock(utils).should_receive("save_tenant_limit_yaml").and_return(
            yaml_path
        ).once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=f"apply -f {yaml_path}",
            json_output=False,
            ignore_error=True,
            return_output=False,
            debug=True,
        ).and_return(1).times(10)

        assert oc_api.create_limit_ranges() is False
        assert mock_sleep.call_count == 10
        mock_sleep.assert_called_with(5)


class TestUploadImageToExternalRegistry(object):
    """
    Tests for OpenShiftAPI.upload_image_to_external_registry.
    """

    def test_upload_image_to_external_registry_returns_none_when_login_fails(self):
        """
        When login_external_registry returns falsy, return None without podman/oc calls.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        flexmock(OpenShiftAPI).should_receive("login_external_registry").and_return(None)
        flexmock(ContainerTestLibUtils).should_receive("run_command").never()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").never()

        assert oc_api.upload_image_to_external_registry("quay.io/foo:1", "myimg:latest") is None

    @patch("container_ci_suite.openshift.time.sleep")
    def test_upload_image_to_external_registry_success(self, mock_sleep):
        """
        Tags, pushes, imports image and returns True after a short sleep.
        """
        registry = "registry.example.com"
        source_image = "quay.io/foo/bar:1"
        tagged_image = "myimg:latest"
        output_name = f"{registry}/core-services-ocp/{tagged_image}"

        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        flexmock(OpenShiftAPI).should_receive("login_external_registry").and_return(
            registry
        )
        flexmock(ContainerTestLibUtils).should_receive("run_command").with_args(
            "podman images"
        ).and_return("REPOSITORY TAG\n").once()
        flexmock(ContainerTestLibUtils).should_receive("run_command").with_args(
            f"podman tag {source_image} {output_name}",
            ignore_error=False,
            return_output=True,
        ).and_return("tagged").once()
        flexmock(ContainerTestLibUtils).should_receive("run_command").with_args(
            f"podman push {output_name}",
            ignore_error=False,
            return_output=True,
        ).and_return("pushed").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            f"import-image {tagged_image} --from={output_name} --confirm",
            json_output=False,
            return_output=True,
        ).and_return("imported").once()

        assert oc_api.upload_image_to_external_registry(source_image, tagged_image) is True
        mock_sleep.assert_called_once_with(3)


class TestCommandAppRun(object):
    """
    Tests for OpenShiftAPI.command_app_run.
    """

    @staticmethod
    def _expected_oc_cmd(user_cmd: str) -> str:
        return f"exec command-app -- bash -c {shlex.quote(user_cmd)}"

    def test_command_app_run_returns_oc_command_output(self):
        """
        Builds exec command-app with shlex-quoted bash -c and returns run_oc_command result.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        user_cmd = "echo $((11*11))"
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=self._expected_oc_cmd(user_cmd),
            ignore_error=True,
            return_output=True,
            json_output=False,
        ).and_return("121\n").once()

        assert oc_api.command_app_run(user_cmd) == "121\n"

    def test_command_app_run_passes_return_output_false(self):
        """
        Forwards return_output=False to run_oc_command (e.g. exit code only).
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        user_cmd = "true"
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            cmd=self._expected_oc_cmd(user_cmd),
            ignore_error=True,
            return_output=False,
            json_output=False,
        ).and_return(0).once()

        assert oc_api.command_app_run(user_cmd, return_output=False) == 0


class TestDeployS2iApp(object):
    """
    Tests for OpenShiftAPI.deploy_s2i_app.
    """

    def test_deploy_s2i_app_returns_false_when_project_not_created(self):
        """
        Short-circuits when project_created is False.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = False
        assert oc_api.deploy_s2i_app("img", "app", ".") is False

    def test_deploy_s2i_app_returns_false_when_upload_image_fails(self):
        """
        Non-shared cluster: upload_image failure returns False before new-app.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        flexmock(utils).should_receive("get_tagged_image").and_return("registry/x:1")
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(False)

        assert oc_api.deploy_s2i_app("quay.io/foo", "https://example.com/app.git", ".") is False

    def test_deploy_s2i_app_returns_false_when_upload_external_fails(self):
        """
        Shared cluster: upload_image_to_external_registry failure returns False.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = True
        flexmock(utils).should_receive("get_tagged_image").and_return("registry/x:1")
        flexmock(OpenShiftAPI).should_receive("upload_image_to_external_registry").and_return(
            False
        )

        assert oc_api.deploy_s2i_app("quay.io/foo", "https://example.com/app.git", ".") is False

    @patch("container_ci_suite.openshift.time.sleep")
    @patch("container_ci_suite.openshift.Path")
    def test_deploy_s2i_app_returns_false_when_new_app_raises(
        self, mock_path, mock_sleep
    ):
        """
        CalledProcessError from oc new-app is caught and returns False.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        path_inst = MagicMock()
        path_inst.is_dir.return_value = False
        mock_path.return_value = path_inst

        flexmock(utils).should_receive("get_tagged_image").and_return("registry/x:1")
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(True)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").and_raise(
            subprocess.CalledProcessError(1, "oc", output=b"fail")
        )

        assert (
            oc_api.deploy_s2i_app(
                "quay.io/foo",
                "https://example.com/app.git",
                ".",
                service_name="svc",
            )
            is False
        )
        mock_sleep.assert_not_called()

    @patch("container_ci_suite.openshift.time.sleep")
    @patch("container_ci_suite.openshift.Path")
    def test_deploy_s2i_app_success_with_explicit_service_name(self, mock_path, mock_sleep):
        """
        Runs new-app with tagged image, app URL, context-dir, and name; then sleeps.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        path_inst = MagicMock()
        path_inst.is_dir.return_value = False
        mock_path.return_value = path_inst

        tagged = "registry/ns/foo:1"
        flexmock(utils).should_receive("get_tagged_image").and_return(tagged)
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(True)
        expected_cmd = (
            f"new-app {tagged}~https://github.com/sclorg/s2i.git "
            "--strategy=source --context-dir=src --name=myapp"
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            expected_cmd,
            json_output=False,
        ).and_return("created").once()

        assert (
            oc_api.deploy_s2i_app(
                "quay.io/foo",
                "https://github.com/sclorg/s2i.git",
                "src",
                service_name="myapp",
            )
            is True
        )
        mock_sleep.assert_called_once_with(3)

    @patch("container_ci_suite.openshift.time.sleep")
    @patch("container_ci_suite.openshift.Path")
    def test_deploy_s2i_app_uses_get_service_default_name(self, mock_path, mock_sleep):
        """
        Empty service_name uses utils.get_service_image(image_name).
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        path_inst = MagicMock()
        path_inst.is_dir.return_value = False
        mock_path.return_value = path_inst

        tagged = "registry/ns/foo:1"
        flexmock(utils).should_receive("get_tagged_image").and_return(tagged)
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(True)
        flexmock(utils).should_receive("get_service_image").with_args(
            image_name="quay.io/foo"
        ).and_return("derived-svc")
        oc_cmd = (
            f"new-app {tagged}~https://github.com/x.git "
            "--strategy=source --context-dir=. --name=derived-svc"
        )
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            oc_cmd,
            json_output=False,
        ).and_return("ok").once()

        assert oc_api.deploy_s2i_app("quay.io/foo", "https://github.com/x.git", ".") is True

    @patch("container_ci_suite.openshift.time.sleep")
    @patch("container_ci_suite.openshift.Path")
    def test_deploy_s2i_app_directory_app_downloads_and_start_build(
        self, mock_path, mock_sleep
    ):
        """
        When app is a directory: download_template for new-app, then start_build after sleep.
        """
        oc_api = OpenShiftAPI(namespace="container-ci-suite-test")
        oc_api.project_created = True
        oc_api.shared_cluster = False
        path_inst = MagicMock()
        path_inst.is_dir.return_value = True
        mock_path.return_value = path_inst

        flexmock(utils).should_receive("get_tagged_image").and_return("registry/ns/i:1")
        flexmock(OpenShiftAPI).should_receive("upload_image").and_return(True)
        flexmock(utils).should_receive("download_template").with_args(
            template_name="/app/src"
        ).and_return("/tmp/app-src").times(2)
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "new-app registry/ns/i:1~/tmp/app-src --strategy=source --context-dir=sub --name=svc",
            json_output=False,
        ).and_return("created").once()
        flexmock(ContainerTestLibUtils).should_receive("run_oc_command").with_args(
            "start-build svc --from-dir=/tmp/app-src",
            json_output=False,
        ).and_return("build-1").once()

        assert oc_api.deploy_s2i_app("img", "/app/src", "sub", service_name="svc") is True
        mock_sleep.assert_called_once_with(3)


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
