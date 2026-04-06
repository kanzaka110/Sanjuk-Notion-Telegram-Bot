---
name: Stock Simulator 통합 프로젝트
description: Stock_bot 전체 기능을 통합한 독립 TUI 프로젝트 — 별도 리포, GCP 배포 완료
type: project
---

Stock_bot의 전체 기능(브리핑+챗봇+주가업데이트)을 별도 리포로 이전 + 터미널 UI 추가.
2026-04-06 GCP 배포 완료, 기존 리포에서 Stock_bot 완전 제거.

**리포:** github.com/kanzaka110/Sanjuk-Stock-Simulator
**로컬:** C:\dev\Sanjuk-Stock-Simulator
**GCP:** /home/kanzaka110/Sanjuk-Stock-Simulator/ (독립 venv)

**CLI 엔트리포인트:**
- `python main.py` — Textual TUI (6개 화면: d/a/t/q/b/s)
- `python main.py briefing` — 브리핑 → Notion + 텔레그램 (cron용)
- `python main.py chatbot` — 텔레그램 챗봇 (systemd용)
- `python main.py price` — Notion 주가 업데이트 (cron용)
- `python main.py ask "질문"` — AI 질의

**GCP 서비스:** stock-chatbot-new (active, stock-bot 대체)
**GCP cron:** run_stock_briefing_kr/us.sh, run_stock_update.sh → 이 리포 main.py 호출

**스택:** Textual TUI + yfinance + Gemini 2.5 Pro/Flash + Claude Sonnet 4.6 + SQLite

**Why:** 기존 Stock_bot은 스크립트 모음이라 인터랙티브 매매 시뮬레이션 불가
**How to apply:** 주식 관련 코드 수정은 이 리포에서만. 기존 Notion-Telegram-Bot 리포에 Stock_bot 없음.
