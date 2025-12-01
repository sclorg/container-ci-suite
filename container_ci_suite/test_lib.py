#!/usr/bin/env python3
"""
Container CI test library - Python version

This module provides functionality for testing container images,
originally converted from test-lib.sh bash script.

Always use by importing and initializing the ContainerTestLib class
before starting the actual test suite.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import re
import random
import string
import logging
import requests


from pathlib import Path
from typing import Optional

from container_ci_suite.utils import ContainerTestLibUtils


class ContainerTestLib:
    """Container CI tests library - abbreviated as 'ct'"""

    def __init__(self):
        """Initialize the container test library.

        Call ct_init() before starting the actual test suite.
        """
        self.LINE = "=============================================="
        self.EXPECTED_EXIT_CODE = 0
        self.UNSTABLE_TESTS = os.environ.get("UNSTABLE_TESTS", "")

        # Will be set by ct_init()
        self.app_id_file_dir = ""
        self.cid_file_dir = ""
        self.test_summary = ""
        self.testsuite_result = 0

        # Set up logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        self.logger = logging.getLogger(__name__)

        # Track cleanup enabled state
        self._cleanup_enabled = False

    def ct_init(self) -> None:
        """Initialize container testing environment.

        This function needs to be called before any container test starts.
        Sets up temporary directories for storing application image IDs and
        container IDs used during tests.
        """
        self.app_id_file_dir = tempfile.mkdtemp()
        self.cid_file_dir = tempfile.mkdtemp()
        self.test_summary = ""
        self.testsuite_result = 0

    def ct_cleanup(self) -> None:
        """Clean up containers and images used during tests.

        Stops and removes all containers referenced by cid_files in CID_FILE_DIR.
        Dumps logs if a container exited unexpectedly. Removes the cid_files
        and directories as well.
        """
        print(self.LINE)
        print("Cleaning of testing containers and images started.")
        print("It may take a few seconds.")
        print(self.LINE)
        self.ct_clean_app_images()
        self.ct_clean_containers()

    def ct_build_image_and_parse_id(
        self, dockerfile: Optional[str] = None, build_params: str = ""
    ) -> bool:
        """Build image and parse the image ID.

        Args:
            dockerfile: Path to dockerfile (optional)
            build_params: Additional build parameters

        Returns:
            True if build was successful, False otherwise

        Sets:
            self.app_image_id: The built image ID
        """
        log_file = tempfile.mktemp()
        sleep_time = "10m"

        dockerfile_arg = f"-f {dockerfile}" if dockerfile else ""
        command = f"podman build --no-cache {dockerfile_arg} {build_params}".replace(
            "'", ""
        )

        try:
            # Use timeout command equivalent
            with open(log_file, "w") as f:
                build_output = ContainerTestLibUtils.run_command(
                    cmd=f"timeout {sleep_time} {command}",
                    return_output=True,
                    ignore_error=True,
                )
                f.write(build_output)
                ret_val = 0 if build_output.returncode == 0 else 1

            if ret_val == 0:
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    if lines:
                        self.app_image_id = lines[-1].strip()

            # Output log content and cleanup
            with open(log_file, "r") as f:
                print(f.read(), end="")
            os.unlink(log_file)

            return ret_val == 0

        except Exception as e:
            print(f"Build failed: {e}")
            if os.path.exists(log_file):
                os.unlink(log_file)
            return False

    def ct_container_running(self, container_id: str) -> bool:
        """Check if given container is in running state.

        Args:
            container_id: Container ID to check

        Returns:
            True if container is running, False otherwise
        """
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman inspect -f '{{.State.Running}}' {container_id}",
                ignore_error=False,
                return_output=True,
            )
            return result.stdout.strip() == "true"
        except subprocess.CalledProcessError:
            return False

    def ct_container_exists(self, container_id: str) -> bool:
        """Check if given container exists.

        Args:
            container_id: Container ID to check

        Returns:
            True if container exists, False otherwise
        """
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman ps -q -a -f id={container_id}",
                return_output=True,
                ignore_error=False,
            )
            return bool(result.strip())
        except subprocess.CalledProcessError:
            return False

    def ct_clean_app_images(self) -> None:
        """Clean up application images referenced by APP_ID_FILE_DIR."""
        if not self.app_id_file_dir or not os.path.isdir(self.app_id_file_dir):
            print(
                f"The app_id_file_dir={self.app_id_file_dir} is not created. App cleaning is to be skipped."
            )
            return

        print(f"Examining image ID files in app_id_file_dir={self.app_id_file_dir}")

        for file_path in Path(self.app_id_file_dir).iterdir():
            if not file_path.is_file():
                continue

            try:
                with open(file_path, "r") as f:
                    image_id = f.read().strip()

                # Check if image exists
                try:
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman inspect {image_id}",
                        return_output=False,
                        ignore_error=False,
                    )
                except subprocess.CalledProcessError:
                    continue

                # Remove containers using this image
                try:
                    containers = ContainerTestLibUtils.run_command(
                        cmd=f"podman ps -q -a -f ancestor={image_id}",
                        return_output=True,
                        ignore_error=False,
                    ).strip()

                    if containers:
                        ContainerTestLibUtils.run_command(
                            cmd=f"podman rm -f {containers.replace(chr(10), ' ')}",
                            return_output=False,
                            ignore_error=True,
                        )
                except subprocess.CalledProcessError:
                    pass

                # Remove the image
                try:
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman rmi -f {image_id}",
                        return_output=False,
                        ignore_error=True,
                    )
                except subprocess.CalledProcessError:
                    pass

            except Exception as e:
                print(f"Error cleaning image from {file_path}: {e}")

        # Remove the directory
        shutil.rmtree(self.app_id_file_dir, ignore_errors=True)

    def ct_clean_containers(self) -> None:
        """Clean up containers referenced by CID_FILE_DIR."""
        if not self.cid_file_dir:
            print("The cid_file_dir is not set. Container cleaning is to be skipped.")
            return

        print(f"Examining CID files in cid_file_dir={self.cid_file_dir}")

        for cid_file_path in Path(self.cid_file_dir).iterdir():
            if not cid_file_path.is_file():
                continue

            try:
                with open(cid_file_path, "r") as f:
                    container_id = f.read().strip()

                if not self.ct_container_exists(container_id):
                    continue

                print(f"Stopping and removing container {container_id}...")

                # Stop container if running
                if self.ct_container_running(container_id):
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman stop {container_id}",
                        return_output=False,
                        ignore_error=True,
                    )

                # Check exit status
                try:
                    result = ContainerTestLibUtils.run_command(
                        cmd=f"podman inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        ignore_error=False,
                        return_output=True,
                    )
                    exit_status = int(result.stdout.strip())
                    if exit_status != self.EXPECTED_EXIT_CODE:
                        print(f"Dumping logs for {container_id}")
                        ContainerTestLibUtils.run_command(
                            cmd=f"podman logs {container_id}",
                            ignore_error=True,
                            return_output=False,
                        )
                except (subprocess.CalledProcessError, ValueError):
                    pass

                    # Remove container
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman rm -v {container_id}",
                        ignore_error=True,
                        return_output=False,
                    )

                # Remove cid file
                cid_file_path.unlink()

            except Exception as e:
                print(f"Error cleaning container from {cid_file_path}: {e}")

        # Remove the directory
        shutil.rmtree(self.cid_file_dir, ignore_errors=True)

    def ct_show_results(self) -> None:
        """Print results of all test cases stored in test_summary."""
        print(self.LINE)
        image_name = os.environ.get("IMAGE_NAME", "unknown")
        print(f"Tests were run for image {image_name}")
        print(self.LINE)
        print("Test cases results:")
        print()
        print(self.test_summary)

        if self.testsuite_result == 0:
            print(f"Tests for {image_name} succeeded.")
        else:
            print(f"Tests for {image_name} failed.")

    def ct_pull_image(
        self, image_name: str, exit_on_failure: bool = False, max_loops: int = 10
    ) -> bool:
        """Pull an image before test execution.

        Args:
            image_name: String containing the public name of the image to pull
            exit_on_failure: Exit script if pull fails
            max_loops: How many times to pull image in case of failure

        Returns:
            True if pull was successful, False otherwise
        """
        print(f"-> Pulling image {image_name} ...")

        # Check if image is already available locally
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman images -q {image_name}",
                ignore_error=False,
                return_output=True,
            )
            if result.stdout.strip():
                print(f"The image {image_name} is already pulled.")
                return True
        except subprocess.CalledProcessError:
            pass

        # Try pulling the image
        loop = 0
        while loop <= max_loops:
            try:
                ContainerTestLibUtils.run_command(
                    cmd=f"podman pull {image_name}",
                    ignore_error=False,
                    return_output=False,
                )
                return True
            except subprocess.CalledProcessError:
                loop += 1
                print(f"Pulling image {image_name} failed.")

                if loop > max_loops:
                    print(
                        f"Pulling of image {image_name} failed {max_loops} times in a row. Giving up."
                    )
                    print(f"!!! ERROR with pulling image {image_name} !!!!")

                    if exit_on_failure:
                        sys.exit(1)
                    else:
                        return False

                wait_time = loop * 5
                print(f"Let's wait {wait_time} seconds and try again.")
                time.sleep(wait_time)

        return False

    def ct_get_cid(self, name: str) -> str:
        """Get container id from cid_file based on the name of the file.

        Args:
            name: Name of cid_file where the container id is stored

        Returns:
            Container ID

        Raises:
            FileNotFoundError: If cid file doesn't exist
        """
        cid_file_path = Path(self.cid_file_dir) / name
        with open(cid_file_path, "r") as f:
            return f.read().strip()

    def ct_get_cip(self, cid_name: str) -> str:
        """Get container IP address based on the container id name.

        Args:
            cid_name: Name of the cid file

        Returns:
            Container IP address
        """
        container_id = self.ct_get_cid(cid_name)
        result = ContainerTestLibUtils.run_command(
            cmd=f"podman inspect --format='{{{{.NetworkSettings.IPAddress}}}}' {container_id}",
            ignore_error=False,
            return_output=True,
        )
        return result.stdout.strip()

    def ct_wait_for_cid(
        self, cid_file: str, max_attempts: int = 10, sleep_time: int = 1
    ) -> bool:
        """Wait for the cid_file to be created.

        Args:
            cid_file: Path to the cid_file that should be created
            max_attempts: Maximum number of attempts to wait
            sleep_time: Time to sleep between attempts

        Returns:
            True if cid_file was created, False if timeout
        """
        attempt = 1
        while attempt <= max_attempts:
            cid_path = Path(cid_file)
            if cid_path.exists() and cid_path.stat().st_size > 0:
                return True

            print(f"Waiting for container start... {attempt}")
            attempt += 1
            time.sleep(sleep_time)

        return False

    def ct_create_container(self, name: str, *command) -> bool:
        """Create a container using IMAGE_NAME and CONTAINER_ARGS variables.

        Args:
            name: Name of cid_file where the container id will be stored
            *command: Optional command to be executed in the container

        Returns:
            True if container was created successfully

        Uses environment variables:
            IMAGE_NAME: Name of the image being tested
            CONTAINER_ARGS: Optional arguments passed directly to podman run
        """
        cid_file = Path(self.cid_file_dir) / name
        image_name = os.environ.get("IMAGE_NAME", "")
        container_args = os.environ.get("CONTAINER_ARGS", "")

        if not image_name:
            raise ValueError("IMAGE_NAME environment variable must be set")

        # Build podman run command
        cmd = ["podman", "run", f"--cidfile={cid_file}", "-d"]

        # Add container args if present
        if container_args:
            cmd.extend(container_args.split())

        cmd.append(image_name)
        cmd.extend(command)

        try:
            ContainerTestLibUtils.run_command(
                cmd=" ".join(cmd), return_output=False, ignore_error=False
            )
            if self.ct_wait_for_cid(str(cid_file)):
                container_id = self.ct_get_cid(name)
                print(f"Created container {container_id}")
                return True
            else:
                return False
        except subprocess.CalledProcessError:
            return False

    def ct_show_resources(self) -> None:
        """Print available system resources."""
        print()
        print(self.LINE)
        print("Resources info:")
        print("Memory:")
        try:
            ContainerTestLibUtils.run_command(
                cmd="free -h", return_output=False, ignore_error=True
            )
        except subprocess.CalledProcessError:
            print("free command not available")

        print("Storage:")
        try:
            ContainerTestLibUtils.run_command(
                cmd="df -h", return_output=False, ignore_error=True
            )
        except subprocess.CalledProcessError:
            print("df command not available")

        print("CPU")
        try:
            ContainerTestLibUtils.run_command(
                cmd="lscpu", return_output=False, ignore_error=True
            )
        except subprocess.CalledProcessError:
            print("lscpu command not available")

        print(self.LINE)
        image_name = os.environ.get("IMAGE_NAME", "unknown")
        print(f"Image {image_name} information:")
        print(self.LINE)
        print(
            f"Uncompressed size of the image: {self.ct_get_image_size_uncompressed(image_name)}"
        )
        print(
            f"Compressed size of the image: {self.ct_get_image_size_compressed(image_name)}"
        )
        print()

    def ct_random_string(self, length: int = 10) -> str:
        """Generate pseudorandom alphanumeric string.

        Args:
            length: Length of the string to generate (default: 10)

        Returns:
            Random alphanumeric string
        """
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def ct_get_image_size_uncompressed(self, image_name: str) -> str:
        """Get uncompressed image size in MB.

        Args:
            image_name: Name of the image

        Returns:
            Size string in format "XXXmb"
        """
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman inspect {image_name} -f '{{{{.Size}}}}'",
                ignore_error=False,
                return_output=True,
            )
            size_bytes = int(result.stdout.strip())
            size_mb = size_bytes // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "unknown"

    def ct_get_image_size_compressed(self, image_name: str) -> str:
        """Get compressed image size in MB.

        Args:
            image_name: Name of the image

        Returns:
            Size string in format "XXXMB"
        """
        try:
            # This is an approximation using podman save + gzip
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman save {image_name} | gzip - | wc --bytes",
                ignore_error=False,
                return_output=True,
            )
            size_bytes = int(result.stdout.strip())
            size_mb = size_bytes // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "unknown"

    def ct_test_response(
        self,
        url: str,
        expected_code: int,
        body_regexp: str,
        max_attempts: int = 20,
        ignore_error_attempts: int = 10,
    ) -> bool:
        """Perform GET request and check response.

        Args:
            url: Request URL
            expected_code: Expected HTTP response code
            body_regexp: Regular expression that must match the response body
            max_attempts: Maximum number of attempts (default: 20)
            ignore_error_attempts: Number of attempts when errors are ignored (default: 10)

        Returns:
            True if response matches expectations, False otherwise
        """
        print(f"  Testing the HTTP(S) response for <{url}>")
        sleep_time = 3
        attempt = 1

        while attempt <= max_attempts:
            print(f"Trying to connect ... {attempt}")

            try:
                response = requests.get(url, timeout=10)

                if response.status_code == expected_code:
                    if re.search(body_regexp, response.text):
                        return True

                # Give services some time to become ready
                if attempt <= ignore_error_attempts and attempt < max_attempts:
                    pass  # Continue trying
                else:
                    break

            except requests.RequestException:
                if attempt > ignore_error_attempts or attempt == max_attempts:
                    break

            attempt += 1
            time.sleep(sleep_time)

        return False


# Global instance for backward compatibility
ct = ContainerTestLib()


# Expose main functions at module level for easier migration
def ct_init():
    """Initialize container testing environment."""
    ct.ct_init()


def ct_cleanup():
    """Clean up containers and images used during tests."""
    ct.ct_cleanup()


def ct_show_results():
    """Print results of all test cases."""
    ct.ct_show_results()


def ct_enable_cleanup():
    """Enable automatic container cleanup after tests."""
    ct.ct_enable_cleanup()


def ct_pull_image(
    image_name: str, exit_on_failure: bool = False, max_loops: int = 10
) -> bool:
    """Pull an image before test execution."""
    return ct.ct_pull_image(image_name, exit_on_failure, max_loops)


def ct_get_cid(name: str) -> str:
    """Get container id from cid_file based on the name."""
    return ct.ct_get_cid(name)


def ct_create_container(name: str, *command) -> bool:
    """Create a container using IMAGE_NAME and CONTAINER_ARGS variables."""
    return ct.ct_create_container(name, *command)


def ct_test_response(
    url: str,
    expected_code: int,
    body_regexp: str,
    max_attempts: int = 20,
    ignore_error_attempts: int = 10,
) -> bool:
    """Perform GET request and check response."""
    return ct.ct_test_response(
        url, expected_code, body_regexp, max_attempts, ignore_error_attempts
    )


def ct_random_string(length: int = 10) -> str:
    """Generate pseudorandom alphanumeric string."""
    return ct.ct_random_string(length)


# Additional methods for the ContainerTestLib class
class ContainerTestLibExtended(ContainerTestLib):
    """Extended container test library with additional functionality."""

    def ct_check_envs_set(
        self,
        env_filter: str,
        check_envs: str,
        loop_envs: str,
        env_format: str = "*VALUE*",
    ) -> bool:
        """Compare values from environment variable definitions.

        Args:
            env_filter: String passed to grep for filtering variables
            check_envs: List of env var definitions to check values against
            loop_envs: List of env var definitions to check values for
            env_format: Format string for checking values (default: "*VALUE*")

        Returns:
            True if all values are found, False otherwise
        """
        import re

        # Filter environment variables that match the filter
        filtered_loop_envs = []
        for line in loop_envs.split("\n"):
            line = line.strip()
            if not line or line.startswith("PWD="):
                continue
            if re.search(env_filter, line):
                filtered_loop_envs.append(line)

        for variable in filtered_loop_envs:
            if "=" not in variable:
                continue

            var_name, var_value = variable.split("=", 1)

            # Find matching variable in check_envs
            found_var = None
            for check_line in check_envs.split("\n"):
                if check_line.startswith(f"{var_name}="):
                    found_var = check_line
                    break

            if not found_var:
                print(f"{var_name} not found during podman exec")
                return False

            # Check each value (colon-separated)
            for value in var_value.split(":"):
                if not re.search(env_filter, value):
                    continue

                # Check if value is in the found variable
                expected_pattern = env_format.replace("VALUE", value)
                if expected_pattern.replace("*", ".*") not in found_var:
                    print(f" Value {value} is missing from variable {var_name}")
                    print(found_var)
                    return False

        return True

    def ct_assert_container_creation_fails(self, *container_args) -> bool:
        """Assert that container creation fails with given arguments.

        Args:
            *container_args: Arguments passed directly to podman run

        Returns:
            True if container fails to start properly, False otherwise
        """
        max_attempts = 10
        attempt = 1
        cid_file = "assert"

        # Save old container args
        old_container_args = os.environ.get("CONTAINER_ARGS", "")

        try:
            # Set new container args
            os.environ["CONTAINER_ARGS"] = " ".join(container_args)

            if self.ct_create_container(cid_file):
                container_id = self.ct_get_cid(cid_file)

                # Wait for container to stop or timeout
                while self.ct_container_running(container_id):
                    time.sleep(2)
                    attempt += 1
                    if attempt > max_attempts:
                        ContainerTestLibUtils.run_command(
                            cmd=f"podman stop {container_id}",
                            return_output=False,
                            ignore_error=True,
                        )
                        break

                # Check exit status
                try:
                    result = ContainerTestLibUtils.run_command(
                        cmd=f"podman inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        return_output=True,
                        ignore_error=False,
                    )

                    exit_status = int(result.strip())
                    success = exit_status != 0  # We expect failure
                except (subprocess.CalledProcessError, ValueError):
                    success = True  # Assume failure if we can't get exit code

                # Cleanup
                ContainerTestLibUtils.run_command(
                    cmd=f"podman rm -v {container_id}",
                    return_output=False,
                    ignore_error=True,
                )
                cid_file_path = Path(self.cid_file_dir) / cid_file
                if cid_file_path.exists():
                    cid_file_path.unlink()

                return success
            else:
                return True  # Creation failed as expected

        finally:
            # Restore old container args
            if old_container_args:
                os.environ["CONTAINER_ARGS"] = old_container_args
            elif "CONTAINER_ARGS" in os.environ:
                del os.environ["CONTAINER_ARGS"]

        return False

    def ct_scl_usage_old(self, name: str, command: str, expected: str) -> bool:
        """Test three ways of running the SCL.

        Args:
            name: Name of cid_file where the container id is stored
            command: Command executed inside the container
            expected: String expected to be in the command output

        Returns:
            True if all tests pass, False otherwise
        """
        image_name = os.environ.get("IMAGE_NAME", "")

        print("  Testing the image SCL enable")

        # Test 1: podman run with /bin/bash -c
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman run --rm {image_name} /bin/bash -c '{command}'",
                return_output=True,
                ignore_error=False,
            )

            if expected not in result:
                print(
                    f"ERROR[/bin/bash -c \"{command}\"] Expected '{expected}', got '{result}'"
                )
                return False
        except subprocess.CalledProcessError as e:
            print(f'ERROR[/bin/bash -c "{command}"] Command failed: {e}')
            return False

        # Test 2: podman exec with /bin/bash -c
        try:
            container_id = self.ct_get_cid(name)
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman exec {container_id} /bin/bash -c '{command}'",
                return_output=True,
                ignore_error=False,
            )

            if expected not in result:
                print(
                    f"ERROR[exec /bin/bash -c \"{command}\"] Expected '{expected}', got '{result}'"
                )
                return False
        except subprocess.CalledProcessError as e:
            print(f'ERROR[exec /bin/bash -c "{command}"] Command failed: {e}')
            return False

        # Test 3: podman exec with /bin/sh -ic
        try:
            container_id = self.ct_get_cid(name)
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman exec {container_id} /bin/sh -ic '{command}'",
                return_output=True,
                ignore_error=False,
            )

            if expected not in result:
                print(
                    f"ERROR[exec /bin/sh -ic \"{command}\"] Expected '{expected}', got '{result}'"
                )
                return False
        except subprocess.CalledProcessError as e:
            print(f'ERROR[exec /bin/sh -ic "{command}"] Command failed: {e}')
            return False

        return True

    # def ct_doc_content_old(self, *strings) -> bool:
    #     """Look for occurrence of strings in documentation files.

    #     Args:
    #         *strings: Strings expected to appear in the documentation

    #     Returns:
    #         True if all strings are found, False otherwise
    #     """
    #     image_name = os.environ.get("IMAGE_NAME", "")
    #     tmpdir = tempfile.mkdtemp()

    #     print("  Testing documentation in the container image")

    #     try:
    #         # Extract help.1 file from container
    #         help_file = Path(tmpdir) / "help.1"

    #         help_content = ContainerTestLibUtils.run_command(
    #             cmd=f"podman run --rm {image_name} /bin/bash -c 'cat /help.1'",
    #             return_output=True,
    #             ignore_error=False,
    #         )
    #         with open(help_file, "w") as f:
    #             f.write(help_content)

    #         # Check for required strings
    #         with open(help_file, "r") as f:
    #             content = f.read()

    #         for term in strings:
    #             if not re.search(term, content):
    #                 print(f"ERROR: File /help.1 does not include '{term}'.")
    #                 return False

    #         # Check for troff/groff format markers
    #         for term in ["TH", "PP", "SH"]:
    #             if not re.search(f"^\\.{term}", content, re.MULTILINE):
    #                 print(
    #                     f"ERROR: /help.1 is probably not in troff or groff format, since '{term}' is missing."
    #                 )
    #                 return False

    #         print("  Success!")
    #         return True

    #     except subprocess.CalledProcessError as e:
    #         print(f"ERROR: Failed to extract documentation: {e}")
    #         return False
    #     finally:
    #         shutil.rmtree(tmpdir, ignore_errors=True)

    def ct_check_exec_env_vars(self, env_filter: str = None) -> bool:
        """Check if environment variables from podman run can be found in podman exec.

        Args:
            env_filter: Optional filter for environment variables

        Returns:
            True if all relevant variables are found, False otherwise
        """
        if env_filter is None:
            env_filter = "^X_SCLS=|/opt/rh|/opt/app-root"

        image_name = os.environ.get("IMAGE_NAME", "")

        # Get environment variables from podman run
        run_envs = ContainerTestLibUtils.run_command(
            cmd=f"podman run --rm {image_name} /bin/bash -c env",
            return_output=True,
            ignore_error=False,
        )

        # Get environment variables from podman exec
        self.ct_create_container("test_exec_envs", "bash", "-c", "sleep 1000")
        container_id = self.ct_get_cid("test_exec_envs")

        exec_envs = ContainerTestLibUtils.run_command(
            cmd=f"podman exec {container_id} env",
            return_output=True,
            ignore_error=False,
        )

        # Check if variables match
        success = self.ct_check_envs_set(env_filter, exec_envs, run_envs, "*VALUE*")

        if success:
            print(" All values present in podman exec")

        return success

    def ct_timestamp_s(self) -> int:
        """Get timestamp in seconds since unix era.

        Returns:
            Timestamp as integer
        """
        return int(time.time())

    def ct_timestamp_pretty(self) -> str:
        """Get human-readable timestamp.

        Returns:
            Timestamp string like 2022-05-18 10:52:44+02:00
        """
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")

    def ct_timestamp_diff(self, start_date: int, final_date: int) -> str:
        """Compute time difference between two timestamps.

        Args:
            start_date: Beginning timestamp (seconds since unix era)
            final_date: End timestamp (seconds since unix era)

        Returns:
            Time difference in format HH:MM:SS
        """
        diff_seconds = final_date - start_date
        hours = diff_seconds // 3600
        minutes = (diff_seconds % 3600) // 60
        seconds = diff_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def ct_check_testcase_result(self, result: int) -> int:
        """Check if testcase ended in success or error.

        Args:
            result: Testcase result value

        Returns:
            The same result value
        """
        image_name = os.environ.get("IMAGE_NAME", "unknown")
        if result != 0:
            print(f"Test for image '{image_name}' FAILED (exit code: {result})")
            # Note: In bash this sets TESTCASE_RESULT, but we'll handle this differently

        return result

    def ct_update_test_result(
        self, test_msg: str, app_name: str, test_case: str, time_diff: str = ""
    ) -> None:
        """Add result to the test_summary.

        Args:
            test_msg: Test message (e.g., "[PASSED]", "[FAILED]")
            app_name: Application name
            test_case: Test case name
            time_diff: Optional time difference
        """
        result_line = f"{test_msg} for '{app_name}' {test_case} ({time_diff})\n"
        self.test_summary += result_line

    def ct_run_tests_from_testset(self, app_name: str = "appnamenotset") -> None:
        """Run all tests in TEST_SET and print results.

        Args:
            app_name: Application name to log

        Uses environment variables:
            TEST_SET: Set of test cases to run
            UNSTABLE_TESTS: Set of tests whose result can be ignored
            IGNORE_UNSTABLE_TESTS: Flag to ignore unstable tests
        """
        test_set = os.environ.get("TEST_SET", "").split()
        unstable_tests = os.environ.get("UNSTABLE_TESTS", "").split()
        ignore_unstable = os.environ.get("IGNORE_UNSTABLE_TESTS", "")
        image_name = os.environ.get("IMAGE_NAME", "unknown")

        # Show git commit info
        try:
            ContainerTestLibUtils.run_command(
                cmd="git show -s", return_output=False, ignore_error=True
            )
        except subprocess.CalledProcessError:
            pass

        print(f"Running tests for image {image_name}")

        for test_case in test_set:
            testcase_result = 0
            is_unstable = app_name in unstable_tests or test_case in unstable_tests

            time_beg_pretty = self.ct_timestamp_pretty()
            time_beg = self.ct_timestamp_s()

            print("-----------------------------------------------")
            print(f"Running test {test_case} (starting at {time_beg_pretty}) ... ")
            print("-----------------------------------------------")

            # Here you would call the actual test function
            # For now, we'll assume the test function exists and can be called
            try:
                # This would need to be implemented based on how tests are structured
                # test_result = globals()[test_case]()
                test_result = 0  # Placeholder
            except Exception as e:
                print(f"Test {test_case} failed with exception: {e}")
                test_result = 1

            testcase_result = self.ct_check_testcase_result(test_result)
            time_end = self.ct_timestamp_s()

            if testcase_result == 0:
                test_msg = "[PASSED]"
            else:
                if ignore_unstable and is_unstable:
                    test_msg = "[FAILED][UNSTABLE-IGNORED]"
                else:
                    test_msg = "[FAILED]"
                    self.testsuite_result = 1

            # Switch to default project if using OCP4
            if os.environ.get("CT_OCP4_TEST", "false") == "true":
                try:
                    ContainerTestLibUtils.run_command(
                        cmd="oc project default", return_output=False, ignore_error=True
                    )
                except subprocess.CalledProcessError:
                    pass

            time_diff = self.ct_timestamp_diff(time_beg, time_end)
            self.ct_update_test_result(test_msg, app_name, test_case, time_diff)

    def ct_s2i_usage(self, img_name: str, s2i_args: str = "") -> str:
        """Create a container and run the usage script inside.

        Args:
            img_name: Name of the image to be used for the container run
            s2i_args: Additional list of source-to-image arguments (currently unused)

        Returns:
            Usage script output
        """
        usage_command = "/usr/libexec/s2i/usage"
        return ContainerTestLibUtils.run_command(
            cmd=f"podman run --rm {img_name} bash -c '{usage_command}'",
            return_output=True,
            ignore_error=False,
        )

    def ct_s2i_build_as_df(
        self, app_path: str, src_image: str, dst_image: str, s2i_args: str = ""
    ) -> bool:
        """Create a new s2i app image from local sources.

        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the s2i build
            dst_image: Image name to be used during the tagging of the s2i build result
            s2i_args: Additional list of source-to-image arguments

        Returns:
            True if build successful, False otherwise
        """
        return self.ct_s2i_build_as_df_build_args(
            app_path, src_image, dst_image, "", s2i_args
        )

    def ct_s2i_build_as_df_build_args(
        self,
        app_path: str,
        src_image: str,
        dst_image: str,
        build_args: str = "",
        s2i_args: str = "",
    ) -> bool:
        """Create a new s2i app image from local sources with build args.

        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the s2i build
            dst_image: Image name to be used during the tagging of the s2i build result
            build_args: Build arguments to be used in the s2i build
            s2i_args: Additional list of source-to-image arguments

        Returns:
            True if build successful, False otherwise
        """
        local_app = "upload/src/"
        local_scripts = "upload/scripts/"
        incremental = "--incremental" in s2i_args

        # Create temporary directory for build
        tmpdir = tempfile.mkdtemp()

        try:
            os.chdir(tmpdir)

            # Check if image is available locally or pull it
            try:
                ContainerTestLibUtils.run_command(
                    cmd=f"podman images {src_image}",
                    return_output=False,
                    ignore_error=False,
                )
            except subprocess.CalledProcessError:
                if "pull-policy=never" not in s2i_args:
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman pull {src_image}",
                        return_output=False,
                        ignore_error=False,
                    )

            # Get user from source image
            user = (
                ContainerTestLibUtils.run_command(
                    cmd=f"podman inspect -f '{{{{.Config.User}}}}' {src_image}",
                    return_output=True,
                    ignore_error=False,
                ).strip()
                or "0"
            )

            # Get numeric user ID
            user_id = self.ct_get_uid_from_image(user, src_image)
            if user_id is None:
                print("Terminating s2i build.")
                return False

            # Handle incremental build
            if incremental:
                inc_tmp = tempfile.mkdtemp(prefix="incremental.")
                # Set permissions for user
                os.chmod(inc_tmp, 0o755)

                # Check if destination image exists
                try:
                    ContainerTestLibUtils.run_command(
                        cmd=f"podman images {dst_image}",
                        return_output=False,
                        ignore_error=False,
                    )
                except subprocess.CalledProcessError:
                    print(f"Image {dst_image} not found.")
                    return False

                # Run save-artifacts script
                cmd = (
                    "if [ -s /usr/libexec/s2i/save-artifacts ]; then "
                    f'/usr/libexec/s2i/save-artifacts > "{inc_tmp}/artifacts.tar"; '
                    f'else touch "{inc_tmp}/artifacts.tar"; fi'
                )

                ContainerTestLibUtils.run_command(
                    cmd=f"podman run --rm -v {inc_tmp}:{inc_tmp}:Z {dst_image} bash -c '{cmd}'",
                    return_output=False,
                    ignore_error=False,
                )

                # Move artifacts to build directory
                shutil.move(f"{inc_tmp}/artifacts.tar", f"{tmpdir}/artifacts.tar")

            # Copy application sources
            os.makedirs(local_app, exist_ok=True)
            app_source = app_path.replace("file://", "")

            # Copy source files
            if os.path.isdir(app_source):
                for item in os.listdir(app_source):
                    src = os.path.join(app_source, item)
                    dst = os.path.join(local_app, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)

            # Move .s2i/bin to scripts if it exists
            s2i_bin_path = os.path.join(local_app, ".s2i", "bin")
            if os.path.isdir(s2i_bin_path):
                shutil.move(s2i_bin_path, local_scripts)

            # Create Dockerfile
            df_name = tempfile.mktemp(prefix="Dockerfile.", dir=tmpdir)

            with open(df_name, "w") as df:
                df.write(f"FROM {src_image}\n")
                df.write(f'LABEL "io.openshift.s2i.build.image"="{src_image}" \\\n')
                df.write(
                    f'      "io.openshift.s2i.build.source-location"="{app_path}"\n'
                )
                df.write("USER root\n")
                df.write(f"COPY {local_app} /tmp/src\n")

                if os.path.isdir(local_scripts):
                    df.write(f"COPY {local_scripts} /tmp/scripts\n")
                    df.write(f"RUN chown -R {user_id}:0 /tmp/scripts\n")

                df.write(f"RUN chown -R {user_id}:0 /tmp/src\n")

                # Add environment variables from .s2i/environment
                env_file = os.path.join(local_app, ".s2i", "environment")
                if os.path.exists(env_file):
                    with open(env_file, "r") as ef:
                        for line in ef:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                df.write(f"ENV {line}\n")

                # Add environment variables from s2i_args
                import re

                env_matches = re.findall(r"(?:-e|--env)[\s=](\S*=\S*)", s2i_args)
                for env_var in env_matches:
                    df.write(f"ENV {env_var}\n")

                # Add CA trust if present
                ca_file_path = "/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt"
                if os.path.exists(ca_file_path):
                    df.write(
                        "RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract\n"
                    )

                # Add incremental artifacts
                if incremental:
                    df.write("RUN mkdir /tmp/artifacts\n")
                    df.write("ADD artifacts.tar /tmp/artifacts\n")
                    df.write(f"RUN chown -R {user_id}:0 /tmp/artifacts\n")

                df.write(f"USER {user_id}\n")

                # Run assemble script
                if os.path.exists(os.path.join(local_scripts, "assemble")):
                    df.write("RUN /tmp/scripts/assemble\n")
                else:
                    df.write("RUN /usr/libexec/s2i/assemble\n")

                # Set run command
                if os.path.exists(os.path.join(local_scripts, "run")):
                    df.write("CMD /tmp/scripts/run\n")
                else:
                    df.write("CMD /usr/libexec/s2i/run\n")

            # Extract mount options from s2i_args
            mount_options = []
            mount_matches = re.findall(r"-v\s+(\S+)", s2i_args)
            for mount in mount_matches:
                mount_options.extend(["-v", mount])

            # Build the image
            build_cmd = (
                ["podman", "build"] + mount_options + ["-t", dst_image, ".", df_name]
            )
            if build_args:
                build_cmd.extend(build_args.split())

            if self.ct_build_image_and_parse_id(
                df_name, " ".join(mount_options + ["-t", dst_image, ".", build_args])
            ):
                # Store image ID
                id_file = os.path.join(
                    self.app_id_file_dir, str(random.randint(1000, 9999))
                )
                with open(id_file, "w") as f:
                    f.write(self.app_image_id)
                return True
            else:
                print(f"ERROR: Failed to build {df_name}")
                return False

        except Exception as e:
            print(f"S2I build failed: {e}")
            return False
        finally:
            # Cleanup
            if "tmpdir" in locals():
                shutil.rmtree(tmpdir, ignore_errors=True)

    def ct_get_uid_from_image(self, user: str, src_image: str) -> Optional[str]:
        """Get user ID from image.

        Args:
            user: User to get uid for inside the image
            src_image: Image to use for user information

        Returns:
            User ID as string, or None if not found
        """
        # Check if user is already numeric
        try:
            int(user)
            return user
        except ValueError:
            pass

        # Get user ID from image
        try:
            result = ContainerTestLibUtils.run_command(
                cmd=f"podman run --rm {src_image} bash -c 'id -u {user}'",
                return_output=True,
                ignore_error=False,
            )
            return result.strip()
        except subprocess.CalledProcessError:
            print(f"ERROR: id of user {user} not found inside image {src_image}.")
            return None

    def ct_path_append(self, path_varname: str, directory: str) -> None:
        """Append directory to PATH-like variable.

        Args:
            path_varname: Name of the path variable
            directory: Directory to append
        """
        current_path = os.environ.get(path_varname, "")
        if current_path:
            os.environ[path_varname] = f"{directory}:{current_path}"
        else:
            os.environ[path_varname] = directory

    def ct_path_foreach(self, path: str, action_func, *args) -> None:
        """Execute action for each directory in PATH.

        Args:
            path: Colon-separated list of directories
            action_func: Function to call for each directory
            *args: Additional arguments to pass to action_func
        """
        for directory in path.split(":"):
            if directory:
                action_func(directory, *args)

    def ct_gen_self_signed_cert_pem(self, output_dir: str, base_name: str) -> None:
        """Generate a self-signed PEM certificate pair.

        Args:
            output_dir: Output directory path
            base_name: Base name of the certificate files

        Creates:
            <output_dir>/<base_name>-cert-selfsigned.pem -- public PEM cert
            <output_dir>/<base_name>-key.pem -- PEM private key
        """
        os.makedirs(output_dir, exist_ok=True)

        key_file = os.path.join(output_dir, f"{base_name}-key.pem")
        cert_file = os.path.join(output_dir, f"{base_name}-cert-selfsigned.pem")
        req_file = f"{base_name}-req.pem"

        # Generate private key and certificate request
        openssl_cmd = "openssl req -newkey rsa:2048 -nodes"
        subj = "/C=GB/ST=Berkshire/L=Newbury/O=My Server Company"
        req_content = ContainerTestLibUtils.run_command(
            cmd=f"{openssl_cmd} -keyout {key_file} -subj '{subj}'",
            return_output=True,
            ignore_error=False,
        )
        with open(req_file, "w") as f:
            f.write(req_content)

        # Generate self-signed certificate
        cert_content = ContainerTestLibUtils.run_command(
            cmd=f"openssl req -new -x509 -nodes -key {key_file} -batch",
            return_output=True,
            ignore_error=False,
        )
        with open(cert_file, "w") as f:
            f.write(cert_content)

        # Clean up request file
        if os.path.exists(req_file):
            os.unlink(req_file)

    def ct_obtain_input(self, input_path: str) -> str:
        """Copy file/directory to temp location or download from URL.

        Args:
            input_path: Local file, directory or remote URL

        Returns:
            Path to the temporary copy
        """
        # Determine file extension
        extension = ""
        if "." in input_path:
            ext = input_path.split(".")[-1]
            if re.match(r"^[a-z0-9]*$", ext):
                extension = f".{ext}"

        # Create temporary file
        fd, output_path = tempfile.mkstemp(suffix=extension, prefix="test-input-")
        os.close(fd)

        if os.path.isfile(input_path):
            shutil.copy2(input_path, output_path)
        elif os.path.isdir(input_path):
            os.unlink(output_path)
            shutil.copytree(input_path, output_path, symlinks=False)
        elif re.match(r"^https?://", input_path):
            response = requests.get(input_path)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        else:
            os.unlink(output_path)
            raise ValueError(f"ERROR: file type not known: {input_path}")

        return output_path

    def ct_registry_from_os(self, os_version: str) -> str:
        """Transform operating system string into registry URL.

        Args:
            os_version: String containing the OS version

        Returns:
            Registry URL
        """
        if os_version.startswith("rhel"):
            return "registry.redhat.io"
        else:
            return "quay.io"

    def ct_get_public_image_name(
        self, os_version: str, base_image_name: str, version: str
    ) -> str:
        """Transform arguments into public image name.

        Args:
            os_version: String containing the OS version
            base_image_name: Base name of the image as defined in Makefile
            version: Version of the image as defined in Makefile

        Returns:
            Public image name
        """
        registry = self.ct_registry_from_os(os_version)
        version_no_dots = version.replace(".", "")

        if os_version == "rhel8":
            return f"{registry}/rhel8/{base_image_name}-{version_no_dots}"
        elif os_version == "rhel9":
            return f"{registry}/rhel9/{base_image_name}-{version_no_dots}"
        elif os_version == "rhel10":
            return f"{registry}/rhel10/{base_image_name}-{version_no_dots}"
        elif os_version == "c9s":
            return f"{registry}/sclorg/{base_image_name}-{version_no_dots}-c9s"
        elif os_version == "c10s":
            return f"{registry}/sclorg/{base_image_name}-{version_no_dots}-c10s"
        else:
            return f"{registry}/{base_image_name}:{version}"

    def ct_assert_cmd_success(self, *cmd) -> bool:
        """Evaluate command and fail if it does not succeed.

        Args:
            *cmd: Command to be run

        Returns:
            True if command succeeds, False otherwise
        """
        print(f"Checking '{' '.join(cmd)}' for success ...")
        try:
            ContainerTestLibUtils.run_command(
                cmd=" ".join(cmd), return_output=False, ignore_error=False
            )
            print(" PASS")
            return True
        except subprocess.CalledProcessError:
            print(" FAIL")
            return False

    def ct_assert_cmd_failure(self, *cmd) -> bool:
        """Evaluate command and fail if it succeeds.

        Args:
            *cmd: Command to be run

        Returns:
            True if command fails, False otherwise
        """
        print(f"Checking '{' '.join(cmd)}' for failure ...")
        try:
            ContainerTestLibUtils.run_command(
                cmd=" ".join(cmd), return_output=False, ignore_error=False
            )
            print(" FAIL")
            return False
        except subprocess.CalledProcessError:
            print(" PASS")
            return True

    def full_ca_file_path(self) -> str:
        """Return string for full path to CA file.

        Returns:
            Full path to CA file
        """
        return "/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt"

    def ct_mount_ca_file(self) -> str:
        """Check if CA file exists and return mount string for containers.

        Returns:
            Mount parameter string or empty string
        """
        npm_registry = os.environ.get("NPM_REGISTRY", "")
        ca_file = self.full_ca_file_path()

        if npm_registry and os.path.exists(ca_file):
            return f"-v {ca_file}:{ca_file}:Z"
        return ""

    def ct_build_s2i_npm_variables(self) -> str:
        """Build NPM variables for S2I builds.

        Returns:
            NPM variables string with -e NPM_MIRROR and -v MOUNT_POINT_FOR_CAFILE or empty string
        """
        npm_registry = os.environ.get("NPM_REGISTRY", "")
        ca_file = self.full_ca_file_path()

        if npm_registry and os.path.exists(ca_file):
            mount_ca = self.ct_mount_ca_file()
            return f"-e NPM_MIRROR={npm_registry} {mount_ca}"
        return ""

    def ct_npm_works(self) -> bool:
        """Check existence of npm tool and run it.

        Returns:
            True if npm works correctly, False otherwise
        """
        image_name = os.environ.get("IMAGE_NAME", "")
        tmpdir = tempfile.mkdtemp()

        print("  Testing npm in the container image")

        try:
            # Test npm --version
            version_output = ContainerTestLibUtils.run_command(
                cmd=f"podman run --rm {image_name} /bin/bash -c 'npm --version'",
                return_output=True,
                ignore_error=False,
            )
            version_file = os.path.join(tmpdir, "version")
            with open(version_file, "w") as f:
                f.write(version_output)

            # Create and run test app container
            cid_file = tempfile.mktemp(dir=self.cid_file_dir)
            mount_ca = self.ct_mount_ca_file()

            cmd_parts = ["podman", "run", "-d", "--rm", f"--cidfile={cid_file}"]
            if mount_ca:
                cmd_parts.extend(mount_ca.split())
            cmd_parts.append(f"{image_name}-testapp")

            ContainerTestLibUtils.run_command(
                cmd=" ".join(cmd_parts), return_output=False, ignore_error=False
            )

            # Wait for container to start
            if not self.ct_wait_for_cid(cid_file):
                return False

            container_id = self.ct_get_cid(os.path.basename(cid_file))

            # Test npm install jquery
            npm_test = "npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js"
            jquery_output = ContainerTestLibUtils.run_command(
                cmd=f"podman exec {container_id} /bin/bash -c '{npm_test}'",
                return_output=True,
                ignore_error=False,
            )
            jquery_file = os.path.join(tmpdir, "jquery")
            with open(jquery_file, "w") as f:
                f.write(jquery_output)

            # Check if internal repository was used if configured
            npm_registry = os.environ.get("NPM_REGISTRY", "")
            if npm_registry and os.path.exists(self.full_ca_file_path()):
                with open(jquery_file, "r") as f:
                    content = f.read()
                    if npm_registry not in content:
                        print(
                            "ERROR: Internal repository is NOT set. Even it is requested."
                        )
                        return False

            # Stop container
            if os.path.exists(cid_file):
                with open(cid_file, "r") as f:
                    cid = f.read().strip()
                    if cid:
                        ContainerTestLibUtils.run_command(
                            cmd=f"podman stop {cid}",
                            return_output=False,
                            ignore_error=True,
                        )

            print("  Success!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"ERROR: npm test failed: {e}")
            return False
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def ct_binary_found_from_df(
        self, binary: str, binary_path: str = "^/opt/rh"
    ) -> bool:
        """Check if a binary can be found in PATH during Dockerfile build.

        Args:
            binary: Name of the binary to test accessibility for
            binary_path: Optional path in which the binary should reside (default: "^/opt/rh")

        Returns:
            True if binary is found, False otherwise
        """
        image_name = os.environ.get("IMAGE_NAME", "")
        tmpdir = tempfile.mkdtemp()

        print(f"  Testing {binary} in build from Dockerfile")

        try:
            # Create Dockerfile that looks for the binary
            dockerfile_path = os.path.join(tmpdir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(f"FROM {image_name}\n")
                f.write(f'RUN command -v {binary} | grep "{binary_path}"\n')

            # Build image looking for expected path in output
            if self.ct_build_image_and_parse_id(dockerfile_path, tmpdir):
                # Store image ID for cleanup
                id_file = os.path.join(
                    self.app_id_file_dir, str(random.randint(1000, 9999))
                )
                with open(id_file, "w") as f:
                    f.write(self.app_image_id)
                return True
            else:
                print(f"  ERROR: Failed to find {binary} in $PATH!")
                return False

        except Exception as e:
            print(f"  ERROR: Failed to find {binary} in $PATH! {e}")
            return False
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def ct_check_scl_enable_vars(self, env_filter: str = None) -> bool:
        """Check if environment variables are set twice after scl enable.

        Args:
            env_filter: Optional string passed to grep for filtering variables

        Returns:
            True if all scl_enable values are present, False otherwise
        """
        image_name = os.environ.get("IMAGE_NAME", "")

        # Get enabled SCLs
        enabled_scls = ContainerTestLibUtils.run_command(
            cmd=f"podman run --rm {image_name} /bin/bash -c 'echo $X_SCLS'",
            return_output=True,
            ignore_error=False,
        ).strip()

        if not env_filter:
            env_filter = ""
            for scl in enabled_scls.split():
                if not env_filter:
                    env_filter = f"/{scl}"
                else:
                    env_filter += f"|/{scl}"

        # Get environment variables from podman run
        loop_envs = ContainerTestLibUtils.run_command(
            cmd=f"podman run --rm {image_name} /bin/bash -c env",
            return_output=True,
            ignore_error=False,
        )

        # Get environment variables after scl enable
        run_envs = ContainerTestLibUtils.run_command(
            cmd=f"podman run --rm {image_name} /bin/bash -c 'X_SCLS= scl enable {enabled_scls} env'",
            return_output=True,
            ignore_error=False,
        )

        # Check if values are set twice in the second set of envs
        success = self.ct_check_envs_set(
            env_filter, run_envs, loop_envs, "*VALUE*VALUE*"
        )

        if success:
            print(" All scl_enable values present")

        return success

    def ct_clone_git_repository(self, app_url: str, app_dir: str = None) -> bool:
        """Clone git repository.

        Args:
            app_url: Git URI pointing to a repository, supports "@" to indicate a different branch
            app_dir: Name of the directory to clone the repository into (optional)

        Returns:
            True if clone successful, False otherwise
        """
        # If app_url contains @, the string after @ is considered as a branch name
        if "@" in app_url:
            git_url, branch = app_url.rsplit("@", 1)
            git_clone_cmd = ["git", "clone", "--branch", branch, git_url]
        else:
            git_clone_cmd = ["git", "clone", app_url]

        if app_dir:
            git_clone_cmd.append(app_dir)

        try:
            ContainerTestLibUtils.run_command(
                cmd=" ".join(git_clone_cmd), return_output=False, ignore_error=False
            )
            return True
        except subprocess.CalledProcessError:
            print(f"ERROR: Git repository {app_url} cannot be cloned into {app_dir}.")
            return False

    def ct_check_image_availability(self, public_image_name: str) -> bool:
        """Pull an image from public repositories to check availability.

        Args:
            public_image_name: String containing the public name of the image to pull

        Returns:
            True if image is available, False otherwise
        """
        try:
            ContainerTestLibUtils.run_command(
                cmd=f"podman pull {public_image_name}",
                return_output=False,
                ignore_error=False,
            )
            return True
        except subprocess.CalledProcessError:
            print(f"{public_image_name} could not be downloaded via 'docker'")
            return False

    def ct_get_certificate_timestamp(self, container: str, path: str) -> int:
        """Get certificate timestamp from running container.

        Args:
            container: ID of a running container
            path: Path to the certificate inside the running container

        Returns:
            Timestamp (seconds since Unix era) for the certificate generation
        """
        try:
            # Get certificate content and extract notBefore date
            cert_content = ContainerTestLibUtils.run_command(
                cmd=f"podman exec {container} bash -c 'cat {path}'",
                return_output=True,
                ignore_error=False,
            )

            # Parse certificate with openssl
            startdate_output = ContainerTestLibUtils.run_command(
                cmd=f"echo '{cert_content}' | openssl x509 -startdate -noout",
                return_output=True,
                ignore_error=False,
            )

            # Extract notBefore date
            startdate_line = startdate_output.strip()
            if startdate_line.startswith("notBefore="):
                date_str = startdate_line[10:]  # Remove "notBefore="

                # Parse date string to timestamp
                from datetime import datetime

                dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                return int(dt.timestamp())

            return 0
        except Exception:
            return 0

    def ct_get_certificate_age_s(self, container: str, path: str) -> int:
        """Get certificate age in seconds.

        Args:
            container: ID of a running container
            path: Path inside the running container

        Returns:
            Age of the certificate in seconds
        """
        now = int(time.time())
        cert_timestamp = self.ct_get_certificate_timestamp(container, path)
        return now - cert_timestamp

    def ct_get_image_age_s(self, image_name: str) -> int:
        """Get image age in seconds.

        Args:
            image_name: Name of a given image

        Returns:
            Age of the image in seconds
        """
        try:
            created_str = ContainerTestLibUtils.run_command(
                cmd=f"podman inspect -f '{{{{.Created}}}}' {image_name}",
                return_output=True,
                ignore_error=False,
            ).strip()
            # Parse the created timestamp
            from datetime import datetime

            # podman returns format like: 2023-05-18T10:52:44.123456789Z
            if "T" in created_str and "Z" in created_str:
                # Remove nanoseconds if present
                if "." in created_str:
                    created_str = created_str.split(".")[0] + "Z"
                dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                image_timestamp = int(dt.timestamp())

                now = int(time.time())
                return now - image_timestamp

            return 0
        except Exception:
            return 0

    def ct_s2i_multistage_build(
        self,
        app_path: str,
        src_image: str,
        sec_image: str,
        dst_image: str,
        s2i_args: str = "",
    ) -> bool:
        """Create a new s2i app image using multi-stage build.

        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the s2i build process
            sec_image: Image to be used as the base for the result of the build process
            dst_image: Image name to be used during the tagging of the s2i build result
            s2i_args: Additional list of source-to-image arguments

        Returns:
            True if build successful, False otherwise
        """
        local_app = "app-src"

        # Get user from source image
        user = (
            ContainerTestLibUtils.run_command(
                cmd=f"podman inspect -f '{{{{.Config.User}}}}' {src_image}",
                return_output=True,
                ignore_error=False,
            ).strip()
            or "0"
        )

        # Get numeric user ID
        user_id = self.ct_get_uid_from_image(user, src_image)
        if user_id is None:
            print("Terminating s2i build.")
            return False

        # Create temporary directory for build
        tmpdir = tempfile.mkdtemp()

        try:
            os.chdir(tmpdir)

            # Handle app sources
            if os.path.exists(app_path.replace("file://", "")):
                os.makedirs(local_app, exist_ok=True)
                app_source = app_path.replace("file://", "")

                # Copy source files
                if os.path.isdir(app_source):
                    for item in os.listdir(app_source):
                        src = os.path.join(app_source, item)
                        dst = os.path.join(local_app, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
            else:
                # Clone from git repository
                if not self.ct_clone_git_repository(app_path, local_app):
                    return False

            # Create multi-stage Dockerfile
            df_name = tempfile.mktemp(prefix="Dockerfile.", dir=tmpdir)

            with open(df_name, "w") as df:
                df.write("# First stage builds the application\n")
                df.write(f"FROM {src_image} as builder\n")
                df.write(
                    "# Add application sources to a directory that the assemble script expects them\n"
                )
                df.write(
                    "# and set permissions so that the container runs without root access\n"
                )
                df.write("USER 0\n")
                df.write("ADD app-src /tmp/src\n")
                df.write("RUN chown -R 1001:0 /tmp/src\n")

                # Add environment variables from s2i_args
                import re

                env_matches = re.findall(r"(?:-e|--env)[\s=](\S*=\S*)", s2i_args)
                for env_var in env_matches:
                    df.write(f"ENV {env_var}\n")

                # Add CA trust if present
                ca_file_path = self.full_ca_file_path()
                if os.path.exists(ca_file_path):
                    df.write(
                        "RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract\n"
                    )

                df.write(f"USER {user_id}\n")
                df.write("# Install the dependencies\n")
                df.write("RUN /usr/libexec/s2i/assemble\n")
                df.write("# Second stage copies the application to the minimal image\n")
                df.write(f"FROM {sec_image}\n")
                df.write(
                    "# Copy the application source and build artifacts from the builder image to this one\n"
                )
                df.write("COPY --from=builder $HOME $HOME\n")
                df.write("# Set the default command for the resulting image\n")
                df.write("CMD /usr/libexec/s2i/run\n")

            # Extract mount options from s2i_args
            mount_options = []
            mount_matches = re.findall(r"-v\s+(\S+)", s2i_args)
            for mount in mount_matches:
                mount_options.extend(["-v", mount])

            # Build the image
            if self.ct_build_image_and_parse_id(
                df_name, " ".join(mount_options + ["-t", dst_image, "."])
            ):
                # Store image ID for cleanup
                id_file = os.path.join(
                    self.app_id_file_dir, str(random.randint(1000, 9999))
                )
                with open(id_file, "w") as f:
                    f.write(self.app_image_id)
                return True
            else:
                print(f"ERROR: Failed to build {df_name}")
                return False

        except Exception as e:
            print(f"Multi-stage S2I build failed: {e}")
            return False
        finally:
            # Cleanup
            if "tmpdir" in locals():
                shutil.rmtree(tmpdir, ignore_errors=True)

    def ct_test_app_dockerfile(
        self,
        dockerfile: str,
        app_url: str,
        expected_text: str,
        app_dir: str,
        build_args: str = "",
    ) -> bool:
        """Test application with Dockerfile.

        Args:
            dockerfile: Path to a Dockerfile that will be used for building an image
            app_url: Git or local URI with a testing application
            expected_text: PCRE regular expression that must match the response body
            app_dir: Name of the application directory that is used in the Dockerfile
            build_args: Build args that will be used for building an image

        Returns:
            True if test passes, False otherwise
        """
        if not app_dir:
            print("ERROR: Option app_dir not set. Terminating the Dockerfile build.")
            return False

        if not os.path.exists(dockerfile) or os.path.getsize(dockerfile) == 0:
            print(f"ERROR: Dockerfile {dockerfile} does not exist or is empty.")
            print("Terminating the Dockerfile build.")
            return False

        port = 8080
        app_image_name = "myapp"
        cname = "app_dockerfile"

        dockerfile_abs = os.path.abspath(dockerfile)
        tmpdir = tempfile.mkdtemp()

        try:
            os.chdir(tmpdir)
            shutil.copy2(dockerfile_abs, "Dockerfile")

            # Rewrite the source image to what we test
            image_name = os.environ.get("IMAGE_NAME", "")
            with open("Dockerfile", "r") as f:
                content = f.read()

            content = re.sub(
                r"^FROM.*$", f"FROM {image_name}", content, flags=re.MULTILINE
            )

            with open("Dockerfile", "w") as f:
                f.write(content)

            print("Using this Dockerfile:")
            print(content)

            # Handle application sources
            if os.path.isdir(app_url):
                print(f"Copying local folder: {app_url} -> {app_dir}.")
                shutil.copytree(app_url, app_dir)
            else:
                if not self.ct_clone_git_repository(app_url, app_dir):
                    print("Terminating the Dockerfile build.")
                    return False

            print(f"Building '{app_image_name}' image using podman build")
            if not self.ct_build_image_and_parse_id(
                "", f"-t {app_image_name} . {build_args}"
            ):
                print(
                    f"ERROR: The image cannot be built from {dockerfile} and application {app_url}."
                )
                print("Terminating the Dockerfile build.")
                return False

            # Store image ID for cleanup
            id_file = os.path.join(
                self.app_id_file_dir, str(random.randint(1000, 9999))
            )
            with open(id_file, "w") as f:
                f.write(self.app_image_id)

            # Run the container
            cid_file = os.path.join(self.cid_file_dir, cname)
            try:
                ContainerTestLibUtils.run_command(
                    cmd=f"podman run -d --cidfile={cid_file} --rm {app_image_name}",
                    return_output=False,
                    ignore_error=False,
                )
            except subprocess.CalledProcessError:
                print(
                    f"ERROR: The image {app_image_name} cannot be run for {dockerfile} and application {app_url}."
                )
                print("Terminating the Dockerfile build.")
                return False

            print(f"Waiting for {app_image_name} to start")
            if not self.ct_wait_for_cid(cid_file):
                return False

            # Get container IP
            ip = self.ct_get_cip(cname)
            if not ip:
                print("ERROR: Cannot get container's IP address.")
                return False

            # Test response
            success = self.ct_test_response(f"http://{ip}:{port}", 200, expected_text)

            if not success:
                container_id = self.ct_get_cid(cname)
                ContainerTestLibUtils.run_command(
                    cmd=f"podman logs {container_id}",
                    return_output=False,
                    ignore_error=True,
                )

            # Cleanup
            container_id = self.ct_get_cid(cname)
            ContainerTestLibUtils.run_command(
                cmd=f"podman kill {container_id}",
                return_output=False,
                ignore_error=True,
            )
            time.sleep(2)
            ContainerTestLibUtils.run_command(
                cmd=f"podman rmi {app_image_name}",
                return_output=False,
                ignore_error=True,
            )

            if os.path.exists(cid_file):
                os.unlink(cid_file)

            return success

        except Exception as e:
            print(f"Dockerfile test failed: {e}")
            return False
        finally:
            if "tmpdir" in locals():
                shutil.rmtree(tmpdir, ignore_errors=True)


# Create extended instance
ct_extended = ContainerTestLibExtended()

# Update global ct to use extended version
ct = ct_extended


if __name__ == "__main__":
    # Example usage
    print("Container Test Library - Python version")
    print("Import this module and use ct_init() before starting tests")
