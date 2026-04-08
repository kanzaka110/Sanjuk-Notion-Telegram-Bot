---
name: GCP Disk Upgrade 2026-04-08
description: GCP 디스크 10GB→20GB 확장 완료 (43% 사용), ohmil Stock-Simulator 중복 삭제
type: project
---

## 2026-04-08 디스크 확장

디스크 10GB → **20GB** 확장. 사용률 90% → **43%** (11G 여유).

**작업 내용:**
1. ohmil 유저의 중복 Sanjuk-Stock-Simulator 삭제 (289MB 확보)
2. gcloud로 디스크 리사이즈: `sanjuk-talk-bot` 디스크 10→20GB
3. VM 내 파티션 확장: `growpart` + `resize2fs`

**디스크 정보:**
- 디스크명: `sanjuk-talk-bot` (인스턴스명 `sanjuk-project`와 다름, GCP에서 디스크 이름 변경 불가)
- 타입: pd-balanced
- 비용: ~$0.80/월 (기존 $0.40 + 추가 $0.40)

**정기 정리 명령어 (필요 시):**
```bash
sudo apt-get clean && sudo journalctl --vacuum-time=3d
sudo find /var/log -name '*.gz' -delete && sudo find /var/log -name '*.1' -delete
rm -rf ~/.cache/pip
```

**Why:** 10GB에서 지속적으로 80-90% 도달, 관리 부담 큼
**How to apply:** 20GB로 여유 생겼으므로 당분간 정리 불필요. 80% 이상 시 위 명령어 실행.
