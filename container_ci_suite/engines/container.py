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
import logging
import re
import time
import subprocess
import shutil

from typing import List, Union
from os import getenv
from pathlib import Path
from tempfile import mkdtemp, mktemp

from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper
from container_ci_suite.utils import ContainerTestLibUtils
from container_ci_suite import utils
from container_ci_suite.exceptions import ContainerCIException

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ContainerImage:

    def __init__(self, image_name: str, cid_file: Path = None, cid_file_dir: Path = None):
        self.image_name: str = image_name
        self.container_args: str = ""
        self.cid_file = cid_file
        self.cid_file_dir = cid_file_dir
        self.app_image_name = "app_dockerfile"
        self.temporary_app_dir: Path = None
        self.application_image_id: str = ""
        logger.info(f"Image name to test: {image_name}")

    def pull_image(self, image_name: str, exit_on_fail: bool = False, loops: int = 10) -> bool:
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
            result = PodmanCLIWrapper.run_docker_command(cmd=f"images -q {image_name}", return_output=True)
            if result.strip():
                print(f"The image {image_name} is already pulled.")
                return True
        except subprocess.CalledProcessError:
            pass

        # Try pulling the image
        for loop in range(1, loops + 1):
            try:
                PodmanCLIWrapper.run_docker_command(cmd=f"pull {image_name}", return_output=False)
                return True
            except subprocess.CalledProcessError:
                print(f"Pulling image {image_name} failed.")
                if loop > loops:
                    print(f"Pulling of image {image_name} failed {loops} times in a row. Giving up.")
                    print(f"!!! ERROR with pulling image {image_name} !!!!")
                    if exit_on_fail:
                        raise ContainerCIException(f"!!! ERROR with pulling image {image_name} !!!!")
                    return False

                wait_time = loop * 5
                print(f"Let's wait {wait_time} seconds and try again.")
                time.sleep(wait_time)

        return False

    @staticmethod
    def is_container_running(container_id: str) -> bool:
        """
        Check if container is in running state.
        Args:
            container_id: Container ID to check
        Returns:
            True if container is running, False otherwise
        """
        try:
            result = PodmanCLIWrapper.run_docker_command(
                cmd=f"inspect -f '{{{{.State.Running}}}}' {container_id}",
                return_output=True
            )
            return result.strip() == "true"
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def is_container_exists(container_id: str) -> bool:
        """
        Check if container exists.
        Args:
            container_id: Container ID to check
        Returns:
            True if container exists, False otherwise
        """
        try:
            result = PodmanCLIWrapper.run_docker_command(
                cmd=f"ps -q -a -f 'id={container_id}'",
                return_output=True
            )
            return bool(result.strip())
        except subprocess.CalledProcessError:
            return False

    def get_cid(self, name: str) -> str:
        """
        Get container ID from cid_file.
        Args:
            name: Name of the cid_file
        Returns:
            Container ID
        """
        cid_file = self.cid_file_dir / name
        return utils.get_file_content(cid_file).strip()

    def get_cip(self, cid_name: str) -> str:
        """
        Get container IP address.
        Args:
            cid_name: Name of the cid_file
        Returns:
            Container IP address
        """
        container_id = self.get_cid(cid_name)
        print(f"Container ID is: {container_id}")
        try:
            result = PodmanCLIWrapper.run_docker_command(
                cmd=f"inspect --format='{{{{.NetworkSettings.IPAddress}}}}' {container_id}",
                return_output=True
            )
            return result.strip()
        except subprocess.CalledProcessError:
            return ""

    def get_container_exit_code(self, cid_name: str) -> str:
        """
        Get container IP address.
        Args:
            cid_name: Name of the cid_file
        Returns:
            Container IP address
        """
        container_id = self.get_cid(cid_name)
        print(f"Container ID is: {container_id}")
        try:
            result = PodmanCLIWrapper.run_docker_command(
                cmd=f"inspect --format='{{{{.State.ExitCode}}}}' {container_id}",
                return_output=True
            )
            return result.strip()
        except subprocess.CalledProcessError:
            return ""

    @staticmethod
    def wait_for_cid(
        cid_file: Union[str, Path],
        max_attempts: int = 10,
        sleep_time: int = 1
    ) -> bool:
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

    def rmi_app(self):
        app_cip = self.get_cid_file(Path(self.temporary_app_dir) / self.app_image_name)
        PodmanCLIWrapper.run_docker_command(cmd=f"kill {app_cip}")
        PodmanCLIWrapper.run_docker_command(cmd=f"rmi {self.app_image_name}")
        if Path(self.temporary_app_dir).exists():
            shutil.rmtree(self.temporary_app_dir)

    def s2i_usage(self) -> str:
        return PodmanCLIWrapper.run_docker_command(
            f"run --rm {self.image_name} bash -c /usr/libexec/s2i/usage"
        )

    def is_image_available(self):
        return PodmanCLIWrapper.run_docker_command(f"inspect {self.image_name}")

    # Replacement for ct_s2i_build_as_df
    def s2i_build_as_df(self, app_path: str, s2i_args: str, src_image: str, dst_image: str):
        named_tmp_dir = mkdtemp()
        tmp_dir = Path(named_tmp_dir)
        if tmp_dir.exists():
            logger.debug("Temporary Directory exists.")
        else:
            logger.debug("Temporary directory not exists.")
        ntf = mktemp(dir=str(tmp_dir), prefix="Dockerfile.")
        df_name = Path(ntf)
        df_content = self.create_dockerfile(
            tmp_dir=tmp_dir,
            app_path=app_path,
            s2i_args=s2i_args,
            src_image=src_image,
            dst_image=dst_image,
        )
        with open(df_name, mode="w") as f:
            f.write('\n'.join(df_content))
        mount_options = utils.get_mount_options_from_s2i_args(s2i_args=s2i_args)
        # Run the build and tag the result
        PodmanCLIWrapper.run_docker_command(
            f"build {mount_options} -f {df_name} --no-cache=true -t {dst_image}"
        )
        return ContainerImage(image_name=dst_image)

    # Replacement for ct_s2i_build_as_df_build_args
    def create_dockerfile(
        self, tmp_dir: Path, app_path: str, s2i_args: str, src_image, dst_image: str
    ) -> List[str]:
        real_app_path = app_path.replace("file://", "")
        df_content: List = []
        local_scripts: str = "upload/scripts"
        local_app: str = "upload/src"
        os.chdir(tmp_dir)
        if not PodmanCLIWrapper.docker_image_exists(src_image):
            if "pull-policy=never" not in s2i_args:
                PodmanCLIWrapper.run_docker_command(f"pull {src_image}")

        user = PodmanCLIWrapper.docker_inspect(
            field="{{.Config.User}}", src_image=src_image
        )
        if not user:
            user = "0"

        assert int(user)
        user_id = PodmanCLIWrapper.docker_get_user_id(src_image=src_image, user=user)
        if not user_id:
            logger.error(f"id of user {user} not found inside image {src_image}.")
            logger.error("Terminating s2i build.")
            return None
        user_id = user

        incremental: bool = "--incremental" in s2i_args
        if incremental:
            inc_tmp = Path(mktemp(dir=str(tmp_dir), prefix="incremental."))
            ContainerTestLibUtils.run_command(f"setfacl -m 'u:{user_id}:rwx' {inc_tmp}")
            # Check if the image exists, build should fail (for testing use case) if it does not
            if not PodmanCLIWrapper.docker_image_exists(src_image):
                return None
            # Run the original image with a mounted in volume and get the artifacts out of it
            cmd = (
                "if [ -s /usr/libexec/s2i/save-artifacts ];"
                ' then /usr/libexec/s2i/save-artifacts > "$inc_tmp/artifacts.tar";'
                ' else touch "$inc_tmp/artifacts.tar"; fi'
            )
            PodmanCLIWrapper.run_docker_command(
                f"run --rm -v {inc_tmp}:{inc_tmp}:Z {dst_image} bash -c {cmd}"
            )
            # Move the created content into the $tmpdir for the build to pick it up
            shutil.move(f"{inc_tmp}/artifacts.tar", tmp_dir.name)
        real_local_app = tmp_dir / local_app
        real_local_scripts = tmp_dir / local_scripts
        os.makedirs(real_local_app.parent)
        shutil.copytree(real_app_path, real_local_app)
        bin_dir = real_local_app / ".s2i" / "bin"
        if bin_dir.exists():
            shutil.move(bin_dir, real_local_scripts)
        df_content.extend(
            [
                f"FROM {src_image}",
                f"LABEL io.openshift.s2i.build.image={src_image} "
                f"io.openshift.s2i.build.source-location={app_path}",
                "USER root",
                f"COPY {local_app}/ /tmp/src",
            ]
        )
        if real_local_scripts.exists():
            df_content.append(f"COPY {local_scripts} /tmp/scripts")
            df_content.append(f"RUN chown -R {user_id}:0 /tmp/scripts")
        df_content.append(f"RUN chown -R {user_id}:0 /tmp/src")

        # Check for custom environment variables inside .s2i/ folder
        env_file = Path(real_local_app / ".s2i" / "environment")
        if env_file.exists():
            with open(env_file) as fd:
                env_content = fd.readlines()
            # Remove any comments and add the contents as ENV commands to the Dockerfile
            env_content = [f"ENV {x}" for x in env_content if not x.startswith("#")]
            df_content.extend(env_content)

        # Filter out env var definitions from $s2i_args
        # and create Dockerfile ENV commands out of them
        env_content = utils.get_env_commands_from_s2i_args(s2i_args=s2i_args)
        df_content.extend(env_content)

        # Check if CA autority is present on host and add it into Dockerfile
        if utils.get_full_ca_file_path().exists():
            df_content.append(
                "RUN cd /etc/pki/ca-trust/source/anchors && update-ca-trust extract"
            )
        # Add in artifacts if doing an incremental build
        if incremental:
            df_content.extend(
                [
                    "RUN mkdir /tmp/artifacts",
                    "RUN artifacts.tar /tmp/artifacts",
                    f"RUN chown -R {user_id}:0 /tmp/artifacts",
                ]
            )
        df_content.append(f"USER {user_id}")
        # If exists, run the custom assemble script, else default to /usr/libexec/s2i/assemble
        if (real_local_scripts / "assemble").exists():
            df_content.append("RUN /tmp/scripts/assemble")
        else:
            df_content.append("RUN /usr/libexec/s2i/assemble")
        # If exists, set the custom run script as CMD, else default to /usr/libexec/s2i/run
        if Path(real_local_scripts / "run").exists():
            df_content.append("CMD /tmp/scripts/run")
        else:
            df_content.append("CMD /usr/libexec/s2i/run")

        logger.error(df_content)
        return df_content

    def build_image_parse_id(self, dockerfile: str = "", build_params: str = "") -> bool:
        dockerfile_name = f"-f {dockerfile}" if dockerfile != "" else ""
        podman_cmd = f"build --no-cache {dockerfile_name} {build_params}"
        print(f"Command for building container: {podman_cmd}")
        try:
            output = PodmanCLIWrapper.run_docker_command(cmd=podman_cmd, ignore_error=True)
            print(f"Output from build is:\n{output}")
            self.application_image_id = output.split("\n")[-2]
            print(f"Application IMAGE id is: {self.application_image_id}.")
            return True
        except subprocess.CalledProcessError as cpe:
            print(f"Building container by command {podman_cmd} failed for reason '{cpe}' and {cpe.stderr}")
            return False

    def test_response(
            self, url: str = "",
            expected_code: int = 200, port: int = 8080,
            expected_output: str = "", max_tests: int = 20
    ) -> bool:
        url = f"{url}:{port}"
        print(f"URL address to get response from container: {url}")
        cmd_to_run = "curl --connect-timeout 10 -k -s -w '%{http_code}' " + f"{url}"
        # Check if application returns proper HTTP_CODE
        print("Check if HTTP_CODE is valid.")
        for count in range(max_tests):
            try:
                output_code = ContainerTestLibUtils.run_command(cmd=f"{cmd_to_run}", return_output=True)
                return_code = output_code[-3:]
                print(f"Output is: {output_code} and Return Code is: {return_code}")
                try:
                    int_ret_code = int(return_code)
                    if int_ret_code == expected_code:
                        print(f"HTTP_CODE is VALID {int_ret_code}")
                        break
                except ValueError:
                    logger.info(return_code)
                    time.sleep(1)
                    continue
                time.sleep(3)
                continue
            except subprocess.CalledProcessError as cpe:
                print(f"Error from {cmd_to_run} is {cpe.stderr}, {cpe.stdout}")
                time.sleep(3)

        cmd_to_run = "curl --connect-timeout 10 -k -s " + f"{url}"
        # Check if application returns proper output
        for count in range(max_tests):
            output_code = ContainerTestLibUtils.run_command(cmd=f"{cmd_to_run}", return_output=True)
            print(f"Check if expected output {expected_output} is in {cmd_to_run}.")
            if expected_output in output_code:
                print(f"Expected output '{expected_output}' is present.")
                return True
            print(
                f"check_response_inside_cluster:"
                f"expected_output {expected_output} not found in output of {cmd_to_run} command. See {output_code}"
            )
            time.sleep(5)
        return False

    # Replacement for ct_create_container
    def create_container(self, cid_file: str, container_args: str = "") -> bool:
        self.cid_file_dir = Path(mkdtemp(suffix=".test_cid_files"))
        p = Path(self.cid_file_dir)
        self.cid_file = p / cid_file

        print(f"The CID file {self.cid_file}")
        args_to_run = ""
        if container_args != "":
            args_to_run = container_args
        if container_args != "":
            cmd = f"run --cidfile={self.cid_file} -d {args_to_run} {self.image_name}"
        else:
            cmd = f"run --cidfile={self.cid_file} -d {self.image_name}"
        try:
            PodmanCLIWrapper.run_docker_command(cmd=cmd)
        except subprocess.CalledProcessError as cpe:
            print(f"The command '{cmd}' failed with {cpe.output} and error: {cpe.stderr}")
            print(f"Failed to create container: {cpe}")
            return False
        if not ContainerImage.wait_for_cid(cid_file=self.cid_file):
            return False
        print(f"Created container {self.get_cid_file()}")
        return True

    def get_cid_file(self, cid_file: Path = None):
        if cid_file is None:
            return utils.get_file_content(self.cid_file)
        return utils.get_file_content(cid_file)

    # Replacement for ct_check_image_availability
    def check_image_availability(self, public_image_name: str):
        try:
            PodmanCLIWrapper.run_docker_command(
                f"pull {public_image_name}", return_output=False
            )
        except subprocess.CalledProcessError as cfe:
            logger.error(f"{public_image_name} could not be downloaded via 'docker'.")
            logger.error(cfe)
            return False
        return True

    # Replacement for ct_clean_containers
    def cleanup_container(self):
        logger.info(f"Cleaning CID_FILE_DIR {self.cid_file_dir} is ongoing.")
        p = Path(self.cid_file_dir)
        cid_files = p.glob("*")
        for cid_file in cid_files:
            if not Path(cid_file).exists():
                continue
            container_id = utils.get_file_content(cid_file)
            logger.info("Stopping container")
            PodmanCLIWrapper.run_docker_command(f"stop {container_id}")
            exit_code = PodmanCLIWrapper.docker_inspect(
                field="{{.State.ExitCode}}", src_image=container_id
            )
            if exit_code != 0:
                logs = PodmanCLIWrapper.run_docker_command(f"logs {container_id}")
                logger.info(logs)
            PodmanCLIWrapper.run_docker_command(f"rm -v {container_id}")
            if not Path(cid_file).exists():
                continue
            cid_file.unlink()
        os.rmdir(self.cid_file_dir)
        logger.info(f"Cleanning CID_FILE_DIR {self.cid_file_dir} is DONE.")

    # Replacement for ct_assert_container_creation_fails
    def assert_container_fails(self, cid_file: str, container_args: str):
        attempt: int = 1
        max_attempts: int = 10
        old_container_args = container_args
        if self.create_container(cid_file, container_args=container_args):
            cid = self.get_cid_file()
            while not PodmanCLIWrapper.docker_inspect(
                field="{{.State.Running}}", src_image=cid
            ):
                time.sleep(2)
                attempt += 1
                if attempt > max_attempts:
                    PodmanCLIWrapper.run_docker_command("stop cid")
                    return True
            exit_code = PodmanCLIWrapper.docker_inspect(
                field="{{.State.ExitCode}}", src_image=cid
            )
            if exit_code == 0:
                return True
            PodmanCLIWrapper.run_docker_command(f"rm -v {cid}")
            self.cid_file.unlink()
        if old_container_args != "":
            self.container_args = old_container_args
        return False

    # Replacement for ct_npm_works
    def npm_works(self):
        tempdir = mkdtemp(suffix="npm_test")
        self.cid_file = Path(tempdir) / "npm_test_cid"
        try:
            try:
                PodmanCLIWrapper.run_docker_command(
                    f'run --rm {self.image_name} /bin/bash -c "npm --version"'
                )
            except subprocess.CalledProcessError:
                logger.error(
                    f"ERROR: 'npm --version' does not work inside the image {self.image_name}."
                )
                return False

            # TODO
            # Add {self.image_name}-testapp as soon as function `s2i_create_df` is ready.
            PodmanCLIWrapper.run_docker_command(
                f"run -d {utils.get_mount_ca_file()} --rm --cidfile={self.cid_file} {self.image_name}"
            )
            if not self.wait_for_cid():
                logger.error("Container did not create cidfile.")
                return False

            try:
                jquery_output = PodmanCLIWrapper.run_docker_command(
                    f"exec {self.get_cid_file(self.cid_file)} "
                    f"/bin/bash -c "
                    f"'npm --verbose install jquery && test -f node_modules/jquery/src/jquery.js'"
                )
            except subprocess.CalledProcessError:
                logger.error(
                    f"npm could not install jquery inside the image ${self.image_name}."
                )
                return False
            if getenv("NPM_REGISTRY") and utils.get_full_ca_file_path().exists():
                if utils.get_os_environment("NPM_REGISTRY") in jquery_output:
                    logger.error("Internal repository is NOT set. Even it is requested.")
                    return False

            if self.cid_file.exists():
                PodmanCLIWrapper.run_docker_command(
                    f"stop {self.get_cid_file(self.cid_file)}"
                )
                self.cid_file.unlink()
            print("Success!")
            logger.info("Npm works.")
            return True
        finally:
            shutil.rmtree(tempdir)

    # Replacement for ct_binary_found_from_df
    def binary_found_from_df(self, binary: str = "", binary_path: str = "^/opt/rh"):
        tempdir = mkdtemp(suffix=f"{self.image_name}_binary")
        dockerfile = Path(tempdir) / "Dockerfile"
        logger.info(f"Testing {binary} in build from Dockerfile")
        content: str = f"""FROM {self.image_name}
RUN which {binary} | grep {binary_path}
        """
        with open(dockerfile, "w") as f:
            f.write(content)
        if not PodmanCLIWrapper.run_docker_command(
            f"build -f {dockerfile} --no-cache {tempdir}", return_output=False
        ):
            logger.error(f"Failed to find {binary} in Dockerfile!")
            return False
        return True

    def doc_content_old(self, strings: List) -> bool:
        logger.info("Testing documentation in the container image")
        files_to_check = ["help.1"]
        for f in files_to_check:
            doc_content = PodmanCLIWrapper.docker_run_command(f'--rm {self.image_name} /bin/bash -c cat {f}')
            for term in strings:
                # test = re.search(f"{term}", doc_content)
                logger.info(f"ERROR: File /{f} does not contain '{term}'.")
                return False
            for term in ["TH", "PP", "SH"]:
                if term not in doc_content:
                    logger.info(f"ERROR: help.1 is probably not in troff or groff format, since {term} is missing")
                    return False
        return True

    # Replacement for ct_check_exec_env_vars
    def test_check_exec_env_vars(self, env_filter: str = "^X_SCLS=|/opt/rh|/opt/app-root"):
        check_envs = PodmanCLIWrapper.docker_run_command(f'--rm {self.image_name} /bin/bash -c env')
        logger.debug(f"Run envs {check_envs}")
        self.create_container(cid_file="exec_env_vars", container_args="bash -c 'sleep 1000'")
        loop_envs = PodmanCLIWrapper.run_docker_command(f"exec {self.get_cid_file(self.cid_file)} env")
        self.test_check_envs_set(env_filter=env_filter, check_envs=check_envs, loop_envs=loop_envs)

    # Replacement for ct_check_scl_enable_vars
    def test_check_envs_set(self, env_filter: str, check_envs: str, loop_envs: str, env_format="VALUE"):
        fields_to_check: List = [
            x for x in loop_envs.split('\n') if re.findall(env_filter, x) and not x.startswith("PWD=")
        ]
        for field in fields_to_check:
            var_name, stripped = field.split('=', 2)
            filtered_envs = [x for x in check_envs.split('\n') if x.startswith(f"{var_name}=")]
            if not filtered_envs:
                logger.error(f"{var_name} not found during 'docker exec'")
                return False
            filter_envs = ''.join(filtered_envs)
            for value in stripped.split(':'):
                # If the value checked does not go through env_filter we do not care about it
                ret = re.findall(env_filter, value)
                if not ret:
                    continue
                new_env = env_format.replace('VALUE', value)
                find_env = re.findall(rf"{new_env}", filter_envs)
                if not find_env:
                    logger.error(f"Value {value} is missing from variable {var_name}")
                    logger.error(filtered_envs)
                    return False
        return True

    def build_test_container(
            self,
            dockerfile: str, app_url: str, app_dir: str,
            build_args: str = "",
            app_image_name: str = "app_dockerfile"
    ) -> bool:
        """
        Function builds testing application container
        param: dockerfile - path to a Dockerfile that will be used for building an image
                         (must work with an application directory called 'app-src')
        param: app_url - git or local URI with a testing application, supports "@" to indicate a different branch
        param: expected_output - PCRE regular expression that must match the response body
        param: app_dir - name of the application directory that is used in the Dockerfile
        param: build_args - build args that will be used for building an image
        param: app_image_name - how the container will be named in output `podman images`. Default app_dockerfile
        """
        self.temporary_app_dir = Path(mkdtemp(suffix="app_test_dir"))
        self.app_image_name = app_image_name
        if not app_dir:
            print("build_test_container: Parameter app_dir has to be set.")
            return False
        if not Path(dockerfile).exists():
            print(f"build_test_container: Dockerfile {dockerfile} does not exist or is empty.")
            return False
        full_path = Path(dockerfile).resolve()
        print(f"Resolved dockerfile {full_path}")
        tempdir = self.temporary_app_dir
        with utils.cwd(tempdir) as _:
            print(f"Copy Dockerfile from {full_path} to '{tempdir}/Dockerfile'")
            shutil.copy(full_path, "Dockerfile")
            docker_content = utils.get_file_content(Path("Dockerfile")).split('\n')
            for index, line in enumerate(docker_content):
                docker_content[index] = re.sub("^FROM.*$", f"FROM  {self.image_name}", line)
            utils.save_file_content('\n'.join(docker_content), Path("Dockerfile"))
            if Path(app_url).is_dir():
                print(f"Copy local folder {app_url} to {app_dir}.")
                shutil.copytree(app_url, app_dir, symlinks=True)
            else:
                utils.clone_git_repository(app_url=app_url, app_dir=app_dir)
            print(f"Building '{app_image_name}' image using docker build")
            if not self.build_image_parse_id(build_params=f"-t {self.app_image_name} . {build_args}"):
                return False
        output = PodmanCLIWrapper.run_docker_command(cmd="images", ignore_error=True)
        print(f"Output from podman images is:\n{output}")
        return True

    def test_app_dockerfile(self) -> bool:
        """
            param: expected_output - PCRE regular expression that must match the response body
        """
        podman_cmd = f"run -d --cidfile={self.cid_file_dir}/{self.app_image_name} --rm {self.app_image_name}"
        print(f"Run container {self.app_image_name}: {podman_cmd}")
        try:
            output = PodmanCLIWrapper.run_docker_command(cmd=podman_cmd, ignore_error=True).strip()
            print(f"Output from build is:\n{output}")
        except subprocess.CalledProcessError as cpe:
            print(f"Building container by command {podman_cmd} failed for reason '{cpe}' and '{cpe.stderr}'")
            return False
        if not ContainerImage.wait_for_cid(
            cid_file=f"{self.cid_file_dir}/{self.app_image_name}"
        ):
            print("Container did not create cidfile. See logs from container.")
            return False
        return True
