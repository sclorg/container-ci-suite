#!/usr/bin/env python3

"""
Example usage of the S2I build functions converted from bash to Python.

This demonstrates how to use the s2i_build_as_df_build_args function
that was converted from the container-test-lib.sh bash script.
"""

import sys
import tempfile
from pathlib import Path

from container_ci_suite.container_lib import ContainerTestLib

# Add the container_ci_suite to the path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Example usage of S2I build functions."""

    # Initialize the test library
    ct = ContainerTestLib()

    print("=== S2I Build Functions Example ===")

    # Example parameters
    src_image = "registry.access.redhat.com/ubi8/python-38"
    dst_image = "my-python-app:latest"

    # Create a simple test application
    with tempfile.TemporaryDirectory() as app_path:
        app_dir = Path(app_path)

        # Create a simple Python application
        (app_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello from S2I Python app!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
""")

        # Create requirements.txt
        (app_dir / "requirements.txt").write_text("Flask==2.0.1\n")

        # Create .s2i directory with environment variables
        s2i_dir = app_dir / ".s2i"
        s2i_dir.mkdir()
        (s2i_dir / "environment").write_text("APP_MODULE=app:app\n")

        print(f"Created test application in: {app_path}")
        print(f"Source image: {src_image}")
        print(f"Destination image: {dst_image}")

        # Example 1: Basic S2I build using s2i_build_as_df
        print("\n1. Testing s2i_build_as_df (wrapper function)...")
        try:
            success = ct.build_as_df(
                app_path=str(app_dir),
                src_image=src_image,
                dst_image=dst_image,
                s2i_args=""
            )
            if success:
                print("✓ S2I build (basic) completed successfully")
            else:
                print("✗ S2I build (basic) failed")
        except Exception as e:
            print(f"✗ S2I build (basic) failed with exception: {e}")

        # Example 2: S2I build with build args using s2i_build_as_df_build_args
        print("\n2. Testing s2i_build_as_df_build_args (full function)...")
        dst_image_with_args = "my-python-app-with-args:latest"
        try:
            success = ct.build_as_df_build_args(
                app_path=str(app_dir),
                src_image=src_image,
                dst_image=dst_image_with_args,
                build_args="--label version=1.0",
                s2i_args="-e FLASK_ENV=development"
            )
            if success:
                print("✓ S2I build (with args) completed successfully")
            else:
                print("✗ S2I build (with args) failed")
        except Exception as e:
            print(f"✗ S2I build (with args) failed with exception: {e}")

        # Example 3: S2I build with mount options
        print("\n3. Testing s2i_build_as_df_build_args with mount options...")
        dst_image_with_mount = "my-python-app-with-mount:latest"
        try:
            success = ct.build_as_df_build_args(
                app_path=str(app_dir),
                src_image=src_image,
                dst_image=dst_image_with_mount,
                build_args="",
                s2i_args="-v /tmp:/tmp:Z -e DEBUG=true"
            )
            if success:
                print("✓ S2I build (with mount) completed successfully")
            else:
                print("✗ S2I build (with mount) failed")
        except Exception as e:
            print(f"✗ S2I build (with mount) failed with exception: {e}")

    print("\n=== S2I Build Examples completed ===")
    print("\nNote: These examples demonstrate the Python conversion of:")
    print("- ct_s2i_build_as_df_build_args() -> s2i_build_as_df_build_args()")
    print("- ct_s2i_build_as_df() -> s2i_build_as_df()")
    print("- ct_get_uid_from_image() -> get_uid_from_image()")

    return 0


if __name__ == "__main__":
    sys.exit(main())
