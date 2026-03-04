"""
Unit tests for build_as_df_build_args and related functions.
"""

from pathlib import Path
from unittest.mock import patch
from subprocess import CalledProcessError

from container_ci_suite.container_lib import ContainerTestLib


class TestBuildAsDfBuildArgs:
    """Test build_as_df_build_args function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_as_df_build_args_success(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test build_as_df_build_args when build succeeds."""
        (temp_dir / "package.json").write_text('{"name": "test"}')
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = ""
        mock_get_uid.return_value = "1001"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        with patch.object(self.lib, "random_string", return_value="testid123"):
            result = self.lib.build_as_df_build_args(
                app_path=temp_dir,
                src_image="quay.io/fedora/nodejs-16",
                dst_image="test-app:latest",
                build_args="",
                s2i_args="",
            )

        assert result is not None
        assert isinstance(result, ContainerTestLib)
        assert result.image_name == "test-app:latest"
        assert result.s2i_image is True
        mock_build.assert_called_once()

    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_build_as_df_build_args_source_path_not_exists(
        self, mock_podman, mock_get_uid
    ):
        """Test build_as_df_build_args when app_path does not exist."""
        mock_podman.return_value = ""

        result = self.lib.build_as_df_build_args(
            app_path=Path("/nonexistent/app/path"),
            src_image="quay.io/fedora/nodejs-16",
            dst_image="test-app:latest",
        )

        assert result is False

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_as_df_build_args_get_uid_fails(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test build_as_df_build_args when get_uid_from_image returns None."""
        (temp_dir / "file.txt").write_text("content")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = ""
        mock_get_uid.return_value = None

        result = self.lib.build_as_df_build_args(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-16",
            dst_image="test-app:latest",
        )

        assert result is False
        mock_build.assert_not_called()

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_as_df_build_args_build_fails(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test build_as_df_build_args when build_image_and_parse_id returns False."""
        (temp_dir / "file.txt").write_text("content")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = ""
        mock_get_uid.return_value = "1001"
        mock_build.return_value = False

        result = self.lib.build_as_df_build_args(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-16",
            dst_image="test-app:latest",
        )

        assert result is None

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_as_df_build_args_with_build_args(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test build_as_df_build_args with build_args parameter."""
        (temp_dir / "package.json").write_text('{"name": "test"}')
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = ""
        mock_get_uid.return_value = "1001"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        with patch.object(self.lib, "random_string", return_value="testid456"):
            result = self.lib.build_as_df_build_args(
                app_path=temp_dir,
                src_image="quay.io/fedora/nodejs-16",
                dst_image="test-app:latest",
                build_args="--build-arg NODE_ENV=production",
                s2i_args="",
            )

        assert result is not None
        call_args = mock_build.call_args
        assert "NODE_ENV=production" in str(call_args)

    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_build_as_df_build_args_pull_fails(
        self, mock_podman, mock_get_uid, temp_dir
    ):
        """Test build_as_df_build_args when image pull fails."""
        (temp_dir / "file.txt").write_text("content")
        mock_podman.side_effect = [
            CalledProcessError(1, "podman images", "not found"),
            CalledProcessError(1, "podman pull", "pull failed"),
        ]

        result = self.lib.build_as_df_build_args(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-16",
            dst_image="test-app:latest",
        )

        assert result is False

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_build_as_df_build_args_with_s2i_env_args(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test build_as_df_build_args with s2i_args containing env vars."""
        (temp_dir / "app.js").write_text("console.log('hello')")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = ""
        mock_get_uid.return_value = "1001"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        with patch.object(self.lib, "random_string", return_value="testid789"):
            result = self.lib.build_as_df_build_args(
                app_path=temp_dir,
                src_image="quay.io/fedora/nodejs-16",
                dst_image="test-app:latest",
                build_args="",
                s2i_args="-e NODE_ENV=production",
            )

        assert result is not None

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_as_df_build_args")
    def test_build_as_df_delegates_to_build_args(self, mock_build_args, temp_dir):
        """Test build_as_df delegates to build_as_df_build_args with empty build_args."""
        (temp_dir / "app.js").write_text("")
        mock_build_args.return_value = ContainerTestLib("test:latest", s2i_image=True)

        result = self.lib.build_as_df(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-16",
            dst_image="test-app:latest",
            s2i_args="-e FOO=bar",
        )

        assert result is not None
        mock_build_args.assert_called_once_with(
            temp_dir, "quay.io/fedora/nodejs-16", "test-app:latest", "", "-e FOO=bar"
        )


class TestMultistageBuild:
    """Test multistage_build function."""

    def setup_method(self):
        self.lib = ContainerTestLib()

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_multistage_build_success(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test multistage_build when build succeeds."""
        (temp_dir / "app.js").write_text("console.log('hello')")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = "1001"
        mock_get_uid.return_value = "1001"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        result = self.lib.multistage_build(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
            s2i_args="",
        )

        assert result is True
        mock_build.assert_called_once()

    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    def test_multistage_build_get_uid_returns_none(
        self, mock_podman, mock_get_uid, temp_dir
    ):
        """Test multistage_build when get_uid_from_image returns None."""
        (temp_dir / "app.js").write_text("content")
        mock_podman.return_value = "1001"
        mock_get_uid.return_value = None

        result = self.lib.multistage_build(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
        )

        assert result is False

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_multistage_build_fails(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test multistage_build when build_image_and_parse_id returns False."""
        (temp_dir / "app.js").write_text("content")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = "1001"
        mock_get_uid.return_value = "1001"
        mock_build.return_value = False

        result = self.lib.multistage_build(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
        )

        assert result is False

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_multistage_build_podman_inspect_fails_uses_default_user(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test multistage_build uses user 0 when podman inspect raises."""
        (temp_dir / "app.js").write_text("content")
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.side_effect = CalledProcessError(1, "podman", "inspect failed")
        mock_get_uid.return_value = "0"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        result = self.lib.multistage_build(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
        )

        assert result is True
        mock_get_uid.assert_called_once_with("0", "quay.io/fedora/nodejs-20")

    @patch("container_ci_suite.container_lib.utils.clone_git_repository")
    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_multistage_build_git_clone_fails(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, mock_clone, temp_dir
    ):
        """Test multistage_build when app_path does not exist and git clone fails."""
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = "1001"
        mock_get_uid.return_value = "1001"
        mock_clone.return_value = False

        result = self.lib.multistage_build(
            app_path=Path("/nonexistent/git/repo"),
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
        )

        assert result is False
        mock_build.assert_not_called()

    @patch("container_ci_suite.container_lib.ContainerTestLib.build_image_and_parse_id")
    @patch("container_ci_suite.container_lib.ContainerTestLib.get_uid_from_image")
    @patch("container_ci_suite.container_lib.PodmanCLIWrapper.call_podman_command")
    @patch("container_ci_suite.container_lib.get_full_ca_file_path")
    def test_multistage_build_with_s2i_args(
        self, mock_ca_path, mock_podman, mock_get_uid, mock_build, temp_dir
    ):
        """Test multistage_build with s2i_args parameter."""
        (temp_dir / "package.json").write_text('{"name": "test"}')
        mock_ca_path.return_value = Path("/nonexistent")
        mock_podman.return_value = "1001"
        mock_get_uid.return_value = "1001"
        mock_build.return_value = True
        self.lib.app_image_id = "sha256:abc123"

        result = self.lib.multistage_build(
            app_path=temp_dir,
            src_image="quay.io/fedora/nodejs-20",
            sec_image="quay.io/fedora/nodejs-20-minimal",
            dst_image="test-app:latest",
            s2i_args="-e NODE_ENV=production",
        )

        assert result is True
        mock_build.assert_called_once()
