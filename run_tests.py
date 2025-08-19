#!/usr/bin/env python3

"""
Test runner script for Container Test Library.

This script provides different ways to run the test suite:
- Unit tests only (fast, no Docker required)
- Integration tests (requires Docker)
- All tests
- Specific test categories
"""

import sys
import subprocess
import argparse


def run_command(cmd, description=""):
    """Run a command and handle errors."""
    print(f"Running: {' '.join(cmd)}")
    if description:
        print(f"Description: {description}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Success")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Failed")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def check_pytest_available():
    """Check if pytest is available."""
    try:
        subprocess.run(["pytest", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_docker_available():
    """Check if Docker is available."""
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Container Test Library tests")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "all", "fast"],
        default="unit",
        help="Type of tests to run (default: unit)"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--parallel", "-n",
        type=int,
        help="Number of parallel processes (requires pytest-xdist)"
    )
    parser.add_argument(
        "--file",
        help="Run specific test file"
    )
    parser.add_argument(
        "--function",
        help="Run specific test function"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not check_pytest_available():
        print("❌ pytest is not available. Install it with: pip install pytest")
        sys.exit(1)

    if args.type in ["integration", "all"] and not check_docker_available():
        print("❌ Docker is not available but required for integration tests")
        print("Either install Docker or run with --type unit")
        sys.exit(1)

    # Build pytest command
    cmd = ["pytest"]

    # Test selection
    if args.type == "unit":
        cmd.extend(["-m", "not integration"])
    elif args.type == "integration":
        cmd.extend(["-m", "integration"])
    elif args.type == "fast":
        cmd.extend(["-m", "not slow and not integration"])
    # "all" runs everything, no marker filter needed

    # Coverage
    if args.coverage:
        cmd.extend([
            "--cov=container_test_lib",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])

    # Verbosity
    if args.verbose:
        cmd.append("-vv")

    # Parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Specific file or function
    if args.file:
        if args.function:
            cmd.append(f"{args.file}::{args.function}")
        else:
            cmd.append(args.file)
    elif args.function:
        cmd.extend(["-k", args.function])

    # Run the tests
    description = f"Running {args.type} tests"
    if args.coverage:
        description += " with coverage"

    success = run_command(cmd, description)

    if success:
        print("\n🎉 All tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
