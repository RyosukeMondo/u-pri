# Operations dashboard

Desired state: a browser operator can edit shipment data, review the exact CSV,
prepare it once, and record manual work without turning a report into a verified
print result.
Raw inputs: `batches`, `shipments`, revisioned `drafts`, append-only
`operator_events` in SQLite; immutable CSV blobs; the local CUPS `PDF` queue.
Method/tools: SQLite transactions and revision checks; FastAPI; same-origin vanilla
JavaScript; `uv run pytest -q`; local browser verification.
Baseline: dashboard `/` returned HTTP 404; live database had 0 batches / 0 shipments.
Target: one complete browser draft → review → CSV → report/history workflow, with
no duplicate batch on retry and no verified-print claim. Installation-time target
remains unmeasured.
Outside judge: fresh-context attacker/on-call reviewer, independent temporary-DB
checks, and a real browser exercising the HTTP service.
Scope: actual carrier authentication, automatic import/printing, and real label
verification remain gated by the owner's Japan Post account setup.

## Operator workflow

Open `/` on the existing Upri server. Use the **Upri API token** from the local `connection.json` whose location is printed by `scripts/local.py setup`
(or your existing private client configuration), not a Japan Post password.
The token stays in tab memory; reload requires re-entry. Use the lock button when
finished. LAN HTTP is for a trusted LAN; Tailscale provides an encrypted path for
already enrolled peers. No token is placed in a URL, cookie or localStorage.

1. Select **新しい下書き**. Enter recipient, sender, ship date and item details.
   Add up to 100 shipments, each with up to three items.
2. Save the draft or choose **保存してCSV内容を確認**. The server validates
   required fields, Japanese ship dates, CP932 encoding and byte limits.
3. Review the actual populated CSV columns. This is a data preview, not a rendered
   shipping label. Confirm to freeze the draft and create one immutable CSV batch.
4. Download the CSV for manual import in ゆうプリR. Prepared drafts cannot be edited;
   use a new draft and new management references for a new preparation.
5. Record manual import/print/failed/uncertain reports and notes. Reports are
   append-only; a later report can correct the operational status without deleting
   the earlier report. No report makes `printing_verified` true.
6. Upload the documented two-column history export to reconcile tracking numbers.
   File provenance remains the operator's responsibility. History reconciliation
   does not prove carrier acceptance or printing.

The PDF card reports the queue's current state when refreshed. It does not match
CUPS jobs to shipment batches, monitor other printers, or submit any print job.
Browser lists are paginated. The dashboard and existing MCP client share the same
batch API; older batches remain visible and their CSV data remains readable.

## Additional REST endpoints

All `/v1/` endpoints require the existing bearer token.

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/drafts?limit=30&offset=0` | Paginated draft list |
| `POST /v1/drafts` | Save validated Batch JSON; optional `Idempotency-Key` for creation retries |
| `GET /v1/drafts/{id}` | Draft payload, revision and prepared batch link |
| `PUT /v1/drafts/{id}` | `{revision, batch}`; stale/frozen updates return 409 |
| `POST /v1/drafts/{id}/prepare` | `{revision}`; transactional preparation and stable retry result |
| `POST /v1/preview` | Validate Batch JSON and return the exact CSV cells/field names without storing |
| `GET /v1/batches?limit=30&offset=0` | Paginated prepared batches and their statuses |
| `GET /v1/batches/{id}/preview` | Decode the stored immutable CSV, including legacy batches |
| `POST /v1/batches/{id}/events` | `{event_id, status, note}`; UUID-keyed idempotent operator report |
| `GET /v1/printer` | Read-only availability of the fixed `PDF` queue |

Event status values: `import_reported`, `print_reported`, `print_failed`,
`print_uncertain`. Batches keep the original `csv_prepared` / `history_received`
state independently. `operator_status` reflects the most recent report, not an
inferred stage. Existing create/download/history routes remain available.
The `draft:` batch idempotency-key prefix is reserved for internal preparation.

## Integrity and privacy

Preparation compares the revision and creates/links the batch in one SQLite
transaction. Concurrent retries return one batch; conflicting references roll
back without freezing the draft. Prepared CSVs are immutable. Edits made from a
stale tab return 409; reload the draft before continuing.

Authenticated responses and static pages use `no-store`. The UI renders data as
text, uses a restrictive CSP, clears draft retry data on lock, aborts pending
requests, and rejects late responses from an earlier unlocked session. Editing
is frozen during save and prepare so pending responses cannot erase new typing.
Drafts and notes contain personal data and persist in the existing protected DB;
no automatic retention/deletion policy is added.

## Verification

```bash
uv run pytest -q
uv run python scripts/local.py doctor
```

Historical development browser verification (not included in this release) used a temporary database, random token, local ephemeral HTTP
server, synthetic addresses, and synthetic history. It never reads production
credentials or sends print jobs. Screenshots go to ignored `research/logs/`.
It covers CP932 download, duplicate preparation, manual status separation, XSS as
text, mobile overflow, pending-edit protection, lock cleanup and late-response
rejection. Desktop-generated labels/history are still unverified.

Red-team reproduced and prompted fixes for three findings: edits during save,
retry fingerprints retained after lock, and edits during CSV preparation.

## Achieved checkpoint — 2026-10-24

Target workflow: **1 / 1 complete synthetic browser workflow passed**, including
save/prepare edit protection, single-batch retry, manual uncertainty report,
history reconciliation and lock/late-response checks. Full suite: **20 passed**.
Fresh adversarial review independently reran the browser workflow and 17 API/
dashboard tests; all three reproduced UI findings were fixed and rechecked.

Live deployment: existing `upri-api` restarted after a protected SQLite backup.
Dashboard changed from HTTP 404 to **200**. Live authenticated browser read/lock
passed; LAN access from `mac_m4` returned 200; its existing four-tool MCP client
passed SDK initialization and capabilities checks. No Mac installation changed.
Production remains at **0 drafts / 0 batches / 0 shipments**, and SQLite integrity
is `ok`. No physical or virtual print job was submitted by dashboard verification.
The PDF queue is read-only status information; actual app-generated labels remain
unverified and the carrier-authentication goal remains blocked.

## Public showcase and supported input

`/demo` needs no token. It runs the same editor, preview and batch views against
fictional, tab-memory data. It never calls `/v1/`, accesses the SQLite database,
or reads/submits printer jobs. Refresh resets the demo. Demo downloads are marked
`DEMO-NOT-FOR-SHIPPING` and use UTF-8; their addresses and tracking values are
explicitly fictional. Do not enter real customer data in the showcase.

| Input | Live behavior |
| --- | --- |
| Manual dashboard entry | Up to 100 shipments, 3 items each; validated draft editing |
| REST/MCP Batch JSON | Same shipment/address/item model |
| Shipment CSV | `POST /v1/import-preview`; headerless 99-column Upri standard-v3 profile, CP932 or UTF-8, up to 100 rows / 1 MiB |
| History CSV | Existing two-column reference/tracking export, up to 64 KiB |

Shipment CSV import is a review step: it populates the same editor as manual
entry without saving a draft or creating a batch. It must round-trip exactly to
our supported export profile. Unsupported columns, service options, or data that
would be discarded are rejected. Arbitrary Excel files, other carriers' CSVs, and
other ゆうプリR profiles are not supported by this importer.

The shared **発送内容のレイアウト** component renders recipient, sender, ship date,
management reference and items from the common CSV field mapping. It is reused
for manual entry, imported CSVs, saved draft review, existing batch inspection and
the showcase. Editing invalidates the old preview. Preview requests freeze the
editor until completion to avoid showing a stale result.

This is a **content layout**, not an official shipping-label PDF. Dimensions,
barcode generation and label-stock placement await actual ゆうプリR verification.

## Printable demonstration labels

The showcase now offers fixed, fictional samples at `/demo-label.pdf?paper=a4`
and `?paper=a6`, without authentication. These are actual PDF print layouts:

- **A6:** 105 × 148 mm, one demo label per page.
- **A4:** 210 × 297 mm, one A6 label per page with a dotted cut boundary and a
  50 mm scale-check line. Print at **100% / actual size**, not fit-to-page.

Every label prominently says **DEMO / 発送不可**. Code128 encodes only
`DEMO-0001` (sequential within the document), never a carrier tracking number.
The samples can be cut out and attached to demonstration parcels, but cannot be
used for postal acceptance. No physical print job is submitted by opening a PDF.

The public samples are fixed data and do **not** reflect edits in the browser-only
showcase. This is stated next to their download links. The authenticated workspace
uses the same renderer for the current contents through
`POST /v1/demo-labels/pdf?paper=a4|a6`, with Batch JSON. Its content-layout panels
provide download buttons. The renderer embeds a Japanese TrueType font and rejects
text that cannot fit legibly rather than truncating names or addresses.

The same-PC API includes unmodified IPA Gothic with its license.
`UPRI_LABEL_FONT` optionally selects another Japanese TrueType font.
ReportLab runs locally on each OS. Dynamic PDF bytes are returned without being saved
on the server or changing any batch/print status.

Validation: 24 tests passed; rendered Japanese text inspected; PDF page dimensions
checked with pypdf; ZXing independently decoded `DEMO-0001` from both PDFs rendered
at 300 dpi. Reduced-size preview images are not the barcode verification source.
Physical paper output and actual Japan Post labels remain unverified.
