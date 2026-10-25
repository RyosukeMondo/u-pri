# OS別・同じPCだけでセットアップ

API、ブラウザー画面、SQLite、MCPをすべて手元のPCで動かします。
ネット接続はソフト取得と日本郵便の認証・通信に必要ですが、別のPCは要りません。

## 1. 共通：Upriを導入

Gitと[uv](https://docs.astral.sh/uv/getting-started/installation/)を同じPCに導入します。
macOS/LinuxはTerminal、WindowsはPowerShellでREADMEの4コマンドを実行します。
uvがPython 3.12と依存パッケージを取得します。OS全体のPythonは置き換えません。
日本語デモPDF用のIPAフォントとライセンスはリポジトリに同梱しています。

保存先：Macは`~/Library/Application Support/Upri`、Windowsは`%LOCALAPPDATA%\Upri`、
Linuxは`~/.local/share/upri`（XDG_DATA_HOME指定時はその下）。
`connection.json`にAPIキー、`upri.sqlite3`に下書き・CSV、`mcp/`にAI連携設定を保存します。
Windowsのファイル保護はユーザープロファイルのACLに依存します。共有フォルダーを指定しないでください。

`setup`は再実行してもキーとDBを残します。別ポートを使う場合はsetup/serve/doctorすべてに
`--port 18769`など同じ値を指定します。`--data-dir`でも保存先を指定できます。
serveは前景プロセスです。常駐やログイン時起動は自動登録しません。

`serve --host 0.0.0.0`で任意にLAN公開できます。初期値は127.0.0.1で、このPC内だけです。
`--host`は待受IPで、URLではありません。LAN/Tailscaleは追加機能であり必須ではありません。
LANのHTTPは暗号化されません。外部からの利用はTailscaleやHTTPSを用意してください。

## 2. Windows：公式のゆうプリR

Windows 11で[日本郵便の公式案内](https://www.post.japanpost.jp/yu-packprint-r/)から申し込み、
指定されたページ・現行手順書でインストールします。現行のAccess Runtimeなど、公式手順に従ってください。
WineやAccess 2016試験版は使いません。UpriのAPIもWindows上で動かします。

会員番号・PC ID・初回パスワードは公式アプリ内で入力します。認証・マスター取得・利用者設定後、
同じPCのブラウザーからCSVを保存し、ゆうプリRへ手動取込します。
標準フォーマットv3／ヘッダーなし／3明細グループで、配送種別`UPRI_PREPAID`を実契約・用紙に対応付けます。
Windows実機での公式導入・発行・プリンター検証は未実施です。

## 3. Mac：Mac内のWineで本体を試す

対象として試験したのはApple Silicon M4・macOS 26.1です。公式対応OSではありません。
仮想Windowsマシン、他PCの.NET、別PCのAPIは使いません。

1. 共通のUpri導入を完了します。
2. Apple SiliconでRosettaがない場合は、MacのTerminalで`softwareupdate --install-rosetta`を実行し、表示される条件を確認します。
3. 実験版の条件と取得するソフトの利用条件を確認し、次を実行します。

```sh
uv run python setup/desktop.py install --accept-experimental
uv run python setup/desktop.py status
uv run python setup/desktop.py registration
```

インストーラーはWine Staging 11.18を[Gcenxの配布元](https://github.com/Gcenx/macOS_Wine_builds/releases/tag/11.18)から取得し照合します。
.NET 3.5 SP1とAccess 2016はMicrosoft、ゆうプリRは日本郵便から取得・照合します。
自作ACE/WMIアダプターと診断プログラムはこのリポジトリのGitHub Releaseから取得します。
Macでコンパイラーを導入する必要はありません。開発用ビルド手順は`scripts/build-mac-trial-tools.sh`です。

本体は`desktop/portable/prefix`という専用Wine環境に作成します。既存のWine環境は変更しません。
Gatekeeperを全体無効化せず、OSがブロックした場合は当該アプリの信頼性を確認して個別に対応してください。
管理用展開・部品登録を使う互換実行であり、Windowsの標準MSI完了や.NET全機能の導入ではありません。
Access 2016はサポート終了済み。365版への置換は未完了です。

DB接続・端末識別・実アプリの認証画面という3つの検査で成功を判定します。
その後の会員認証・正式発行・実印刷は未検証です。認証後に本体を開く場合は`registration`を`app`に替えます。

## 4. Linux：Linux内のWineで本体を試す

APIと操作画面は共通コマンドでネイティブ実行します。
本体の実験にはx86_64 LinuxのGUIセッション、Wine（wineとwineserver）、7zが必要です。
Ubuntuでは管理者がローカルに`wine`・`p7zip-full`・`msitools`を用意し、同じPCのTerminalで上記のdesktopコマンドを実行します。
`--wine-bin /path/to/bin`でWineを選択できます。Wineは自動ダウンロードしません。
LinuxのWine 9はMSI管理用展開の一部を扱えないため、msitoolsのmsiextractで公式MSIを展開します。汎用スクリプトの新規構築でもDB・端末識別・認証画面を確認しました（ローカルXvfb画面で試験）。
最新の結果は[検証記録](standalone-verification.md)を参照してください。

## 再実行・容量・片付け

デスクトップ試験は4 GiB以上の空きを要求します。初回のWine・Microsoftファイルの取得時間は回線に依存します。
MacはAPFS、Linuxは通常のローカルファイルシステムを使います。ExFATへの直接導入は対応しません。
外付けAPFS領域なら、install/status/registration/appすべてに同じ`--directory /Volumes/YourAPFS/UpriDesktop`を追加します。
取得済み公式ファイルは`--assets /path/to/cache`で再利用できますが、毎回ハッシュを照合します。

成功したprefixは再実行で置き換えません。失敗時も残して`portable/logs`を調べ、別の新しいdirectoryで再試験します。
自動的に再認証、実発送、実印刷は行いません。再試験が既存PC IDの再利用を意味するわけではありません。

削除する場合はサーバーとWineアプリを閉じ、必要なDBをバックアップしてから、自分で指定したUpri保存先と
リポジトリだけを削除します。OSのPython・Rosetta・他アプリのWineを削除する必要はありません。
