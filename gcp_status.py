"""
GCP VM 시스템 상태 모듈 — 수다봇 비서 컨텍스트 제공
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
봇 서비스 상태, 시스템 자원, tmux 세션 상태를 텍스트로 반환.
"""

import logging
import subprocess

log = logging.getLogger(__name__)

SERVICES = ["luck-bot", "chatbot", "stock-bot", "ue-bot", "game-news-bot"]
TMUX_SESSIONS = [
    "Sanjuk-Claude-Code",
    "Sanjuk-Stock-Simulator",
    "Sanjuk-Unreal",
    "3dsmax-mcp",
    "Sanjuk-Claude-Code-shiftup",
]


def _run(cmd: str, timeout: int = 5) -> str:
    """쉘 명령어를 실행하고 결과를 반환한다."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_service_status() -> str:
    """systemd 봇 서비스 상태를 반환한다."""
    lines = []
    for svc in SERVICES:
        output = _run(f"systemctl is-active {svc} 2>/dev/null")
        status = output if output else "unknown"
        marker = "OK" if status == "active" else "DOWN"
        lines.append(f"- {svc}: {marker}")
    return "\n".join(lines)


def get_system_resources() -> str:
    """CPU, 메모리, 디스크 사용량을 반환한다."""
    mem = _run("free -h | awk '/^Mem:/{print $3\"/\"$2}'")
    disk = _run("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'")
    uptime = _run("uptime -p")
    return f"- 메모리: {mem}\n- 디스크: {disk}\n- 가동: {uptime}"


def get_tmux_status() -> str:
    """tmux 세션 상태를 반환한다."""
    output = _run("tmux list-sessions 2>/dev/null")
    if not output:
        return "tmux 세션 없음"
    active = []
    for line in output.split("\n"):
        name = line.split(":")[0].strip()
        if name:
            active.append(name)
    missing = [s for s in TMUX_SESSIONS if s not in active]
    parts = [f"- 활성: {len(active)}개"]
    if missing:
        parts.append(f"- 비활성: {', '.join(missing)}")
    return "\n".join(parts)


def get_gcp_context() -> str:
    """봇 프롬프트에 삽입할 GCP 시스템 컨텍스트를 반환한다."""
    try:
        services = get_service_status()
        resources = get_system_resources()
        tmux = get_tmux_status()

        return (
            "━━━ GCP VM 상태 (sanjuk-project) ━━━\n"
            f"[봇 서비스]\n{services}\n\n"
            f"[시스템 자원]\n{resources}\n\n"
            f"[Claude Code 세션]\n{tmux}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    except Exception as e:
        log.error("GCP 상태 조회 실패: %s", e)
        return ""
