#!/usr/bin/env python3
"""
Dockerfile processor module to replace sed commands with Python functionality.
This module provides utilities to process Dockerfiles by replacing version strings
and environment variables.
"""

import re
import tempfile

from pathlib import Path
from typing import Union


class DockerfileProcessor:
    """
    A class to process Dockerfiles by replacing version strings and environment variables.
    This replaces the functionality of sed commands used in shell scripts.
    """

    def __init__(self, dockerfile_path: Union[str, Path]):
        """
        Initialize the DockerfileProcessor with a path to a Dockerfile.
        Args:
            dockerfile_path: Path to the Dockerfile to process
        """
        self.dockerfile_path = Path(dockerfile_path)
        self.content = ""
        if not self.dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")
        with open(self.dockerfile_path, 'r') as f:
            self.content = f.read()

    def update_variable_in_dockerfile(self, version: str, variable: str):
        """
        Process the Dockerfile to replace NGINX version strings.
        This method performs the same operations as the sed command:
        Args:
            version: The NGINX version to use for replacement
            variable: Expression to replace with $
        Returns:
            The processed Dockerfile content as a string
        """

        # Replace all occurrences of $NGINX_VERSION (equivalent to s/\$NGINX_VERSION/$version/g)
        split_dockerfile = self.content.split("\n")
        for index, line in enumerate(split_dockerfile):
            if line.startswith("#"):
                continue
            split_dockerfile[index] = re.sub(
                fr'\${variable}',
                version,
                line
            )
        self.content = '\n'.join(split_dockerfile)

    def update_env_in_dockerfile(self, version: str, what_to_replace: str):
        """
        Process the Dockerfile to replace NGINX version strings.
        This method performs the same operations as the sed command:
        Args:
            version: The NGINX version to use for replacement
            what_to_replace: Expression to replace
        Returns:
            The processed Dockerfile content as a string
        """

        split_dockerfile = self.content.split("\n")
        for index, line in enumerate(split_dockerfile):
            if line.startswith("#"):
                continue
            split_dockerfile[index] = re.sub(
                fr'^{what_to_replace}.*$',
                f"{what_to_replace}={version}",
                line
            )
        self.content = '\n'.join(split_dockerfile)

    def create_temp_dockerfile(self) -> str:
        """
        Create a temporary Dockerfile with processed version strings.
        Args:
            version: The NGINX version to use for replacement
        Returns:
            Path to the temporary Dockerfile
        """
        # Create a temporary file
        local_docker_file = tempfile.mktemp(prefix="/tmp/new_dockerfile")
        with open(local_docker_file, "w") as f:
            f.write(self.content)

        return str(local_docker_file)

    def validate_dockerfile_syntax(self, content: str) -> bool:
        """
        Basic validation of Dockerfile syntax.
        Args:
            content: Dockerfile content to validate
        Returns:
            True if basic syntax checks pass, False otherwise
        """
        lines = content.strip().split('\n')
        # Check for basic Dockerfile structure
        has_from = any(line.strip().upper().startswith('FROM') for line in lines)
        if not has_from:
            return False
        # Check for valid instruction format
        valid_instructions = {
            'FROM', 'RUN', 'CMD', 'LABEL', 'EXPOSE', 'ENV', 'ADD', 'COPY',
            'ENTRYPOINT', 'VOLUME', 'USER', 'WORKDIR', 'ARG', 'ONBUILD',
            'STOPSIGNAL', 'HEALTHCHECK', 'SHELL'
        }
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Extract the instruction (first word)
            instruction = line.split()[0].upper()
            if instruction not in valid_instructions:
                return False

        return True

    def get_content(self):
        return self.content
