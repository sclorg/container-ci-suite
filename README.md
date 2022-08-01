# container-ci-suite

[![Run Tox tests on container-ci-suite](https://github.com/sclorg/container-ci-suite/actions/workflows/python-tests.yml/badge.svg)](https://github.com/sclorg/container-ci-suite/actions/workflows/python-tests.yml)


This repo is used for testing SCL containers. For container execution `docker` or `podman` commands are used.
No Python bidings. The same for OpenShift tests. `oc` command is used.

##  How to use Container CI Suite for testing containers

Install this suite by command:

```bash
pip3 install git+https://github.com/phracek/container-ci-suite
```

### Run a test with Container-CI-Suite

```python
import os

import pytest

from container_ci_suite.api import ContainerCISuite

image_name = os.environ.get("IMAGE_NAME", "nginx-container")
test_dir = os.path.abspath(os.path.dirname(__file__))


class TestDummyImage(object):
    def test_s2i_usage(self):
        ccs = ContainerCISuite(image_name=image_name)
        ccs.s2i_usage()

```

## container-common-scripts functions and arguments

* [x] ct_cleanup
* [ ] ct_enable_cleanup
* [x] ct_check_envs_set
* [x] ct_get_cip
* [x] ct_get_cid
* [x] ct_wait_for_cid
* [x] ct_assert_container_creation_fails
* [x] ct_create_container
* [x] ct_scl_usage_old
* [ ] ct_doc_content_old
* [x] full_ca_file_path
* [x] ct_mount_ca_file
* [x] ct_build_s2i_npm_variables
* [x] ct_npm_works
* [x] ct_binary_found_from_df
* [ ] ct_check_exec_env_vars
* [ ] ct_check_scl_enable_vars
* [ ] ct_path_append
* [ ] ct_path_foreach
* [ ] ct_run_test_list
* [ ] ct_gen_self_signed_cert_pem
* [ ] ct_obtain_input
* [ ] ct_test_response
* [x] ct_registry_from_os
* [x] ct_get_public_image_name
* [ ] ct_assert_cmd_success
* [ ] ct_assert_cmd_failure
* [ ] ct_random_string
* [x] ct_s2i_usage
* [ ] ct_s2i_build_as_df
* [x] ct_check_image_availability
* [ ] ct_check_latest_imagestreams
* [ ] ct_test_app_dockerfile
* [ ] ct_get_uid_from_image
* [ ] ct_clone_git_repository
* [ ] ct_show_resources
* [ ] ct_s2i_multistage_build


## OpenShift tests

* [ ] ct_os_cleanup
* [ ] ct_os_check_compulsory_vars
* [ ] ct_os_get_status
* [ ] ct_os_print_logs
* [ ] ct_os_enable_print_logs
* [ ] ct_get_public_ip
* [ ] ct_os_run_in_pod
* [ ] ct_os_get_service_ip
* [ ] ct_os_get_all_pods_status
* [ ] ct_os_get_all_pods_name
* [ ] ct_os_get_pod_status
* [ ] ct_os_get_build_pod_status
* [ ] ct_os_get_buildconfig_pod_name
* [ ] ct_os_get_pod_name
* [ ] ct_os_get_pod_ip
* [ ] ct_os_get_sti_build_logs
* [ ] ct_os_check_pod_readiness
* [ ] ct_os_wait_pod_ready
* [ ] ct_os_wait_rc_ready
* [ ] ct_os_deploy_pure_image
* [ ] ct_os_deploy_s2i_image
* [ ] ct_os_deploy_template_image
* [ ] _ct_os_get_uniq_project_name
* [ ] ct_os_new_project
* [ ] ct_os_delete_project
* [ ] ct_delete_all_objects
* [ ] ct_os_docker_login
* [ ] ct_os_upload_image
* [ ] ct_os_is_tag_exists
* [ ] ct_os_template_exists
* [ ] ct_os_install_in_centos
* [ ] ct_os_cluster_up
* [ ] ct_os_cluster_down
* [ ] ct_os_cluster_running
* [ ] ct_os_logged_in
* [ ] ct_os_set_path_oc
* [ ] ct_os_get_latest_ver
* [ ] ct_os_download_upstream_oc
* [ ] ct_os_test_s2i_app_func
* [ ] ct_os_test_s2i_app
* [ ] ct_os_test_template_app_func
* [ ] ct_os_test_template_app
* [ ] ct_os_test_image_update
* [ ] ct_os_deploy_cmd_image
* [ ] ct_os_cmd_image_run
* [ ] ct_os_test_response_internal
* [ ] ct_os_get_image_from_pod
* [ ] ct_os_check_cmd_internal
* [ ] ct_os_test_image_stream_template
* [ ] ct_os_wait_stream_ready
* [ ] ct_os_test_image_stream_s2i
* [ ] ct_os_test_image_stream_quickstart
* [ ] ct_os_service_image_info
