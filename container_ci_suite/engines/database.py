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
Database Testing Wrapper Module

This module provides database-specific testing functionality for container tests.
It includes utilities for testing database connections, login access, and other
database-related operations for MySQL/MariaDB and PostgreSQL containers.

Converted from bash functions in:
- mysql-container/test/run (lines 219-239)
- postgresql-container/test/run_test (lines 198-218)
"""

import logging
import subprocess
import time
from typing import Optional, Literal
from enum import Enum

from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types."""

    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRESQL = "postgresql"
    POSTGRES = "postgres"


class DatabaseWrapper:
    """
    Database testing wrapper class.

    This class provides methods for testing MySQL/MariaDB and PostgreSQL database
    containers, including connection testing, login access verification, and other
    database-specific operations.

    This is a Python/PyTest conversion of the bash assert_login_access functions from:
    - mysql-container/test/run (lines 219-239)
    - postgresql-container/test/run_test (lines 198-218)

    Attributes:
        image_name: Name of the database container image to test
        db_type: Type of database (mysql, mariadb, postgresql)

    Example:
        >>> # MySQL
        >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
        >>> assert db.assert_login_success("172.17.0.2", "user", "pass")

        >>> # PostgreSQL
        >>> db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
        >>> assert db.assert_login_success("172.17.0.2", "user", "pass")
    """

    def __init__(
        self,
        image_name: str,
        db_type: Literal["mysql", "mariadb", "postgresql", "postgres"] = "mysql",
    ):
        """
        Initialize the DatabaseWrapper.

        Args:
            image_name: Name of the database container image
            db_type: Type of database (mysql, mariadb, postgresql, postgres)
        """
        self.image_name = image_name
        self.db_type = db_type.lower()
        logger.debug(
            f"DatabaseWrapper initialized with image: {image_name}, "
            f"type: {self.db_type}"
        )

    def assert_login_success(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        port: int = None,
    ) -> bool:
        """
        Assert that login succeeds for the given credentials.

        This is a convenience function that calls assert_login_access with
        expected_success=True. It works for both MySQL and PostgreSQL.

        Args:
            container_ip: IP address of the container
            username: Username to test login with
            password: Password to test login with
            database: Database name to connect to (default: "db")
            port: Port number (default: 3306 for MySQL, 5432 for PostgreSQL)

        Returns:
            True if login succeeds, False otherwise

        Example:
            >>> # MySQL
            >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
            >>> assert db.assert_login_success("172.17.0.2", "user", "pass")

            >>> # PostgreSQL
            >>> db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
            >>> assert db.assert_login_success("172.17.0.2", "user", "pass")
        """
        return self.assert_login_access(
            container_ip=container_ip,
            username=username,
            password=password,
            expected_success=True,
            database=database,
            port=port,
        )

    def assert_login_access(
        self,
        container_ip: str,
        username: str,
        password: str,
        expected_success: bool,
        database: str = "db",
        port: int = None,
    ) -> bool:
        """
        Assert that login access works as expected for MySQL/MariaDB or PostgreSQL.

        This function tests whether a user can successfully log in to a database
        container with the given credentials. It verifies that the login either
        succeeds or fails as expected.

        Automatically detects database type and uses appropriate command.

        Args:
            container_ip: IP address of the container
            username: Username to test login with
            password: Password to test login with
            expected_success: Whether login should succeed (True) or fail (False)
            database: Database name to connect to (default: "db")
            port: Port number (default: 3306 for MySQL, 5432 for PostgreSQL)

        Returns:
            True if login behavior matches expectations, False otherwise

        Example:
            >>> # MySQL - test valid login
            >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
            >>> assert db.assert_login_access("172.17.0.2", "user", "pass", True)

            >>> # PostgreSQL - test invalid login
            >>> db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
            >>> assert db.assert_login_access("172.17.0.2", "user", "wrong", False)
        """
        logger.info(
            f"Testing {self.db_type} login as {username}:{password}; "
            f"expected_success={expected_success}"
        )

        try:
            if self.db_type in ["postgresql", "postgres"]:
                success = self._test_postgresql_login(
                    container_ip, username, password, database, port
                )
            else:  # mysql or mariadb
                success = self._test_mysql_login(
                    container_ip, username, password, database, port
                )

            if success and expected_success:
                logger.info(f"    {username}({password}) access granted as expected")
                return True
            elif not success and not expected_success:
                logger.info(f"    {username}({password}) access denied as expected")
                return True
            else:
                logger.error(f"    {username}({password}) login assertion failed")
                return False

        except Exception as e:
            logger.error(f"Error during login test: {e}")
            if not expected_success:
                logger.info(f"    {username}({password}) access denied as expected")
                return True
            else:
                logger.error(f"    {username}({password}) login assertion failed")
                return False

    def _test_mysql_login(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        port: int = None,
    ) -> bool:
        """
        Test MySQL/MariaDB login.

        Bash equivalent:
        mysql_cmd "$container_ip" "$USER" "$PASS" -e 'SELECT 1;' | grep -q -e 1
        """
        try:
            str_port = "--port " + str(port) if port else ""
            cmd = (
                f"run --rm {self.image_name} mysql "
                f"--host {container_ip} {str_port} "
                f"-u{username} -p{password} "
                f"-e 'SELECT 1;' {database}"
            )

            output = PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)

            # Check if the output contains "1" which indicates successful query
            return "1" in output

        except subprocess.CalledProcessError:
            return False

    def _test_postgresql_login(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        port: int = None,
    ) -> bool:
        """
        Test PostgreSQL login.

        Bash equivalent:
        docker run --rm -e PGPASSWORD="$PASS" "$IMAGE_NAME" psql -v ON_ERROR_STOP=1 \
          "postgresql://$PGUSER@$CONTAINER_IP:5432/${DB-db}" -At -c 'SELECT 1;'
        """
        try:
            str_port = str(port) if port else "5432"
            connection_string = (
                f"postgresql://{username}@{container_ip}:{str_port}/{database}"
            )

            cmd = (
                f"run --rm -e PGPASSWORD={password} {self.image_name} "
                f"psql -v ON_ERROR_STOP=1 '{connection_string}' -At -c 'SELECT 1;'"
            )

            output = PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)

            # PostgreSQL returns "1" on successful query
            return "1" in output.strip()

        except subprocess.CalledProcessError:
            return False

    def mysql_cmd(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        port: int = 3306,
        extra_args: str = "",
        sql_command: Optional[str] = None,
    ) -> str:
        """
        Execute a MySQL command against a container.

        This is a Python equivalent of the bash mysql_cmd function:
        ```bash
        function mysql_cmd() {
          local container_ip="$1"; shift
          local login="$1"; shift
          local password="$1"; shift
          docker run --rm ${CONTAINER_EXTRA_ARGS:-} "$IMAGE_NAME" mysql \\
            --host "$container_ip" -u"$login" -p"$password" "$@" db
        }
        ```

        Args:
            container_ip: IP address of the MySQL container
            username: MySQL username
            password: MySQL password
            database: Database name (default: "db")
            port: Port number (default: 3306)
            extra_args: Additional arguments to pass to mysql command
            sql_command: SQL command to execute (e.g., "-e 'SELECT 1;'")

        Returns:
            Command output as string

        Raises:
            subprocess.CalledProcessError: If the command fails

        Example:
            >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
            >>> output = db.mysql_cmd("172.17.0.2", "user", "pass",
            ...                       sql_command="-e 'SELECT 1;'")
        """
        cmd_parts = [
            "run --rm",
            self.image_name,
            "mysql",
            f"--host {container_ip}",
            f"--port {port}",
            f"-u{username}",
            f"-p{password}",
        ]

        if extra_args:
            cmd_parts.append(extra_args)

        if sql_command:
            cmd_parts.append(sql_command)

        cmd_parts.append(database)

        cmd = " ".join(cmd_parts)
        logging.debug(f"Executing command: {cmd}")

        return PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)

    def postgresql_cmd(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        port: int = 5432,
        extra_args: str = "",
        sql_command: Optional[str] = None,
    ) -> str:
        """
        Execute a PostgreSQL command against a container.

        This is a Python equivalent of the bash postgresql_cmd function:
        ```bash
        function postgresql_cmd() {
          docker run --rm -e PGPASSWORD="$PASS" "$IMAGE_NAME" psql -v ON_ERROR_STOP=1 \\
            "postgresql://$PGUSER@$CONTAINER_IP:5432/${DB-db}" "$@"
        }
        ```

        Args:
            container_ip: IP address of the PostgreSQL container
            username: PostgreSQL username
            password: PostgreSQL password
            database: Database name (default: "db")
            port: Port number (default: 5432)
            extra_args: Additional arguments to pass to psql command
            sql_command: SQL command to execute (e.g., "-c 'SELECT 1;'")

        Returns:
            Command output as string

        Raises:
            subprocess.CalledProcessError: If the command fails

        Example:
            >>> db = DatabaseWrapper(image_name="postgres:13", db_type="postgresql")
            >>> output = db.postgresql_cmd("172.17.0.2", "user", "pass",
            ...                            sql_command="-c 'SELECT 1;'")
        """
        connection_string = f"postgresql://{username}@{container_ip}:{port}/{database}"

        cmd_parts = [
            "run --rm",
            f"-e PGPASSWORD={password}",
            self.image_name,
            "psql",
            "-v ON_ERROR_STOP=1",
            f"'{connection_string}'",
        ]

        if extra_args:
            cmd_parts.append(extra_args)

        if sql_command:
            cmd_parts.append(sql_command)

        cmd = " ".join(cmd_parts)

        return PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)

    def test_connection(
        self,
        container_ip: str,
        username: str,
        password: str,
        database: str = "db",
        max_attempts: int = 60,
        sleep_time: int = 3,
        sql_cmd: Optional[str] = None,
    ) -> bool:
        """
        Test database connection with retries.

        This function attempts to connect to a database container multiple times,
        waiting between attempts. Useful for testing container startup.
        Works for both MySQL and PostgreSQL.

        Args:
            container_ip: IP address of the container
            username: Database username
            password: Database password
            database: Database name (default: "db")
            port: Port number (default: 3306 for MySQL, 5432 for PostgreSQL)
            max_attempts: Maximum number of connection attempts (default: 60)
            sleep_time: Seconds to wait between attempts (default: 3)

        Returns:
            True if connection successful, False otherwise

        Example:
            >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
            >>> if db.test_connection("172.17.0.2", "user", "pass"):
            ...     print("Database is ready!")
        """
        logger.info(f"Testing {self.db_type} connection to {container_ip}...")
        logger.info("Trying to connect...")
        for attempt in range(1, max_attempts + 1):
            try:
                if self.db_type in ["postgresql", "postgres"]:
                    sql_cmd = sql_cmd or "-At -c 'SELECT 1;'"
                    return_output = self.postgresql_cmd(
                        container_ip=container_ip,
                        username=username,
                        password=password,
                        database=database,
                        sql_command=sql_cmd,
                    )
                else:  # mysql or mariadb
                    sql_cmd = sql_cmd or "-e 'SELECT 1;'"
                    return_output = self.mysql_cmd(
                        container_ip=container_ip,
                        username=username,
                        password=password,
                        database=database,
                        sql_command=sql_cmd,
                    )
                logging.debug(f"Output: {return_output}")
                logger.info(f"Connection successful on attempt {attempt}")
                return True

            except subprocess.CalledProcessError:
                if attempt < max_attempts:
                    logger.debug(f"Attempt {attempt} failed, retrying...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to connect after {max_attempts} attempts")
                    return False

        return False

    def assert_local_access(self, container_id: str, username: str = None) -> bool:
        """
        Assert that local access to database works from inside the container.

        This tests if the database command works when executed inside the container.
        Works for both MySQL and PostgreSQL.

        Bash equivalent (MySQL):
        ```bash
        docker exec $(ct_get_cid "$id") bash -c 'mysql -uroot <<< "SELECT 1;"'
        ```

        Bash equivalent (PostgreSQL):
        ```bash
        docker exec -i $(get_cid "$id") bash -c psql <<< "SELECT 1;"
        ```

        Args:
            container_id: Container ID or name
            username: Username to test with (default: "root" for MySQL, None for PostgreSQL)

        Returns:
            True if local access works, False otherwise

        Example:
            >>> db = DatabaseWrapper(image_name="mysql:8.0", db_type="mysql")
            >>> assert db.assert_local_access("mysql_container")
        """
        try:
            if self.db_type in ["postgresql", "postgres"]:
                # PostgreSQL doesn't need username for local access
                cmd = f"exec -i {container_id} bash -c 'psql <<< \"SELECT 1;\"'"
            else:  # mysql or mariadb
                user = username or "root"
                cmd = f"exec {container_id} bash -c 'mysql -u{user} <<< \"SELECT 1;\"'"

            output = PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)

            if "1" in output:
                logger.info("    Local access granted as expected")
                return True
            else:
                logger.error("    Local access assertion failed")
                return False

        except subprocess.CalledProcessError:
            logger.error("    Local access assertion failed")
            return False

    # def run_db_command(
    #     self, container_id: str, username: str, password: str, db_command: str
    # ) -> str:
    #     """
    #     Run a database command inside the container.

    #     Args:
    #         container_id: Container ID or name
    #         command: Command to run like mysql or psql

    #     Returns:
    #         Command output as string
    #     """
    #     if self.db_type in ["postgresql", "postgres"]:
    #         db_cmd = (
    #             f"psql -h {container_ip} -u{username} -p{password} -e '{db_command};'"
    #         )
    #     else:
    #         db_cmd = (
    #             f"mysql -h {container_ip} -u{username} -p{password}  -e '{db_command};'"
    #         )
    #     return PodmanCLIWrapper.call_podman_command(
    #         cmd=f"run --rm {container_id} {db_cmd}", return_output=True
    #     )
