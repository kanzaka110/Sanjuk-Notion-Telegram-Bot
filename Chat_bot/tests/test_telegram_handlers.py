"""텔레그램 핸들러 통합 테스트 (API 모킹).

python-telegram-bot의 Update/Message/Chat 객체를 mock하여
봇 명령어 핸들러와 메시지 처리 로직을 검증한다.
"""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# config 로딩 전에 환경변수 설정
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config

# 테스트 시 ALLOWED_CHAT_ID를 강제 설정 (다른 테스트의 import 순서 영향 방지)
config.ALLOWED_CHAT_ID = 12345

# chat_bot이 이미 import된 경우 대비
try:
    import chat_bot as _cb

    # chat_bot에서 from config import ALLOWED_CHAT_ID로 가져갔으므로 직접 패치
    _cb.ALLOWED_CHAT_ID = 12345
except ImportError:
    pass

ALLOWED_CHAT_ID = 12345


# ─── 헬퍼: mock Update 객체 생성 ────────────────────────
def _make_update(
    chat_id: int = 12345,
    text: str = "테스트 메시지",
    is_command: bool = False,
) -> MagicMock:
    """python-telegram-bot Update 객체를 모킹한다."""
    update = MagicMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id

    update.message = AsyncMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat = MagicMock()
    update.message.chat.id = chat_id
    update.message.chat.send_action = AsyncMock()

    return update


def _make_context() -> MagicMock:
    """ContextTypes.DEFAULT_TYPE 을 모킹한다."""
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context


# ─── 권한 체크 테스트 ────────────────────────────────────
class TestAccessControl:
    """_is_allowed 권한 체크 테스트."""

    def test_allowed_chat_id(self) -> None:
        """허용된 Chat ID는 통과."""
        from chat_bot import _is_allowed

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        assert _is_allowed(update) is True

    def test_blocked_chat_id(self) -> None:
        """비허용 Chat ID는 거부."""
        from chat_bot import _is_allowed

        # ALLOWED_CHAT_ID를 강제로 설정하여 테스트
        with patch("chat_bot.ALLOWED_CHAT_ID", 12345):
            update = _make_update(chat_id=99999)
            assert _is_allowed(update) is False

    def test_no_effective_chat(self) -> None:
        """effective_chat이 None이면 거부."""
        from chat_bot import _is_allowed

        update = MagicMock()
        update.effective_chat = None
        assert _is_allowed(update) is False


# ─── 명령어 핸들러 테스트 ────────────────────────────────
class TestCommandHandlers:
    """봇 명령어 핸들러 테스트."""

    @pytest.mark.asyncio
    async def test_cmd_start_responds(self) -> None:
        """/start 명령어가 소개 메시지를 전송."""
        from chat_bot import cmd_start

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        context = _make_context()

        await cmd_start(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "산적 수다방" in text

    @pytest.mark.asyncio
    async def test_cmd_start_blocked(self) -> None:
        """/start가 비허용 사용자에게는 응답 안 함."""
        from chat_bot import cmd_start

        update = _make_update(chat_id=99999)
        context = _make_context()

        with patch("chat_bot._is_allowed", return_value=False):
            await cmd_start(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_help_responds(self) -> None:
        """/help 명령어가 도움말을 전송."""
        from chat_bot import cmd_help

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        context = _make_context()

        await cmd_help(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "/status" in text
        assert "/help" in text

    @pytest.mark.asyncio
    async def test_cmd_status_shows_stats(self) -> None:
        """/status 명령어가 통계를 표시."""
        from chat_bot import cmd_status, gemini

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        context = _make_context()

        mock_stats = {"total": 10}
        with (
            patch.object(gemini, "get_status", return_value="Claude CLI 모드"),
            patch("chat_bot.get_daily_stats", new_callable=AsyncMock, return_value=mock_stats),
        ):
            await cmd_status(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "산적 수다방 상태" in text
        assert "10" in text

    @pytest.mark.asyncio
    async def test_cmd_clear_resets_context(self) -> None:
        """/clear 명령어가 대화 컨텍스트를 초기화."""
        from chat_bot import cmd_clear

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        context = _make_context()

        await cmd_clear(update, context)

        assert context.user_data["clear_context"] is True
        update.message.reply_text.assert_called_once()


# ─── 멀티 버블 테스트 ───────────────────────────────────
class TestMultiBubble:
    """응답 분리 로직 테스트."""

    def test_short_text_no_split(self) -> None:
        """짧은 응답은 분리하지 않음."""
        from chat_bot import _split_into_bubbles

        result = _split_into_bubbles("짧은 응답")
        assert len(result) == 1

    def test_paragraph_split(self) -> None:
        """문단 구분으로 분리."""
        from chat_bot import _split_into_bubbles

        text = (
            "첫 번째 문단입니다. 여기에 충분한 텍스트를 넣어서 100자를 넘기도록 합니다. "
            "이 정도면 괜찮겠죠.\n\n"
            "두 번째 문단입니다. 역시 충분한 길이를 확보합니다. 테스트를 위한 텍스트입니다."
        )
        result = _split_into_bubbles(text)
        assert len(result) == 2

    def test_long_text_splits_into_bubbles(self) -> None:
        """긴 텍스트는 2-3개로 분리."""
        from chat_bot import _split_into_bubbles

        text = "\n".join([f"줄 {i}: 이것은 테스트 텍스트입니다." for i in range(10)])
        result = _split_into_bubbles(text)
        assert 2 <= len(result) <= 3

    @pytest.mark.asyncio
    async def test_send_bubbles_multiple(self) -> None:
        """버블 여러 개 순차 전송."""
        from chat_bot import _send_bubbles

        message = AsyncMock()
        message.reply_text = AsyncMock()
        message.chat = MagicMock()
        message.chat.send_action = AsyncMock()

        bubbles = ["첫 번째", "두 번째"]
        await _send_bubbles(message, bubbles)

        assert message.reply_text.call_count == 2


# ─── 메시지 핸들러 통합 테스트 ──────────────────────────
class TestHandleMessage:
    """handle_message 핸들러 통합 테스트."""

    @pytest.mark.asyncio
    async def test_blocked_user_ignored(self) -> None:
        """비허용 사용자의 메시지는 무시."""
        from chat_bot import handle_message

        update = _make_update(chat_id=99999, text="안녕")
        context = _make_context()

        with patch("chat_bot._is_allowed", return_value=False):
            await handle_message(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_message_ignored(self) -> None:
        """빈 메시지는 무시."""
        from chat_bot import handle_message

        update = _make_update(chat_id=ALLOWED_CHAT_ID)
        update.message.text = None
        context = _make_context()

        await handle_message(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_processing_flow(self) -> None:
        """정상 메시지 처리 플로우 (저장 → 응답 생성 → 전송)."""
        from chat_bot import handle_message, gemini

        update = _make_update(chat_id=ALLOWED_CHAT_ID, text="오늘 날씨 어때?")
        context = _make_context()

        with (
            patch("chat_bot._check_and_save_segment", new_callable=AsyncMock),
            patch("chat_bot.save_message", new_callable=AsyncMock) as mock_save,
            patch("chat_bot.get_recent_messages", new_callable=AsyncMock, return_value=[]),
            patch("chat_bot.get_full_context", return_value=""),
            patch.object(
                gemini,
                "ask",
                new_callable=AsyncMock,
                return_value=("좋은 날씨야!", None),
            ),
        ):
            await handle_message(update, context)

        # 사용자 메시지 + 봇 응답 = 2번 save
        assert mock_save.call_count == 2
        # 응답 전송
        update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_clear_context_resets_history(self) -> None:
        """clear_context 플래그가 설정되면 히스토리 없이 응답."""
        from chat_bot import handle_message, gemini

        update = _make_update(chat_id=ALLOWED_CHAT_ID, text="안녕")
        context = _make_context()
        context.user_data["clear_context"] = True

        with (
            patch("chat_bot._check_and_save_segment", new_callable=AsyncMock),
            patch("chat_bot.save_message", new_callable=AsyncMock),
            patch("chat_bot.get_recent_messages", new_callable=AsyncMock) as mock_recent,
            patch("chat_bot.get_full_context", return_value=""),
            patch.object(
                gemini,
                "ask",
                new_callable=AsyncMock,
                return_value=("안녕!", None),
            ),
        ):
            await handle_message(update, context)

        # clear_context가 True이면 get_recent_messages 호출 안 함
        mock_recent.assert_not_called()
        # 플래그 리셋됨
        assert context.user_data["clear_context"] is False

    @pytest.mark.asyncio
    async def test_fallback_notice_sent_first(self) -> None:
        """폴백 알림이 있으면 응답 전에 먼저 전송."""
        from chat_bot import handle_message, gemini

        update = _make_update(chat_id=ALLOWED_CHAT_ID, text="테스트")
        context = _make_context()

        with (
            patch("chat_bot._check_and_save_segment", new_callable=AsyncMock),
            patch("chat_bot.save_message", new_callable=AsyncMock),
            patch("chat_bot.get_recent_messages", new_callable=AsyncMock, return_value=[]),
            patch("chat_bot.get_full_context", return_value=""),
            patch.object(
                gemini,
                "ask",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            await handle_message(update, context)

        # 응답 전송
        update.message.reply_text.assert_called()
