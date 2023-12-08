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
        self.hc_api = HelmChartsAPI(path=path, package_name=package_name, version="0.0.1")
    def test_package_imagestream(self):
        self.hc_api.helm_package()

```

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
