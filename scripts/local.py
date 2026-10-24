"""Same-computer Upri setup, server and diagnostics. Run with uv run python."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def default_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Upri'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Upri'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'upri'


def connection(directory, port, create=False):
    directory = directory.expanduser().resolve()
    path = directory / 'connection.json'
    if path.is_symlink():
        raise RuntimeError('Refusing symlink connection file')
    if create:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as f:
                json.dump({'url': f'http://127.0.0.1:{port}', 'token': secrets.token_urlsafe(36)}, f)
    data = json.loads(path.read_text(encoding='utf-8'))
    if len(data.get('token', '')) < 32:
        raise RuntimeError('Invalid private connection file; do not overwrite existing data')
    if data['url'] != f'http://127.0.0.1:{port}':
        raise RuntimeError('Port differs from saved configuration; use the original --port or a separate --data-dir')
    return directory, data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['setup', 'serve', 'doctor'])
    p.add_argument('--data-dir', type=Path, default=default_directory())
    p.add_argument('--host', default='127.0.0.1', help='Bind IP; local-only by default')
    p.add_argument('--port', type=int, default=18767)
    a = p.parse_args()
    if '%' in a.host or not 1 <= a.port <= 65535:
        p.error('Use an unscoped bind IP and a port from 1 to 65535')
    ipaddress.ip_address(a.host)
    directory, data = connection(a.data_dir, a.port, create=a.command == 'setup')
    if a.command == 'setup':
        subprocess.run([sys.executable, str(ROOT / 'client/install.py'), '--host', data['url'],
                        '--directory', str(directory / 'mcp'), '--token-stdin'],
                       input=data['token'] + '\n', text=True, check=True)
        print('Ready. Start: uv run python scripts/local.py serve (use the same --data-dir / --port if customized)')
        print('Dashboard: ' + data['url'] + '/; fictional demo: ' + data['url'] + '/demo')
        print('Private API key: ' + str(directory / 'connection.json') + ' (do not paste into chat)')
        return
    if a.command == 'serve':
        os.environ.update(UPRI_API_TOKEN=data['token'], UPRI_DB=str(directory / 'upri.sqlite3'))
        import uvicorn
        from upri.api import create_app
        uvicorn.run(create_app(), host=a.host, port=a.port, access_log=False)
        return
    # Verify this instance, including authentication; a different service on this port must fail.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path in ['/health', '/v1/capabilities', '/demo', '/demo-label.pdf?paper=a4']:
        req = urllib.request.Request(data['url'] + path, headers={'Authorization': 'Bearer ' + data['token']})
        with opener.open(req, timeout=15) as response:
            body = response.read()
            if path.endswith('paper=a4') and not body.startswith(b'%PDF'):
                raise RuntimeError('Demo PDF failed')
            print('OK ' + path)
    print('Local API/dashboard/demo PDF verified. Carrier authentication and shipping are NOT verified.')


if __name__ == '__main__':
    main()
