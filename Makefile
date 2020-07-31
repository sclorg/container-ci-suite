.PHONY: prepare build build-generator build-test run run-generator test test-in-container clean send-master-sync send-pr-sync image-push deploy

TEST_IMAGE_NAME = container-ci-suite-test

build-test:
	docker build --tag ${TEST_IMAGE_NAME} -f Dockerfile.tests .

test:
	cd tests && PYTHONPATH=$(CURDIR) pytest --color=yes --verbose --showlocals

test-in-container: build-test
	docker run --rm --net=host -e DEPLOYMENT=test ${TEST_IMAGE_NAME}

clean:
	find . -name '*.pyc' -delete

