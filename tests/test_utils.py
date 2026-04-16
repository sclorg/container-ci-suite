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

import os
import yaml

from pathlib import Path
from unittest.mock import patch

from flexmock import flexmock

import pytest

from container_ci_suite.utils import (
    get_public_image_name,
    get_npm_variables,
    get_mount_ca_file,
    get_mount_options_from_s2i_args,
    get_env_commands_from_s2i_args,
    download_template,
)
from container_ci_suite import utils

from tests.conftest import create_ca_file, delete_ca_file


class TestContainerCISuiteUtils(object):
    """
    Test Container CI Suite utils.
    """

    @pytest.mark.parametrize(
        "os_name,base_image_name,version,expected_str",
        [
            ("rhel8", "nodejs", "14", "registry.redhat.io/rhel8/nodejs-14"),
        ],
    )
    def test_get_public_image_name(
        self, os_name, base_image_name, version, expected_str
    ):
        """
        Test get_public_image_name.
        """
        name = get_public_image_name(
            os_name=os_name, base_image_name=base_image_name, version=version
        )
        assert name == expected_str

    def test_get_npm_variables_no_ca_file(self):
        """
        Test get_npm_variables_no_ca_file.
        """
        assert get_npm_variables() == ""

    def test_get_mount_ca_file_no_ca_file(self):
        """
        Test get_mount_ca_file_no_ca_file.
        """
        assert get_mount_ca_file() == ""

    def test_get_npm_variables(self):
        """
        Test get_npm_variables.
        """
        create_ca_file()
        flexmock(utils).should_receive("get_full_ca_file_path").and_return(
            Path("/tmp/CA_FILE_PATH")
        )
        assert get_npm_variables() == f"-e NPM_MIRROR=foobar {get_mount_ca_file()}"
        delete_ca_file()

    def test_get_mount_ca_file(self):
        """
        Test get_mount_ca_file.
        """
        create_ca_file()
        assert get_mount_ca_file() == f"{get_mount_ca_file()}"
        delete_ca_file()

    @pytest.mark.parametrize(
        "s2i_args,expected_output",
        [
            ("--pull-never", ""),
            (
                "--pull-never -v /some/foo/bar/file:/some/foo/bar/file:Z",
                "-v /some/foo/bar/file:/some/foo/bar/file:Z",
            ),
            ("-v ./relative/path:/target:Z", "-v ./relative/path:/target:Z"),
            ("-v /host/path:/container:ro", "-v /host/path:/container:ro"),
            ("", ""),
        ],
    )
    def test_get_mount_options_from_s2i_args(self, s2i_args, expected_output):
        """
        Test get_mount_options_from_s2i_args.
        """
        ret_value = get_mount_options_from_s2i_args(s2i_args=s2i_args)
        assert ret_value == expected_output

    @pytest.mark.parametrize(
        "s2i_args,expected_output",
        [
            ("--pull-never", []),
            ("--pull-never -e NODE=development", ["ENV NODE=development"]),
            ("--pull-never -e=NODE=development", ["ENV NODE=development"]),
            (
                "-v mount_point:mount_point:Z -e FOO=bar --env TEST=deployment",
                ["ENV FOO=bar", "ENV TEST=deployment"],
            ),
            ("-v mount_point:mount_point:Z -e FOO=bar --env TEST", ["ENV FOO=bar"]),
            ("-v mount_point:mount_point:Z -e=FOO=bar --env=TEST", ["ENV FOO=bar"]),
            ("", []),
            ("-e KEY1=val1 -e KEY2=val2", ["ENV KEY1=val1", "ENV KEY2=val2"]),
        ],
    )
    def test_get_env_commands_from_s2i_args(self, s2i_args, expected_output):
        """
        Test get_env_commands_from_s2i_args.
        """
        assert get_env_commands_from_s2i_args(s2i_args=s2i_args) == expected_output

    @pytest.mark.parametrize(
        "image_name,version,os_name,expected_output",
        [
            ("rhel8/ubi8", "", "", False),
            ("", "2.4", "", False),
            ("", "", "rhel8", False),
            ("rhel8/httpd-24:1", "2.4", "rhel8", True),
            ("rhel8/httpd-24", "2.4", "rhel9", True),
            ("registry.io/ns/image:1.0", "2.0", "rhel8", True),
        ],
    )
    def test_check_variables(self, image_name, version, os_name, expected_output):
        """
        Test check_variables.
        """
        os.environ["IMAGE_NAME"] = image_name
        os.environ["VERSION"] = version
        os.environ["OS"] = os_name
        assert utils.check_variables() == expected_output

    @pytest.mark.parametrize(
        "image_name,version,expected_output",
        [
            ("rhel8/httpd-24:1", "2.4", "httpd-24:2.4"),
            ("/httpd-24:1", "2.4", "httpd-24:2.4"),
            ("", "2.4", None),
            ("rhel8/httpd", "2.4", "httpd:2.4"),
            ("registry.io/namespace/image:1.0", "2.0", "namespace:2.0"),
            ("singlepart", "1.0", None),
            ("registry.io/ubi8:8", "2.0", "ubi8:2.0"),
        ],
    )
    def test_get_tagged_image(self, image_name, version, expected_output):
        """
        Test get_tagged_image.
        """
        assert (
            utils.get_tagged_image(image_name=image_name, version=version)
            == expected_output
        )

    @pytest.mark.parametrize(
        "image_name,expected_output",
        [
            ("rhel8/httpd-24:1", "httpd-24-testing"),
            ("/httpd-24:1", "httpd-24-testing"),
            ("", None),
            ("rhel8/httpd", "httpd-testing"),
        ],
    )
    def test_get_service_image(self, image_name, expected_output):
        """
        Test get_service_image.
        """
        assert utils.get_service_image(image_name=image_name) == expected_output

    def test_get_image_name_no_image_id_file(self, temp_dir):
        """
        Test get_image_name when .image-id file does not exist.
        """
        assert utils.get_image_name(str(temp_dir)) is None

    @patch("container_ci_suite.utils.ContainerTestLibUtils.run_command")
    @patch("container_ci_suite.utils.get_file_content")
    def test_get_image_name_success(
        self, mock_get_file_content, mock_run_command, temp_dir
    ):
        """
        Test get_image_name when .image-id exists and docker inspect succeeds.
        """
        image_id_file = temp_dir / ".image-id"
        image_id_file.write_text("sha256:abc123\n")
        mock_get_file_content.return_value = "sha256:abc123"
        mock_run_command.side_effect = ["httpd-24", "2.4"]
        result = utils.get_image_name(str(temp_dir))
        assert result == "httpd-24:2.4"
        assert mock_run_command.call_count == 2

    def test_tenantnamespace_yaml(self):
        """
        Test tenantnamespace_yaml.
        """
        expected_yaml = {
            "apiVersion": "tenant.paas.redhat.com/v1alpha1",
            "kind": "TenantNamespace",
            "metadata": {
                "labels": {
                    "tenant.paas.redhat.com/namespace-type": "build",
                    "tenant.paas.redhat.com/tenant": "core-services-ocp",
                },
                "name": "123456",
                "namespace": "core-services-ocp--config",
            },
            "spec": {
                "type": "build",
                "roles": ["namespace-admin", "tenant-egress-admin"],
                "network": {"security-zone": "internal"},
            },
        }
        tenant_yaml = utils.save_tenant_namespace_yaml(project_name="123456")
        with open(tenant_yaml) as fd:
            yaml_load = yaml.safe_load(fd.read())
        assert yaml_load
        assert yaml_load["metadata"]["name"] == "123456"
        assert yaml_load == expected_yaml

    def test_tenantnegress_yaml(self):
        """
        Test tenantnegress_yaml.
        """
        tenant_yaml = utils.save_tenant_egress_yaml(project_name="123456")
        with open(tenant_yaml) as fd:
            yaml_load = yaml.safe_load(fd.read())
        assert yaml_load
        assert yaml_load["metadata"]["namespace"] == "core-services-ocp--123456"
        assert yaml_load["spec"]["egress"][0]["to"]["dnsName"] == "github.com"
        check_address = False
        check_dnsName = False
        check_deny = False
        for egress in yaml_load["spec"]["egress"]:
            if "cidrSelector" in egress["to"]:
                if egress["to"]["cidrSelector"] == "52.92.128.0/17":
                    check_address = True
                if (
                    egress["to"]["cidrSelector"] == "0.0.0.0/0"
                    and egress["type"] == "Deny"
                ):
                    check_deny = True
            if "dnsName" in egress["to"]:
                if egress["to"]["dnsName"] == "registry.npmjs.org":
                    check_dnsName = True
        assert check_address
        assert check_dnsName
        assert check_deny

    def test_tenantlimits_yaml(self):
        """
        Test tenantlimits_yaml.
        """
        tenant_limits_yaml = utils.save_tenant_limit_yaml()
        with open(tenant_limits_yaml) as fd:
            yaml_load = yaml.safe_load(fd.read())
        assert yaml_load
        assert len(yaml_load["spec"]["limits"]) == 2
        check_pod_max = False
        check_pod_min = False
        check_container_max = False
        check_container_min = False
        for limits in yaml_load["spec"]["limits"]:
            if "Pod" in limits["type"]:
                if limits["max"]["cpu"] == "8" and limits["max"]["memory"] == "8Gi":
                    check_pod_max = True
                if limits["min"]["cpu"] == "4" and limits["min"]["memory"] == "2Gi":
                    check_pod_min = True
            if "Container" in limits["type"]:
                if limits["max"]["cpu"] == "8" and limits["max"]["memory"] == "8Gi":
                    check_container_max = True
                if limits["min"]["cpu"] == "2" and limits["min"]["memory"] == "2Gi":
                    check_container_min = True
        assert check_pod_max
        assert check_pod_min
        assert check_container_max
        assert check_container_min

    def test_download_template_local_file(self, temp_dir):
        """
        Test download_template with a local file.
        """
        source_file = temp_dir / "template.yaml"
        source_file.write_text("apiVersion: v1\nkind: Template")
        result = download_template(str(source_file), dir_name=str(temp_dir))
        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".yaml"
        assert Path(result).read_text() == "apiVersion: v1\nkind: Template"

    def test_download_template_local_directory(self, temp_dir):
        """
        Test download_template with a local directory.
        """
        source_dir = temp_dir / "template_dir"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("content")
        result = download_template(str(source_dir), dir_name=str(temp_dir))
        assert result is not None
        assert Path(result).is_dir()
        assert (Path(result) / "file.txt").read_text() == "content"

    def test_download_template_nonexistent(self, temp_dir):
        """
        Test download_template with non-existent path.
        """
        result = download_template("/nonexistent/path/12345", dir_name=str(temp_dir))
        assert result is None

    @patch("container_ci_suite.utils.requests.get")
    def test_download_template_http_url_fails(self, mock_get, temp_dir):
        """
        Test download_template when HTTP request fails.
        """
        import requests

        mock_get.side_effect = requests.HTTPError("404 Not Found")
        with pytest.raises(requests.HTTPError):
            download_template(
                "https://example.com/missing.yaml", dir_name=str(temp_dir)
            )

    @pytest.mark.parametrize(
        "json_data,expected_output",
        [
            ({"helm": "False"}, False),
            ({"helm": "True"}, True),
            ({"helm": True}, True),
            ({"ocp4": "False"}, False),
            ({"ocp4": "True"}, True),
            ({"ocp4": True}, True),
            ({"ocp4": "false"}, False),
            ({"ocp4": None}, False),
            ({"ocp4": "true"}, True),
            ({"ocp4": ""}, False),
            ({"ocp4": "Somthing"}, False),
            ({"ocp4": "Y"}, True),
            ({"helm": "y"}, True),
            ({"helm": "1"}, True),
            ({"helm": "No"}, False),
            ({"helm": "0"}, False),
            ({"helm": "true"}, True),
        ],
    )
    def test_is_shared_cluster(self, json_data, expected_output):
        """
        Test is_shared_cluster.
        """
        flexmock(utils).should_receive("get_json_data").and_return(json_data)
        test = json_data.keys()
        assert utils.is_shared_cluster(test_type="".join(test)) == expected_output

    def test_is_shared_cluster_key_not_present(self):
        """
        Test is_shared_cluster when test_type key is not in json data.
        """
        flexmock(utils).should_receive("get_json_data").and_return({"helm": True})
        assert utils.is_shared_cluster(test_type="ocp4") is False
