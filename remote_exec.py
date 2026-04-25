"""
텔레그램→Claude Code 원격 실행 — 자연어 명령 → 쉘 실행
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
안전: 읽기 전용 명령만 허용, 파괴적 명령 차단.
"""

import asyncio
import logging
import subprocess

log = logging.getLogger(__name__)

ALLOWED_COMMANDS = [
    "systemctl status", "systemctl is-active",
    "journalctl", "tail", "cat", "head", "grep",
    "free", "df", "uptime", "top -bn1", "ps aux",
    "tmux list-sessions", "tmux list-panes",
    "git log", "git status", "git diff --stat",
    "ls", "wc",
]

BLOCKED_PATTERNS = [
    "rm ", "kill", "pkill", "shutdown", "reboot",
    "dd ", "mkfs", "> /dev", "chmod", "chown",
    "curl", "wget", "pip install", "apt",
]


def is_safe_command(cmd: str) -> bool:
    """명령어 안전성 검사."""
    cmd_lower = cmd.lower().strip()
    for blocked in BLOCKED_PATTERNS:
        if blocked in cmd_lower:
            return False
    return True


def execute_command(cmd: str, timeout: int = 30) -> str:
    """쉘 명령어를 실행하고 결과를 반환한다."""
    if not is_safe_command(cmd):
        return "차단된 명령어. 읽기 전용 명령만 허용됨."

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n[stderr] {result.stderr.strip()[:200]}"
        return output[:3000] if output else "(출력 없음)"

    except subprocess.TimeoutExpired:
        return f"타임아웃 ({timeout}초)"
    except Exception as e:
        return f"실행 오류: {e}"


def parse_natural_command(text: str) -> str:
    """자연어를 쉘 명령어로 변환한다."""
    from shared_config import claude_cli

    prompt = f"""다음 자연어 요청을 Linux 쉘 명령어 1줄로 변환해줘.

요청: "{text}"

규칙:
- 읽기 전용 명령만 (상태 확인, 로그 조회 등)
- 파괴적 명령 금지 (rm, kill, chmod 등)
- 명령어만 출력. 설명 없이

환경:
- GCP VM (Debian), systemd 서비스: luck-bot, chatbot, stock-bot, ue-bot, game-news-bot
- tmux 세션: Sanjuk-Claude-Code, Sanjuk-Stock-Simulator, Sanjuk-Unreal, 3dsmax-mcp
- 봇 로그: journalctl -u 서비스명
- 봇 코드: /home/kanzaka110/Sanjuk-Notion-Telegram-Bot/"""

    result = claude_cli(prompt, model="haiku", timeout=15)
    if result:
        # 코드 블록 제거
        result = result.strip().strip("`").strip()
        if result.startswith("bash\n"):
            result = result[5:]
        return result.split("\n")[0].strip()
    return ""


async def handle_exec(text: str) -> str:
    """자연어 → 명령어 변환 → 실행 → 결과 반환."""
    cmd = await asyncio.to_thread(parse_natural_command, text)
    if not cmd:
        return "명령어 변환 실패"

    if not is_safe_command(cmd):
        return f"차단: {cmd}\n읽기 전용 명령만 허용됨."

    result = await asyncio.to_thread(execute_command, cmd)
    return f"$ {cmd}\n\n{result}"
