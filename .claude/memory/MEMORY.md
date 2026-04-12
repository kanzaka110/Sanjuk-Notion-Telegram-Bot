# Memory Index

- [Project Overview](project_overview.md) — 3개 텔레그램 봇 + Claude CLI 기반 (UE봇/주식 별도 리포)
- [Stock Simulator](project_stock_simulator.md) — 주식 전용 TUI 프로젝트, GCP 배포 완료 (2026-04-06)
- [Repo Consolidation 2026-04-01](project_repo_consolidation.md) — 분산 리포 5개를 단일 리포로 통합 완료
- [GCP Service Migration](project_gcp_service_migration.md) — 3봇 체제, UE/주식 별도 리포 분리 (04-12)
- [Briefing Improvements](project_briefing_improvements.md) — 게임뉴스 시프트업/URL검증 (UE는 Sanjuk-Unreal로 이전)
- [GCP Disk Upgrade 2026-04-08](project_gcp_disk_cleanup.md) — 디스크 10→20GB 확장 완료 (43%), 디스크명=sanjuk-talk-bot
- [User Profile](user_profile.md) — Claude CLI 기반 봇 개발자, 다중 리포 운영, 한국어 우선
- [Push/Pull Commands](feedback_update_all.md) — "푸시"=전체 아웃바운드, "풀"=외부→로컬 동기화
- [GCP .env Loading](feedback_env_loading.md) — source 대신 export xargs 방식 사용 필요
- [GCP SSH from Local](reference_gcp_ssh.md) — gcloud CLI, ohmil(기본)/kanzaka110(서비스) 유저
- [New PC Setup Guide](reference_new_pc_setup.md) — 새 PC 셋업 전체 절차 (클론, setup.sh, gcloud, SSH)
- [Remote Triggers & Sessions](reference_remote_triggers.md) — 리모트 세션 4개 + 트리거 8개 (04-12 업데이트)
- [GCP Memory Sync](feedback_gcp_memory_sync.md) — 메모리 변경 시 GCP 자동 푸시, 다중 환경 동기화
- [GCP Execution](feedback_gcp_execution.md) — 봇 실행/테스트는 항상 GCP에서 (로컬은 편집/커밋만)
