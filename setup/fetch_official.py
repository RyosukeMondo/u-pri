#!/usr/bin/env python3
"""Fetch official prerequisites, never execute or redistribute their contents.
Python 3.9+ standard library; works on macOS and Linux.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request

HOSTS = {'www.post.japanpost.jp', 'download.microsoft.com'}


def check_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Only approved official HTTPS download hosts are allowed')
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def valid(path, asset):
    return (not path.is_symlink() and path.is_file()
            and path.stat().st_size == asset['size'] and digest(path) == asset['sha256'])


def fetch(asset, directory, opener=None):
    check_url(asset['url'])
    name = asset['filename']
    if Path(name).name != name or name in ('.', '..'):
        raise ValueError('Invalid filename')
    dest = directory / name
    if dest.is_symlink():
        raise ValueError('Refusing a symlink destination: ' + name)
    if valid(dest, asset):
        return 'verified_cached'
    if dest.exists():
        raise ValueError('Existing file differs from pinned manifest; move it aside before retrying: ' + name)
    if shutil.disk_usage(directory).free < asset['size'] + 64 * 1024 * 1024:
        raise ValueError('Insufficient free space for ' + name)
    opener = opener or urllib.request.build_opener(OfficialRedirect())
    # Create and hold an exclusive random file before any network operation.
    fd, temporary = tempfile.mkstemp(prefix='.' + name + '-', suffix='.part', dir=directory)
    part = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as out:
            with opener.open(asset['url'], timeout=60) as response:
                check_url(response.geturl())
                count = 0
                h = hashlib.sha256()
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > asset['size']:
                        raise ValueError('Download exceeds pinned size: ' + name)
                    h.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
                if count != asset['size'] or h.hexdigest() != asset['sha256']:
                    raise ValueError('Size/SHA-256 mismatch; official file may have changed: ' + name)
            # link() creates the destination only if absent; no overwrite race.
            os.link(part, dest)
        return 'downloaded_verified'
    finally:
        part.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'fetch', 'check'], nargs='?', default='fetch')
    parser.add_argument('--dir', type=Path, default=Path.home() / 'Downloads/Upri-official')
    parser.add_argument('--only', choices=['yuprir', 'access2016', 'dotnet35'], action='append')
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('official-sources.json').read_text(encoding='utf-8'))
    assets = [a for a in manifest['assets'] if not args.only or a['id'] in args.only]
    directory = args.dir.expanduser().resolve()
    if args.command == 'plan':
        print(json.dumps({'directory':str(directory), 'bytes':sum(a['size'] for a in assets),
                          'assets':assets, 'executes_installers':False}, ensure_ascii=False, indent=2))
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / '.upri-download.lock'
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    failed = False
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for asset in assets:
            try:
                state = ('verified' if valid(directory/asset['filename'], asset) else 'missing_or_changed') if args.command == 'check' else fetch(asset, directory)
                failed |= state == 'missing_or_changed'
                print(json.dumps({'asset':asset['id'],'status':state}, ensure_ascii=False), flush=True)
            except Exception as exc:
                failed = True
                print(json.dumps({'asset':asset['id'],'status':'failed','error':str(exc)},ensure_ascii=False),flush=True)
    print(json.dumps({'downloads_verified':not failed,'installation_verified':False,
                      'next':'Files verified only; see docs/standalone.md for the separate experimental desktop installer.'}),flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
