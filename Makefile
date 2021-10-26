.PHONY: build-test test test-in-container clean

TEST_IMAGE_NAME = container-ci-suite-test
UNAME=$(shell uname)
ifeq ($(UNAME),Darwin)
	PODMAN := /usr/local/bin/docker
else
	PODMAN := /usr/bin/podman
endif

build-test:
	$(PODMAN) build --tag ${TEST_IMAGE_NAME} -f Dockerfile.tests .

test:
	cd tests && PYTHONPATH=$(CURDIR) pytest --color=yes -v --showlocals

test-in-container: build-test
	$(PODMAN) run --rm --net=host -e DEPLOYMENT=test ${TEST_IMAGE_NAME}

clean:
	find . -name '*.pyc' -delete
