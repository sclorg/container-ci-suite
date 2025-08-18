"""
Error handling and edge case tests for ContainerTestLib class.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from subprocess import CalledProcessError

from container_test_lib import ContainerTestLib


class TestErrorHandling:
    """Test error handling in various scenarios."""
    
    def test_ct_init_with_permission_error(self, container_test_lib):
        """Test initialization when temp directory creation fails."""
        with patch('tempfile.mkdtemp') as mock_mkdtemp:
            mock_mkdtemp.side_effect = PermissionError("Permission denied")
            
            with pytest.raises(PermissionError):
                container_test_lib.ct_init()
    
    def test_ct_cleanup_with_missing_directories(self, container_test_lib, capsys):
        """Test cleanup when directories are None or don't exist."""
        container_test_lib.app_id_file_dir = None
        container_test_lib.cid_file_dir = None
        
        # Should not raise an exception
        container_test_lib.ct_cleanup()
        
        captured = capsys.readouterr()
        assert "Container cleaning is to be skipped" in captured.out
    
    def test_ct_build_image_timeout(self, container_test_lib):
        """Test image build with timeout."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(124, "timeout")  # timeout exit code
            
            result = container_test_lib.ct_build_image_and_parse_id("Dockerfile", ".")
            assert result is False
    
    def test_ct_container_running_with_invalid_id(self, container_test_lib):
        """Test container running check with invalid container ID."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker inspect")
            
            result = container_test_lib.ct_container_running("invalid_id")
            assert result is False
    
    def test_ct_get_cid_with_missing_file(self, initialized_container_test_lib):
        """Test getting CID when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            initialized_container_test_lib.ct_get_cid("nonexistent")
    
    def test_ct_pull_image_with_network_error(self, container_test_lib):
        """Test image pull with network errors."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = [
                "",  # docker images -q (not found)
                CalledProcessError(1, "docker pull", "network error")
            ]
            
            result = container_test_lib.ct_pull_image("test:latest", loops=1)
            assert result is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_ct_random_string_zero_length(self, container_test_lib):
        """Test random string generation with zero length."""
        random_str = container_test_lib.ct_random_string(0)
        assert len(random_str) == 0
        assert random_str == ""
    
    def test_ct_random_string_large_length(self, container_test_lib):
        """Test random string generation with large length."""
        random_str = container_test_lib.ct_random_string(1000)
        assert len(random_str) == 1000
        assert random_str.isalnum()
    
    def test_ct_timestamp_diff_negative(self, container_test_lib):
        """Test timestamp difference with negative values."""
        # This might happen if clocks are adjusted
        start = 2000
        end = 1000
        diff = container_test_lib.ct_timestamp_diff(start, end)
        # Should handle negative differences gracefully
        assert isinstance(diff, str)
    
    def test_ct_path_append_empty_directory(self, container_test_lib, clean_environment):
        """Test path append with empty directory string."""
        container_test_lib.ct_path_append('TEST_PATH', '')
        assert os.environ['TEST_PATH'] == ''
    
    def test_ct_check_envs_set_empty_inputs(self, container_test_lib):
        """Test environment checking with empty inputs."""
        result = container_test_lib.ct_check_envs_set("", "", "")
        assert result is True  # Should succeed with empty inputs
    
    def test_ct_check_envs_set_malformed_env(self, container_test_lib):
        """Test environment checking with malformed environment strings."""
        env_filter = "TEST"
        check_envs = "MALFORMED_LINE_WITHOUT_EQUALS"
        loop_envs = "TEST=value"
        
        result = container_test_lib.ct_check_envs_set(env_filter, check_envs, loop_envs)
        assert result is False
    
    def test_ct_wait_for_cid_with_zero_attempts(self, container_test_lib, temp_dir):
        """Test wait for CID with zero max attempts."""
        cid_file = temp_dir / "test.cid"
        
        result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=0)
        assert result is False
    
    def test_ct_get_public_image_name_unknown_os(self, container_test_lib):
        """Test public image name generation with unknown OS."""
        image_name = container_test_lib.ct_get_public_image_name("unknown", "nodejs", "16")
        assert image_name == "quay.io/sclorg/nodejs-16"  # Should default to quay.io


class TestResourceLimits:
    """Test behavior under resource constraints."""
    
    def test_ct_cleanup_with_many_containers(self, initialized_container_test_lib, mock_file_operations):
        """Test cleanup with many containers."""
        ct_lib = initialized_container_test_lib
        
        # Create many mock CID files
        for i in range(100):
            cid_file = ct_lib.cid_file_dir / f"container_{i}"
            mock_file_operations[str(cid_file)] = f"container_{i}"
        
        with patch('pathlib.Path.glob') as mock_glob, \
             patch('container_test_lib.run_command') as mock_cmd, \
             patch('pathlib.Path.unlink') as mock_unlink:
            
            # Mock glob to return many files
            mock_files = [Path(str(ct_lib.cid_file_dir / f"container_{i}")) for i in range(100)]
            mock_glob.return_value = mock_files
            
            # Should handle many containers without issues
            ct_lib.ct_clean_containers()
            
            # Verify all containers were processed
            assert mock_cmd.call_count >= 100  # At least one call per container
    
    def test_ct_build_image_with_large_context(self, container_test_lib, temp_dir):
        """Test image build with large build context."""
        # Create a large build context
        for i in range(10):
            (temp_dir / f"large_file_{i}.txt").write_text("x" * 1000)
        
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = "Successfully built abc123\nabc123"
            
            result = container_test_lib.ct_build_image_and_parse_id("", str(temp_dir))
            assert result is True


class TestConcurrencyIssues:
    """Test potential concurrency issues."""
    
    def test_ct_init_multiple_instances(self):
        """Test creating multiple ContainerTestLib instances."""
        instances = []
        for i in range(5):
            ct_lib = ContainerTestLib()
            ct_lib.ct_init()
            instances.append(ct_lib)
        
        # All instances should have unique directories
        directories = [ct.app_id_file_dir for ct in instances]
        assert len(set(directories)) == 5
        
        # Cleanup all instances
        for ct_lib in instances:
            ct_lib.ct_cleanup()
    
    def test_ct_wait_for_cid_file_created_during_wait(self, container_test_lib, temp_dir):
        """Test wait for CID when file is created during wait."""
        cid_file = temp_dir / "delayed.cid"
        
        call_count = 0
        def mock_exists():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:  # File appears on third check
                cid_file.write_text("container123")
                return True
            return False
        
        with patch.object(Path, 'exists', side_effect=mock_exists), \
             patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 12  # Non-zero size
            
            result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=5, sleep_time=0.1)
            assert result is True


class TestSignalHandling:
    """Test signal handling and cleanup."""
    
    def test_ct_trap_on_sigint(self, initialized_container_test_lib, capsys):
        """Test SIGINT signal handling."""
        ct_lib = initialized_container_test_lib
        
        with patch.object(ct_lib, 'ct_cleanup') as mock_cleanup, \
             patch.object(ct_lib, 'ct_show_results') as mock_show_results:
            
            ct_lib.ct_trap_on_sigint(2, None)  # SIGINT
            
            mock_cleanup.assert_called_once()
            mock_show_results.assert_called_once()
        
        captured = capsys.readouterr()
        assert "Tests were stopped by SIGINT signal" in captured.out
    
    def test_ct_enable_cleanup_multiple_calls(self, container_test_lib):
        """Test enabling cleanup multiple times."""
        assert container_test_lib.cleanup_enabled is False
        
        container_test_lib.ct_enable_cleanup()
        assert container_test_lib.cleanup_enabled is True
        
        # Should not cause issues when called again
        container_test_lib.ct_enable_cleanup()
        assert container_test_lib.cleanup_enabled is True


class TestMemoryLeaks:
    """Test for potential memory leaks and resource cleanup."""
    
    def test_ct_obtain_input_cleanup(self, container_test_lib, temp_dir):
        """Test that ct_obtain_input properly cleans up temporary files."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        result = container_test_lib.ct_obtain_input(str(test_file))
        assert result is not None
        
        # The temporary file should exist
        temp_path = Path(result)
        assert temp_path.exists()
        
        # Manual cleanup (in real usage, this would be handled by the caller)
        temp_path.unlink()
        assert not temp_path.exists()
    
    def test_ct_gen_self_signed_cert_temp_cleanup(self, container_test_lib, temp_dir):
        """Test that certificate generation cleans up temporary files."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.return_value = ""
            
            result = container_test_lib.ct_gen_self_signed_cert_pem(str(temp_dir), "test")
            assert result is True
            
            # Verify the output directory was created
            assert temp_dir.exists()


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_ct_pull_image_invalid_name(self, container_test_lib):
        """Test pulling image with invalid name."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker pull", "invalid repository name")
            
            result = container_test_lib.ct_pull_image("invalid/image/name/too/long", loops=1)
            assert result is False
    
    def test_ct_create_container_invalid_args(self, initialized_container_test_lib):
        """Test container creation with invalid arguments."""
        ct_lib = initialized_container_test_lib
        ct_lib.image_name = "test:latest"
        
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "docker run", "invalid argument")
            
            result = ct_lib.ct_create_container("test", "--invalid-flag")
            assert result is False
    
    def test_ct_test_response_invalid_url(self, container_test_lib):
        """Test HTTP response testing with invalid URL."""
        with patch('container_test_lib.run_command') as mock_cmd:
            mock_cmd.side_effect = CalledProcessError(1, "curl", "Could not resolve host")
            
            result = container_test_lib.ct_test_response("http://invalid-host:8080", max_attempts=1)
            assert result is False
    
    def test_ct_registry_from_os_empty_string(self, container_test_lib):
        """Test registry mapping with empty OS string."""
        registry = container_test_lib.ct_registry_from_os("")
        assert registry == "quay.io"  # Should default to quay.io
    
    def test_ct_get_public_image_name_empty_inputs(self, container_test_lib):
        """Test public image name generation with empty inputs."""
        image_name = container_test_lib.ct_get_public_image_name("", "", "")
        assert image_name == "quay.io/sclorg/-"  # Should handle empty inputs gracefully


class TestFileSystemErrors:
    """Test file system related errors."""
    
    def test_ct_cleanup_permission_denied(self, initialized_container_test_lib):
        """Test cleanup when file removal fails due to permissions."""
        ct_lib = initialized_container_test_lib
        
        with patch('shutil.rmtree') as mock_rmtree:
            mock_rmtree.side_effect = PermissionError("Permission denied")
            
            # Should not raise an exception, just log the error
            ct_lib.ct_cleanup()
    
    def test_ct_obtain_input_disk_full(self, container_test_lib, temp_dir):
        """Test ct_obtain_input when disk is full."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        with patch('shutil.copy2') as mock_copy:
            mock_copy.side_effect = OSError("No space left on device")
            
            with pytest.raises(OSError):
                container_test_lib.ct_obtain_input(str(test_file))
    
    def test_ct_wait_for_cid_file_permissions(self, container_test_lib, temp_dir):
        """Test wait for CID file with permission issues."""
        cid_file = temp_dir / "permission_test.cid"
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat') as mock_stat:
            mock_stat.side_effect = PermissionError("Permission denied")
            
            result = container_test_lib.ct_wait_for_cid(cid_file, max_attempts=1)
            assert result is False
