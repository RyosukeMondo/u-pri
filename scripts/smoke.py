"""Real HTTP/restart smoke test. Uses synthetic data and a separate temporary DB.
Does not contact Japan Post or any printer. Emits timings, never credentials.
"""
import csv
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

token = secrets.token_urlsafe(36)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, UPRI_API_TOKEN=token, UPRI_DB=directory + "/db")
    def start():
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "upri.api:create_app", "--factory",
                                 "--port", str(port), "--no-access-log"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                    return proc
            except httpx.ConnectError:
                pass
            time.sleep(.05)
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("Service did not start")

    proc = start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {token}"}) as c:
            addr = dict(name="試験 太郎", postal_code="1000001", address1="東京都千代田区千代田1", phone="0312345678")
            payload = {"shipments": [dict(reference=f"SMOKE-{i:03d}",
                ship_date=str(datetime.now(ZoneInfo("Asia/Tokyo")).date()), recipient=addr,
                sender=addr, items=[dict(name="書籍", quantity=1)]) for i in range(100)]}
            start_time = time.perf_counter()
            r = c.post("/v1/batches", json=payload, headers={"Idempotency-Key": "smoke"})
            assert r.status_code == 201, r.text
            created = r.json()
            raw = c.get(created["csv_url"]).content
            elapsed = (time.perf_counter() - start_time) * 1000
            rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
            assert len(rows) == 100 and all(len(row) == 99 for row in rows)
            assert c.post("/v1/batches", json=payload, headers={"Idempotency-Key": "smoke"}).json()["id"] == created["id"]
            proc.terminate(); proc.wait(timeout=5)
            proc = start()
            assert c.get('/v1/batches/' + created['id']).status_code == 200
            history = "お客様側管理番号,お問い合わせ番号\r\nSMOKE-000,123456789012\r\n"
            r = c.post('/v1/batches/' + created['id'] + '/history', content=history.encode('cp932'))
            assert r.status_code == 200 and r.json()['state'] == 'csv_prepared'
            assert r.json()['shipments'][0]['tracking'] == '123456789012'
            Path('research/logs').mkdir(parents=True, exist_ok=True)
            Path('research/logs/smoke.csv').write_bytes(raw)
            print(json.dumps(dict(records=100, columns=99, create_and_download_ms=round(elapsed, 2),
                                 restart_persistence=True, retry_same_batch=True, history_roundtrip=True)))
    finally:
        proc.terminate()
        proc.wait(timeout=5)
