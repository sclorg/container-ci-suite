# container-ci-suite

[![Run Tox tests on container-ci-suite](https://github.com/sclorg/container-ci-suite/actions/workflows/python-tests.yml/badge.svg)](https://github.com/sclorg/container-ci-suite/actions/workflows/python-tests.yml)


This repo is used for testing SCL containers. For container execution `docker` or `podman` commands are used.
No Python bidings. The same for OpenShift tests. `oc` command is used.

##  How to use Container CI Suite for testing containers

Install this suite from PyPi:

```bash
pip3 install container-ci-suite
```

Install this suite from GitHub repository:

```bash
pip3 install git+https://github.com/sclorg/container-ci-suite
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
