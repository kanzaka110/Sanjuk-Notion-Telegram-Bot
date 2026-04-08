@echo off
REM GCP VM의 remote-control 상태 확인
"C:\Users\ohmil\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" compute ssh sanjuk-project --zone=us-central1-b --command="tmux has-session -t telegram 2>/dev/null && echo 'GCP remote-control: RUNNING' || echo 'GCP remote-control: STOPPED'"
