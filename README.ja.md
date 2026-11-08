# Hermes Fast Chat

コマンドひとつで、新しい Hermes CLI/TUI セッションを Fast モードで起動します。
本体での Fast 起動が手軽になるまでの、小さなコミュニティ製の橋渡しです。
Hermes 本体やプロファイルの既定設定は変更しません。

[English](README.md) · [プラグインカタログ](https://hermes-agent.nousresearch.com/marketplace/fast-chat) · [MIT ライセンス](LICENSE)

## インストール

```bash
hermes plugins install iyoda/hermes-fast-chat --enable
```

## 起動

```bash
hermes fast-chat
```

モデルと CLI/TUI はプロファイル設定に従います。Fast 非対応の場合は設定済みの
フォールバックを試し、全候補が非対応なら停止します。通常速度への自動切り替えはしません。
毎回、新しいセッションを作成します。

必要な場合だけ指定できます。

```bash
hermes fast-chat --tui
hermes fast-chat --model <model> --provider <provider>
hermes -p <profile> fast-chat
hermes fast-chat --help
```

名前付きプロファイルではインストール時も `-p <profile>` を付けます。
`--model` を指定すると自動フォールバックはしません。経路が曖昧な場合は
`--provider` も指定してください。フォールバックへの認証情報の直接指定は未対応です。
認証情報には名前付きプロバイダーを使います。

Hermes >=0.23.0、Python 3.11+、`websockets>=15,<16` と、既定の
`plugins.isolation: in_process` が必要です（`host` モードではCLIコマンド登録が省略されます）。
Gateway はセッション作成時の `service_tier` と `config.set fast` への対応が必要です。
Windows は `gateway attach` が必要で、動作未検証です。
Fast の利用可否と料金はプロバイダーと利用権限に依存し、追加料金が発生する場合があります。

## 役割

独自設定・モデル用ツール・本体へのパッチを持たない、起動専用プラグインです。
本体に同等の起動方法が整ったら、そちらの利用を優先します。

## 安全性と副作用

- 登録するのは `fast-chat` CLIコマンドのみ。ツール・フック・ミドルウェア・Desktop UI は追加しません。
- Gateway と TUI の起動には、指定された Hermes 実行ファイルをシェルなしで直接使います。
  信頼できる実行ファイルを指定してください。Gateway は終了後も稼働する場合があります。
- 対象プロファイルの設定を読み、認証済み Gateway WebSocket に接続します。
  旧 macOS/Linux 版ではループバック接続と同一ユーザーの Unix 制御ソケットを使い、
  所有者・権限・接続相手 UID・Gateway の識別情報を検証します。
  この経路ではプロファイルの `gateway.sock.path` ポインターを読む場合があります。
- 単回利用の接続情報はメモリ内だけで扱い、保存しません。`.env`・`auth.json`・
  キーチェーン・プロバイダーの認証ストアは読まず、認証は Hermes に任せます。
- Hermes 経由で新規セッションと起動設定を保存し、プロファイルの既定設定は変更しません。
  起動準備で推論は送信せず、検証失敗時は空セッションが残る場合があります。
  起動後は通常の Hermes／プロバイダー間の通信と、承認されたツール実行が行われ得ます。
- テレメトリ・自動更新・承認回避・無人実行モードは追加しません。
  対話端末向けであり、cron やエージェントのツールからの実行向けではありません。

## 開発

```bash
HERMES_SOURCE=/path/to/hermes-agent bash scripts/test.sh
ruff check .
hermes plugins validate .
```

テストはローカル接続を使い、有料のモデルAPIを呼びません。
不具合は [GitHub Issues](https://github.com/iyoda/hermes-fast-chat/issues) へ。
