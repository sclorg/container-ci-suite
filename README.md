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

from container_ci_suite.container import ContainerAPI

image_name = os.environ.get("IMAGE_NAME", "nginx-container")
test_dir = os.path.abspath(os.path.dirname(__file__))


class TestDummyImage(object):
    def test_s2i_usage(self):
        ccs = ContainerAPI(image_name=image_name)
        ccs.s2i_usage()

```

### Run a test with Container-CI-Suite for Example repositories

```python
import os

import pytest

from container_ci_suite.openshift import OpenShiftAPI

test_dir = os.path.abspath(os.path.dirname(__file__))

IS_RUBY = OpenShiftAPI.get_raw_url_for_json(container="s2i-ruby-container", dir="imagestreams", filename="ruby-rhel.json")
IS_POSTGRESQL = OpenShiftAPI.get_raw_url_for_json(container="postgresql-container", dir="imagestreams", filename="postgresql-rhel.json")
TEMPLATE_RAILS_POSTGRESQL = OpenShiftAPI.get_raw_url_for_json(container="s2i-ruby-container", dir="examples", filename="rails-postgresql-persistent.json")

class TestRubyEx:
    def setup_method(self):
        self.oc_api = OpenShiftAPI(namespace="test-ruby-ex")

    # Reference https://github.com/sclorg/s2i-nodejs-container/blob/master/test/test-lib-nodejs.sh#L561 (ct_os_test_template_app_func)
    def test_deployment_template(self):
        self.oc_api.create(IS_RUBY)
        self.oc_api.create(IS_POSTGRESQL)
        assert self.oc_api.check_is_exists(is_name="ruby", version_to_check="2.5-ubi8")
        assert self.oc_api.check_is_exists(is_name="postgresql", version_to_check="10-el8")
        self.oc_api.process_file(TEMPLATE_RAILS_POSTGRESQL)
        self.oc_api.new_app(image_name="ruby:2.5-ubi8", github_repo="https://github.com/sclorg/ruby-ex")
        self.oc_api.is_pod_ready(pod_name="")
        self.oc_api.ct_os_check_service_image_info()
        #oc process -f rails-postgresql.json -p NAMESPACE=$(oc project -q) | oc create -f -

    # Reference https://github.com/sclorg/s2i-nodejs-container/blob/master/test/test-lib-nodejs.sh#L554 (ct_os_test_s2i_app_func)
    # ct_os_deploy_s2i_image
    def test_s2i_app_func(self):
        self.oc_api.create(IS_RUBY)
        self.oc_api.create(IS_POSTGRESQL)
        assert self.oc_api.check_is_exists(is_name="ruby", version_to_check="2.5-ubi8")
        assert self.oc_api.check_is_exists(is_name="postgresql", version_to_check="10-el8")
        self.oc_api.process_file(TEMPLATE_RAILS_POSTGRESQL)
        self.oc_api.new_app("ruby-ex-tests/ruby:2.5-ubi8~https://github.com/sclorg/ruby-ex")
        self.oc_api.start-build() # service-name, --from-dir
        self.oc_api.is_pod_ready()
        self.oc_api.ct_os_check_service_image_info()
        #oc process -f rails-postgresql.json -p NAMESPACE=$(oc project -q) | oc create -f -

    # Reference https://github.com/sclorg/s2i-nodejs-container/blob/master/test/test-lib-nodejs.sh#L533 (ct_os_test_image_stream_quickstart)
    # ct_os_deploy_s2i_image
    def test_iamgestream_quicstart(self):
        self.oc_api.create(IS_RUBY)
        self.oc_api.create(IS_POSTGRESQL)
        assert self.oc_api.check_is_exists(is_name="ruby", version_to_check="2.5-ubi8")
        assert self.oc_api.check_is_exists(is_name="postgresql", version_to_check="10-el8")
        self.oc_api.process_file(TEMPLATE_RAILS_POSTGRESQL)
        self.oc_api.create()
        self.oc_api.ct_os_test_template_app("ruby-ex-tests/ruby:2.5-ubi8~https://github.com/sclorg/ruby-ex")
        self.oc_api.start-build() # service-name, --from-dir
        self.oc_api.is_pod_ready()
        self.oc_api.ct_os_check_service_image_info()
        #oc process -f rails-postgresql.json -p NAMESPACE=$(oc project -q) | oc create -f -

```

## Run a test with Container-CI-Suite for Helm charts

```python
import os

import pytest

from container_ci_suite.helm import HelmChartsAPI

test_dir = os.path.abspath(os.path.dirname(__file__))


class TestHelmPostgresqlImageStreams:
    def setup_method(self):
        package_name = "postgresql-imagestreams"
        path = os.path.join(test_dir, "../charts/redhat", package_name)
        self.hc_api = HelmChartsAPI(path=path, package_name=package_name)
    def test_package_imagestream(self):
        self.hc_api.helm_package()

```

## Container functions onboarding

- [] ct_init - call `ct_enable_cleanup`, creates temp dir for app_id and cid_files
- [] ct_cleanup - call `ct_clean_app_images`, and `ct_clean_container`
- [] ct_build_image_and_parse_id -
- [x] ct_container_running - ContainerCISuite.is_container_running - used for cleaning containers only
- [x] ct_container_exists - ContainerCISuite.is_container_exists - used for cleaning containers only
- [] ct_clean_app_images
- [x] ct_clean_containers - ContainerCISuite.cleanup_container
- [] ct_show_results
- [] ct_enable_cleanup
- [] ct_trap_on_exit
- [] ct_trap_on_sigint
- [x] ct_pull_image - PodmanCLIWrapper.docker_pull_image
- [] ct_check_envs_set
- [] ct_get_cid
- [x] ct_get_cip - ContainerCISuite.get_cip
- [x] ct_wait_for_cid - ContainerCISuite.wait_for_cid
- [x] ct_assert_container_creation_fails - ContainerCISuite.assert_container_fails
- [x] ct_create_container - ContainerCISuite.create_container
- [] ct_scl_usage_old
- [] ct_doc_content_old
- [x] full_ca_file_path - utils.get_full_ca_file_path
- [x] ct_mount_ca_file - utils.get_mount_ca_file
- [x] ct_build_s2i_npm_variables - utils.get_npm_variables
- [x] ct_npm_works - ContainerCISuite.npm_works
- [x] ct_binary_found_from_df - ContainerCISuite.binary_found_from_df
- [x] ct_check_exec_env_vars - ContainerCISuite.test_check_exec_env_vars
- [x] ct_check_scl_enable_vars - ContainerCISuite.test_check_envs_set
- [] ct_path_append
- [] ct_path_foreach
- [] ct_gen_self_signed_cert_pem
- [] ct_obtain_input -
- [x] ct_test_response - UPDATE NEEDED utils.get_response_request
- [x] ct_registry_from_os - utils.get_registry_name
- [x] ct_get_public_image_name - utils.get_public_image_name
- [] ct_assert_cmd_success
- [] ct_assert_cmd_failure
- [] ct_random_string
- [x] ct_s2i_usage - ContainerCISuite.s2i_usage
- [x] ct_s2i_build_as_df - ContainerCISuite.s2i_build_as_df
- [x] ct_s2i_build_as_df_build_args - ContainerCISuite.s2i_create_df
- [] ct_s2i_multistage_build
- [x] ct_check_image_availability - ContainerCISuite.check_image_availability
- [] ct_show_resources
- [] ct_clone_git_repository
- [] ct_get_uid_from_image
- [] ct_test_app_dockerfile
- [] ct_check_testcase_result
- [] ct_update_test_result
- [] ct_run_tests_from_testset
- [] ct_timestamp_s
- [] ct_timestamp_pretty
- [] ct_timestamp_diff
- [] ct_get_certificate_timestamp
- [] ct_get_certificate_age_s
- [] ct_get_image_age_s
- [] ct_get_image_size_uncompresseed
- [] ct_get_image_size_compresseed
