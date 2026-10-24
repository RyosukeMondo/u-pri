# 公式部品の自動取得（Mac / Linux・実験版）

このフォルダーにMicrosoftや日本郵便のバイナリは含みません。各利用者のPCが、公式HTTPS配布元から直接取得します。Python 3.9以降の標準ライブラリだけを使用します。

```bash
# リポジトリを取得したディレクトリで実行
python3 setup/fetch_official.py plan
python3 setup/fetch_official.py fetch
python3 setup/fetch_official.py check
# 内蔵ディスクを使わない場合
python3 setup/fetch_official.py fetch --dir /Volumes/YourSSD/Upri-official
```

Macでは `setup/Download-Official.command` を実行しても同じ取得処理になります。既定の保存先は `~/Downloads/Upri-official`。Pythonがない場合は自動で大きな開発環境を追加せず、取得先を案内します。

対象：ゆうプリR 64bit ZIP、Access Database Engine 2016 x64、.NET Framework 3.5 SP1フルパッケージ。`--only access2016` などで対象を限定できます。URL・サイズ・SHA-256は同梱の `official-sources.json` に記録しています。SHA-256はこのプロジェクトが公式配布物から記録した値で、Microsoft等が公表した署名の検証ではありません。

保存先はハードリンクを利用できるファイルシステム（Mac標準のAPFSなど）が必要です。ExFATの外付けドライブには直接保存せず、APFSディスクイメージ内などを指定してください。

同じファイルは再検証して再利用します。途中失敗時は `.part` を削除し、再実行で最初から取得します。サイズ・ハッシュ変更、公式外へのリダイレクト、既存ファイルの不一致はエラーにします。既存ファイルを勝手に上書きしません。エラー時の終了コードは1です。公式配布の更新時は、保守者が取得元と内容を確認してマニフェストを更新します。

## ダウンロード後

1. 各製品の利用条件を確認します。取得スクリプトはインストーラーを実行せず、利用規約への同意も代行しません。
2. WineとMicrosoft .NET、Access、ゆうプリRを専用環境に導入する場合は、別コマンド`uv run python setup/desktop.py install --accept-experimental`を使います。[同じPCへのセットアップ](../docs/standalone.md)を参照してください。管理用展開・部品登録方式の実験版で、標準MSI完了とは異なります。`fetch_official.py`自体は取得だけです。
3. DB接続と会員認証画面を診断します。その後、利用者が会員番号・PC ID・初回パスワードを実アプリに入力します。
4. 正式なプレビュー、発行、印刷、送信は別途検証します。

Wine自体は今回の3製品とは別のOSS互換環境です。試験で使用したMacビルドの提供元は https://github.com/Gcenx/macOS_Wine_builds 。本スクリプトはWine・Rosetta・Homebrewを追加せず、Gatekeeper設定も変更しません。

Access 2016はサポート終了済み。Mac＋Wineは実験的な構成です。公式部品を同梱しないことは、各製品の利用条件を免除する意味ではありません。

詳細： [OS別の導入](../docs/standalone.md)、[検証記録](../docs/standalone-verification.md)。
