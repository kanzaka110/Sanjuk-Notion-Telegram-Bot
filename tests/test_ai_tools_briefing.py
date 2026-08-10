def test_ai_tools_owner_uses_bounded_three_stage_session(monkeypatch):
    from AI_tools import briefing

    stages = []

    class Session:
        def __enter__(self): return None
        def __exit__(self, *args): return False

    monkeypatch.setattr(briefing, "briefing_model_session", lambda kind: Session())
    monkeypatch.setattr(briefing, "route_current", lambda stage, prompt: stages.append(stage) or "result")
    result = briefing.build_briefing("2026-08-10")
    assert result == "result"
    assert stages == ["AI_PUBLIC_EVIDENCE", "AI_PUBLIC_ANALYSIS", "AI_PUBLIC_EDITORIAL"]
