---
name: GCP Disk Cleanup 2026-04-06
description: GCP 디스크 84%→71% 정리 완료, 정기 정리 필요 항목 기록
type: project
---

2026-04-06 GCP 디스크 정리 수행. 7.6G/9.7G (84%) → 6.4G/9.7G (71%), 약 1.2GB 확보.

**정리 항목:**
- apt 캐시: `sudo apt-get clean` (~377MB)
- journal 로그: `sudo journalctl --vacuum-time=3d` (237MB)
- /var/log 오래된 로그: `.gz`, `.1`, `.old` 삭제 + syslog/btmp/auth.log truncate (~550MB)
- google-cloud-ops-agent 로그: `/var/log/google-cloud-ops-agent/` 정리
- pip 캐시: `~/.cache/pip` 삭제
- exim4 로그: truncate

**주요 공간 소비자 (정리 후):**
- ~/Sanjuk-Notion-Telegram-Bot/venv: 320MB (필수, 삭제 불가)
- ~/Sanjuk-Notion-Telegram-Bot: 322MB 전체
- /var/log: 정리 후에도 ops-agent, journal이 계속 쌓임

**Why:** e2-micro 인스턴스 디스크 10GB로 주기적 정리 필요
**How to apply:** 디스크 80% 이상 시 위 명령어 순서대로 실행. journal은 3일 유지가 적절.
