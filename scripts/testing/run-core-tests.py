#!/usr/bin/env python3
"""
Run core tests for MicroVM Sandbox to verify basic functionality.
This script focuses on testing the most critical components.
"""

import subprocess
import sys
import os
from pathlib import Path

# Core test modules to run (excluding problematic ones for now)
CORE_TESTS = [
    "tests/unit/test_api_endpoints.py",
    "tests/unit/test_ch_client.py", 
    "tests/unit/test_config.py",
    "tests/unit/test_guest_client.py",
    "tests/unit/test_helpers.py",
    "tests/unit/test_network_manager.py",
    "tests/unit/test_resource_manager.py",
    "tests/unit/test_snapshot_manager.py",
    "tests/unit/test_vm_manager.py"
]

def run_test_module(test_path):
    """Run a specific test module and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {test_path}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_path, 
            "-v", 
            "--tb=short",
            "--no-header",
            "--disable-warnings"
        ], capture_output=True, text=True, timeout=120)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {test_path} took too long to run")
        return False
    except Exception as e:
        print(f"ERROR running {test_path}: {e}")
        return False

def run_quick_syntax_check():
    """Run a quick syntax check on core modules."""
    print("Running syntax checks...")
    
    core_modules = [
        "src/api/server.py",
        "src/core/vm_manager.py", 
        "src/core/ch_client.py",
        "src/utils/config.py"
    ]
    
    for module in core_modules:
        if os.path.exists(module):
            try:
                subprocess.run([sys.executable, "-m", "py_compile", module], 
                             check=True, capture_output=True)
                print(f"✓ {module}")
            except subprocess.CalledProcessError as e:
                print(f"✗ {module}: {e}")
                return False
        else:
            print(f"? {module}: File not found")
    
    return True

def main():
    """Run the core test suite."""
    print("MicroVM Sandbox Core Test Suite")
    print("="*60)
    
    # Change to project root
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    
    # Add project to Python path
    sys.path.insert(0, str(project_root))
    
    # Run syntax checks first
    if not run_quick_syntax_check():
        print("\nSyntax checks failed! Aborting test run.")
        return 1
    
    # Run core tests
    passed = 0
    failed = 0
    
    for test_path in CORE_TESTS:
        if os.path.exists(test_path):
            if run_test_module(test_path):
                passed += 1
                print(f"✓ {test_path} PASSED")
            else:
                failed += 1
                print(f"✗ {test_path} FAILED")
        else:
            print(f"? {test_path} NOT FOUND")
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All core tests PASSED!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())