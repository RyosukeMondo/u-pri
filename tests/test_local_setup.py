import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_setup', ROOT / 'scripts/local.py')
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def test_setup_preserves_key_and_local_mcp(tmp_path):
    cmd = [sys.executable, str(ROOT / 'scripts/local.py'), 'setup', '--data-dir', str(tmp_path), '--port', '19876']
    first = subprocess.run(cmd, capture_output=True, text=True, check=True)
    original = (tmp_path / 'connection.json').read_bytes()
    (tmp_path / 'upri.sqlite3').write_bytes(b'preserve database')
    second = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert (tmp_path / 'connection.json').read_bytes() == original
    assert (tmp_path / 'upri.sqlite3').read_bytes() == b'preserve database'
    conf = json.loads(original)
    assert conf['url'] == 'http://127.0.0.1:19876'
    assert json.loads((tmp_path / 'mcp/connection.json').read_text(encoding='utf-8')) == conf
    assert conf['token'] not in first.stdout + second.stdout
    assert conf['token'] not in (tmp_path / 'mcp/claude-config.snippet.json').read_text(encoding='utf-8')


def test_mismatched_port_does_not_overwrite(tmp_path):
    import pytest
    local.connection(tmp_path, 19876, create=True)
    old = (tmp_path / 'connection.json').read_bytes()
    with pytest.raises(RuntimeError, match='Port differs'):
        local.connection(tmp_path, 19877, create=True)
    assert (tmp_path / 'connection.json').read_bytes() == old


def test_clean_checkout_has_no_missing_gallery_links(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from upri.api import create_app
    monkeypatch.setenv('UPRI_DEMO_LAYOUT_DIR', str(tmp_path / 'no-gallery'))
    with TestClient(create_app(db_path=tmp_path/'db', token='x'*40)) as client:
        assert '/demo-layouts/' not in client.get('/demo').text
        pdf = client.get('/demo-label.pdf?paper=a4')
        assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
