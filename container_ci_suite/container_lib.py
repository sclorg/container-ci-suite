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
import time
import shutil
import tempfile
import subprocess
import logging
import urllib.request
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper
from container_ci_suite import utils
from container_ci_suite.engines.container import ContainerImage
from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite.utils import (
    get_full_ca_file_path,
    get_os_environment,
    get_mount_ca_file,
    get_env_commands_from_s2i_args,
    get_mount_options_from_s2i_args,
)

logger = logging.getLogger(__name__)

# Global constants
LINE = "=============================================="


class ContainerTestLib:
    """
    Container Test Library - Main class providing container testing functionality.
    This is a Python replacement for the container-test-lib.sh shell script.
    """

    def __init__(self, image_name: str = os.getenv("IMAGE_NAME"), s2i_image: bool = False, app_name: str = ""):
        """Initialize the container test library."""
        self.app_id_file_dir = Path(tempfile.mkdtemp(prefix="app_ids_"))
        self.cid_file_dir = Path(tempfile.mkdtemp(prefix="cid_files_"))
        self.image_name = image_name
        self.s2i_image: bool = s2i_image
        self._lib = None
        self.app_name = app_name

    @property
    def lib(self):
        if not self._lib:
            self._lib = ContainerImage(
                image_name=self.image_name,
                cid_file_dir=self.cid_file_dir,
                cid_file=self.app_id_file_dir
            )
        return self._lib

    def set_new_image(self, image_name):
        self.image_name = image_name

    def cleanup(self) -> None:
        """
        Clean up containers and images used during tests.
        Stops and removes all containers and cleans up temporary directories.
        """
        logging.info(LINE)
        logging.info("Cleaning of testing containers and images started.")
        logging.info("It may take a few seconds.")
        logging.info(LINE)

        self.clean_app_images()
        self.clean_containers()

    def build_image_and_parse_id(self, dockerfile: str = "", build_params: str = "") -> bool:
        """
        Build container image and parse the image ID.

        Args:
            dockerfile: Path to Dockerfile (optional)
            build_params: Additional build parameters

        Returns:
            True if build successful, False otherwise
        """
        try:
            log_file = Path(tempfile.mktemp(prefix="build_log_"))
            sleep_time = "10m"

            dockerfile_arg = f"-f {dockerfile}" if dockerfile else ""
            command = f"docker build --no-cache {dockerfile_arg} {build_params}".replace("'", "")

            # Run build command with timeout
            timeout_cmd = f"timeout {sleep_time} {command}"

            try:
                log_content = ContainerTestLibUtils.run_command(timeout_cmd, return_output=True)
                logging.info(log_content)
                with open(log_file, 'w') as f:
                    f.write(log_content)
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

    def clean_app_images(self) -> None:
        """Clean up application images referenced by APP_ID_FILE_DIR."""
        if not self.app_id_file_dir or not self.app_id_file_dir.exists():
            print(f"The APP_ID_FILE_DIR={self.app_id_file_dir} is not created. App cleaning is to be skipped.")
            return
        logging.info(f"Examining image ID files in APP_ID_FILE_DIR={self.app_id_file_dir}")
        for file_path in self.app_id_file_dir.glob("*"):
            if not file_path.is_file():
                continue
            try:
                image_id = utils.get_file_content(file_path).strip()
                # Check if image exists
                try:
                    PodmanCLIWrapper.call_podman_command(cmd=f"inspect {image_id}", return_output=False)
                except subprocess.CalledProcessError:
                    continue
                # Remove containers using this image
                try:
                    containers = PodmanCLIWrapper.call_podman_command(
                        cmd=f"ps -q -a -f ancestor={image_id}",
                        return_output=True
                    ).strip()
                    if containers:
                        PodmanCLIWrapper.call_podman_command(cmd=" rm -f {containers}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass
                # Remove the image
                try:
                    PodmanCLIWrapper.call_podman_command(f"rmi -f {image_id}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass
            except Exception as e:
                logger.warning(f"Error cleaning image from {file_path}: {e}")

        # Remove the directory
        shutil.rmtree(self.app_id_file_dir)

    def clean_containers(self) -> None:
        """Clean up containers referenced by CID_FILE_DIR."""
        if not self.cid_file_dir:
            logging.info("The CID_FILE_DIR is not set. Container cleaning is to be skipped.")
            return

        logging.info(f"Examining CID files in CID_FILE_DIR={self.cid_file_dir}")

        for cid_file in self.cid_file_dir.glob("*"):
            if not cid_file.is_file():
                continue
            logging.info(f"Let's clean file {cid_file}")

            try:
                container_id = utils.get_file_content(cid_file).strip()
                if not ContainerImage.is_container_exists(container_id):
                    continue
                logging.info(f"Stopping and removing container {container_id}...")
                # Stop container if running
                if ContainerImage.is_container_running(container_id):
                    PodmanCLIWrapper.call_podman_command(cmd=f"stop {container_id}", ignore_error=True)
                    logging.info(f"Container {container_id} stopped")
                # Check exit status and dump logs if needed
                try:
                    exit_status = PodmanCLIWrapper.call_podman_command(
                        cmd=f"inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        return_output=True
                    ).strip()
                    if int(exit_status) != 0:
                        logging.info(f"Dumping logs for {container_id}")
                        try:
                            logs = PodmanCLIWrapper.call_podman_command(cmd=f"logs {container_id}", return_output=True)
                            logging.debug(logs)
                        except subprocess.CalledProcessError:
                            pass
                except subprocess.CalledProcessError:
                    pass
                # Remove container
                PodmanCLIWrapper.call_podman_command(cmd=f"rm -v {container_id}", ignore_error=True)
                if cid_file.exists():
                    cid_file.unlink()
            except Exception as e:
                logger.warning(f"Error cleaning container from {cid_file}: {e}")
        # Remove the directory
        if self.cid_file_dir.exists():
            shutil.rmtree(self.cid_file_dir)

    def pull_image(self, image_name: str, exit_on_fail: bool = False, loops: int = 10) -> bool:
        return self.lib.pull_image(
            image_name=image_name,
            exit_on_fail=exit_on_fail,
            loops=loops
        )

    @staticmethod
    def check_envs_set(
        env_filter: str,
        check_envs: str,
        loop_envs: str,
        env_format: str = "*VALUE*"
    ) -> bool:
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
            filtered_envs = [env for env in check_envs.split('\n') if env.startswith(f"{var_name}=")]
            if not filtered_envs:
                logging.info(f"{var_name} not found during 'docker exec'")
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
                    logging.info(f"Value {value} is missing from variable {var_name}")
                    logging.info(filtered_env)
                    return False

        return True

    def get_cid(self, cid_file_name: str) -> str:
        logging.debug(f"Get content of CID_NAME: {cid_file_name}")
        return self.lib.get_cid(cid_file_name=cid_file_name)

    def get_cip(self, cid_file_name: str = "app_dockerfile") -> str:
        return self.lib.get_cip(cid_file_name=cid_file_name)

    def assert_container_creation_fails(self, container_args: str) -> bool:
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
            if self.create_container(cid_file):
                container_id = self.get_cid(cid_file)

                attempt = 1
                while attempt <= max_attempts:
                    if not ContainerImage.is_container_running(container_id):
                        break
                    time.sleep(2)
                    attempt += 1
                    if attempt > max_attempts:
                        PodmanCLIWrapper.call_podman_command(cmd=f"stop {container_id}", ignore_error=True)
                        return False

                # Check exit status
                try:
                    exit_status = PodmanCLIWrapper.call_podman_command(
                        cmd=f"inspect -f '{{{{.State.ExitCode}}}}' {container_id}",
                        return_output=True
                    ).strip()
                    if exit_status == "0":
                        return False
                except subprocess.CalledProcessError:
                    pass

                # Clean up
                PodmanCLIWrapper.call_podman_command(cmd=f"rm -v {container_id}", ignore_error=True)
                cid_path = self.cid_file_dir / cid_file
                if cid_path.exists():
                    cid_path.unlink()
        finally:
            if old_container_args:
                self.container_args = old_container_args
        return True

    def run_command(self, cmd: str, return_output: bool = True, ignore_errors: bool = False):
        return ContainerTestLibUtils.run_command(cmd=cmd, return_output=return_output, ignore_error=ignore_errors)

    def build_test_container(self, dockerfile: str, app_url: str, app_dir: str, build_args: str = ""):
        return self.lib.build_test_container(
            dockerfile=dockerfile, app_url=app_url, app_dir=app_dir, build_args=build_args
        )

    def test_app_dockerfile(self):
        return self.lib.test_app_dockerfile()

    def create_container(
        self,
        cid_file_name: str = "",
        container_args: str = "",
        command: str = ""
    ) -> bool:
        """
        Create a container.
        Args:
            cid_file_name: Name for the cid_file_name
            command: Command to run in container
            container_args: Additional container arguments
        Returns:
            True if container created successfully, False otherwise
        """
        if not container_args:
            container_args = getattr(self, 'container_args', '')
        if not self.cid_file_dir.exists():
            self.cid_file_dir = Path(tempfile.mkdtemp(prefix="cid_files_"))
        full_cid_file_name: Path = self.cid_file_dir / cid_file_name
        try:
            cmd = f"run --cidfile={full_cid_file_name} -d {container_args} {self.image_name} {command}"
            logging.info(f"Command to create container is '{cmd}'.")
            PodmanCLIWrapper.call_podman_command(cmd=cmd, return_output=True)
            if not ContainerImage.wait_for_cid(cid_file_name=full_cid_file_name):
                return False
            container_id = utils.get_file_content(full_cid_file_name).strip()
            logging.info(f"Created container {container_id}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create container: {e}")
            return False

    def scl_usage_old(
            self,
            cid_file_name: str,
            command: str,
            expected: str,
            image_name: str = ""
    ) -> bool:
        """
        Test SCL usage in three different ways.
        Args:
            cid_file_name: Name for cid_file_name
            command: Command to execute
            expected: Expected string in output
            image_name: Image name to test

        Returns:
            True if all tests pass, False otherwise
        """
        logging.debug("Testing the image SCL enable")

        # Test 1: docker run
        try:
            output = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {image_name} /bin/bash -c '{command}'",
                return_output=True
            )
            if expected not in output:
                logging.error(f"ERROR[/bin/bash -c '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        # Test 2: docker exec with bash
        try:
            container_id = self.get_cid(cid_file_name=cid_file_name)
            output = PodmanCLIWrapper.call_podman_command(
                cmd=f"exec {container_id} /bin/bash -c '{command}'",
                return_output=True
            )
            if expected not in output:
                logging.error(f"ERROR[exec /bin/bash -c '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        # Test 3: docker exec with sh
        try:
            container_id = self.get_cid(cid_file_name=cid_file_name)
            output = PodmanCLIWrapper.call_podman_command(
                cmd=f"exec {container_id} /bin/sh -ic '{command}'",
                return_output=True
            )
            if expected not in output:
                logging.error(f"ERROR[exec /bin/sh -ic '{command}'] Expected '{expected}', got '{output}'")
                return False
        except subprocess.CalledProcessError:
            return False

        return True

    def doc_content_old(
            self,
            strings: List[str],
            image_name: str = ""
    ) -> bool:
        """
        Check documentation content in container.
        Args:
            strings: List of strings to check for
            image_name: Image name to test
        Returns:
            True if all strings found and format is correct, False otherwise
        """
        logging.info("Testing documentation in the container image")
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Extract help files from container
            for filename in ["help.1"]:
                try:
                    content = PodmanCLIWrapper.call_podman_command(
                        cmd=f"run --rm {image_name} /bin/bash -c 'cat /{filename}'",
                        return_output=True
                    )

                    help_file = tmpdir / filename
                    with open(help_file, 'w') as f:
                        f.write(content)

                    # Check for required strings
                    for term in strings:
                        if term not in content:
                            logging.error(f"ERROR: File /{filename} does not include '{term}'.")
                            return False

                    # Check format
                    for term in ["TH", "PP", "SH"]:
                        if not re.search(f"^\\.{term}", content, re.MULTILINE):
                            logging.error(
                                f"ERROR: /{filename} is probably not in troff or groff format,"
                                f"since '{term}' is missing."
                            )
                            return False

                except subprocess.CalledProcessError:
                    logging.error(f"ERROR: Could not extract {filename} from container")
                    return False

            logging.info("Success!")
            return True

        finally:
            shutil.rmtree(tmpdir)

    def mount_ca_file(self) -> str:
        """
        Get mount parameter for CA file.
        Returns:
            Mount parameter string or empty string
        """
        return get_mount_ca_file()

    def build_s2i_npm_variables(self) -> str:
        """
        Build S2I npm variables.
        Returns:
            NPM variables string
        """
        npm_registry = get_os_environment("NPM_REGISTRY")
        if npm_registry and get_full_ca_file_path().exists():
            return f"-e NPM_MIRROR={npm_registry} {self.mount_ca_file()}"
        return ""

    # TODO
    # Moved to engines/container.py
    def npm_works(self, image_name: str = "") -> bool:
        """
        Test if npm works in the container.
        Args:
            image_name: Image name to test
        Returns:
            True if npm works, False otherwise
        """
        tmpdir = Path(tempfile.mkdtemp())
        cid_file_name = tmpdir / "npm_test_cid"

        try:
            logging.info("Testing npm in the container image")
            npm_registry = get_os_environment("NPM_REGISTRY")

            # Test npm version
            try:
                cmd = f"run --rm {image_name} /bin/bash -c 'npm --version'"
                logging.debug(f"Podman command for getting npm version is: '{cmd}'")
                version_output = PodmanCLIWrapper.call_podman_command(
                    cmd=cmd,
                    return_output=True
                )
                version_file = tmpdir / "version"
                with open(version_file, 'w') as f:
                    f.write(version_output)
            except subprocess.CalledProcessError:
                logging.error(f"ERROR: 'npm --version' does not work inside the image {image_name}.")
                return False

            # Start test container
            test_app_image = f"{image_name}-testapp"

            try:
                cmd = f"run -d {get_mount_ca_file()} --rm --cidfile={cid_file_name} {test_app_image}"
                logging.info(f"Podman command for running in daemon is: '{cmd}'")
                PodmanCLIWrapper.call_podman_command(
                    cmd=cmd,
                    return_output=False
                )
            except subprocess.CalledProcessError:
                logging.error(f"ERROR: Could not start {test_app_image}")
                return False

            # Wait for container
            if not ContainerImage.wait_for_cid(cid_file_name=cid_file_name):
                return False

            container_id = utils.get_file_content(filename=cid_file_name).strip()

            # Test npm install
            try:
                cmd = (f"exec {container_id} /bin/bash -c "
                       f"'npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js'")
                logging.info(f"Podman command for testing npm is: '{cmd}'")
                jquery_output = PodmanCLIWrapper.call_podman_command(
                    cmd=cmd,
                    return_output=True
                )

                jquery_file = tmpdir / "jquery"
                with open(jquery_file, 'w') as f:
                    f.write(jquery_output)

            except subprocess.CalledProcessError:
                logging.error(f"ERROR: npm could not install jquery inside the image {image_name}.")
                return False

            # Check NPM registry if configured
            if npm_registry and get_full_ca_file_path().exists():
                if npm_registry not in jquery_output:
                    logging.debug("ERROR: Internal repository is NOT set. Even it is requested.")
                    return False

            # Stop container
            if cid_file_name.exists():
                try:
                    PodmanCLIWrapper.call_podman_command(cmd=f"stop {container_id}", ignore_error=True)
                except subprocess.CalledProcessError:
                    pass

            logging.info("Success!")
            return True

        finally:
            shutil.rmtree(tmpdir)

    def binary_found_from_df(
        self,
        binary: str,
        binary_path: str = "^/opt/rh",
        image_name: str = ""
    ) -> bool:
        """
        Check if binary can be found during Dockerfile build.
        Args:
            binary: Binary name to check
            binary_path: Expected path pattern
            image_name: Image name to test
        Returns:
            True if binary found, False otherwise
        """
        tmpdir = Path(tempfile.mkdtemp())

        try:
            print(f"Testing {binary} in build from Dockerfile")

            # Create Dockerfile
            dockerfile = tmpdir / "Dockerfile"
            with open(dockerfile, 'w') as f:
                f.write(f"FROM {image_name}\n")
                f.write(f"RUN command -v {binary} | grep '{binary_path}'\n")

            # Build image
            if self.build_image_and_parse_id(str(dockerfile), str(tmpdir)):
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

    def check_exec_env_vars(
            self,
            env_filter: str = "^X_SCLS=|/opt/rh|/opt/app-root",
            image_name: str = ""
    ) -> bool:
        """
        Check if environment variables from 'docker run' are available in 'docker exec'.
        Args:
            env_filter: Filter for environment variables
            image_name: Image name to test
        Returns:
            True if all variables present, False otherwise
        """
        tmpdir = Path(tempfile.mkdtemp())
        try:
            # Get environment variables from docker run
            run_envs = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {image_name} /bin/bash -c env",
                return_output=True
            )
            # Create container for exec test
            if not self.create_container("test_exec_envs", "bash -c 'sleep 1000'", image_name):
                return False

            container_id = self.get_cid("test_exec_envs")
            # Get environment variables from docker exec
            exec_envs = PodmanCLIWrapper.call_podman_command(cmd=f"exec {container_id} env", return_output=True)
            # Check environment variables
            result = self.check_envs_set(env_filter, exec_envs, run_envs)
            if result:
                print("All values present in 'docker exec'")

            return result

        finally:
            shutil.rmtree(tmpdir)

    def check_scl_enable_vars(self, env_filter: str = "", image_name: str = "") -> bool:
        """
        Check if environment variables are set twice after SCL enable.
        Args:
            env_filter: Filter for environment variables
            image_name: Image name to test
        Returns:
            True if all variables set correctly, False otherwise
        """
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Get enabled SCLs
            enabled_scls = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {image_name} /bin/bash -c 'echo $X_SCLS'",
                return_output=True
            ).strip()
            if not env_filter:
                # Build filter from enabled SCLs
                scl_list = enabled_scls.split()
                if scl_list:
                    env_filter = "|".join([f"/{scl}" for scl in scl_list])

            # Get environment variables
            loop_envs = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {image_name} /bin/bash -c env",
                return_output=True
            )
            run_envs = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {image_name} /bin/bash -c 'X_SCLS= scl enable {enabled_scls} env'",
                return_output=True
            )
            # Check if values are set twice
            result = self.check_envs_set(env_filter, run_envs, loop_envs, "*VALUE*VALUE*")
            if result:
                print("All scl_enable values present")
            return result

        finally:
            shutil.rmtree(tmpdir)

    def path_append(self, path_var: str, directory: str) -> None:
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

    def gen_self_signed_cert_pem(self, output_dir: str, base_name: str) -> bool:
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
            ContainerTestLibUtils.run_command(
                f"openssl req -newkey rsa:2048 -nodes -keyout {key_file} "
                f"-subj '/C=GB/ST=Berkshire/L=Newbury/O=My Server Company' > {req_file}",
                return_output=False
            )

            # Generate self-signed certificate
            ContainerTestLibUtils.run_command(
                f"openssl req -new -x509 -nodes -key {key_file} -batch > {cert_file}",
                return_output=False
            )

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Certificate generation failed: {e}")
            return False

    def obtain_input(self, input_path: str) -> Optional[str]:
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
            temp_file = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-file")
            shutil.copy2(input_path, temp_file)
            return temp_file

        elif Path(input_path).is_dir():
            # Local directory
            temp_dir = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-dir")
            shutil.copytree(input_path, temp_dir, symlinks=True)
            return temp_dir

        elif input_path.startswith(('http://', 'https://')):
            # URL
            temp_file = tempfile.mktemp(suffix=extension, dir="/var/tmp", prefix="test-input-url")
            try:
                urllib.request.urlretrieve(input_path, temp_file)
                return temp_file
            except Exception as e:
                logger.error(f"Failed to download {input_path}: {e}")
                return None
        else:
            logger.error(f"File type not known: {input_path}")
            return None

    def test_response(
        self, url: str,
        expected_code: int = 200,
        port: int = 8080,
        expected_output: str = "",
        max_attempts: int = 20, ignore_error_attempts: int = 10,
        page: str = "",
        host: str = "localhost",
        debug: bool = False,

    ) -> bool:
        """
        Test HTTP response from application container.

        Args:
            url: Request URL
            expected_code: Expected HTTP response code
            port: Port where curl will be used
            expected_output: Regular expression for response body
            max_attempts: Maximum number of attempts
            ignore_error_attempts: Number of attempts to ignore errors
            page: Page where curl will be used. Page hast to start with '/'
            host: host where curl will be used

        Returns:
            True if response matches expectations, False otherwise
        """
        print(f"Testing the HTTP(S) response for <{url}:{port}>")
        sleep_time = 3

        insecure = ""
        full_url = f"{url}:{port}"
        if page:
            full_url = f"{full_url}{page}"
        host_header = f'-H "Host: {host}"'
        if url.startswith("https://"):
            insecure = "--insecure"

        for attempt in range(1, max_attempts + 1):
            print(f"Trying to connect ... {attempt}")
            try:
                # Create temporary file for response
                response_file = tempfile.NamedTemporaryFile(mode='w+', prefix='test_response_')
                # Use curl to get response
                curl_cmd = f"curl {insecure} -is {host_header} --connect-timeout 10 -s -w '%{{http_code}}' '{full_url}'"
                result = ContainerTestLibUtils.run_command(
                    cmd=curl_cmd,
                    return_output=True
                )
                if debug:
                    print(result)
                response_file.write(result)
                if len(result) >= 3:
                    response_code = result[-3:]
                    response_body = result[:-3]

                    try:
                        code_int = int(response_code)
                        if code_int == expected_code:
                            if debug:
                                print("Expected code from curl PASSED.")
                                print(f"Let's check {expected_output} in response: '{response_body}'")
                            if not expected_output or re.search(expected_output, response_body):
                                print(f"Expected output '{expected_output}' found in response")
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

    @staticmethod
    def registry_from_os(os_name: str) -> str:
        """
        Transform OS string into registry URL.
        Args:
            os_name: Operating system string
        Returns:
            Registry URL
        """
        return "registry.redhat.io" if os_name.startswith("rhel") else "quay.io"

    def get_public_image_name(self, os_name: str, base_image_name: str, version: str) -> str:
        """
        Transform arguments into public image name.
        Args:
            os_name: Operating system string
            base_image_name: Base image name
            version: Version string
        Returns:
            Public image name
        """
        registry = ContainerTestLib.registry_from_os(os_name)
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

    @staticmethod
    def assert_cmd_success(*cmd) -> bool:
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
            ContainerTestLibUtils.run_command(cmd_str, return_output=False)
            print(" PASS")
            return True
        except subprocess.CalledProcessError:
            print(" FAIL")
            return False

    @staticmethod
    def assert_cmd_failure(*cmd) -> bool:
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
            ContainerTestLibUtils.run_command(cmd_str, return_output=False)
            print(" FAIL")
            return False
        except subprocess.CalledProcessError:
            print(" PASS")
            return True

    def random_string(self, length: int = 10) -> str:
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

    def s2i_usage(self) -> str:
        """
        Run S2I usage script inside container.
        Returns:
            Usage script output
        """
        usage_command = "/usr/libexec/s2i/usage"
        try:
            return PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {self.image_name} bash -c {usage_command}",
                return_output=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"S2I usage failed: {e}")
            return ""

    def show_resources(self) -> None:
        """Show system resources information."""
        print("Resources info:")
        print("Memory:")
        try:
            ContainerTestLibUtils.run_command("free -h", return_output=True)
        except subprocess.CalledProcessError:
            print("Memory info not available")
        print("Storage:")
        try:
            ContainerTestLibUtils.run_command("df -h", return_output=True)
        except subprocess.CalledProcessError:
            print("Storage info not available")
        print("CPU")
        try:
            ContainerTestLibUtils.run_command("lscpu", return_output=True)
        except subprocess.CalledProcessError:
            print("CPU info not available")

        print(LINE)
        print(f"Image {self.image_name} information:")
        print(LINE)
        print(f"Uncompressed size of the image: {self.get_image_size_uncompressed(self.image_name)}")
        print(f"Compressed size of the image: {self.get_image_size_compressed(self.image_name)}")

    def get_image_size_uncompressed(self, image_name: str) -> str:
        """
        Get uncompressed image size.
        Args:
            image_name: Image name
        Returns:
            Size string in MB
        """
        try:
            size_bytes = PodmanCLIWrapper.call_podman_command(
                cmd=f"inspect {image_name} -f '{{{{.Size}}}}'",
                return_output=True
            ).strip()
            size_mb = int(size_bytes) // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "Unknown"

    def get_image_size_compressed(self, image_name: str) -> str:
        """
        Get compressed image size.
        Args:
            image_name: Image name
        Returns:
            Size string in MB
        """
        try:
            # Save image and compress to get size
            result = PodmanCLIWrapper.call_podman_command(
                cmd=f"save {image_name} | gzip - | wc --bytes",
                return_output=True
            )
            size_bytes = int(result.strip())
            size_mb = size_bytes // (1024 * 1024)
            return f"{size_mb}MB"
        except (subprocess.CalledProcessError, ValueError):
            return "Unknown"

    def timestamp_s(self) -> int:
        """Get timestamp in seconds since Unix epoch."""
        return int(time.time())

    def timestamp_pretty(self) -> str:
        """Get human-readable timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")

    def timestamp_diff(self, start_date: int, final_date: int) -> str:
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

    def get_uid_from_image(self, user: str, src_image: str) -> Optional[str]:
        """
        Get user ID from image.
        This is the Python equivalent of ct_get_uid_from_image.
        Args:
            user: User to get UID for
            src_image: Image to check
        Returns:
            User ID string or None if not found
        """
        # Check if user is numeric
        try:
            int(user)
            return user
        except ValueError:
            pass
        # Get user ID from image
        try:
            user_id = PodmanCLIWrapper.call_podman_command(
                cmd=f"run --rm {src_image} bash -c 'id -u {user}' 2>/dev/null",
                return_output=True
            ).strip()
            return user_id
        except subprocess.CalledProcessError:
            print(f"ERROR: id of user {user} not found inside image {src_image}.")
            return None

    def build_as_df_build_args(
        self,
        app_path: Path,
        src_image: str,
        dst_image: str,
        build_args: str = "",
        s2i_args: str = ""
    ):
        """
        Create a new S2I app image from local sources using Dockerfile approach.
        This is the Python equivalent of ct_s2i_build_as_df_build_args.
        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the S2I build
            dst_image: Image name to be used during the tagging of the S2I build result
            build_args: Build arguments to be used in the S2I build
            s2i_args: Additional list of source-to-image arguments
        Returns:
            True if build successful, False otherwise
        """
        local_app = "upload/src/"
        local_scripts = "upload/scripts/"
        incremental = "--incremental" in s2i_args
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())
        original_cwd = os.getcwd()

        try:
            os.chdir(tmpdir)
            # Create Dockerfile name
            df_name = Path(tempfile.mktemp(dir=str(tmpdir), prefix="Dockerfile."))
            # Check if the image is available locally and try to pull it if it is not
            try:
                PodmanCLIWrapper.call_podman_command(cmd=f"images {src_image}", return_output=True)
            except subprocess.CalledProcessError:
                if "pull-policy=never" not in s2i_args:
                    try:
                        PodmanCLIWrapper.call_podman_command(cmd=f"pull {src_image}", return_output=False)
                    except subprocess.CalledProcessError:
                        print(f"Failed to pull source image {src_image}")
                        return False
            # Get user from source image
            try:
                user = PodmanCLIWrapper.call_podman_command(
                    cmd=f"inspect -f '{{{{.Config.User}}}}' {src_image}",
                    return_output=True
                ).strip()
                user = user or "0"  # Default to root if no user is set
            except subprocess.CalledProcessError:
                user = "0"
            # Get user ID from image
            user_id = self.get_uid_from_image(user, src_image)
            if not user_id:
                print("Terminating s2i build.")
                return False
            # Handle incremental build
            if incremental:
                inc_tmp = Path(tempfile.mkdtemp(prefix="incremental."))
                try:
                    # Set permissions for incremental directory
                    ContainerTestLibUtils.run_command(f"setfacl -m 'u:{user_id}:rwx' {inc_tmp}")
                    # Check if the destination image exists
                    try:
                        PodmanCLIWrapper.call_podman_command(cmd=f"images {dst_image}", return_output=True)
                    except subprocess.CalledProcessError:
                        print(f"Image {dst_image} not found.")
                        return False
                    # Run the original image with mounted volume to get artifacts
                    cmd = (
                        "if [ -s /usr/libexec/s2i/save-artifacts ]; then "
                        f"/usr/libexec/s2i/save-artifacts > '{inc_tmp}/artifacts.tar'; "
                        f"else touch '{inc_tmp}/artifacts.tar'; fi"
                    )
                    PodmanCLIWrapper.call_podman_command(
                        cmd=f"run --rm -v {inc_tmp}:{inc_tmp}:Z {dst_image} bash -c \"{cmd}\"",
                        return_output=True
                    )
                    # Move artifacts to build directory
                    shutil.move(str(inc_tmp / "artifacts.tar"), str(tmpdir / "artifacts.tar"))
                except subprocess.CalledProcessError as e:
                    print(f"Incremental build setup failed: {e}")
                    return False
                finally:
                    if inc_tmp.exists():
                        shutil.rmtree(inc_tmp, ignore_errors=True)

            # Strip file:// from APP_PATH and copy contents
            clean_app_path = app_path
            local_app_path = tmpdir / local_app
            local_scripts_path = tmpdir / local_scripts
            # Create directories and copy application source
            local_app_path.mkdir(parents=True, exist_ok=True)

            if Path(clean_app_path).exists():
                # Copy all contents from source to destination
                for item in Path(clean_app_path).iterdir():
                    if item.is_dir():
                        shutil.copytree(item, local_app_path / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, local_app_path)
            else:
                print(f"Source path {clean_app_path} does not exist")
                return False
            # Move .s2i/bin to scripts directory if it exists
            s2i_bin_path = local_app_path / ".s2i" / "bin"
            if s2i_bin_path.exists():
                local_scripts_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s2i_bin_path), str(local_scripts_path))
            # Create Dockerfile content
            dockerfile_lines = [
                f"FROM {src_image}",
                f"LABEL \"io.openshift.s2i.build.image\"=\"{src_image}\" \\",
                f"      \"io.openshift.s2i.build.source-location\"=\"{app_path}\"",
                "USER root",
                f"COPY {local_app} /tmp/src"
            ]
            # Add scripts copy if directory exists
            if local_scripts_path.exists():
                dockerfile_lines.extend([
                    f"COPY {local_scripts} /tmp/scripts",
                    f"RUN chown -R {user_id}:0 /tmp/scripts"
                ])
            dockerfile_lines.append(f"RUN chown -R {user_id}:0 /tmp/src")
            # Check for custom environment variables inside .s2i/ folder
            env_file = local_app_path / ".s2i" / "environment"
            if env_file.exists():
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                dockerfile_lines.append(f"ENV {line}")
                except Exception as e:
                    print(f"Warning: Could not read environment file: {e}")
            # Filter out env var definitions from s2i_args and create Dockerfile ENV commands
            env_commands = get_env_commands_from_s2i_args(s2i_args)
            dockerfile_lines.extend(env_commands)
            # Check if CA authority is present on host and add it into Dockerfile
            if get_full_ca_file_path().exists():
                dockerfile_lines.append("RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract")
            # Add artifacts if doing an incremental build
            if incremental:
                dockerfile_lines.extend([
                    "RUN mkdir /tmp/artifacts",
                    "ADD artifacts.tar /tmp/artifacts",
                    f"RUN chown -R {user_id}:0 /tmp/artifacts"
                ])
            dockerfile_lines.append(f"USER {user_id}")
            # Add assemble script
            if local_scripts_path.exists() and (local_scripts_path / "assemble").exists():
                dockerfile_lines.append("RUN /tmp/scripts/assemble")
            else:
                dockerfile_lines.append("RUN /usr/libexec/s2i/assemble")
            # Add run script
            if local_scripts_path.exists() and (local_scripts_path / "run").exists():
                dockerfile_lines.append("CMD /tmp/scripts/run")
            else:
                dockerfile_lines.append("CMD /usr/libexec/s2i/run")
            # Write Dockerfile
            with open(df_name, 'w') as f:
                f.write('\n'.join(dockerfile_lines))
            # Get mount options from s2i_args
            mount_options = get_mount_options_from_s2i_args(s2i_args)
            # Build the image
            build_command_parts = []
            if mount_options:
                build_command_parts.append(mount_options)
            build_command_parts.extend(["-t", dst_image, ".", build_args])
            build_command = " ".join(filter(None, build_command_parts))
            if not self.build_image_and_parse_id(str(df_name), build_command):
                print(f"ERROR: Failed to build {df_name}")
                return None
            # Store image ID for cleanup
            if hasattr(self, 'app_image_id') and self.app_image_id:
                id_file = self.app_id_file_dir / str(hash(dst_image))
                with open(id_file, 'w') as f:
                    f.write(self.app_image_id)
            return ContainerTestLib(dst_image, s2i_image=True, app_name=os.path.basename(app_path))
        except Exception as e:
            print(f"S2I build failed: {e}")
            return None
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
            # Clean up temporary directory
            if tmpdir.exists():
                shutil.rmtree(tmpdir, ignore_errors=True)

    def build_as_df(
        self,
        app_path: Path,
        src_image: str,
        dst_image: str,
        s2i_args: str = ""
    ):
        """
        Create a new S2I app image from local sources (wrapper function).
        This is the Python equivalent of ct_s2i_build_as_df.
        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the S2I build
            dst_image: Image name to be used during the tagging of the S2I build result
            s2i_args: Additional list of source-to-image arguments
        Returns:
            True if build successful, False otherwise
        """
        return self.build_as_df_build_args(app_path, src_image, dst_image, "", s2i_args)

    def multistage_build(
        self,
        app_path: Path,
        src_image: str,
        sec_image: str,
        dst_image: str,
        s2i_args: str = ""
    ) -> bool:
        """
        Create a new S2I app image from local sources using multistage build.
        This is the Python equivalent of ct_s2i_multistage_build.

        Args:
            app_path: Local path to the app sources to be used in the test
            src_image: Image to be used as a base for the S2I build process
            sec_image: Image to be used as the base for the result of the build process
            dst_image: Image name to be used during the tagging of the S2I build result
            s2i_args: Additional list of source-to-image arguments

        Returns:
            True if build successful, False otherwise
        """
        local_app = "app-src"

        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())
        original_cwd = os.getcwd()

        try:
            os.chdir(tmpdir)

            # Create Dockerfile name
            df_name = Path(tempfile.mktemp(dir=str(tmpdir), prefix="Dockerfile."))

            # Get user from source image
            try:
                user = PodmanCLIWrapper.call_podman_command(
                    cmd=f"inspect -f '{{{{.Config.User}}}}' {src_image}",
                    return_output=True
                ).strip()
                user = user or "0"  # Default to root if no user is set
            except subprocess.CalledProcessError:
                user = "0"

            # Get user ID from image
            user_id = self.get_uid_from_image(user, src_image)
            if not user_id:
                print("Terminating s2i build.")
                return False

            # Handle application source
            local_app_path = tmpdir / local_app
            local_app_path.mkdir(parents=True, exist_ok=True)

            # If the path exists on the local host, copy it into the directory for the build
            # Otherwise handle it as a link to a git repository
            clean_app_path = app_path

            if Path(clean_app_path).exists():
                # Copy all contents from source to destination
                for item in Path(clean_app_path).iterdir():
                    if item.is_dir():
                        shutil.copytree(item, local_app_path / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, local_app_path)
            else:
                # Clone git repository
                if not utils.clone_git_repository(str(app_path), str(local_app_path)):
                    print(f"Failed to clone git repository: {app_path}")
                    return False

            # Create Dockerfile content for multistage build
            dockerfile_lines = [
                "# First stage builds the application",
                f"FROM {src_image} as builder",
                "# Add application sources to a directory that the assemble script expects them",
                "# and set permissions so that the container runs without root access",
                "USER 0",
                f"ADD {local_app} /tmp/src",
                "RUN chown -R 1001:0 /tmp/src"
            ]

            # Filter out env var definitions from s2i_args and create Dockerfile ENV commands
            env_commands = get_env_commands_from_s2i_args(s2i_args)
            dockerfile_lines.extend(env_commands)

            # Check if CA authority is present on host and add it into Dockerfile
            if get_full_ca_file_path().exists():
                dockerfile_lines.append("RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract")

            dockerfile_lines.extend([
                f"USER {user_id}",
                "# Install the dependencies",
                "RUN /usr/libexec/s2i/assemble",
                "# Second stage copies the application to the minimal image",
                f"FROM {sec_image}",
                "# Copy the application source and build artifacts from the builder image to this one",
                "COPY --from=builder $HOME $HOME",
                "# Set the default command for the resulting image",
                "CMD /usr/libexec/s2i/run"
            ])

            # Write Dockerfile
            with open(df_name, 'w') as f:
                f.write('\n'.join(dockerfile_lines))

            # Get mount options from s2i_args
            mount_options = get_mount_options_from_s2i_args(s2i_args)

            # Build the image
            build_command_parts = []
            if mount_options:
                build_command_parts.append(mount_options)
            build_command_parts.extend(["-t", dst_image, "."])
            build_command = " ".join(filter(None, build_command_parts))

            if not self.build_image_and_parse_id(str(df_name), build_command):
                print(f"ERROR: Failed to build {df_name}")
                return False

            # Store image ID for cleanup
            if hasattr(self, 'app_image_id') and self.app_image_id:
                id_file = self.app_id_file_dir / str(hash(dst_image))
                with open(id_file, 'w') as f:
                    f.write(self.app_image_id)

            return True

        except Exception as e:
            print(f"S2I multistage build failed: {e}")
            return False

        finally:
            # Restore original working directory
            os.chdir(original_cwd)
            # Clean up temporary directory
            if tmpdir.exists():
                shutil.rmtree(tmpdir, ignore_errors=True)

    def get_logs(self, cid_file_name: str):
        logs = self.lib.get_logs(cid_file_name=cid_file_name)
        return logs
