# Hermes Fast Chat

モデルと Fast を指定して新しい CLI/TUI セッションを起動する独立したプラグインです。
Hermes のコアファイルやデフォルト設定を書き換えません。

## インストール

GitHub からインストールできます。

```bash
hermes plugins install iyoda/hermes-fast-chat --enable
```

手動で配置する場合は次の手順を使います。

対象プロファイルのプラグインディレクトリに、このディレクトリ全体を
`fast-chat` という名前でコピーしてください。コピー先は対象プロファイルの
`HERMES_HOME/plugins/fast-chat` です。上書きせず、新規ディレクトリとして配置します。

```bash
hermes plugins validate /absolute/path/to/fast-chat
hermes plugins enable fast-chat
```

名前付きプロファイルの場合は enable と起動の両方に `-p <profile>` を付けます。
CLI コマンド登録には、既定の `plugins.isolation: in_process` が必要です。
`host` モードでは Hermes がプラグインの CLI コマンド登録をスキップします。

## 起動

```bash
hermes fast-chat --model <model> --provider <provider>
hermes fast-chat --tui --model <model> --provider <provider>
hermes -p <profile> fast-chat --tui --model <model>
```

`--provider` は省略できます。`--reasoning <level>`、`--tier ultrafast`、
`--in <directory>` にも対応します。`--hermes-bin /absolute/path/to/hermes` で
起動する Hermes 実行ファイルを明示できます。

`--model` だけではプロバイダーは変更しません。例えばデフォルトが Anthropic で、
OpenAI Codex のモデルを利用する場合は、次のように明示します。

```bash
hermes fast-chat --model gpt-6.1-sol --provider openai-codex
```

公開 CLI の `hermes gateway attach --start --json` で認証情報を取得し、
公開 JSON-RPC の `session.create` にモデルと `service_tier` を渡します。
同じ接続で `config.set fast` の対応モデル・利用権限チェックを通してから、
TUI は `hermes --tui --resume <session-id>` で起動します。CLI は公開プラグイン API の
`cli.HermesCLI` にモデル・プロバイダー・セッション ID と速度を引き継いで起動します。
旧版 CLI が空セッションの再開でデフォルト値を保持する場合にも対応します。
推論はこの段階では行いません。
再接続・Gateway 再起動に備えて tier は作成時のセッション設定にも保存します。

`gateway attach` のない旧版では `gateway ensure --json` で接続先を確認し、
同じユーザーのローカル制御ソケットから単回利用の接続チケットを取得します。
この互換経路は macOS/Linux 向けで、ソケットの所有者・権限・接続相手 UID と
Gateway のプロファイル・インスタンス ID を確認します。非公開の Hermes Python API の
インポートやコア変更は行いません。

対応していないモデルや利用権限ではエラーで停止します。その場合、作成済みの空の
セッションが残ることがあります。表示されたセッション ID で確認できます。
Gateway の対応判定を通っても、実際に要求した速度で処理されるかはプロバイダー次第です。

## セキュリティ・プロセスの開示

- `ctx.register_cli_command` で `fast-chat` コマンドのみを登録します。
  モデル用ツール、フック、ミドルウェア、Desktop UI は追加しません。
- 指定された Hermes 実行ファイルをシェルを介さず直接起動します。
  信頼できる実行ファイルを指定してください。Gateway の起動と、`--tui` 指定時の
  対話フロントエンドに使用します。起動した Gateway は終了後も稼働し得ます。
- 認証された WebSocket で Hermes Gateway に接続します。旧版の互換経路は
  ループバック限定で、必要に応じて対象プロファイルの `gateway.sock.path` を読み、
  同一ユーザーの Unix 制御ソケットに接続します。新経路は `gateway attach` が
  返した接続先を使用します。
- 単回利用の Gateway 接続情報をメモリ上で扱います。`.env`、`auth.json`、
  キーチェーン、プロバイダーの認証ストアは読みません。接続情報も保存しません。
  プロバイダー認証とセッション保存は Hermes が管理します。
- Hermes を通して新規セッションと起動設定を保存します。プロファイルの
  デフォルト設定は変更しません。起動後は通常の Hermes フロントエンドと Gateway が
  設定済みプロバイダーへの通信や承認されたツール実行を行い得ます。
  Fast モードはプロバイダーの追加料金が発生する場合があります。
- テレメトリ、自動更新、承認回避、無人実行モードは追加しません。
  対話端末向けのコマンドであり、cron やエージェントのツールからの実行向けではありません。

## 要件と制限

- Hermes >=0.23.0 をサポート下限とします。それ以前の全バージョンが非互換という意味では
  ありません。必要な Gateway の契約は実行時に確認します。
- Python 3.11 以上、`websockets>=15,<16`（対応する Hermes 実行環境に含まれます）。
- Gateway が `gateway ensure`、セッション作成の `service_tier`、`config.set fast`
  に対応していること。Windows は `gateway attach` も必要です。
  起動時に作成契約を確認し、非対応の Gateway では停止します。
- 毎回、新しいセッションを作成します。既存セッションのモデルや速度は変更しません。
- 通常のモデル・ツール設定は Gateway のプロファイルから読みます。
  シェル固有の追加環境変数、クライアントへの一時的な API キー引き渡しには未対応です。
- CLI/TUI の対話は親プロセスの端末を引き継ぎます。

プラグイン登録前でも、`websockets` が入っている Python で動作確認できます。

```bash
python /absolute/path/to/fast-chat/launcher.py --tui --model <model>
```

テストは Hermes リポジトリの `scripts/run_tests.sh` から、このプラグインの
`tests/test_fast_chat.py` を指定して実行できます。ローカルの WebSocket サーバーで
CLI/TUI の RPC と再開引数、利用不可時の停止を検証し、有料 API は呼びません。
