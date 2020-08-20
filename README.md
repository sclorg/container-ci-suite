# container-ci-suite
This repos is used for testing SCL containers

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

ct_cleanup ... DONE
ct_enable_cleanup
ct_check_envs_set
ct_get_cip ... DONE
ct_get_cid ... DONE
ct_wait_for_cid ... DONE
ct_assert_container_creation_fails ... DONE
ct_create_container ... DONE
ct_scl_usage_old ... DONE - Does to exist in sclorg organization
ct_doc_content_old
full_ca_file_path ... DONE
ct_mount_ca_file ... DONE
ct_build_s2i_npm_variables ... DONE
ct_npm_works ... DONE
ct_binary_found_from_df ... DONE
ct_check_exec_env_vars
ct_check_scl_enable_vars
ct_path_append
ct_path_foreach
ct_run_test_list
ct_gen_self_signed_cert_pem
ct_obtain_input
ct_test_response
ct_registry_from_os ... DONE
ct_get_public_image_name ... DONE
ct_assert_cmd_success
ct_assert_cmd_failure
ct_random_string
ct_s2i_usage ... DONE
ct_s2i_build_as_df
ct_check_image_availability ... DONE
ct_check_latest_imagestreams
