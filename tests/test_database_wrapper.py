#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2018-2024 Red Hat, Inc.

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

"""
Tests for DatabaseWrapper class.

This test module verifies the functionality of the DatabaseWrapper class,
which is a Python/PyTest conversion of the bash assert_login_access functions
from mysql-container/test/run and postgresql-container/test/run_test.
"""

import pytest
import subprocess
from unittest.mock import patch

from container_ci_suite.engines.database import DatabaseWrapper


class TestDatabaseWrapperMySQL:
    """Test suite for DatabaseWrapper class with MySQL."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.image_name = "mysql:8.0"
        self.db = DatabaseWrapper(image_name=self.image_name, db_type="mysql")
        self.container_ip = "172.17.0.2"
        self.username = "testuser"
        self.password = "testpass"
        self.database = "testdb"

    def test_init_mysql(self):
        """Test DatabaseWrapper initialization for MySQL."""
        assert self.db.image_name == self.image_name
        assert self.db.db_type == "mysql"

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_success_mysql(self, mock_podman):
        """Test assert_login_success for MySQL when login succeeds."""
        mock_podman.return_value = "1\n"

        result = self.db.assert_login_success(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
        )

        assert result is True
        mock_podman.assert_called_once()
        call_args = mock_podman.call_args[1]["cmd"]
        assert "mysql" in call_args
        assert f"--host {self.container_ip}" in call_args
        assert f"-u{self.username}" in call_args
        assert f"-p{self.password}" in call_args

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_access_mysql_success(self, mock_podman):
        """Test assert_login_access for MySQL when login succeeds."""
        mock_podman.return_value = "1\n"

        result = self.db.assert_login_access(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
            expected_success=True,
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_access_mysql_failure_expected(self, mock_podman):
        """Test assert_login_access for MySQL when login fails as expected."""
        mock_podman.side_effect = subprocess.CalledProcessError(1, "cmd")

        result = self.db.assert_login_access(
            container_ip=self.container_ip,
            username=self.username,
            password="wrongpass",
            expected_success=False,
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_mysql_cmd(self, mock_podman):
        """Test mysql_cmd method."""
        expected_output = "Query result"
        mock_podman.return_value = expected_output

        result = self.db.mysql_cmd(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
        )

        assert result == expected_output
        call_args = mock_podman.call_args[1]["cmd"]
        assert "mysql" in call_args
        assert "--port 3306" in call_args


class TestDatabaseWrapperPostgreSQL:
    """Test suite for DatabaseWrapper class with PostgreSQL."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.image_name = "postgres:13"
        self.db = DatabaseWrapper(image_name=self.image_name, db_type="postgresql")
        self.container_ip = "172.17.0.2"
        self.username = "testuser"
        self.password = "testpass"
        self.database = "testdb"

    def test_init_postgresql(self):
        """Test DatabaseWrapper initialization for PostgreSQL."""
        assert self.db.image_name == self.image_name
        assert self.db.db_type == "postgresql"

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_success_postgresql(self, mock_podman):
        """Test assert_login_success for PostgreSQL when login succeeds."""
        mock_podman.return_value = "1"

        result = self.db.assert_login_success(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
        )

        assert result is True
        mock_podman.assert_called_once()
        call_args = mock_podman.call_args[1]["cmd"]
        assert "psql" in call_args
        assert f"PGPASSWORD={self.password}" in call_args
        assert f"postgresql://{self.username}@{self.container_ip}" in call_args

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_access_postgresql_success(self, mock_podman):
        """Test assert_login_access for PostgreSQL when login succeeds."""
        mock_podman.return_value = "1"

        result = self.db.assert_login_access(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
            expected_success=True,
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_login_access_postgresql_failure_expected(self, mock_podman):
        """Test assert_login_access for PostgreSQL when login fails as expected."""
        mock_podman.side_effect = subprocess.CalledProcessError(1, "cmd")

        result = self.db.assert_login_access(
            container_ip=self.container_ip,
            username=self.username,
            password="wrongpass",
            expected_success=False,
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_postgresql_cmd(self, mock_podman):
        """Test postgresql_cmd method."""
        expected_output = "Query result"
        mock_podman.return_value = expected_output

        result = self.db.postgresql_cmd(
            container_ip=self.container_ip,
            username=self.username,
            password=self.password,
        )

        assert result == expected_output
        call_args = mock_podman.call_args[1]["cmd"]
        assert "psql" in call_args
        assert "5432" in call_args
        assert "ON_ERROR_STOP=1" in call_args


class TestDatabaseWrapperCommon:
    """Test common functionality across database types."""

    @pytest.mark.parametrize(
        "db_type,image",
        [
            ("mysql", "mysql:8.0"),
            ("mariadb", "mariadb:10.5"),
            ("postgresql", "postgres:13"),
            ("postgres", "postgres:14"),
        ],
    )
    def test_init_different_types(self, db_type, image):
        """Test initialization with different database types."""
        db = DatabaseWrapper(image_name=image, db_type=db_type)
        assert db.image_name == image
        assert db.db_type == db_type.lower()

    @pytest.mark.parametrize(
        "db_type,expected_port",
        [
            ("mysql", 3306),
            ("mariadb", 3306),
            ("postgresql", 5432),
            ("postgres", 5432),
        ],
    )
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_default_ports(self, mock_podman, db_type, expected_port):
        """Test that default ports are used correctly."""
        mock_podman.return_value = "1"
        db = DatabaseWrapper(image_name="test:latest", db_type=db_type)

        db.test_connection("172.17.0.2", "user", "pass")

        call_args = mock_podman.call_args[1]["cmd"]
        assert str(expected_port) in call_args

    @patch("container_ci_suite.engines.database.time.sleep")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_test_connection_with_retries_mysql(self, mock_podman, mock_sleep):
        """Test test_connection with retries for MySQL."""
        # Fail twice, then succeed
        mock_podman.side_effect = [
            subprocess.CalledProcessError(1, "cmd"),
            subprocess.CalledProcessError(1, "cmd"),
            "1\n",
        ]

        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
        result = db.test_connection(
            container_ip="172.17.0.2",
            username="user",
            password="pass",
            max_attempts=10,
            sleep_time=1,
        )

        assert result is True
        assert mock_podman.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("container_ci_suite.engines.database.time.sleep")
    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_test_connection_with_retries_postgresql(self, mock_podman, mock_sleep):
        """Test test_connection with retries for PostgreSQL."""
        # Fail twice, then succeed
        mock_podman.side_effect = [
            subprocess.CalledProcessError(1, "cmd"),
            subprocess.CalledProcessError(1, "cmd"),
            "1",
        ]

        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
        result = db.test_connection(
            container_ip="172.17.0.2",
            username="user",
            password="pass",
            max_attempts=10,
            sleep_time=1,
        )

        assert result is True
        assert mock_podman.call_count == 3
        assert mock_sleep.call_count == 2

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_local_access_mysql(self, mock_podman):
        """Test assert_local_access for MySQL."""
        mock_podman.return_value = "1\n"
        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")

        result = db.assert_local_access(container_id="mysql_container")

        assert result is True
        call_args = mock_podman.call_args[1]["cmd"]
        assert "exec mysql_container" in call_args
        assert "mysql -uroot" in call_args

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_local_access_postgresql(self, mock_podman):
        """Test assert_local_access for PostgreSQL."""
        mock_podman.return_value = "1"
        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")

        result = db.assert_local_access(container_id="pg_container")

        assert result is True
        call_args = mock_podman.call_args[1]["cmd"]
        assert "exec -i pg_container" in call_args
        assert "psql" in call_args

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_assert_local_access_failure(self, mock_podman):
        """Test assert_local_access when access fails."""
        mock_podman.side_effect = subprocess.CalledProcessError(1, "cmd")
        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")

        result = db.assert_local_access(container_id="mysql_container")

        assert result is False


class TestDatabaseWrapperEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_image_name(self):
        """Test initialization with empty image name."""
        db = DatabaseWrapper(image_name="", db_type="mysql")
        assert db.image_name == ""

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_special_characters_in_password_mysql(self, mock_podman):
        """Test handling of special characters in password for MySQL."""
        mock_podman.return_value = "1\n"
        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")

        special_password = "p@ss!w0rd#123"
        result = db.assert_login_success(
            container_ip="172.17.0.2", username="user", password=special_password
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_special_characters_in_password_postgresql(self, mock_podman):
        """Test handling of special characters in password for PostgreSQL."""
        mock_podman.return_value = "1"
        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")

        special_password = "p@ss!w0rd#123"
        result = db.assert_login_success(
            container_ip="172.17.0.2", username="user", password=special_password
        )

        assert result is True

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_custom_port_mysql(self, mock_podman):
        """Test using custom port for MySQL."""
        mock_podman.return_value = "1\n"
        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")

        custom_port = 3307
        result = db.assert_login_success(
            container_ip="172.17.0.2",
            username="user",
            password="pass",
            port=custom_port,
        )

        assert result is True
        call_args = mock_podman.call_args[1]["cmd"]
        assert f"--port {custom_port}" in call_args

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_custom_port_postgresql(self, mock_podman):
        """Test using custom port for PostgreSQL."""
        mock_podman.return_value = "1"
        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")

        custom_port = 5433
        result = db.assert_login_success(
            container_ip="172.17.0.2",
            username="user",
            password="pass",
            port=custom_port,
        )

        assert result is True
        call_args = mock_podman.call_args[1]["cmd"]
        assert f":{custom_port}/" in call_args


class TestDatabaseWrapperIntegration:
    """Integration tests (skipped by default)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires actual MySQL container running")
    def test_real_mysql_connection(self):
        """Integration test with real MySQL container."""
        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")

        # These would need to be actual values from a running container
        container_ip = "172.17.0.2"
        username = "root"
        password = "rootpass"

        assert db.test_connection(container_ip, username, password, max_attempts=10)
        assert db.assert_login_success(container_ip, username, password)

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires actual PostgreSQL container running")
    def test_real_postgresql_connection(self):
        """Integration test with real PostgreSQL container."""
        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")

        # These would need to be actual values from a running container
        container_ip = "172.17.0.2"
        username = "postgres"
        password = "postgres"

        assert db.test_connection(container_ip, username, password, max_attempts=10)
        assert db.assert_login_success(container_ip, username, password)


class TestDatabaseWrapperDocumentation:
    """Test that documentation examples work correctly."""

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_docstring_example_mysql(self, mock_podman):
        """Test the MySQL example from the docstring."""
        mock_podman.return_value = "1\n"

        db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
        assert db.assert_login_success("172.17.0.2", "user", "pass")

    @patch(
        "container_ci_suite.engines.podman_wrapper.PodmanCLIWrapper.call_podman_command"
    )
    def test_docstring_example_postgresql(self, mock_podman):
        """Test the PostgreSQL example from the docstring."""
        mock_podman.return_value = "1"

        db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
        assert db.assert_login_success("172.17.0.2", "user", "pass")


# Run tests with: pytest tests/test_database_wrapper.py -v
# Run with coverage: pytest tests/test_database_wrapper.py --cov=container_ci_suite.engines.database --cov-report=html
# Run MySQL tests only: pytest tests/test_database_wrapper.py::TestDatabaseWrapperMySQL -v
# Run PostgreSQL tests only: pytest tests/test_database_wrapper.py::TestDatabaseWrapperPostgreSQL -v
