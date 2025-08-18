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
Container Test Library - Python version

This module provides a Python replacement for the container-test-lib.sh shell script.
It contains all the functionality needed for testing container images.
"""

import os
import re
import sys
import time
import signal
import shutil
import tempfile
import subprocess
import logging
import atexit
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

try:
    from container_ci_suite.engines.container import PodmanCLIWrapper
    from container_ci_suite.utils import (
        run_command,
        get_file_content,
        get_full_ca_file_path,
        get_os_environment,
        get_mount_ca_file,
        get_env_commands_from_s2i_args,
        get_mount_options_from_s2i_args,
    )
except ImportError:
    # Fallback imports for standalone usage
    PodmanCLIWrapper = None

    def run_command(cmd, return_output=True, ignore_error=False, shell=True, debug=False, **kwargs):
        """Fallback run_command implementation."""
        if debug:
            print(f"command: {cmd}")
        try:
            if return_output:
                return subprocess.check_output(
                    cmd, 
                    shell=shell, 
                    text=True, 
                    stderr=subprocess.STDOUT,
                    **kwargs
                )
            else:
                return subprocess.check_call(cmd, shell=shell, **kwargs)
        except subprocess.CalledProcessError as cpe:
            if ignore_error:
                if return_output:
                    return cpe.output if hasattr(cpe, 'output') else ""
                else:
                    return cpe.returncode
            else:
                raise cpe

    def get_file_content(filename):
        """Fallback get_file_content implementation."""
        with open(filename, 'r') as f:
            return f.read()

    def get_full_ca_file_path():
        """Fallback get_full_ca_file_path implementation."""
        return Path("/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt")

    def get_os_environment(var):
        """Fallback get_os_environment implementation."""
        return os.environ.get(var)

    def get_mount_ca_file():
        """Fallback get_mount_ca_file implementation."""
        if get_os_environment("NPM_REGISTRY") and get_full_ca_file_path().exists():
            ca_path = "/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt"
            return f"-v {ca_path}:{ca_path}:Z"
        return ""

    def get_env_commands_from_s2i_args(s2i_args):
        """Fallback get_env_commands_from_s2i_args implementation."""
        import re
        matchObj = re.findall(r"(-e|--env)\s*(\S*)=(\S*)", s2i_args)
        return [f"ENV {x[1]}={x[2]}" for x in matchObj] if matchObj else []

    def get_mount_options_from_s2i_args(s2i_args):
        """Fallback get_mount_options_from_s2i_args implementation."""
        import re
        searchObj = re.search(r"(-v \.*\S*)", s2i_args)
        return searchObj.group() if searchObj else ""

logger = logging.getLogger(__name__)

# Global constants
LINE = "=============================================="
EXPECTED_EXIT_CODE = 0


class ContainerTestLib:
    """
    Container Test Library - Main class providing container testing functionality.
    This is a Python replacement for the container-test-lib.sh shell script.
    """

    def __init__(self):
        """Initialize the container test library."""
        self.app_id_file_dir: Optional[Path] = None
        self.cid_file_dir: Optional[Path] = None
        self.test_summary: str = ""
        self.testsuite_result: int = 0
        self.expected_exit_code: int = EXPECTED_EXIT_CODE
        self.unstable_tests: List[str] = []
        self.cleanup_enabled: bool = False

        # Set up unstable tests from environment
        unstable_env = get_os_environment("UNSTABLE_TESTS")
        if unstable_env:
            self.unstable_tests = unstable_env.split()

    def ct_init(self) -> None:
        """
        Initialize container testing environment.
        Sets up temporary directories and enables cleanup handlers.
        """
        self.app_id_file_dir = Path(tempfile.mkdtemp(prefix="ct_app_ids_"))
        self.cid_file_dir = Path(tempfile.mkdtemp(prefix="ct_cid_files_"))
        self.test_summary = ""
        self.testsuite_result = 0
        self.ct_enable_cleanup()
        logger.info(f"Container test environment initialized")
        logger.info(f"APP_ID_FILE_DIR: {self.app_id_file_dir}")
        logger.info(f"CID_FILE_DIR: {self.cid_file_dir}")

    def ct_cleanup(self) -> None:
        """
        Clean up containers and images used during tests.
        Stops and removes all containers and cleans up temporary directories.
        """
        print(LINE)
        print("Cleaning of testing containers and images started.")
        print("It may take a few seconds.")
        print(LINE)

        self.ct_clean_app_images()
        self.ct_clean_containers()

    def ct_build_image_and_parse_id(self, dockerfile: str = "", build_params: str = "") -> bool:
        """
        Build container image and parse the image ID.

        Args:
            dockerfile: Path to Dockerfile (optional)
            build_params: Additional build parameters

        Returns:
            True if build successful, False otherwise
        """
        try:
            log_file = Path(tempfile.mktemp(prefix="ct_build_log_"))
            sleep_time = "10m"

            dockerfile_arg = f"-f {dockerfile}" if dockerfile else ""
            command = f"docker build --no-cache {dockerfile_arg} {build_params}"

            # Remove any single quotes from the command
            command = command.replace("'", "")

            # Run build command with timeout
            timeout_cmd = f"timeout {sleep_time} {command}"
            
            try:
                log_content = run_command(timeout_cmd, return_output=True)
                print(log_content)
                
                # Extract image ID from last line
                lines = log_content.strip().split('\n')
                if lines:
                    self.app_image_id = lines[-1].strip()
                
                return True
                
            except subprocess.CalledProcessError:
                return False

        except Exception as e:
            logger.error(f"Build failed: {e}")
            return False

    def ct_container_running(self, container_id: str) -> bool:
        """
        Check if container is in running state.

        Args:
            container_id: Container ID to check

        Returns:
            True if container is running, False otherwise
        """
        try:
            result = run_command(
                f"docker inspect -f '{{{{.State.Running}}}}' {container_id}",
                return_output=True
            )
            return result.strip() == "true"
        except subprocess.CalledProcessError:
            return False

    def ct_container_exists(self, container_id: str) -> bool:
        """
        Check if container exists.

        Args:
            container_id: Container ID to check

        Returns:
            True if container exists, False otherwise
        """
        try:
            result = run_command(
                f"docker ps -q -a -f 'id={container_id}'",
                return_output=True
            )
            return bool(result.strip())
        except subprocess.CalledProcessError:
            return False

    def ct_clean_app_images(self) -> None:
        """Clean up application images referenced by APP_ID_FILE_DIR."""
        if not self.app_id_file_dir or not self.app_id_file_dir.exists():
            print(f"The APP_ID_FILE_DIR={self.app_id_file_dir} is not created. App cleaning is to be skipped.")
            return

        print(f"Examining image ID files in APP_ID_FILE_DIR={self.app_id_file_dir}")

        for file_path in self.app_id_file_dir.glob("*"):
            if not file_path.is_file():
                continue

            try:
                image_id = get_file_content(file_path).strip()

                # Check if image exists
                try:
                    run_command(f"docker inspect {image_id}", return_output=False)
                except subprocess.CalledProcessError:
                    continue

                # Remove containers using this image
                try:
                    containers = run_command(
                        f"docker ps -q -a -f ancestor={image_id}",
                        return_output=True
                    ).strip()
                    if containers:
                        run_command(f"docker rm -f {containers}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass

                # Remove the image
                try:
                    run_command(f"docker rmi -f {image_id}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass

            except Exception as e:
                logger.warning(f"Error cleaning image from {file_path}: {e}")

        # Remove the directory
        shutil.rmtree(self.app_id_file_dir)

    def ct_clean_containers(self) -> None:
        """Clean up containers referenced by CID_FILE_DIR."""
        if not self.cid_file_dir:
            print("The CID_FILE_DIR is not set. Container cleaning is to be skipped.")
            return

        print(f"Examining CID files in CID_FILE_DIR={self.cid_file_dir}")

        for cid_file in self.cid_file_dir.glob("*"):
            if not cid_file.is_file():
                continue

            try:
                container_id = get_file_content(cid_file).strip()

                if not self.ct_container_exists(container_id):
                    continue

                print(f"Stopping and removing container {container_id}...")

                # Stop container if running
                if self.ct_container_running(container_id):
                    run_command(f"docker stop {container_id}", ignore_error=True)

                # Check exit status and dump logs if needed
                try:
                    exit_status = run_command(
                        f"docker inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        return_output=True
                    ).strip()

                    if exit_status != str(self.expected_exit_code):
                        print(f"Dumping logs for {container_id}")
                        try:
                            logs = run_command(f"docker logs {container_id}", return_output=True)
                            print(logs)
                        except subprocess.CalledProcessError:
                            pass
                except subprocess.CalledProcessError:
                    pass

                # Remove container
                run_command(f"docker rm -v {container_id}", ignore_error=True)
                cid_file.unlink()

            except Exception as e:
                logger.warning(f"Error cleaning container from {cid_file}: {e}")

        # Remove the directory
        if self.cid_file_dir.exists():
            shutil.rmtree(self.cid_file_dir)

    def ct_show_results(self, image_name: str = "") -> None:
        """
        Print results of all test cases.

        Args:
            image_name: Name of the tested container image
        """
        print(LINE)
        if image_name:
            print(f"Tests were run for image {image_name}")
        print(LINE)
        print("Test cases results:")
        print()
        print(self.test_summary)

        if self.testsuite_result is not None:
            if self.testsuite_result == 0:
                print(f"Tests for {image_name} succeeded.")
            else:
                print(f"Tests for {image_name} failed.")

    def ct_enable_cleanup(self) -> None:
        """Enable automatic container cleanup after tests."""
        if not self.cleanup_enabled:
            atexit.register(self.ct_trap_on_exit)
            signal.signal(signal.SIGINT, self.ct_trap_on_sigint)
            signal.signal(signal.SIGTERM, self.ct_trap_on_exit)
            self.cleanup_enabled = True

    def ct_trap_on_exit(self, exit_code: int = None) -> None:
        """Handle exit trap for cleanup."""
        if exit_code is None:
            exit_code = 0

        if exit_code == 130:  # SIGINT
            return

        print(f"Tests finished with EXIT={exit_code}")
        if exit_code == 0:
            exit_code = self.testsuite_result or 0

        debug = get_os_environment("DEBUG")
        if not debug:
            self.ct_show_resources()

        self.ct_cleanup()
        self.ct_show_results()
        # Don't call sys.exit from atexit handler to avoid SystemExit exception

    def ct_trap_on_sigint(self, signum, frame) -> None:
        """Handle SIGINT signal."""
        print("Tests were stopped by SIGINT signal")
        self.ct_cleanup()
        self.ct_show_results()
        sys.exit(130)

    def ct_pull_image(self, image_name: str, exit_on_fail: bool = False, loops: int = 10) -> bool:
        """
        Pull an image before test execution.

        Args:
            image_name: Name of the image to pull
            exit_on_fail: Exit if pull fails
            loops: Number of retry attempts

        Returns:
            True if pull successful, False otherwise
        """
        print(f"-> Pulling image {image_name} ...")

        # Check if image is already available locally
        try:
            result = run_command(f"docker images -q {image_name}", return_output=True)
            if result.strip():
                print(f"The image {image_name} is already pulled.")
                return True
        except subprocess.CalledProcessError:
            pass

        # Try pulling the image
        for loop in range(1, loops + 1):
            try:
                run_command(f"docker pull {image_name}", return_output=False)
                return True
            except subprocess.CalledProcessError:
                print(f"Pulling image {image_name} failed.")
                if loop > loops:
                    print(f"Pulling of image {image_name} failed {loops} times in a row. Giving up.")
                    print(f"!!! ERROR with pulling image {image_name} !!!!")
                    if exit_on_fail:
                        sys.exit(1)
                    return False

                wait_time = loop * 5
                print(f"Let's wait {wait_time} seconds and try again.")
                time.sleep(wait_time)

        return False

    def ct_check_envs_set(self, env_filter: str, check_envs: str, loop_envs: str,
                         env_format: str = "*VALUE*") -> bool:
        """
        Compare environment variable values between two lists.

        Args:
            env_filter: Filter for environment variables
            check_envs: Environment variables to check against
            loop_envs: Environment variables to check
            env_format: Format string for value checking

        Returns:
            True if all environment variables match, False otherwise
        """
        for line in loop_envs.split('\n'):
            line = line.strip()
            if not line or not re.search(env_filter, line) or line.startswith("PWD="):
                continue

            if '=' not in line:
                continue

            var_name, stripped = line.split('=', 1)

            # Find matching environment variable in check_envs
            filtered_envs = [env for env in check_envs.split('\n')
                           if env.startswith(f"{var_name}=")]

            if not filtered_envs:
                print(f"{var_name} not found during 'docker exec'")
                return False

            filtered_env = filtered_envs[0]

            # Check each value in the colon-separated list
            for value in stripped.split(':'):
                if not re.search(env_filter, value):
                    continue

                # Replace VALUE in env_format with actual value
                pattern = env_format.replace("VALUE", re.escape(value))
                pattern = pattern.replace("*", ".*")

                if not re.search(pattern, filtered_env):
                    print(f"Value {value} is missing from variable {var_name}")
                    print(filtered_env)
                    return False

        return True

    def ct_get_cid(self, name: str) -> str:
        """
        Get container ID from cid_file.

        Args:
            name: Name of the cid_file

        Returns:
            Container ID
        """
        cid_file = self.cid_file_dir / name
        return get_file_content(cid_file).strip()

    def ct_get_cip(self, cid_name: str) -> str:
        """
        Get container IP address.

        Args:
            cid_name: Name of the cid_file

        Returns:
            Container IP address
        """
        container_id = self.ct_get_cid(cid_name)
        try:
            result = run_command(
                f"docker inspect --format='{{{{.NetworkSettings.IPAddress}}}}' {container_id}",
                return_output=True
            )
            return result.strip()
        except subprocess.CalledProcessError:
            return ""

    def ct_wait_for_cid(self, cid_file: Union[str, Path], max_attempts: int = 10,
                       sleep_time: int = 1) -> bool:
        """
        Wait for cid_file to be created.

        Args:
            cid_file: Path to cid_file
            max_attempts: Maximum number of attempts
            sleep_time: Sleep time between attempts

        Returns:
            True if cid_file created, False otherwise
        """
        cid_path = Path(cid_file)

        for attempt in range(1, max_attempts + 1):
            if cid_path.exists() and cid_path.stat().st_size > 0:
                return True
            print(f"Waiting for container start... {attempt}")
            time.sleep(sleep_time)

        return False

    def ct_assert_container_creation_fails(self, container_args: str) -> bool:
        """
        Assert that container creation should fail.

        Args:
            container_args: Container arguments

        Returns:
            True if container creation failed as expected, False otherwise
        """
        cid_file = "assert"
        max_attempts = 10

        old_container_args = getattr(self, 'container_args', "")
        self.container_args = container_args

        try:
            if self.ct_create_container(cid_file):
                container_id = self.ct_get_cid(cid_file)

                attempt = 1
                while attempt <= max_attempts:
                    if not self.ct_container_running(container_id):
                        break
                    time.sleep(2)
                    attempt += 1
                    if attempt > max_attempts:
                        run_command(f"docker stop {container_id}", ignore_error=True)
                        return False

                # Check exit status
                try:
                    exit_status = run_command(
                        f"docker inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        return_output=True
                    ).strip()
                    if exit_status == "0":
                        return False
                except subprocess.CalledProcessError:
                    pass

                # Clean up
                run_command(f"docker rm -v {container_id}", ignore_error=True)
                cid_path = self.cid_file_dir / cid_file
                if cid_path.exists():
                    cid_path.unlink()

        finally:
            if old_container_args:
                self.container_args = old_container_args

        return True

    def ct_create_container(self, name: str, command: str = "", image_name: str = "",
                          container_args: str = "") -> bool:
        """
        Create a container.

        Args:
            name: Name for the cid_file
            command: Command to run in container
            image_name: Image name to use
            container_args: Additional container arguments

        Returns:
            True if container created successfully, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        if not container_args:
            container_args = getattr(self, 'container_args', '')

        cid_file = self.cid_file_dir / name

        try:
            cmd = f"docker run --cidfile={cid_file} -d {container_args} {image_name} {command}"
            run_command(cmd, return_output=False)

            if not self.ct_wait_for_cid(cid_file):
                return False

            container_id = get_file_content(cid_file).strip()
            print(f"Created container {container_id}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create container: {e}")
            return False

    def ct_scl_usage_old(self, name: str, command: str, expected: str, image_name: str = "") -> bool:
        """
        Test SCL usage in three different ways.

        Args:
            name: Name for cid_file
            command: Command to execute
            expected: Expected string in output
            image_name: Image name to test

        Returns:
            True if all tests pass, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        print("Testing the image SCL enable")

        # Test 1: docker run
        try:
            output = run_command(f"docker run --rm {image_name} /bin/bash -c '{command}'",
                               return_output=True)
            if expected not in output:
                print(f"ERROR[/bin/bash -c '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        # Test 2: docker exec with bash
        try:
            container_id = self.ct_get_cid(name)
            output = run_command(f"docker exec {container_id} /bin/bash -c '{command}'",
                               return_output=True)
            if expected not in output:
                print(f"ERROR[exec /bin/bash -c '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        # Test 3: docker exec with sh
        try:
            container_id = self.ct_get_cid(name)
            output = run_command(f"docker exec {container_id} /bin/sh -ic '{command}'",
                               return_output=True)
            if expected not in output:
                print(f"ERROR[exec /bin/sh -ic '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        return True

    def ct_doc_content_old(self, strings: List[str], image_name: str = "") -> bool:
        """
        Check documentation content in container.

        Args:
            strings: List of strings to check for
            image_name: Image name to test

        Returns:
            True if all strings found and format is correct, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        print("Testing documentation in the container image")

        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Extract help files from container
            for filename in ["help.1"]:
                try:
                    content = run_command(
                        f"docker run --rm {image_name} /bin/bash -c 'cat /{filename}'",
                        return_output=True
                    )

                    help_file = tmpdir / filename
                    with open(help_file, 'w') as f:
                        f.write(content)

                    # Check for required strings
                    for term in strings:
                        if term not in content:
                            print(f"ERROR: File /{filename} does not include '{term}'.")
                            return False

                    # Check format
                    for term in ["TH", "PP", "SH"]:
                        if not re.search(f"^\\.{term}", content, re.MULTILINE):
                            print(f"ERROR: /{filename} is probably not in troff or groff format, since '{term}' is missing.")
                            return False

                except subprocess.CalledProcessError:
                    print(f"ERROR: Could not extract {filename} from container")
                    return False

            print("Success!")
            return True

        finally:
            shutil.rmtree(tmpdir)

    def ct_mount_ca_file(self) -> str:
        """
        Get mount parameter for CA file.

        Returns:
            Mount parameter string or empty string
        """
        return get_mount_ca_file()

    def ct_build_s2i_npm_variables(self) -> str:
        """
        Build S2I npm variables.

        Returns:
            NPM variables string
        """
        npm_registry = get_os_environment("NPM_REGISTRY")
        if npm_registry and get_full_ca_file_path().exists():
            return f"-e NPM_MIRROR={npm_registry} {self.ct_mount_ca_file()}"
        return ""

    def ct_npm_works(self, image_name: str = "") -> bool:
        """
        Test if npm works in the container.

        Args:
            image_name: Image name to test

        Returns:
            True if npm works, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        tmpdir = Path(tempfile.mkdtemp())
        cid_file = tmpdir / "npm_test_cid"

        try:
            print("Testing npm in the container image")

            # Test npm version
            try:
                version_output = run_command(
                    f"docker run --rm {image_name} /bin/bash -c 'npm --version'",
                    return_output=True
                )
                version_file = tmpdir / "version"
                with open(version_file, 'w') as f:
                    f.write(version_output)
            except subprocess.CalledProcessError:
                print(f"ERROR: 'npm --version' does not work inside the image {image_name}.")
                return False

            # Start test container
            mount_ca = self.ct_mount_ca_file()
            test_app_image = f"{image_name}-testapp"

            try:
                run_command(
                    f"docker run -d {mount_ca} --rm --cidfile={cid_file} {test_app_image}",
                    return_output=False
                )
            except subprocess.CalledProcessError:
                print(f"ERROR: Could not start {test_app_image}")
                return False

            # Wait for container
            if not self.ct_wait_for_cid(cid_file):
                return False

            container_id = get_file_content(cid_file).strip()

            # Test npm install
            try:
                jquery_output = run_command(
                    f"docker exec {container_id} /bin/bash -c "
                    f"'npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js'",
                    return_output=True
                )

                jquery_file = tmpdir / "jquery"
                with open(jquery_file, 'w') as f:
                    f.write(jquery_output)

            except subprocess.CalledProcessError:
                print(f"ERROR: npm could not install jquery inside the image {image_name}.")
                return False

            # Check NPM registry if configured
            npm_registry = get_os_environment("NPM_REGISTRY")
            if npm_registry and get_full_ca_file_path().exists():
                if npm_registry not in jquery_output:
                    print("ERROR: Internal repository is NOT set. Even it is requested.")
                    return False

            # Stop container
            if cid_file.exists():
                try:
                    run_command(f"docker stop {container_id}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass

            print("Success!")
            return True

        finally:
            shutil.rmtree(tmpdir)

    def ct_binary_found_from_df(self, binary: str, binary_path: str = "^/opt/rh",
                               image_name: str = "") -> bool:
        """
        Check if binary can be found during Dockerfile build.

        Args:
            binary: Binary name to check
            binary_path: Expected path pattern
            image_name: Image name to test

        Returns:
            True if binary found, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        tmpdir = Path(tempfile.mkdtemp())

        try:
            print(f"Testing {binary} in build from Dockerfile")

            # Create Dockerfile
            dockerfile = tmpdir / "Dockerfile"
            with open(dockerfile, 'w') as f:
                f.write(f"FROM {image_name}\n")
                f.write(f"RUN command -v {binary} | grep '{binary_path}'\n")

            # Build image
            if self.ct_build_image_and_parse_id(str(dockerfile), str(tmpdir)):
                # Store image ID for cleanup
                if hasattr(self, 'app_image_id'):
                    id_file = self.app_id_file_dir / str(hash(binary))
                    with open(id_file, 'w') as f:
                        f.write(self.app_image_id)
                return True
            else:
                print(f"ERROR: Failed to find {binary} in $PATH!")
                return False

        finally:
            shutil.rmtree(tmpdir)

    def ct_check_exec_env_vars(self, env_filter: str = "^X_SCLS=|/opt/rh|/opt/app-root",
                              image_name: str = "") -> bool:
        """
        Check if environment variables from 'docker run' are available in 'docker exec'.

        Args:
            env_filter: Filter for environment variables
            image_name: Image name to test

        Returns:
            True if all variables present, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Get environment variables from docker run
            run_envs = run_command(
                f"docker run --rm {image_name} /bin/bash -c env",
                return_output=True
            )

            # Create container for exec test
            if not self.ct_create_container("test_exec_envs", "bash -c 'sleep 1000'", image_name):
                return False

            container_id = self.ct_get_cid("test_exec_envs")

            # Get environment variables from docker exec
            exec_envs = run_command(f"docker exec {container_id} env", return_output=True)

            # Check environment variables
            result = self.ct_check_envs_set(env_filter, exec_envs, run_envs)
            if result:
                print("All values present in 'docker exec'")

            return result

        finally:
            shutil.rmtree(tmpdir)

    def ct_check_scl_enable_vars(self, env_filter: str = "", image_name: str = "") -> bool:
        """
        Check if environment variables are set twice after SCL enable.

        Args:
            env_filter: Filter for environment variables
            image_name: Image name to test

        Returns:
            True if all variables set correctly, False otherwise
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Get enabled SCLs
            enabled_scls = run_command(
                f"docker run --rm {image_name} /bin/bash -c 'echo $X_SCLS'",
                return_output=True
            ).strip()

            if not env_filter:
                # Build filter from enabled SCLs
                scl_list = enabled_scls.split()
                if scl_list:
                    env_filter = "|".join([f"/{scl}" for scl in scl_list])

            # Get environment variables
            loop_envs = run_command(
                f"docker run --rm {image_name} /bin/bash -c env",
                return_output=True
            )

            run_envs = run_command(
                f"docker run --rm {image_name} /bin/bash -c 'X_SCLS= scl enable {enabled_scls} env'",
                return_output=True
            )

            # Check if values are set twice
            result = self.ct_check_envs_set(env_filter, run_envs, loop_envs, "*VALUE*VALUE*")
            if result:
                print("All scl_enable values present")

            return result

        finally:
            shutil.rmtree(tmpdir)

    def ct_path_append(self, path_var: str, directory: str) -> None:
        """
        Append directory to PATH-like variable.

        Args:
            path_var: Name of the path variable
            directory: Directory to append
        """
        current_value = os.environ.get(path_var, "")
        if current_value:
            os.environ[path_var] = f"{directory}:{current_value}"
        else:
            os.environ[path_var] = directory

    def ct_path_foreach(self, path: str, action: callable, *args) -> None:
        """
        Execute action for each directory in path.

        Args:
            path: Colon-separated path string
            action: Function to call for each directory
            *args: Additional arguments for action
        """
        for directory in path.split(':'):
            if directory:
                action(directory, *args)

    def ct_gen_self_signed_cert_pem(self, output_dir: str, base_name: str) -> bool:
        """
        Generate self-signed PEM certificate pair.

        Args:
            output_dir: Output directory
            base_name: Base name for certificate files

        Returns:
            True if successful, False otherwise
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            # Generate private key and certificate request
            key_file = output_path / f"{base_name}-key.pem"
            req_file = f"{base_name}-req.pem"
            cert_file = output_path / f"{base_name}-cert-selfsigned.pem"

            # Generate key and request
            run_command(
                f"openssl req -newkey rsa:2048 -nodes -keyout {key_file} "
                f"-subj '/C=GB/ST=Berkshire/L=Newbury/O=My Server Company' > {req_file}",
                return_output=False
            )

            # Generate self-signed certificate
            run_command(
                f"openssl req -new -x509 -nodes -key {key_file} -batch > {cert_file}",
                return_output=False
            )

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Certificate generation failed: {e}")
            return False

    def ct_obtain_input(self, input_path: str) -> Optional[str]:
        """
        Copy file/directory or download from URL to temporary location.

        Args:
            input_path: Local file, directory, or URL

        Returns:
            Path to temporary file/directory or None on error
        """
        # Determine file extension
        extension = ""
        if '.' in input_path:
            ext_part = input_path.split('.')[-1]
            if re.match(r'^[a-z0-9]*$', ext_part):
                extension = f".{ext_part}"

        # Create temporary file/directory
        if Path(input_path).is_file():
            # Local file
            temp_file = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-")
            shutil.copy2(input_path, temp_file)
            return temp_file

        elif Path(input_path).is_dir():
            # Local directory
            temp_dir = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-")
            shutil.copytree(input_path, temp_dir, symlinks=True)
            return temp_dir

        elif input_path.startswith(('http://', 'https://')):
            # URL
            temp_file = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-")
            try:
                urllib.request.urlretrieve(input_path, temp_file)
                return temp_file
            except Exception as e:
                logger.error(f"Failed to download {input_path}: {e}")
                return None
        else:
            logger.error(f"File type not known: {input_path}")
            return None

    def ct_test_response(self, url: str, expected_code: int = 200, body_regexp: str = "",
                        max_attempts: int = 20, ignore_error_attempts: int = 10) -> bool:
        """
        Test HTTP response from application container.

        Args:
            url: Request URL
            expected_code: Expected HTTP response code
            body_regexp: Regular expression for response body
            max_attempts: Maximum number of attempts
            ignore_error_attempts: Number of attempts to ignore errors

        Returns:
            True if response matches expectations, False otherwise
        """
        print(f"Testing the HTTP(S) response for <{url}>")
        sleep_time = 3

        for attempt in range(1, max_attempts + 1):
            print(f"Trying to connect ... {attempt}")

            try:
                # Create temporary file for response
                with tempfile.NamedTemporaryFile(mode='w+', prefix='ct_test_response_') as response_file:
                    # Use curl to get response
                    result = run_command(
                        f"curl --connect-timeout 10 -s -w '%{{http_code}}' '{url}'",
                        return_output=True
                    )

                    if len(result) >= 3:
                        response_code = result[-3:]
                        response_body = result[:-3]

                        try:
                            code_int = int(response_code)
                            if code_int == expected_code:
                                if not body_regexp or re.search(body_regexp, response_body):
                                    return True
                        except ValueError:
                            pass

                    # Give services time to start up
                    if attempt <= ignore_error_attempts or attempt == max_attempts:
                        if attempt < max_attempts:
                            time.sleep(sleep_time)
                        continue

            except subprocess.CalledProcessError:
                pass

            if attempt < max_attempts:
                time.sleep(sleep_time)

        return False

    def ct_registry_from_os(self, os_name: str) -> str:
        """
        Transform OS string into registry URL.

        Args:
            os_name: Operating system string

        Returns:
            Registry URL
        """
        if os_name.startswith("rhel"):
            return "registry.redhat.io"
        else:
            return "quay.io"

    def ct_get_public_image_name(self, os_name: str, base_image_name: str, version: str) -> str:
        """
        Transform arguments into public image name.

        Args:
            os_name: Operating system string
            base_image_name: Base image name
            version: Version string

        Returns:
            Public image name
        """
        registry = self.ct_registry_from_os(os_name)
        version_no_dots = version.replace('.', '')

        if os_name == "rhel8":
            return f"{registry}/rhel8/{base_image_name}-{version_no_dots}"
        elif os_name == "rhel9":
            return f"{registry}/rhel9/{base_image_name}-{version_no_dots}"
        elif os_name == "rhel10":
            return f"{registry}/rhel10/{base_image_name}-{version_no_dots}"
        elif os_name == "c9s":
            return f"{registry}/sclorg/{base_image_name}-{version_no_dots}-c9s"
        elif os_name == "c10s":
            return f"{registry}/sclorg/{base_image_name}-{version_no_dots}-c10s"
        else:
            return f"{registry}/sclorg/{base_image_name}-{version_no_dots}"

    def ct_assert_cmd_success(self, *cmd) -> bool:
        """
        Assert that command succeeds.

        Args:
            *cmd: Command and arguments

        Returns:
            True if command succeeds, False otherwise
        """
        cmd_str = ' '.join(str(arg) for arg in cmd)
        print(f"Checking '{cmd_str}' for success ...")

        try:
            run_command(cmd_str, return_output=False)
            print(" PASS")
            return True
        except subprocess.CalledProcessError:
            print(" FAIL")
            return False

    def ct_assert_cmd_failure(self, *cmd) -> bool:
        """
        Assert that command fails.

        Args:
            *cmd: Command and arguments

        Returns:
            True if command fails, False otherwise
        """
        cmd_str = ' '.join(str(arg) for arg in cmd)
        print(f"Checking '{cmd_str}' for failure ...")

        try:
            run_command(cmd_str, return_output=False)
            print(" FAIL")
            return False
        except subprocess.CalledProcessError:
            print(" PASS")
            return True

    def ct_random_string(self, length: int = 10) -> str:
        """
        Generate random alphanumeric string.

        Args:
            length: Length of string to generate

        Returns:
            Random string
        """
        import random
        import string

        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def ct_s2i_usage(self, img_name: str, s2i_args: str = "") -> str:
        """
        Run S2I usage script inside container.

        Args:
            img_name: Image name
            s2i_args: S2I arguments (currently unused)

        Returns:
            Usage script output
        """
        usage_command = "/usr/libexec/s2i/usage"
        try:
            return run_command(f"docker run --rm {img_name} bash -c {usage_command}",
                             return_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"S2I usage failed: {e}")
            return ""

    def ct_show_resources(self) -> None:
        """Show system resources information."""
        print()
        print(LINE)
        print("Resources info:")
        print("Memory:")
        try:
            run_command("free -h", return_output=False)
        except subprocess.CalledProcessError:
            print("Memory info not available")

        print("Storage:")
        try:
            run_command("df -h", return_output=False)
        except subprocess.CalledProcessError:
            print("Storage info not available")

        print("CPU")
        try:
            run_command("lscpu", return_output=False)
        except subprocess.CalledProcessError:
            print("CPU info not available")

        image_name = getattr(self, 'image_name', '')
        if image_name:
            print(LINE)
            print(f"Image {image_name} information:")
            print(LINE)
            print(f"Uncompressed size of the image: {self.ct_get_image_size_uncompressed(image_name)}")
            print(f"Compressed size of the image: {self.ct_get_image_size_compressed(image_name)}")
            print()

    def ct_get_image_size_uncompressed(self, image_name: str) -> str:
        """
        Get uncompressed image size.

        Args:
            image_name: Image name

        Returns:
            Size string in MB
        """
        try:
            size_bytes = run_command(
                f"docker inspect {image_name} -f '{{{{.Size}}}}'",
                return_output=True
            ).strip()
            size_mb = int(size_bytes) // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "Unknown"

    def ct_get_image_size_compressed(self, image_name: str) -> str:
        """
        Get compressed image size.

        Args:
            image_name: Image name

        Returns:
            Size string in MB
        """
        try:
            # Save image and compress to get size
            result = run_command(
                f"docker save {image_name} | gzip - | wc --bytes",
                return_output=True
            )
            size_bytes = int(result.strip())
            size_mb = size_bytes // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "Unknown"

    def ct_timestamp_s(self) -> int:
        """Get timestamp in seconds since Unix epoch."""
        return int(time.time())

    def ct_timestamp_pretty(self) -> str:
        """Get human-readable timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")

    def ct_timestamp_diff(self, start_date: int, final_date: int) -> str:
        """
        Compute time difference between timestamps.

        Args:
            start_date: Start timestamp
            final_date: End timestamp

        Returns:
            Time difference in HH:MM:SS format
        """
        diff_seconds = final_date - start_date
        hours, remainder = divmod(diff_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def ct_run_tests_from_testset(self, app_name: str = "appnamenotset", test_set: List[str] = None,
                                 image_name: str = "") -> None:
        """
        Run all tests in test set.

        Args:
            app_name: Application name for logging
            test_set: List of test functions to run
            image_name: Image name being tested
        """
        if test_set is None:
            test_set = []

        if not image_name:
            image_name = getattr(self, 'image_name', '')

        # Show git information if available
        try:
            print()
            run_command("git show -s", return_output=False)
            print()
        except subprocess.CalledProcessError:
            pass

        print(f"Running tests for image {image_name}")

        for test_case in test_set:
            testcase_result = 0

            # Check if test is unstable
            is_unstable = (app_name in self.unstable_tests or
                          test_case.__name__ in self.unstable_tests)

            time_beg_pretty = self.ct_timestamp_pretty()
            time_beg = self.ct_timestamp_s()

            print("-----------------------------------------------")
            print(f"Running test {test_case.__name__} (starting at {time_beg_pretty}) ... ")
            print("-----------------------------------------------")

            try:
                result = test_case()
                testcase_result = 0 if result else 1
            except Exception as e:
                logger.error(f"Test {test_case.__name__} failed with exception: {e}")
                testcase_result = 1

            time_end = self.ct_timestamp_s()

            if testcase_result == 0:
                test_msg = "[PASSED]"
            else:
                ignore_unstable = get_os_environment("IGNORE_UNSTABLE_TESTS")
                if ignore_unstable and is_unstable:
                    test_msg = "[FAILED][UNSTABLE-IGNORED]"
                else:
                    test_msg = "[FAILED]"
                    self.testsuite_result = 1

            time_diff = self.ct_timestamp_diff(time_beg, time_end)
            self.ct_update_test_result(test_msg, app_name, test_case.__name__, time_diff)

    def ct_update_test_result(self, test_msg: str, app_name: str, test_case: str,
                             time_diff: str = "") -> None:
        """
        Add result to test summary.

        Args:
            test_msg: Test result message
            app_name: Application name
            test_case: Test case name
            time_diff: Time difference string
        """
        result_line = f"{test_msg} for '{app_name}' {test_case} ({time_diff})\n"
        self.test_summary += result_line

    def ct_check_testcase_result(self, result: int, image_name: str = "") -> int:
        """
        Check testcase result and update overall result.

        Args:
            result: Test case result code
            image_name: Image name being tested

        Returns:
            Result code
        """
        if not image_name:
            image_name = getattr(self, 'image_name', '')

        if result != 0:
            print(f"Test for image '{image_name}' FAILED (exit code: {result})")
            self.testsuite_result = 1

        return result


# Global instance for backward compatibility
ct = ContainerTestLib()

# Function aliases for backward compatibility
def ct_init():
    """Initialize container testing environment."""
    return ct.ct_init()

def ct_cleanup():
    """Clean up containers and images."""
    return ct.ct_cleanup()

def ct_show_results(image_name: str = ""):
    """Show test results."""
    return ct.ct_show_results(image_name)

def ct_enable_cleanup():
    """Enable cleanup handlers."""
    return ct.ct_enable_cleanup()

# Add more function aliases as needed...
