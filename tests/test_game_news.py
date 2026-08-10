"""게임뉴스 브리핑 날짜 로직 테스트."""

from datetime import datetime, date, timezone, timedelta
from unittest.mock import patch

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("TELEGRAM_CHAT_ID", "test-chat-id")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")

from GameNews_bot.game_news import get_target_date, KST


class TestGetTargetDate:
    """get_target_date 헬퍼 테스트."""

    def test_returns_yesterday(self):
        """2026-05-24 09:15 KST 브리핑 → 대상일 2026-05-23."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)
        assert get_target_date(now) == date(2026, 5, 23)

    def test_midnight_boundary(self):
        """자정 직후에도 하루 전을 반환."""
        now = datetime(2026, 5, 24, 0, 0, 1, tzinfo=KST)
        assert get_target_date(now) == date(2026, 5, 23)

    def test_month_boundary(self):
        """월 경계: 5월 1일 → 4월 30일."""
        now = datetime(2026, 5, 1, 9, 0, 0, tzinfo=KST)
        assert get_target_date(now) == date(2026, 4, 30)

    def test_year_boundary(self):
        """연 경계: 1월 1일 → 12월 31일."""
        now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=KST)
        assert get_target_date(now) == date(2025, 12, 31)

    def test_no_arg_uses_now(self):
        """인자 없이 호출 시 현재 시간 기준."""
        result = get_target_date()
        expected = (datetime.now(KST) - timedelta(days=1)).date()
        assert result == expected


class TestFetchNewsPrompt:
    """fetch_news 프롬프트에 target_date가 올바르게 포함되는지 테스트."""

    def test_prompt_contains_target_date_not_today(self):
        """프롬프트에 target_date(어제)가 포함되고, 당일이 필터 날짜로 쓰이지 않아야 함."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)
        target_iso = "2026-05-23"
        today_iso = "2026-05-24"

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "mock result"
            from GameNews_bot.game_news import fetch_news
            fetch_news(now=now)

            prompt = mock_cli.call_args[0][0]
            # target_date가 프롬프트에 포함
            assert target_iso in prompt
            # 당일(2026-05-24)이 필터 날짜로 사용되지 않음
            assert f"게시일이 {today_iso}" not in prompt
            # target_date가 필터 날짜로 사용됨
            assert f"게시일이 {target_iso}" in prompt

    def test_prompt_excludes_old_articles(self):
        """프롬프트에 오래된 기사 제외 지시가 포함."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "mock result"
            from GameNews_bot.game_news import fetch_news
            fetch_news(now=now)

            prompt = mock_cli.call_args[0][0]
            assert "절대 포함하지 마세요" in prompt
            assert "제외" in prompt

    def test_search_queries_use_target_date(self):
        """검색어에 target_date ISO가 포함."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "mock result"
            from GameNews_bot.game_news import fetch_news
            fetch_news(now=now)

            prompt = mock_cli.call_args[0][0]
            assert "게임 뉴스 2026-05-23" in prompt
            assert "2026.05.23" in prompt


class TestSummarizeNewsPrompt:
    """summarize_news 프롬프트에 target_date가 올바르게 포함되는지 테스트."""

    def test_prompt_filters_by_target_date(self):
        """summarize 프롬프트가 target_date로 필터링."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)
        target_iso = "2026-05-23"
        today_iso = "2026-05-24"

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "요약 결과"
            from GameNews_bot.game_news import summarize_news
            summarize_news("테스트 기사 데이터", now=now)

            prompt = mock_cli.call_args[0][0]
            assert f"게시일이 정확히 {target_iso}" in prompt
            assert f"게시일이 {today_iso}인 기사만" not in prompt

    def test_prompt_excludes_unknown_dates(self):
        """날짜 불명 기사 제외 지시가 프롬프트에 포함."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "요약 결과"
            from GameNews_bot.game_news import summarize_news
            summarize_news("테스트 데이터", now=now)

            prompt = mock_cli.call_args[0][0]
            assert "확인할 수 없는 기사" in prompt or "날짜 불명" in prompt

    def test_result_message_contains_target_date(self):
        """결과 메시지에 대상 날짜가 명시."""
        now = datetime(2026, 5, 24, 9, 15, 0, tzinfo=KST)

        with patch("GameNews_bot.game_news.claude_cli") as mock_cli:
            mock_cli.return_value = "📅 2026년 05월 23일 (2026-05-23) 게임뉴스\n내용"
            from GameNews_bot.game_news import summarize_news
            summarize_news("테스트", now=now)

            prompt = mock_cli.call_args[0][0]
            # 출력 형식에 대상 날짜가 포함되어야 함
            assert "2026-05-23" in prompt
            assert "2026년 05월 23일" in prompt
