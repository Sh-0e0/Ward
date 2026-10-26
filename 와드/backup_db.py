"""wildrift.db 백업: backups/ 폴더에 날짜별로 저장하고 최근 14개만 남김 (윈도우/리눅스 공통)"""
import os
import sqlite3
from datetime import date

DB_PATH = "wildrift.db"
BACKUP_DIR = "backups"
KEEP = 14

os.makedirs(BACKUP_DIR, exist_ok=True)
target = os.path.join(BACKUP_DIR, f"wildrift-{date.today().isoformat()}.db")

src = sqlite3.connect(DB_PATH)
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)  # 봇이 켜져 있어도 안전하게 복사
src.close()
dst.close()

old = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("wildrift-") and f.endswith(".db"))
for name in old[:-KEEP]:
    os.remove(os.path.join(BACKUP_DIR, name))
print("백업 완료:", target)
