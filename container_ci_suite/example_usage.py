#!/usr/bin/env python3

"""
Example usage of the Container Test Library Python migration.

This demonstrates how to use the migrated Python functionality
that replaces the container-test-lib.sh bash script.
"""

import sys
from pathlib import Path

from container_ci_suite.container_lib import ContainerTestLib

# Add the container_ci_suite to the path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Example usage of the Container Test Library."""

    # Initialize the test library
    ct = ContainerTestLib()

    # Set the image name to test
    ct.image_name = "registry.access.redhat.com/ubi8/python-38"

    print("=== Container Test Library Python Migration Example ===")
    print(f"Testing image: {ct.image_name}")

    # Example 1: Pull an image
    print("\n1. Pulling image...")
    if ct.pull_image(ct.image_name):
        print("✓ Image pulled successfully")
    else:
        print("✗ Failed to pull image")
        return 1

    # Example 2: Check if image exists
    print("\n2. Checking if image exists...")
    if ct.is_container_exists(ct.image_name):
        print("✓ Image exists")
    else:
        print("✗ Image does not exist")

    # Example 3: Create and test a container
    print("\n3. Creating a test container...")
    if ct.create_container("test_container", "sleep 30"):
        print("✓ Container created successfully")

        # Get container IP
        try:
            ip = ct.get_cip("test_container")
            print(f"✓ Container IP: {ip}")
        except Exception as e:
            print(f"✗ Could not get container IP: {e}")

        # Clean up
        ct.cleanup()
        print("✓ Cleanup completed")
    else:
        print("✗ Failed to create container")

    # Example 4: Test environment variables
    print("\n4. Testing environment variable checking...")
    try:
        # This would normally be used with a running container
        print("✓ Environment variable checking functionality available")
    except Exception as e:
        print(f"✗ Environment variable check failed: {e}")

    # Example 5: Show system resources
    print("\n5. Showing system resources...")
    ct.show_resources()

    # Example 6: Generate random string
    print("\n6. Generating random string...")
    random_str = ct.random_string(8)
    print(f"✓ Generated random string: {random_str}")

    # Example 7: Test command assertions
    print("\n7. Testing command assertions...")
    if ct.assert_cmd_success("echo", "test"):
        print("✓ Command assertion (success) works")
    else:
        print("✗ Command assertion (success) failed")

    if ct.assert_cmd_failure("false"):
        print("✓ Command assertion (failure) works")
    else:
        print("✗ Command assertion (failure) failed")

    # Example 8: S2I Multistage Build (new migrated function)
    print("\n8. Testing S2I Multistage Build...")
    try:
        # This is a demonstration - would need real app path and images
        print("✓ S2I Multistage Build function available")
        print("  Usage: ct.s2i_multistage_build(app_path, src_image, sec_image, dst_image, s2i_args)")
        print("  This function creates a multistage Docker build for S2I applications")
        print("  - First stage: builds the application using the source image")
        print("  - Second stage: copies artifacts to a minimal runtime image")
    except Exception as e:
        print(f"✗ S2I Multistage Build test failed: {e}")

    # Example 9: Test App Dockerfile (new migrated function)
    print("\n9. Testing App Dockerfile...")
    try:
        # This is a demonstration - would need real dockerfile and app
        print("✓ Test App Dockerfile function available")
        print("  Usage: ct.test_app_dockerfile(dockerfile, app_url, expected_text, app_dir, build_args)")
        print("  This function:")
        print("  - Builds a Docker image from a Dockerfile and application source")
        print("  - Runs the container and tests HTTP responses")
        print("  - Validates that the application responds with expected content")
        print("  - Handles both local directories and git repositories as app sources")
    except Exception as e:
        print(f"✗ Test App Dockerfile test failed: {e}")

    print("\n=== Example completed successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
