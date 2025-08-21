#!/usr/bin/env python3

"""
Test script for the s2i_multistage_build function migration.
This script demonstrates the usage of the migrated ct_s2i_multistage_build function.
"""

import tempfile
import shutil
from pathlib import Path
from container_ci_suite.container_lib import ContainerTestLib


def test_s2i_multistage_build():
    """Test the s2i_multistage_build function with a simple example."""

    # Initialize the container test library
    ctl = ContainerTestLib()

    # Create a temporary directory with a simple app
    test_app_dir = Path(tempfile.mkdtemp(prefix="test_app_"))

    try:
        # Create a simple test application
        (test_app_dir / "index.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>Test App</title>
</head>
<body>
    <h1>Hello from S2I Multistage Build!</h1>
</body>
</html>
""")

        # Create a simple package.json for Node.js app
        (test_app_dir / "package.json").write_text("""
{
  "name": "test-app",
  "version": "1.0.0",
  "description": "Test application for S2I multistage build",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  }
}
""")

        # Create a simple server.js
        (test_app_dir / "server.js").write_text("""
const http = require('http');
const fs = require('fs');

const server = http.createServer((req, res) => {
    if (req.url === '/') {
        fs.readFile('index.html', (err, data) => {
            if (err) {
                res.writeHead(404);
                res.end('Not found');
                return;
            }
            res.writeHead(200, {'Content-Type': 'text/html'});
            res.end(data);
        });
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

const port = process.env.PORT || 8080;
server.listen(port, () => {
    console.log(`Server running on port ${port}`);
});
""")

        print("Testing s2i_multistage_build function...")
        print(f"Test app directory: {test_app_dir}")

        # Test parameters (using example images - these would need to be real images in actual use)
        app_path = str(test_app_dir)
        src_image = "registry.access.redhat.com/ubi8/nodejs-16"  # Builder image
        sec_image = "registry.access.redhat.com/ubi8/nodejs-16-minimal"  # Runtime image
        dst_image = "test-multistage-app:latest"
        s2i_args = "-e NODE_ENV=production"

        print(f"App path: {app_path}")
        print(f"Source image: {src_image}")
        print(f"Second stage image: {sec_image}")
        print(f"Destination image: {dst_image}")
        print(f"S2I args: {s2i_args}")

        # Call the migrated function
        result = ctl.s2i_multistage_build(
            app_path=app_path,
            src_image=src_image,
            sec_image=sec_image,
            dst_image=dst_image,
            s2i_args=s2i_args
        )

        if result:
            print("✅ s2i_multistage_build completed successfully!")
            print(f"Built image: {dst_image}")
        else:
            print("❌ s2i_multistage_build failed!")

        return result

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

    finally:
        # Clean up test directory
        if test_app_dir.exists():
            shutil.rmtree(test_app_dir)

        # Clean up container test library resources
        ctl.cleanup()


def main():
    """Main function to run the test."""
    print("=" * 60)
    print("Testing migrated ct_s2i_multistage_build function")
    print("=" * 60)

    success = test_s2i_multistage_build()

    print("=" * 60)
    if success:
        print("🎉 Migration test completed successfully!")
    else:
        print("💥 Migration test failed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
