"""
음성 메시지 처리 모듈 — Whisper STT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
텔레그램 음성 메시지 → faster-whisper STT → 텍스트 변환.
e2-small VM에 맞게 tiny 모델 사용 (메모리 ~150MB).
"""

import logging
import os
import tempfile

log = logging.getLogger(__name__)

_model = None


def _get_model():
    """Whisper 모델을 로딩한다 (싱글톤, 첫 호출 시 다운로드)."""
    global _model
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel
        _model = WhisperModel("tiny", device="cpu", compute_type="int8")
        log.info("Whisper 모델 로딩 완료 (tiny, cpu, int8)")
        return _model
    except Exception as e:
        log.error("Whisper 모델 로딩 실패: %s", e)
        return None


def transcribe_audio(file_path: str) -> str:
    """오디오 파일을 텍스트로 변환한다.

    Args:
        file_path: 오디오 파일 경로 (ogg, mp3, wav 등)

    Returns:
        변환된 텍스트. 실패 시 빈 문자열.
    """
    model = _get_model()
    if not model:
        return ""

    try:
        segments, info = model.transcribe(
            file_path,
            language="ko",
            beam_size=3,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        log.info("STT 완료: %.1f초 오디오 → %d자", info.duration, len(text))
        return text
    except Exception as e:
        log.error("STT 실패: %s", e)
        return ""


async def handle_voice_message(update, context) -> str | None:
    """텔레그램 음성/오디오 메시지를 텍스트로 변환한다.

    Args:
        update: 텔레그램 Update 객체
        context: 텔레그램 Context 객체

    Returns:
        변환된 텍스트. 실패 시 None.
    """
    voice = update.message.voice or update.message.audio
    if not voice:
        return None

    try:
        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        await file.download_to_drive(tmp_path)

        import asyncio
        text = await asyncio.to_thread(transcribe_audio, tmp_path)

        os.unlink(tmp_path)

        if not text:
            return None

        return text

    except Exception as e:
        log.error("음성 메시지 처리 실패: %s", e)
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return None
