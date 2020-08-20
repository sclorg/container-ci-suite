.PHONY: build-test test test-in-container clean

TEST_IMAGE_NAME = container-ci-suite-test

build-test:
	docker build --tag ${TEST_IMAGE_NAME} -f Dockerfile.tests .

test:
	cd tests && PYTHONPATH=$(CURDIR) pytest --color=yes --verbose --showlocals

test-in-container: build-test
	docker run --rm --net=host -e DEPLOYMENT=test ${TEST_IMAGE_NAME}

clean:
	find . -name '*.pyc' -delete
