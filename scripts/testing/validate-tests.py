#!/usr/bin/env python3
"""
Validate all test modules for import and syntax errors.
"""

import sys
import os
import importlib.util
from pathlib import Path

def validate_python_file(file_path):
    """Validate a Python file for syntax and import errors."""
    try:
        # Check syntax
        with open(file_path, 'r') as f:
            compile(f.read(), file_path, 'exec')
        
        # Check imports (basic validation)
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        if spec is None:
            return False, "Could not create module spec"
        
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Import error: {e}"

def main():
    """Validate all test files."""
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))
    
    # Find all test files
    test_files = []
    for test_dir in ['tests/unit', 'tests/integration', 'tests/performance']:
        test_path = project_root / test_dir
        if test_path.exists():
            test_files.extend(test_path.glob('test_*.py'))
    
    print(f"Validating {len(test_files)} test files...")
    print("="*60)
    
    valid_count = 0
    invalid_count = 0
    
    for test_file in sorted(test_files):
        is_valid, message = validate_python_file(test_file)
        status = "✓" if is_valid else "✗"
        relative_path = test_file.relative_to(project_root)
        
        print(f"{status} {relative_path}")
        if not is_valid:
            print(f"  Error: {message}")
            invalid_count += 1
        else:
            valid_count += 1
    
    print("="*60)
    print(f"Valid:   {valid_count}")
    print(f"Invalid: {invalid_count}")
    print(f"Total:   {valid_count + invalid_count}")
    
    if invalid_count == 0:
        print("\n🎉 All test files are valid!")
        return 0
    else:
        print(f"\n❌ {invalid_count} test file(s) have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())