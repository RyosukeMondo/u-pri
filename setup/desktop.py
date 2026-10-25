"""Install/launch the experimental local Wine desktop; never authenticates or prints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WINE_URL = 'https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.18/wine-staging-11.18-osx64.tar.xz'
WINE_SHA = 'b63704b91af269bc026a87f12bd297c4a50caaf570c322e600b6621ef918f127'


def download(url, target, sha, size=None):
    if target.is_symlink():
        raise RuntimeError('Refusing symlink download')
    if target.exists():
        with target.open('rb') as cached:
            actual_sha = hashlib.file_digest(cached, 'sha256').hexdigest()
        if actual_sha != sha:
            raise RuntimeError('Cached download mismatch; preserve it and choose a fresh directory')
        return target
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix='.download-')
    try:
        h = hashlib.sha256(); count = 0
        with os.fdopen(fd, 'wb') as out, urllib.request.urlopen(url, timeout=60) as response:
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > (size or 1024 * 1024 * 1024):
                    raise RuntimeError('Download larger than expected')
                h.update(block); out.write(block)
        if h.hexdigest() != sha or (size and count != size):
            raise RuntimeError('Download integrity check failed')
        os.link(tmp, target)
    finally:
        os.unlink(tmp)
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['install', 'registration', 'app', 'status'])
    default = Path.home() / ('Library/Application Support/Upri/desktop' if sys.platform == 'darwin' else '.local/share/upri/desktop')
    p.add_argument('--directory', type=Path, default=default)
    p.add_argument('--accept-experimental', action='store_true', help='Use experimental Wine + unsupported Access2016; review supplier terms first')
    p.add_argument('--wine-bin', type=Path, help='Directory containing wine and wineserver; Linux requires this or PATH')
    p.add_argument('--assets', type=Path, help='Optional existing official download cache; every file is reverified')
    a = p.parse_args()
    if sys.platform not in ('darwin', 'linux'):
        p.error('On Windows use the official Japan Post installer, not Wine')
    base = a.directory.expanduser().resolve()
    result_path = base / 'portable/result.json'
    if a.command == 'status':
        print(result_path.read_text(encoding='utf-8') if result_path.exists() else '{"portable_setup_verified":false}')
        return
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    # One installer per directory; do not replace or merge existing Wine prefixes.
    import fcntl
    fd = os.open(base / '.install.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config_path = base / 'desktop.json'
        if a.command != 'install':
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if not result.get('portable_setup_verified'):
                raise RuntimeError('Setup probes have not passed')
            config = json.loads(config_path.read_text(encoding='utf-8'))
            prefix = base / 'portable/prefix'
            env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all', LC_ALL='ja_JP.UTF-8',
                       WINEDLLOVERRIDES='winemenubuilder.exe=d;mscoree,mscorwks=n;ngen.exe=n')
            exe = '420107Z02P04V02.exe' if a.command == 'registration' else '420107K01P01V01.exe'
            subprocess.run([str(Path(config['wine_bin']) / 'wine'), 'C:\\ゆうプリR\\' + exe],
                           cwd=prefix / 'drive_c/ゆうプリR', env=env, check=True)
            return
        if not a.accept_experimental:
            p.error('Read docs/standalone.md and supplier terms, then add --accept-experimental')
        if (base / 'portable').exists():
            if result_path.exists() and json.loads(result_path.read_text(encoding='utf-8')).get('portable_setup_verified'):
                print('Existing verified prefix preserved. Use registration or app to launch.'); return
            raise RuntimeError('Incomplete prefix preserved. Inspect portable/logs; choose a NEW --directory to retry')
        if shutil.disk_usage(base).free < 4 * 1024**3:
            raise RuntimeError('At least 4 GiB free space is required for the desktop trial')
        if sys.platform == 'darwin':
            if platform.machine() == 'arm64' and subprocess.run(['/usr/bin/arch', '-x86_64', '/usr/bin/true'], capture_output=True).returncode:
                raise RuntimeError('Install Rosetta locally first: softwareupdate --install-rosetta (interactive license)')
            runtime = a.wine_bin or base / 'Wine Staging.app/Contents/Resources/wine/bin'
            if not (runtime / 'wine').is_file():
                archive = download(WINE_URL, base / 'wine-staging.tar.xz', WINE_SHA)
                # Python 3.12+ safe data filter also allows internal bundle symlinks.
                with tarfile.open(archive) as tar:
                    tar.extractall(base, filter='data')
        else:
            if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
                raise RuntimeError('Run from the Linux graphical desktop terminal')
            if platform.machine() not in ('x86_64', 'AMD64'):
                raise RuntimeError('The Linux desktop trial requires x86_64')
            if not shutil.which('7z') or not shutil.which('msiextract'):
                raise RuntimeError('Install p7zip-full and msitools locally first')
            runtime = a.wine_bin or Path(shutil.which('wine') or '/missing/wine').parent
        for name in ['wine', 'wineserver']:
            if not (runtime / name).is_file():
                raise RuntimeError('Missing runtime: ' + str(runtime / name))
        manifest = json.loads((ROOT / 'setup/compat-release.json').read_text(encoding='utf-8'))
        archive = download(manifest['url'], base / 'upri-compat.zip', manifest['sha256'], manifest['size'])
        helpers = base / 'helpers'; helpers.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist()) != set(manifest['files']):
                raise RuntimeError('Unexpected helper files')
            for name in manifest['files']:
                target = helpers / name
                if target.is_symlink(): raise RuntimeError('Refusing symlink helper')
                target.write_bytes(z.read(name))
        config_path.write_text(json.dumps({'wine_bin': str(runtime.resolve())}))
        assets = a.assets.expanduser().resolve() if a.assets else base / 'official'
        subprocess.run([sys.executable, str(ROOT / 'scripts/mac-trial/clean-install.py'),
                        '--base', str(base), '--name', 'portable', '--wine-bin', str(runtime),
                        '--helpers', str(helpers), '--assets', str(assets)], check=True)
        print('Local desktop probes passed. Credentials and formal shipping are still pending.')


if __name__ == '__main__':
    main()
