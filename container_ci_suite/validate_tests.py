#!/usr/bin/env python3

"""
Simple test validation script for Container Test Library.
This script validates the test structure without requiring pytest installation.
"""

import sys
import ast
import importlib.util
from pathlib import Path


def validate_test_file(file_path):
    """Validate a test file for basic structure."""
    print(f"Validating {file_path.name}...")
    
    try:
        # Parse the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Count test functions and classes
        test_functions = 0
        test_classes = 0
        imports = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                test_functions += 1
            elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                test_classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports += 1
        
        print(f"  ✅ Parsed successfully")
        print(f"  📊 Test classes: {test_classes}")
        print(f"  📊 Test functions: {test_functions}")
        print(f"  📊 Import statements: {imports}")
        
        # conftest.py is special - it contains fixtures, not tests
        if test_functions == 0 and test_classes == 0 and not file_path.name == "conftest.py":
            print(f"  ⚠️  No test functions or classes found")
            return False
        elif file_path.name == "conftest.py":
            print(f"  ✅ Configuration file (fixtures and setup)")
        
        # Check for pytest fixtures in conftest.py
        if file_path.name == "conftest.py":
            fixture_count = content.count("@pytest.fixture")
            print(f"  📊 Pytest fixtures: {fixture_count}")
        
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def validate_imports():
    """Validate that the main module can be imported."""
    print("Validating imports...")
    
    try:
        # Add current directory to path
        sys.path.insert(0, str(Path.cwd()))
        
        # Try to import the main module
        from container_test_lib import ContainerTestLib
        print("  ✅ ContainerTestLib imported successfully")
        
        # Test basic instantiation
        ct_lib = ContainerTestLib()
        print("  ✅ ContainerTestLib instantiated successfully")
        
        # Test a simple method
        random_str = ct_lib.ct_random_string(5)
        print(f"  ✅ Basic method call successful: {random_str}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        return False


def validate_test_structure():
    """Validate the overall test structure."""
    print("Validating test structure...")
    
    tests_dir = Path("tests")
    if not tests_dir.exists():
        print("  ❌ tests/ directory not found")
        return False
    
    print("  ✅ tests/ directory exists")
    
    # Check for required files
    required_files = [
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/test_container_test_lib.py",
        "tests/test_integration.py",
        "tests/test_error_handling.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"  ❌ Missing files: {', '.join(missing_files)}")
        return False
    
    print("  ✅ All required test files exist")
    
    # Check for configuration files
    config_files = ["pytest.ini", "requirements-test.txt"]
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"  ✅ {config_file} exists")
        else:
            print(f"  ⚠️  {config_file} not found")
    
    return True


def main():
    """Main validation function."""
    print("🧪 Container Test Library - Test Validation")
    print("=" * 50)
    
    all_valid = True
    
    # Validate imports
    if not validate_imports():
        all_valid = False
    
    print()
    
    # Validate test structure
    if not validate_test_structure():
        all_valid = False
    
    print()
    
    # Validate individual test files
    test_files = [
        Path("tests/test_container_test_lib.py"),
        Path("tests/test_integration.py"),
        Path("tests/test_error_handling.py"),
        Path("tests/conftest.py")
    ]
    
    for test_file in test_files:
        if test_file.exists():
            if not validate_test_file(test_file):
                all_valid = False
        else:
            print(f"❌ {test_file} not found")
            all_valid = False
        print()
    
    # Summary
    print("=" * 50)
    if all_valid:
        print("🎉 All validations passed!")
        print("📋 Test suite is ready to run with pytest")
        print("💡 Install pytest with: pip install pytest")
        print("🚀 Run tests with: pytest tests/")
    else:
        print("❌ Some validations failed!")
        print("🔧 Please fix the issues above before running tests")
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
