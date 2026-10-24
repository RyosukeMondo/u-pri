#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.9以降が必要です。https://www.python.org/downloads/macos/'
  exit 1
fi
python3 fetch_official.py fetch "$@"
if [ -t 0 ]; then
  echo '公式ファイルの取得・照合が完了しました。インストール完了ではありません。README.mdをご覧ください。'
  read -r -p 'Enterで閉じます。' _
fi
