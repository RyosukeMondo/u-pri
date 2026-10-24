import csv
import re
import hashlib
import hmac
import json
import os
import io
import subprocess
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .csvio import export_csv, parse_history, FIELDS, import_csv
from .models import Batch
from .labels import render_demo_labels, sample_batch


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    batch: Batch


class DraftRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)


class OperatorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID
    status: Literal["import_reported", "print_reported", "print_failed", "print_uncertain"]
    note: str = Field(default="", max_length=500)


def create_app(db_path=None, token=None, delivery_type=None):
    token = token or os.environ.get("UPRI_API_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("Set UPRI_API_TOKEN to at least 32 random characters")
    delivery_type = delivery_type or os.environ.get("UPRI_DELIVERY_TYPE", "UPRI_PREPAID")
    if not delivery_type or len(delivery_type.encode("cp932")) > 20 or any(ord(c) < 32 for c in delivery_type):
        raise RuntimeError("Invalid UPRI_DELIVERY_TYPE")
    db_path = Path(db_path or os.environ.get("UPRI_DB", "data/upri.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not db_path.exists():
        fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)

    @contextmanager
    def db():
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with db() as conn:
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY, idem TEXT UNIQUE NOT NULL, digest TEXT NOT NULL,
            csv BLOB NOT NULL, created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS shipments (
            reference TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
            tracking TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL,
            prepared_batch TEXT REFERENCES batches(id));
          CREATE TABLE IF NOT EXISTS operator_events (
            id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
            status TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL);
        """)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(drafts)")}
        for column in ("idem", "initial_digest"):
            if column not in columns:
                conn.execute(f"ALTER TABLE drafts ADD COLUMN {column} TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS drafts_idem ON drafts(idem)")

    app = FastAPI(title="Upri CSV Bridge", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")
    # Only prebuilt fictional specimens are public; never mount app data or RPX sources.
    demo_layout_dir = Path(os.environ.get("UPRI_DEMO_LAYOUT_DIR", str(Path(__file__).resolve().parents[1] / "output/layout-gallery")))
    if (demo_layout_dir / "catalog.json").is_file():
        app.mount("/demo-layouts", StaticFiles(directory=demo_layout_dir, html=True), name="demo-layouts")

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get("/demo", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    def dashboard():
        html = (static_dir / "index.html").read_text(encoding='utf-8')
        if not (demo_layout_dir / "catalog.json").is_file():
            html = re.sub(r"<!-- OPTIONAL_GALLERY_START -->.*?<!-- OPTIONAL_GALLERY_END -->", "", html, flags=re.S)
        return HTMLResponse(html)

    security = HTTPBearer(auto_error=False)

    def auth(cred: HTTPAuthorizationCredentials | None = Depends(security)):
        if cred is None or not hmac.compare_digest(cred.credentials.encode(), token.encode()):
            raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic input/context can contain addresses. Do not echo them.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()]})

    def result(conn, batch_id):
        row = conn.execute("SELECT id, created FROM batches WHERE id=?", (batch_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Batch not found")
        shipments = [dict(x) for x in conn.execute(
            "SELECT reference,tracking FROM shipments WHERE batch_id=? ORDER BY reference", (batch_id,))]
        complete = all(s["tracking"] for s in shipments)
        events = [dict(e) for e in conn.execute(
            "SELECT id,status,note,created FROM operator_events WHERE batch_id=? ORDER BY rowid", (batch_id,))]
        return {**dict(row), "state": "history_received" if complete else "csv_prepared",
                "shipments": shipments, "csv_url": f"/v1/batches/{batch_id}/csv",
                "printing_verified": False, "operator_events": events,
                "operator_status": events[-1]["status"] if events else "not_reported"}

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": "csv_bridge", "desktop_verified": False}

    def label_pdf(batch, paper):
        try:
            raw = render_demo_labels(batch, paper)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return Response(raw, media_type="application/pdf", headers={
            "Content-Disposition": f'inline; filename="UPRI-DEMO-NOT-FOR-SHIPPING-{paper}.pdf"',
            "X-Upri-Label-Type": "demo-not-valid-for-shipping"})

    @app.get("/demo-label.pdf", include_in_schema=False)
    def public_sample_label(paper: Literal["a4", "a6"] = "a4"):
        # Public fixed fictional sample only; never reads the database or submitted data.
        return label_pdf(sample_batch(), paper)

    @app.post("/v1/demo-labels/pdf", dependencies=[Depends(auth)])
    def custom_demo_labels(batch: Batch, paper: Literal["a4", "a6"] = "a4"):
        return label_pdf(batch, paper)

    @app.get("/v1/capabilities", dependencies=[Depends(auth)])
    def capabilities():
        return {"profile": "standard_v3_prepaid_yupack", "columns": 99, "details": 3,
                "encoding": "cp932", "delivery_type": delivery_type,
                "desktop_import": "manual", "printing": "manual", "carrier_api": False}

    def validate_export(batch):
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        if any(not today <= s.ship_date <= today + timedelta(days=100) for s in batch.shipments):
            raise HTTPException(422, "Ship date must be today through 100 days ahead in Japan")
        try:
            return export_csv(batch, delivery_type)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, str(exc))

    def prepare(conn, batch, key):
        digest = hashlib.sha256(batch.model_dump_json().encode()).hexdigest()
        existing = conn.execute("SELECT id,digest FROM batches WHERE idem=?", (key,)).fetchone()
        if existing:
            if existing["digest"] != digest:
                raise HTTPException(409, "Idempotency key already used for different data")
            return result(conn, existing["id"]), False
        payload = validate_export(batch)
        bid = str(uuid.uuid4())
        try:
            conn.execute("INSERT INTO batches VALUES (?,?,?,?,?)", (
                bid, key, digest, payload, datetime.now(ZoneInfo("UTC")).isoformat()))
            conn.executemany("INSERT INTO shipments(reference,batch_id) VALUES (?,?)",
                             [(s.reference, bid) for s in batch.shipments])
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Shipment reference already exists")
        return result(conn, bid), True

    @app.post("/v1/batches", dependencies=[Depends(auth)])
    def create_batch(batch: Batch, response: Response,
                     idempotency_key: str = Header(min_length=1, max_length=128)):
        if idempotency_key.startswith("draft:"):
            raise HTTPException(422, "Reserved idempotency key prefix")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            value, created = prepare(conn, batch, idempotency_key)
            response.status_code = 201 if created else 200
            return value

    @app.get("/v1/batches", dependencies=[Depends(auth)])
    def list_batches(limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        with db() as conn:
            ids = conn.execute("SELECT id FROM batches ORDER BY created DESC,id LIMIT ? OFFSET ?", (limit, offset))
            return {"items": [result(conn, row["id"]) for row in ids],
                    "total": conn.execute("SELECT count(*) FROM batches").fetchone()[0]}

    def csv_preview(raw):
        return {"rows": list(csv.reader(io.StringIO(raw.decode("cp932")))),
                "columns": 99, "encoding": "cp932", "bytes": len(raw),
                "field_names": [FIELDS[i if i < 81 else 81 + (i - 81) % 6]["name"] for i in range(99)],
                "label_generated": False, "printing_verified": False}

    @app.get("/v1/batches/{batch_id}/preview", dependencies=[Depends(auth)])
    def batch_preview(batch_id: uuid.UUID):
        with db() as conn:
            row = conn.execute("SELECT csv FROM batches WHERE id=?", (str(batch_id),)).fetchone()
            if not row:
                raise HTTPException(404, "Batch not found")
            return csv_preview(bytes(row["csv"]))

    @app.post("/v1/preview", dependencies=[Depends(auth)])
    def preview(batch: Batch):
        raw = validate_export(batch)
        return csv_preview(raw)

    @app.post("/v1/import-preview", dependencies=[Depends(auth)])
    async def import_preview(request: Request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 1048576:
                raise HTTPException(413, "Shipment CSV exceeds 1 MiB")
        try:
            batch = import_csv(bytes(raw), delivery_type)
            exported = validate_export(batch)
        except (ValueError, UnicodeError, csv.Error):
            raise HTTPException(422, "Use Upri's headerless 99-column standard v3 CSV (UTF-8/CP932), 1–100 shipments. Unsupported fields are rejected, not discarded")
        return {"batch": batch.model_dump(mode="json"), "preview": csv_preview(exported), "saved": False}

    def draft_result(conn, did):
        row = conn.execute("SELECT * FROM drafts WHERE id=?", (did,)).fetchone()
        if not row:
            raise HTTPException(404, "Draft not found")
        value = dict(row)
        value.pop("idem", None)
        value.pop("initial_digest", None)
        value["batch"] = json.loads(value.pop("payload"))
        return value

    @app.get("/v1/drafts", dependencies=[Depends(auth)])
    def list_drafts(limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        with db() as conn:
            rows = conn.execute("SELECT id,revision,created,updated,prepared_batch FROM drafts ORDER BY updated DESC,id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            return {"items": [dict(r) for r in rows], "total": conn.execute("SELECT count(*) FROM drafts").fetchone()[0]}

    @app.post("/v1/drafts", dependencies=[Depends(auth)], status_code=201)
    def create_draft(batch: Batch, response: Response,
                     idempotency_key: str | None = Header(default=None, min_length=1, max_length=128)):
        did = str(uuid.uuid4())
        now = datetime.now(ZoneInfo("UTC")).isoformat()
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            digest = hashlib.sha256(batch.model_dump_json().encode()).hexdigest()
            if idempotency_key:
                existing = conn.execute("SELECT id,initial_digest FROM drafts WHERE idem=?", (idempotency_key,)).fetchone()
                if existing:
                    if existing["initial_digest"] != digest:
                        raise HTTPException(409, "Draft idempotency key already used for different data")
                    response.status_code = 200
                    return draft_result(conn, existing["id"])
            validate_export(batch)
            conn.execute("INSERT INTO drafts(id,revision,payload,created,updated,prepared_batch,idem,initial_digest) VALUES (?,1,?,?,?,NULL,?,?)", (did, batch.model_dump_json(), now, now, idempotency_key, digest))
            return draft_result(conn, did)

    @app.get("/v1/drafts/{draft_id}", dependencies=[Depends(auth)])
    def get_draft(draft_id: uuid.UUID):
        with db() as conn:
            return draft_result(conn, str(draft_id))

    @app.put("/v1/drafts/{draft_id}", dependencies=[Depends(auth)])
    def update_draft(draft_id: uuid.UUID, update: DraftUpdate):
        validate_export(update.batch)
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = draft_result(conn, str(draft_id))
            if current["revision"] != update.revision or current["prepared_batch"]:
                raise HTTPException(409, "Draft changed or already prepared; reload before editing")
            conn.execute("UPDATE drafts SET payload=?,revision=revision+1,updated=? WHERE id=?",
                         (update.batch.model_dump_json(), datetime.now(ZoneInfo("UTC")).isoformat(), str(draft_id)))
            return draft_result(conn, str(draft_id))

    @app.post("/v1/drafts/{draft_id}/prepare", dependencies=[Depends(auth)])
    def prepare_draft(draft_id: uuid.UUID, request: DraftRevision):
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = draft_result(conn, str(draft_id))
            if current["revision"] != request.revision:
                raise HTTPException(409, "Draft changed; reload before preparing")
            if current["prepared_batch"]:
                return result(conn, current["prepared_batch"])
            value, _ = prepare(conn, Batch.model_validate(current["batch"]), f"draft:{draft_id}:{request.revision}")
            conn.execute("UPDATE drafts SET prepared_batch=? WHERE id=?", (value["id"], str(draft_id)))
            return value

    @app.post("/v1/batches/{batch_id}/events", dependencies=[Depends(auth)])
    def record_event(batch_id: uuid.UUID, event: OperatorEvent):
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result(conn, str(batch_id))
            existing = conn.execute("SELECT * FROM operator_events WHERE id=?", (str(event.event_id),)).fetchone()
            if existing:
                if (existing["batch_id"], existing["status"], existing["note"]) != (str(batch_id), event.status, event.note):
                    raise HTTPException(409, "Event ID already used for different data")
            else:
                conn.execute("INSERT INTO operator_events VALUES (?,?,?,?,?)", (str(event.event_id), str(batch_id), event.status, event.note, datetime.now(ZoneInfo("UTC")).isoformat()))
            return result(conn, str(batch_id))

    @app.get("/v1/printer", dependencies=[Depends(auth)])
    def printer_status():
        try:
            p = subprocess.run(["lpstat", "-p", "PDF"], capture_output=True, text=True, timeout=3,
                               env={**os.environ, "LC_ALL": "C"})
            status = "unavailable" if p.returncode else ("disabled" if "disabled" in p.stdout else "printing" if "now printing" in p.stdout else "idle")
        except (OSError, subprocess.TimeoutExpired):
            status = "unavailable"
        return {"queue": "PDF", "status": status, "automatic_printing": False,
                "job_to_batch_link": False, "printing_verified": False}

    @app.get("/v1/batches/{batch_id}", dependencies=[Depends(auth)])
    def get_batch(batch_id: uuid.UUID):
        with db() as conn:
            return result(conn, str(batch_id))

    @app.get("/v1/batches/{batch_id}/csv", dependencies=[Depends(auth)])
    def get_csv(batch_id: uuid.UUID):
        with db() as conn:
            row = conn.execute("SELECT csv FROM batches WHERE id=?", (str(batch_id),)).fetchone()
        if row is None:
            raise HTTPException(404, "Batch not found")
        return Response(bytes(row["csv"]), media_type="text/csv; charset=windows-31j", headers={
            "Content-Disposition": f'attachment; filename="{batch_id}.csv"', "Cache-Control": "no-store"})

    @app.post("/v1/batches/{batch_id}/history", dependencies=[Depends(auth)])
    async def history(batch_id: uuid.UUID, request: Request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 65536:
                raise HTTPException(413, "History exceeds 64 KiB")
        try:
            records = parse_history(bytes(raw))
        except (ValueError, UnicodeError, csv.Error):
            raise HTTPException(422, "Invalid history CSV; use the documented two-column export filter")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = result(conn, str(batch_id))
            known = {s["reference"]: s["tracking"] for s in current["shipments"]}
            for ref, tracking in records.items():
                if ref not in known or known[ref] not in (None, tracking):
                    raise HTTPException(409, "Unknown reference or conflicting tracking number")
            try:
                conn.executemany("UPDATE shipments SET tracking=? WHERE reference=? AND batch_id=?",
                                 [(n, r, str(batch_id)) for r, n in records.items()])
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Tracking number already assigned")
            return result(conn, str(batch_id))

    return app
