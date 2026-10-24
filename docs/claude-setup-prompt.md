# Claude Code / Claude Desktopに渡すプロンプト

以下をコピーしてください。Claude Codeは対象PCのローカルフォルダーで使用します。
Claude Desktopの作業モードはクラウド・隔離VMで実行することがあるため、実行先の判定が必要です。
ホスト操作ができない場合はユーザーが対象PCのTerminalで実行します。
その制約を理由に、別PCのAPI構成へ変更しないでください。

```text
このPCだけでUpriをセットアップしてください。
リポジトリ: https://github.com/RyosukeMondo/u-pri

必須条件:
- API、操作画面、SQLite、MCP、ゆうプリR本体を同じ物理PCに配置する。
  別のLinux/Windows/Mac PC、SSH接続先、リモートAPIに依存しない。
- まずOS、CPU、実行場所、GUIセッション、ディスク空きを調べる。
  Claudeのクラウド/隔離VMとホストOSを区別する。MacなのにLinuxと出た場合、
  それはMac本体ではない可能性がある。ホストのTerminalで実行する。
  ホスト操作権限がなければ、必要なローカルコマンドを提示し、成功と報告しない。
- README.md、docs/standalone.md、docs/standalone-verification.mdを先に読む。
- Git/uvがなければ公式手順から導入。既存Pythonや他の環境は置換しない。
  git clone後、uv sync --frozen --python 3.12、
  uv run python scripts/local.py setup、serveで同じPCの127.0.0.1:18767に起動。
  ポート使用中なら既存プロセスを終了せず、空きポートと専用data-dirを選ぶ。
- doctorを実行し、画面とデモPDFを開く。scripts/smoke.pyを同じPCで実行して
  架空データのCSV作成、再起動後の保存、重複再送の挙動を確認する。
- Windowsは日本郵便の公式インストーラーを使用。
  Mac/LinuxはWine実験版の制約を説明し、setup/desktop.pyの手順で同じPCに構築。
  Microsoftと日本郵便のファイルは公式配布元から直接取得し、ハッシュ確認を省略しない。
  MacのRosettaなどOSが必要とする利用条件・管理者操作はユーザー本人に行ってもらう。
- MCPはsetupが生成するclaude-config.snippet.jsonを既存設定を保ってマージし、
  ホストを再起動/再読込する。APIキーやconnection.jsonをチャットへ出力しない。
- 会員番号、PC ID、初回パスワードは実アプリで本人が入力する。
  認証情報がなくても、ローカルAPI、画面、CSV、デモPDF、認証画面まで進める。
- 認証を回避せず、勝手に正式発行・データ送信・実印刷を行わない。
  会員認証画面の表示と、正式ラベルが発行できることは別として報告する。
- 最後にローカルURL、起動/停止/再開方法、保存先、確認できた機能、残る手順を報告。
  起動したプロセスが実際に稼働していることを確認し、未検証を完了扱いしない。
```

参考：[Claude Desktopの導入・隔離VMの説明](https://support.claude.com/en/articles/10065433-install-claude-desktop)、
[Claude Coworkの実行構成](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview)。
GUI操作や端末制御の可否は利用プラン・バージョン・権限で変わります。このプロンプトで権限は追加されません。
