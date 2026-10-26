# 서버에 올리기

공통 규칙
- 봇 토큰은 `.env`(또는 호스팅 패널의 환경변수 `DISCORD_TOKEN`)에만 넣고, 절대 GitHub나 채팅에 올리지 않기
- 봇은 한 곳에서만 켜기 (PC와 서버에서 동시에 켜면 응답이 두 번 나옴)
- `wildrift.db`가 티어/전적 데이터. 옮길 때 같이 옮기고, 주기적으로 백업하기

## A. 봇 호스팅 패널 (파일 업로드형, 가장 쉬움)
1. 호스팅에 가입하고 새 서비스를 만든다 (런타임: Python)
2. `wildrift-bot.zip`을 올려서 압축을 푼다 (`.env`는 포함되어 있지 않음)
3. 패널의 환경변수(또는 `.env` 파일 직접 생성)에 `DISCORD_TOKEN=토큰`을 넣는다
4. 시작 명령어를 `python bot.py`로 설정한다
5. 라이브러리 설치: 패널이 `requirements.txt`를 자동 설치하면 그대로, 아니면 패널 콘솔에서 `pip install -r requirements.txt`
6. 시작 → 로그에 에러가 없고 디스코드에서 봇이 온라인이면 성공
7. 무료 플랜은 며칠~한 달마다 직접 갱신해야 하는 곳이 많으니 갱신 주기를 꼭 확인하기. 램이 128MB 이하면 부족할 수 있음 (256MB 이상 권장)

## B. 리눅스 서버 (VPS, 오라클 클라우드, 라즈베리파이 등. Ubuntu 기준)
```
sudo apt update && sudo apt install -y python3-venv
mkdir -p ~/wildrift-bot && cd ~/wildrift-bot      # 여기에 파일 업로드 (scp, sftp 등)
python3 -m venv venv
venv/bin/pip install -r requirements.txt
nano .env                                         # DISCORD_TOKEN=토큰 입력 후 저장
venv/bin/python bot.py                            # 먼저 직접 실행해서 에러 없는지 확인 (Ctrl+C로 종료)
```
자동 실행/재시작 등록 (deploy/wildrift-bot.service 안의 사용자명과 경로를 먼저 수정):
```
sudo cp deploy/wildrift-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wildrift-bot
sudo systemctl status wildrift-bot                # active (running) 이면 성공
journalctl -u wildrift-bot -f                     # 실시간 로그
```
하루 한 번 자동 백업 (crontab -e 에 추가):
```
0 4 * * * cd /home/ubuntu/wildrift-bot && venv/bin/python backup_db.py
```

## 코드를 업데이트할 때
1. 봇 중지 (패널 정지 버튼 또는 `sudo systemctl stop wildrift-bot`)
2. 새 파일로 덮어쓰기 (**`wildrift.db`와 `.env`는 덮어쓰지 않기**)
3. 다시 시작
