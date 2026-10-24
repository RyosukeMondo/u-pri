import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from upri.api import create_app

TOKEN = "test-token-" * 5


def payload(ref="TEST-001"):
    address = dict(name="試験 太郎", postal_code="1000001", address1="東京都千代田区千代田1",
                   phone="0312345678")
    return {"shipments": [dict(reference=ref, ship_date=str(datetime.now(ZoneInfo("Asia/Tokyo")).date()),
                               recipient=address, sender=address, items=[dict(name="書籍", quantity=2)])]}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "test.db", TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})


def create(client, data=None, key="key-1"):
    return client.post("/v1/batches", json=data or payload(), headers={"Idempotency-Key": key})


def test_auth_and_private_errors(client):
    assert client.get("/v1/capabilities", headers={"Authorization": "Bearer bad"}).status_code == 401
    p = payload()
    p["shipments"][0]["recipient"]["name"] = "secret-name\n"
    # Whitespace is normalized, interior control characters must be rejected.
    p["shipments"][0]["recipient"]["name"] = "secret\nname"
    r = create(client, p)
    assert r.status_code == 422
    assert "secret" not in r.text
    assert client.get("/v1/capabilities", headers={b"Authorization": b"Bearer \xff"}).status_code == 401


def test_strict_quantity_and_phone(client):
    p = payload()
    p["shipments"][0]["items"][0]["quantity"] = True
    assert create(client, p).status_code == 422
    p["shipments"][0]["items"][0]["quantity"] = 1
    p["shipments"][0]["recipient"]["phone"] = "0--------"
    assert create(client, p).status_code == 422


def test_csv_contract_and_roundtrip(client):
    p = payload()
    p["shipments"][0]["items"] = [{"name": '本,"冊"', "quantity": 2}, {"name": "文具"}]
    r = create(client, p)
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    raw = client.get(r.json()["csv_url"]).content
    assert raw.endswith(b"\r\n")
    row, = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    # Positions from official manual 6-1 section 6; not the export implementation.
    assert len(row) == 99
    assert row[0] == "TEST-001" and row[11] == "1000001"
    assert row[15] == "試験 太郎" and row[31] == "試験 太郎"
    assert row[68] == "UPRI_PREPAID" and row[71] == "0"
    assert row[82:84] == ['本,"冊"', "2"]
    assert row[88:90] == ["文具", "1"]
    assert row[93:] == [""] * 6
    hist = "お客様側管理番号,お問い合わせ番号\r\nTEST-001,123456789012\r\n".encode("cp932")
    for _ in range(2):
        r = client.post(f"/v1/batches/{bid}/history", content=hist)
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "history_received"
        assert r.json()["printing_verified"] is False


def test_retries_and_conflicts(client):
    first = create(client)
    assert create(client).json()["id"] == first.json()["id"]
    assert create(client, payload("TEST-002")).status_code == 409
    assert create(client, key="different").status_code == 409
    assert create(client, payload("TEST-002"), "new").status_code == 201


def test_concurrent_retry(client):
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: create(client), range(6)))
    assert sorted(r.status_code for r in results) == [200] * 5 + [201]
    assert len({r.json()["id"] for r in results}) == 1


@pytest.mark.parametrize("value", ["😀", "あ" * 26, "a\x00b"])
def test_invalid_item(client, value):
    p = payload()
    p["shipments"][0]["items"][0]["name"] = value
    assert create(client, p).status_code == 422


def test_unknown_fields_and_date(client):
    p = payload()
    p["shipments"][0]["cash_on_delivery"] = True
    assert create(client, p).status_code == 422
    del p["shipments"][0]["cash_on_delivery"]
    p["shipments"][0]["ship_date"] = "2099-01-01"
    assert create(client, p).status_code == 422


def test_history_atomicity(client):
    bid = create(client).json()["id"]
    url = f"/v1/batches/{bid}/history"
    data = "お客様側管理番号,お問い合わせ番号\nTEST-001,123456789012\nUNKNOWN,123456789013\n"
    assert client.post(url, content=data.encode()).status_code == 409
    assert client.get(f"/v1/batches/{bid}").json()["shipments"][0]["tracking"] is None
    assert client.post(url, content=b"x" * 65537).status_code == 413
    assert client.post(url, content=b"bad,header\n").status_code == 422


def test_persistence(tmp_path):
    path = tmp_path / "db"
    with TestClient(create_app(path, TOKEN), headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        bid = create(c).json()["id"]
    with TestClient(create_app(path, TOKEN), headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        assert c.get(f"/v1/batches/{bid}").status_code == 200
        assert create(c).json()["id"] == bid
