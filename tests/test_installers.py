import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_reinstall_does_not_follow_symlinks(tmp_path):
    dest = tmp_path / "client"
    dest.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.write_text("PRESERVE ME")
    for name in ("connection.json", "upri_mcp.py", "batch.schema.json", "claude-config.snippet.json"):
        (dest / name).symlink_to(unrelated)
    r = subprocess.run([sys.executable, str(ROOT / 'client/install.py'), '--host', 'http://127.0.0.1:18767',
                        '--token-stdin', '--directory', str(dest)], input='t' * 40 + '\n', text=True,
                       capture_output=True)
    assert r.returncode == 0, r.stderr
    assert unrelated.read_text(encoding='utf-8') == "PRESERVE ME"
    assert not (dest / 'connection.json').is_symlink()
    assert dest.stat().st_mode & 0o777 == 0o700
    assert (dest / 'connection.json').stat().st_mode & 0o777 == 0o600
    assert json.loads((dest / 'connection.json').read_text(encoding='utf-8'))['token'] == 't' * 40
    assert 't' * 40 not in r.stdout


def test_service_host_rejects_scope_injection(tmp_path):
    for host in ('::1%\nExecStartPre=touch REVIEW_PROBE\n#', '::1%lo --workers 99', '127.0.0.1\n'):
        r = subprocess.run(['bash', str(ROOT / 'scripts/install-service.sh'), '--host', host],
                           capture_output=True, text=True)
        assert r.returncode != 0
        assert 'Scoped addresses' in r.stderr


def test_client_schema_is_current():
    from upri.models import Batch
    assert json.loads((ROOT / 'client/batch.schema.json').read_text(encoding='utf-8')) == Batch.model_json_schema()
