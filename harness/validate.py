#!/usr/bin/env python3
"""Standalone harness validation for Sanjuk-Notion-Telegram-Bot."""

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

SECRET_PATTERNS = [
    re.compile(r'sk-ant-[a-zA-Z0-9_-]{20,}'),
    re.compile(r'sk-proj-[a-zA-Z0-9_-]{20,}'),
    re.compile(r'API_KEY\s*=\s*["\'][a-zA-Z0-9_-]{10,}["\']'),
]

REQUIRED_FILES = [
    "CLAUDE.md",
    "shared_config.py",
    "Chat_bot/chat_bot.py",
    "Chat_bot/requirements.txt",
]

REQUIRED_DIRS = ["Chat_bot", "GameNews_bot", "Luck_bot", "scripts", "tests"]


def check_required_files():
    """Check that required files exist."""
    missing = [f for f in REQUIRED_FILES if not (PROJECT_ROOT / f).exists()]
    return missing


def check_required_dirs():
    """Check that required directories exist."""
    missing = [d for d in REQUIRED_DIRS if not (PROJECT_ROOT / d).exists()]
    return missing


def check_python_syntax():
    """Verify all Python files have valid syntax."""
    errors = []
    for py_file in PROJECT_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            ast.parse(source)
        except SyntaxError as e:
            errors.append(f"{py_file.relative_to(PROJECT_ROOT)}: {e}")
    return errors


def check_no_secrets():
    """Scan for hardcoded secrets."""
    violations = []
    for py_file in PROJECT_ROOT.rglob("*.py"):
        if "test_" in py_file.name or "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.findall(content):
                violations.append(str(py_file.relative_to(PROJECT_ROOT)))
    return violations


def main():
    """Run all validations."""
    passed = 0
    failed = 0

    # Required files
    missing_files = check_required_files()
    if missing_files:
        print(f"FAIL: Missing files: {missing_files}")
        failed += 1
    else:
        print(f"PASS: All {len(REQUIRED_FILES)} required files exist")
        passed += 1

    # Required dirs
    missing_dirs = check_required_dirs()
    if missing_dirs:
        print(f"FAIL: Missing directories: {missing_dirs}")
        failed += 1
    else:
        print(f"PASS: All {len(REQUIRED_DIRS)} required directories exist")
        passed += 1

    # Python syntax
    syntax_errors = check_python_syntax()
    if syntax_errors:
        print(f"FAIL: Syntax errors: {syntax_errors}")
        failed += 1
    else:
        print("PASS: All Python files have valid syntax")
        passed += 1

    # Secrets
    secrets = check_no_secrets()
    if secrets:
        print(f"FAIL: Possible secrets in: {secrets}")
        failed += 1
    else:
        print("PASS: No hardcoded secrets detected")
        passed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
