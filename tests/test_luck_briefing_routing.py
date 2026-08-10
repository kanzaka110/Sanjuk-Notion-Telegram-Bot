import ast
from pathlib import Path


def _function(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def test_luck_scheduler_owns_private_session_but_commands_do_not():
    path = Path(__file__).parents[1] / "Luck_bot" / "luck_bot.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scheduled = ast.dump(_function(tree, "scheduled_daily"), include_attributes=False)
    assert "briefing_model_session" in scheduled
    assert "LUCK" in scheduled
    for name in ("cmd_fortune", "cmd_week", "cmd_month", "handle_message"):
        node = ast.dump(_function(tree, name), include_attributes=False)
        assert "briefing_model_session" not in node
