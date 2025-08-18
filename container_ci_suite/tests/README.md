# Container Test Library - Test Suite

This directory contains a comprehensive pytest suite for the ContainerTestLib class.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest fixtures and configuration
├── test_container_test_lib.py  # Unit tests for core functionality
├── test_integration.py         # Integration tests requiring Docker
├── test_error_handling.py      # Error handling and edge cases
└── README.md                   # This file
```

## Test Categories

### Unit Tests (`test_container_test_lib.py`)
- **Fast execution** (no Docker required)
- **Mocked dependencies** for isolation
- **Core functionality testing**:
  - Initialization and setup
  - Utility functions
  - Registry and image name functions
  - Command assertions
  - Container operations (mocked)
  - Environment checking
  - File operations
  - Test result tracking

### Integration Tests (`test_integration.py`)
- **Requires Docker** to be available
- **Real container operations** (when possible)
- **Network access** for some tests
- **Comprehensive workflows**:
  - Complete container lifecycle
  - Image build and cleanup
  - S2I operations
  - Environment variable checking
  - HTTP response testing
  - NPM functionality
  - Documentation validation
  - Certificate generation
  - Test suite execution

### Error Handling Tests (`test_error_handling.py`)
- **Edge cases and boundary conditions**
- **Error scenarios and recovery**
- **Resource constraints**
- **Concurrency issues**
- **Signal handling**
- **Input validation**
- **File system errors**

## Running Tests

### Prerequisites

1. **Install test dependencies**:
   ```bash
   pip install -r requirements-test.txt
   ```

2. **For integration tests**, ensure Docker is installed and running:
   ```bash
   docker --version
   ```

### Quick Start

```bash
# Run all unit tests (fast, no Docker required)
python run_tests.py --type unit

# Run all tests including integration tests (requires Docker)
python run_tests.py --type all

# Run with coverage reporting
python run_tests.py --type unit --coverage

# Run specific test file
python run_tests.py --file tests/test_container_test_lib.py

# Run specific test function
python run_tests.py --function test_ct_init_creates_directories
```

### Using pytest directly

```bash
# Run unit tests only
pytest -m "not integration"

# Run integration tests only (requires Docker)
pytest -m integration

# Run with coverage
pytest --cov=container_test_lib --cov-report=html

# Run specific test
pytest tests/test_container_test_lib.py::TestContainerTestLibInit::test_init_creates_instance

# Run with verbose output
pytest -vv

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.integration` - Requires Docker
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.network` - Requires network access
- `@pytest.mark.unit` - Unit tests (default)

## Fixtures

### Core Fixtures (`conftest.py`)

- `container_test_lib` - Basic ContainerTestLib instance
- `initialized_container_test_lib` - Pre-initialized instance with cleanup
- `temp_dir` - Temporary directory for tests
- `clean_environment` - Clean environment variables

### Mocking Fixtures

- `mock_run_command` - Mock command execution
- `mock_podman_wrapper` - Mock container operations
- `mock_docker_commands` - Mock Docker command responses
- `mock_file_operations` - Mock file system operations

### Sample Data Fixtures

- `sample_dockerfile_content` - Example Dockerfile
- `sample_environment_vars` - Example environment variables

## Test Coverage

The test suite aims for comprehensive coverage of:

- ✅ **Core functionality** (95%+ coverage)
- ✅ **Error handling** (exception paths)
- ✅ **Edge cases** (boundary conditions)
- ✅ **Integration scenarios** (real Docker operations)
- ✅ **Utility functions** (all helper methods)
- ✅ **Signal handling** (cleanup on interruption)

### Coverage Reports

Generate HTML coverage reports:

```bash
pytest --cov=container_test_lib --cov-report=html
# Open htmlcov/index.html in browser
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Example Unit Test

```python
def test_new_functionality(container_test_lib, mock_run_command):
    """Test description."""
    # Arrange
    mock_run_command.return_value = "expected_output"
    
    # Act
    result = container_test_lib.new_method("input")
    
    # Assert
    assert result == "expected_result"
    mock_run_command.assert_called_once_with("expected_command")
```

### Example Integration Test

```python
@pytest.mark.integration
def test_real_docker_operation(initialized_container_test_lib):
    """Test real Docker operation."""
    ct_lib = initialized_container_test_lib
    
    # This test will only run if Docker is available
    result = ct_lib.ct_pull_image("hello-world:latest")
    assert result is True
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - run: pip install -r requirements-test.txt
      - run: pytest -m "not integration" --cov=container_test_lib

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - run: pip install -r requirements-test.txt
      - run: pytest -m integration
```

## Performance Considerations

### Fast Tests (Unit)
- Use mocks for external dependencies
- Avoid file system operations when possible
- Keep test data small
- Target < 1 second per test

### Slow Tests (Integration)
- Mark with `@pytest.mark.slow`
- Use real Docker operations sparingly
- Clean up resources properly
- Target < 30 seconds per test

## Debugging Tests

### Common Issues

1. **Import errors**: Check PYTHONPATH and module structure
2. **Mock issues**: Verify mock patch targets
3. **File permissions**: Ensure test directories are writable
4. **Docker issues**: Check Docker daemon status

### Debug Commands

```bash
# Run with debugging output
pytest -vv --tb=long

# Run specific failing test
pytest tests/test_file.py::test_function -vv

# Drop into debugger on failure
pytest --pdb

# Show print statements
pytest -s
```

## Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Follow AAA pattern** (Arrange, Act, Assert)
3. **One assertion per test** when possible
4. **Use fixtures** for common setup
5. **Mock external dependencies** in unit tests
6. **Clean up resources** in integration tests
7. **Test error conditions** not just happy paths
8. **Use markers** to categorize tests appropriately

## Contributing

When adding new functionality to ContainerTestLib:

1. **Write tests first** (TDD approach)
2. **Add both unit and integration tests**
3. **Test error conditions**
4. **Update fixtures** if needed
5. **Maintain test coverage** above 90%
6. **Run full test suite** before submitting
