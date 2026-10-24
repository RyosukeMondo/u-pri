# Upri — 1台で動かす発送準備API・画面・MCP

Windows・macOS・Linuxそれぞれの**同じPC内**にAPI、操作画面、SQLite、
AI用MCPクライアントを導入します。別のUbuntu・Windows PCは不要です。

**できること：**手入力／99列CSV／REST APIで下書き作成、内容プレビュー、
ゆうプリR取込用CSVの出力、作業状況の手動記録。
**未検証：**日本郵便の会員認証後の正式ラベル発行・実印刷。
CSV作成は印刷完了ではありません。日本郵便の公式サービスではありません。

## まずローカルで起動

[uv公式手順](https://docs.astral.sh/uv/getting-started/installation/)でuvを導入し、
このリポジトリを取得します。Pythonはuvが同じPCに用意します。

```sh
git clone https://github.com/RyosukeMondo/u-pri.git
cd u-pri
uv sync --frozen --python 3.12
uv run python scripts/local.py setup
uv run python scripts/local.py serve
```

ブラウザーで **http://127.0.0.1:18767/demo** を開くと、キー不要で架空データを試せます。
実際の下書きは **http://127.0.0.1:18767/** を使います。
APIキーのファイルはsetupが場所だけ表示します。キーをチャットに貼らないでください。
端末を閉じるとサーバーは停止します。同じserveコマンドで再開できます。

別のローカルTerminalで確認：

```sh
uv run python scripts/local.py doctor
```

## 同じPCでゆうプリR本体も使う

| OS | 本体の導入 | 状態 |
|---|---|---|
| Windows 11 | 日本郵便の公式インストーラー・現行手順を使用 | 公式対応OS。プロジェクトの実機印刷検証は未実施 |
| Mac | 同じMac内にWine＋Microsoft .NET＋Access 2016＋ゆうプリRを取得・構築 | 実験版。Mac M4でDB・端末識別・会員認証画面まで確認 |
| Linux | 同じLinux内にWine＋同じMicrosoft部品＋ゆうプリRを構築 | 実験版。既存Ubuntu環境の認証画面を確認。新しい汎用導入コマンドの結果は検証記録参照 |

Mac/Linux試験版（GUIセッションのTerminalで実行）：

```sh
uv run python setup/desktop.py install --accept-experimental
uv run python setup/desktop.py registration
```

Wine・Rosettaなどの条件、取得元、再実行・削除方法は **[OS別セットアップ](docs/standalone.md)** を読んでください。
MacではWineを配布元から自動取得します。LinuxではローカルにWineと7zの導入が必要です。
Microsoft・日本郵便のソフトは公式配布元から直接取得し、ここには同梱しません。
自作互換部品のみGitHub ReleaseからSHA-256照合して取得します。

## Claudeに導入を依頼

**[コピーして使えるプロンプト](docs/claude-setup-prompt.md)** — Claude Code／Claude Desktop作業モード向け。
Claude Desktopのクラウド・隔離VM内への導入を、Mac本体への導入と誤認しないようにしてください。

`setup`が同じPCの127.0.0.1に接続するMCP設定を生成します。
APIキーを含まない`mcp/claude-config.snippet.json`を既存のMCP設定にマージし、
ホストを再起動します。4つのツールは下書き準備・取得用で、`print_label`はありません。
[APIと操作画面](docs/dashboard.md) ／ [検証結果](docs/standalone-verification.md)

## 開発・公開範囲

```sh
uv run pytest
uv run python scripts/smoke.py
```

デモPDFは発送不可です。公開リポジトリに顧客データ、認証情報、公式インストーラー、
同梱RPX帳票、私用の試験環境を含めません。558件の帳票ギャラリーも同梱しません。
自作コードはMIT、参照スキーマはCC BY 4.0、同梱IPAゴシックはIPAフォントライセンスv1.0です。
