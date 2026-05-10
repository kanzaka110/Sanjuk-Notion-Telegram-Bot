"""
사진/문서 분석 모듈 — Claude Vision 활용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
텔레그램 사진 → Claude CLI로 분석 (영수증 OCR, 스크린샷 분석 등).
Claude CLI는 이미지 파일을 직접 입력으로 받을 수 있음.
"""

import asyncio
import logging
import os
import subprocess
import tempfile

log = logging.getLogger(__name__)

CLAUDE_CLI = "/usr/bin/claude"


def analyze_image(image_path: str, user_prompt: str = "") -> str:
    """이미지를 Claude로 분석한다.

    Args:
        image_path: 이미지 파일 경로
        user_prompt: 사용자 추가 지시 (없으면 자동 분석)

    Returns:
        분석 결과 텍스트
    """
    if not user_prompt:
        user_prompt = "이 이미지를 분석해줘. 영수증이면 항목과 금액을 추출하고, 문서면 내용을 요약하고, 스크린샷이면 무엇을 보여주는지 설명해줘."

    try:
        # Claude CLI에 이미지 파일을 파이프로 전달
        cmd = [
            CLAUDE_CLI, "-p", user_prompt,
            "--model", "sonnet",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]

        # stdin으로 이미지 데이터 전달
        with open(image_path, "rb") as img_file:
            result = subprocess.run(
                cmd,
                stdin=img_file,
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        log.warning("이미지 분석 실패: %s", result.stderr[:200] if result.stderr else "")
        return "이미지 분석에 실패했어."

    except subprocess.TimeoutExpired:
        return "이미지 분석 시간 초과."
    except Exception as e:
        log.error("이미지 분석 오류: %s", e)
        return f"이미지 분석 오류: {e}"


async def handle_photo_message(update, context, user_caption: str = "") -> str | None:
    """텔레그램 사진 메시지를 분석한다.

    Returns:
        분석 결과 텍스트. 실패 시 None.
    """
    if not update.message.photo:
        return None

    try:
        # 가장 큰 해상도 사진 가져오기
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        await file.download_to_drive(tmp_path)

        result = await asyncio.to_thread(
            analyze_image, tmp_path, user_caption,
        )

        os.unlink(tmp_path)
        return result

    except Exception as e:
        log.error("사진 처리 실패: %s", e)
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return None
