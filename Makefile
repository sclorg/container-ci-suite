.PHONY: build-test test test-in-container clean help test-unit test-integration test-all install-test-deps clean test-coverage test-coverage-unit test-coverage-integration

# Default target
help:
	@echo "Container Test Library - Available targets:"
	@echo ""
	@echo "  install-test-deps       - Install test dependencies"
	@echo "  test-unit               - Run unit tests only (fast, no Docker required)"
	@echo "  test-integration        - Run integration tests (requires Docker)"
	@echo "  test-all                - Run all tests"
	@echo "  test-coverage           - Run all tests with coverage reporting"
	@echo "  test-coverage-unit      - Run unit tests with coverage (output: coverage-unit.xml)"
	@echo "  test-coverage-integration - Run integration tests with coverage (output: coverage-integration.xml)"
	@echo "  clean                   - Clean up test artifacts"
	@echo "  help                    - Show this help message"

TEST_IMAGE_NAME = container-ci-suite-test
UNAME=$(shell uname)
ifeq ($(UNAME),Darwin)
	PODMAN := /opt/podman/bin/podman #docker
else
	PODMAN := /usr/bin/podman
endif

build-test:
	$(PODMAN) build --tag ${TEST_IMAGE_NAME} -f Dockerfile.tests .

test:
	cd tests && PYTHONPATH=$(CURDIR) pytest --color=yes -v --showlocals

test-in-container: build-test
	$(PODMAN) run --rm --net=host -e DEPLOYMENT=test ${TEST_IMAGE_NAME}

# Install test dependencies
install-test-deps:
	@echo "📦 Installing test dependencies..."
	cd tests && pip3 install --user -r requirements-test.txt

# Run unit tests (fast, no Docker required)
test-unit:
	@echo "🚀 Running unit tests..."
	cd tests && python3 -m pytest -m "not integration" -v

# Run integration tests (requires Docker)
test-integration:
	@echo "🐳 Running integration tests (requires Docker)..."
	cd tests && python3 -m pytest -m integration -v

# Run all tests
test-all:
	@echo "🧪 Running all tests..."
	cd tests && python3 -m pytest -v


# Run tests with coverage
test-coverage:
	@echo "📊 Running tests with coverage..."
	cd tests && python3 -m pytest --cov=container_ci_suite --cov-report=html --cov-report=term-missing

# Run unit tests with coverage (for Codecov - unit-tests flag)
test-coverage-unit:
	@echo "📊 Running unit tests with coverage..."
	cd tests && PYTHONPATH=$(CURDIR) python3 -m pytest -m "not integration" --cov=container_ci_suite --cov-report=xml:../coverage-unit.xml --cov-report=term-missing

# Run integration tests with coverage (for Codecov - integration-tests flag)
test-coverage-integration:
	@echo "📊 Running integration tests with coverage..."
	cd tests && PYTHONPATH=$(CURDIR) python3 -m pytest -m integration --cov=container_ci_suite --cov-report=xml:../coverage-integration.xml --cov-report=term-missing

# Clean up test artifacts
clean:
	@echo "🧹 Cleaning up test artifacts..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f coverage-unit.xml coverage-integration.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
