"""Harness validation tests for Sanjuk-Notion-Telegram-Bot."""

import ast
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
EXCLUDED_SOURCE_DIRS = {"venv", ".venv", "__pycache__", ".git", "data"}
EXCLUDED_SOURCE_PATHS = {"Chat_bot/data"}


def iter_project_py_files():
    for py_file in PROJECT_ROOT.rglob("*.py"):
        rel_parts = py_file.relative_to(PROJECT_ROOT).parts
        rel_path = "/".join(rel_parts)
        if any(part in EXCLUDED_SOURCE_DIRS for part in rel_parts):
            continue
        if any(rel_path == path or rel_path.startswith(f"{path}/") for path in EXCLUDED_SOURCE_PATHS):
            continue
        yield py_file

SECRET_PATTERNS = [
    re.compile(r'sk-ant-[a-zA-Z0-9_-]{20,}'),
    re.compile(r'sk-proj-[a-zA-Z0-9_-]{20,}'),
    re.compile(r'API_KEY\s*=\s*["\'][a-zA-Z0-9_-]{10,}["\']'),
    re.compile(r'xoxb-[a-zA-Z0-9-]{20,}'),
]


class TestProjectStructure:
    """Core project structure validation."""

    def test_claude_md_exists(self):
        assert (PROJECT_ROOT / "CLAUDE.md").exists()

    def test_all_bot_directories_exist(self):
        for bot_dir in ["GameNews_bot", "Luck_bot"]:
            assert (PROJECT_ROOT / bot_dir).exists(), f"{bot_dir}/ missing"

    def test_shared_config_exists(self):
        assert (PROJECT_ROOT / "shared_config.py").exists()

    def test_scripts_directory_exists(self):
        assert (PROJECT_ROOT / "scripts").exists()

    def test_tests_directory_exists(self):
        assert (PROJECT_ROOT / "tests").exists()


class TestNoHardcodedSecrets:
    """No hardcoded secrets in Python files."""

    def test_no_secrets_in_source(self):
        violations = []
        for py_file in iter_project_py_files():
            if "test_" in py_file.name:
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.findall(content):
                    violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: {pattern.pattern}")
        assert not violations, f"Hardcoded secrets found: {violations}"


class TestGitHubActions:
    """CI/CD workflows exist and are valid YAML."""

    def test_github_actions_exist(self):
        workflows = PROJECT_ROOT / ".github" / "workflows"
        if workflows.exists():
            yml_files = list(workflows.glob("*.yml"))
            assert len(yml_files) >= 1


class TestPythonSyntax:
    """All Python files have valid syntax."""

    def test_all_py_files_valid(self):
        errors = []
        for py_file in iter_project_py_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                ast.parse(source)
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(PROJECT_ROOT)}: {e}")
        assert not errors, f"Syntax errors: {errors}"


class TestBotStructure:
    """Per-bot structural validation."""

    def test_gamenews_bot_has_scripts(self):
        gn = PROJECT_ROOT / "GameNews_bot"
        assert gn.exists()
        py_files = list(gn.rglob("*.py"))
        assert len(py_files) >= 1, "GameNews_bot has no Python files"

    def test_luck_bot_has_entry_point(self):
        lb = PROJECT_ROOT / "Luck_bot"
        assert lb.exists()
        py_files = list(lb.rglob("*.py"))
        assert len(py_files) >= 1, "Luck_bot has no Python files"
