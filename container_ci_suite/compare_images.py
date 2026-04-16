import logging
import subprocess

from container_ci_suite.engines.podman_wrapper import PodmanCLIWrapper

logger = logging.getLogger(__name__)


class ContainerCompareClass:
    """
    Container Compare Class - Utility functions for container comparison.
    """

    @staticmethod
    def get_image_size_uncompressed(image_name: str) -> int:
        """
        Get uncompressed image size.
        Args:
            image_name: Image name
        Returns:
            Size (int)
        """
        try:
            size_bytes = PodmanCLIWrapper.call_podman_command(
                cmd=f"inspect {image_name} -f '{{{{.Size}}}}'", return_output=True
            ).strip()
            size_bytes = int(size_bytes)
            return size_bytes
        except (subprocess.CalledProcessError, ValueError):
            return 0

    @staticmethod
    def get_image_size_compressed(image_name: str) -> int:
        """
        Get compressed image size.
        Args:
            image_name: Image name
        Returns:
            Size (int)
        """
        try:
            # Save image and compress to get size
            result = PodmanCLIWrapper.call_podman_command(
                cmd=f"save {image_name} | gzip - | wc --bytes", return_output=True
            )
            size_bytes = int(result.strip())
            return size_bytes
        except (subprocess.CalledProcessError, ValueError):
            return 0

    @staticmethod
    def is_uncompressed_image_smaller_than_official_image(
        uncompressed_image_name: str, official_image_name: str
    ) -> bool:
        """
        Check if the built image is smaller than the official image.
        Args:
            uncompressed_image_name: The uncompressed image name
            official_image_name: The official image name
        Returns:
            True if the built image is smaller than the official image, False otherwise
        """
        built_image_size = ContainerCompareClass.get_image_size_uncompressed(
            uncompressed_image_name
        )
        if not PodmanCLIWrapper.podman_image_exists(official_image_name):
            logger.warning(
                "Official image %s does not exist on the system. Let's pull it.",
                official_image_name,
            )
            if not PodmanCLIWrapper.podman_pull_image(official_image_name):
                logger.error(
                    "Failed to pull the official image %s", official_image_name
                )
                return False
        official_image_size = ContainerCompareClass.get_image_size_uncompressed(
            official_image_name
        )
        logger.info("Built image size: %s", built_image_size)
        logger.info("Official image size: %s", official_image_size)
        if built_image_size < official_image_size:
            logger.info("Built image is smaller than the official image")
            return True
        logger.info("Built image is not smaller than the official image")
        return False

    @staticmethod
    def is_compressed_image_smaller_than_official_image(
        compressed_image_name: str, official_image_name: str
    ) -> bool:
        """
        Check if the compressed image is smaller than the official image.
        Args:
            compressed_image_name: The compressed image name
            official_image_name: The official image name
        Returns:
            True if the compressed image is smaller than the official image, False otherwise
        """
        compressed_image_size = ContainerCompareClass.get_image_size_compressed(
            compressed_image_name
        )
        official_image_size = ContainerCompareClass.get_image_size_compressed(
            official_image_name
        )
        logger.info("Compressed image size: %s", compressed_image_size)
        logger.info("Official image size: %s", official_image_size)
        if compressed_image_size < official_image_size:
            logger.info("Compressed image is smaller than the official image")
            return True
        logger.info("Compressed image is not smaller than the official image")
        return False
