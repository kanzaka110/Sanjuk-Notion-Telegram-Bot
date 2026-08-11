import json
from pathlib import Path

import pytest


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_content_router_enforces_caps_privacy_and_terminal_lineage(tmp_path):
    from briefing_model_router import (
        RoutingRefusal,
        briefing_model_session,
        get_run_summary,
        record_delivery,
        route_current,
    )

    calls = []

    def executor(prompt: str, **kwargs):
        calls.append((prompt, kwargs))
        return "ok"

    with briefing_model_session("GAME_NEWS", state_dir=tmp_path, run_id="game-1"):
        assert route_current("GAME_PUBLIC_EVIDENCE", "public game release", _executor=executor) == "ok"
        assert route_current("GAME_PUBLIC_ANALYSIS", "public reaction", _executor=executor) == "ok"
        assert route_current("GAME_PUBLIC_EDITORIAL", "public dated sources", _executor=executor) == "ok"
        with pytest.raises(RoutingRefusal, match="stage_call_cap_exhausted"):
            route_current("GAME_PUBLIC_EDITORIAL", "second editorial", _executor=executor)
        with pytest.raises(RoutingRefusal, match="sensitive_public_payload"):
            route_current("GAME_PUBLIC_ANALYSIS", "birth_date=1980-01-01", _executor=executor)
        record_delivery(success=True, attempts=2)
        summary = get_run_summary()

    assert [item[1]["authority"] for item in calls] == [
        "public_evidence", "public_analysis", "public_editorial"
    ]
    assert summary["provider_call_counts"] == {"perplexity": 1, "grok": 1, "codex": 1}
    assert summary["sensitive_rejection_count"] == 1
    assert summary["fallback_count"] == 0
    assert summary["outbound_sensitive_count"] == 0
    assert summary["order_authority_invocations"] == 0
    events = _events(tmp_path / "lineage-v1.jsonl")
    assert len([row for row in events if row["event_type"] == "delivery_terminal"]) == 1
    assert len([row for row in events if row["event_type"] == "run_summary"]) == 1
    assert {row["run_id"] for row in events} == {"game-1"}
    assert all(len(row["repo_commit"]) == 40 for row in events)
    lineage = (tmp_path / "lineage-v1.jsonl").read_text(encoding="utf-8")
    assert "public game release" not in lineage
    assert "birth_date" not in lineage


def test_content_router_auto_records_failed_delivery_on_exception(tmp_path):
    from briefing_model_router import briefing_model_session

    with pytest.raises(RuntimeError):
        with briefing_model_session("GAME_NEWS", state_dir=tmp_path, run_id="failed-1"):
            raise RuntimeError("boom")
    events = _events(tmp_path / "lineage-v1.jsonl")
    terminal = [row for row in events if row["event_type"] == "delivery_terminal"]
    summaries = [row for row in events if row["event_type"] == "run_summary"]
    assert len(terminal) == 1 and terminal[0]["outcome"] == "failed"
    assert terminal[0]["reason_code"] == "delivery_not_recorded"
    assert len(summaries) == 1 and summaries[0]["delivery_success"] is False


def test_content_router_keeps_luck_private_and_public_providers_at_zero(tmp_path):
    from briefing_model_router import briefing_model_session, get_run_summary, record_delivery, route_current

    seen = []

    def executor(prompt: str, **kwargs):
        seen.append(kwargs)
        return "private result"

    with briefing_model_session("LUCK", state_dir=tmp_path):
        for _ in range(3):
            assert route_current("LUCK_PRIVATE_FINAL", "private saju input", _executor=executor)
        record_delivery(success=True, attempts=1)
        summary = get_run_summary()

    assert {item["provider"] for item in seen} == {"claude"}
    assert {item["authority"] for item in seen} == {"private_advice"}
    assert summary["provider_call_counts"] == {"claude": 3}
    assert summary["fallback_count"] == 0
    assert summary["outbound_sensitive_count"] == 0
    assert summary["order_authority_invocations"] == 0


def test_grok_provider_flag_has_explicit_value():
    source = (Path(__file__).parents[1] / "briefing_grok_cli.py").read_text(encoding="utf-8")
    assert '"--provider",\n        _PROVIDER,\n        "-m",' in source
