"""Standard v3, fixed three details: 81 + 3 * 6 = 99 columns.

Schema attribution: spec/NOTICE.md. Byte limits are enforced strictly; never
replace unencodable characters or silently truncate customer addresses.
"""
import csv
import io
import json
from pathlib import Path

from .models import Batch

FIELDS = json.loads((Path(__file__).parent / "spec/import_v3.json").read_text(encoding='utf-8'))["fields"]
HISTORY_HEADERS = ["お客様側管理番号", "お問い合わせ番号"]


def export_csv(batch: Batch, delivery_type: str) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    for shipment in batch.shipments:
        row = [""] * 99
        values = {1: shipment.reference, 4: shipment.ship_date.strftime("%Y%m%d"),
                  6: "0", 7: "0", 8: "0", 9: "0", 54: "1", 69: delivery_type, 72: "0"}
        for addr, numbers in [(shipment.recipient, (12, 13, 14, 15, 16, 19)),
                              (shipment.sender, (28, 29, 30, 31, 32, 35))]:
            for number, value in zip(numbers, (addr.postal_code, addr.address1,
                                               addr.address2, addr.address3, addr.name, addr.phone)):
                values[number] = value
        for number, value in values.items():
            row[number - 1] = value
        for index, item in enumerate(shipment.items):
            row[82 + index * 6] = item.name
            row[83 + index * 6] = str(item.quantity)
        for index, value in enumerate(row):
            field = FIELDS[index if index < 81 else 81 + (index - 81) % 6]
            size = len(value.encode("cp932"))
            if field["bytes"] is not None and size > field["bytes"]:
                raise ValueError(f"{shipment.reference}: column {index + 1} exceeds {field['bytes']} CP932 bytes")
        writer.writerow(row)
    return out.getvalue().encode("cp932")


def parse_history(raw: bytes) -> dict[str, str]:
    import re
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp932")
    rows = csv.reader(io.StringIO(text, newline=""), strict=True)
    if next(rows, None) != HISTORY_HEADERS:
        raise ValueError("Expected two-column custom history filter: " + ",".join(HISTORY_HEADERS))
    result = {}
    for row in rows:
        if len(row) != 2 or not re.fullmatch(r"[0-9]{11,12}", row[1]):
            raise ValueError("Each history row needs a reference and an 11–12 digit tracking number")
        if row[0] in result or row[1] in result.values():
            raise ValueError("Duplicate reference or tracking number in history")
        result[row[0]] = row[1]
        if len(result) > 100:
            raise ValueError("At most 100 history records per request")
    if not result:
        raise ValueError("Empty history")
    return result


def import_csv(raw: bytes, delivery_type: str) -> Batch:
    """Import only our exact supported 99-column profile, rejecting lossy conversion."""
    from datetime import datetime
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp932')
    rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    if not 1 <= len(rows) <= 100 or any(len(row) != 99 for row in rows):
        raise ValueError('Use 1–100 headerless rows with exactly 99 columns (Upri standard v3 profile)')
    shipments = []
    for row in rows:
        shipment = {'reference': row[0], 'ship_date': datetime.strptime(row[3], '%Y%m%d').date(), 'items': []}
        for who, offset in [('recipient', 11), ('sender', 27)]:
            shipment[who] = dict(zip(('postal_code','address1','address2','address3','name','phone'),
                                    (row[offset],row[offset+1],row[offset+2],row[offset+3],row[offset+4],row[offset+7])))
        for pos in (82, 88, 94):
            if row[pos] or row[pos+1]:
                shipment['items'].append({'name': row[pos], 'quantity': int(row[pos+1])})
        shipments.append(shipment)
    batch = Batch.model_validate({'shipments': shipments})
    canonical = list(csv.reader(io.StringIO(export_csv(batch, delivery_type).decode('cp932'))))
    if rows != canonical:
        raise ValueError('CSV contains unsupported or noncanonical fields; use the Upri standard v3 export profile. No fields were discarded')
    return batch
