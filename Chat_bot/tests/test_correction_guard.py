import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_correction_completes_matching_dog_todo(tmp_path, monkeypatch):
    import todo_manager
    monkeypatch.setattr(todo_manager, "TODO_PATH", str(tmp_path / "todos.json"))
    todo_manager.add_todo("오후에 강아지 만나고 와서 할 일")

    from correction_guard import apply_user_correction
    msg = apply_user_correction("강아지 만나는건 이미 끝났다고 몇번을 이야기 했어")

    assert "정리했어" in msg
    assert todo_manager.get_pending_todos() == []


def test_suppression_context_records_topic(tmp_path, monkeypatch):
    import todo_manager
    monkeypatch.setattr(todo_manager, "TODO_PATH", str(tmp_path / "todos.json"))
    from correction_guard import apply_user_correction, get_suppression_context, SUPPRESSION_PATH
    monkeypatch.setattr("correction_guard.SUPPRESSION_PATH", tmp_path / "suppression.json")

    apply_user_correction("봄이 관련 그만 말해")
    ctx = get_suppression_context()

    assert "봄이/강아지 만나기" in ctx
    assert "반복 언급 금지" in ctx


def test_filtered_todos_hide_suppressed_topic(tmp_path, monkeypatch):
    import todo_manager
    monkeypatch.setattr(todo_manager, "TODO_PATH", str(tmp_path / "todos.json"))
    todo_manager.add_todo("오후에 강아지 만나고 와서 할 일")
    todo_manager.add_todo("부산 호텔 체크인 확인")

    from correction_guard import get_filtered_todo_context
    monkeypatch.setattr("correction_guard.SUPPRESSION_PATH", tmp_path / "suppression.json")
    (tmp_path / "suppression.json").write_text(json.dumps([
        {"topic": "봄이/강아지 만나기", "keywords": ["강아지", "봄이", "보미"], "rule": "반복 언급 금지"}
    ], ensure_ascii=False), encoding="utf-8")

    ctx = get_filtered_todo_context()

    assert "강아지" not in ctx
    assert "부산 호텔" in ctx


def test_old_vague_todos_are_hidden(tmp_path, monkeypatch):
    import todo_manager
    monkeypatch.setattr(todo_manager, "TODO_PATH", str(tmp_path / "todos.json"))
    item = todo_manager.add_todo("나중에 할 일")
    old = datetime.now().astimezone() - timedelta(days=20)
    data = [{**item, "created": old.isoformat()}]
    Path(todo_manager.TODO_PATH).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    from correction_guard import get_filtered_todo_context
    monkeypatch.setattr("correction_guard.SUPPRESSION_PATH", tmp_path / "suppression.json")

    assert get_filtered_todo_context() == ""
