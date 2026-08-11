import ast
import asyncio
import sys
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


def test_luck_chunk_delivery_attempts_all_chunks_and_fails_closed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sys.path.insert(0, str(Path(__file__).parents[1] / "Luck_bot"))
    import Luck_bot.luck_bot as luck

    class Bot:
        def __init__(self):
            self.calls = 0

        async def send_message(self, **_kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("transport")

    bot = Bot()
    result = asyncio.run(luck.send_long_message(bot, 1, "x" * 5000))
    assert bot.calls == 2
    assert result == {
        "success": False,
        "reason_code": "telegram_transport_failed",
        "attempts": 2,
    }
