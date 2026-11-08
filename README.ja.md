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
```

Hermes >=0.23.0 と既定の `plugins.isolation: in_process` が必要です。
Fast の利用可否と料金はプロバイダーと利用権限に依存し、追加料金が発生する場合があります。

## 役割

独自設定・モデル用ツール・本体へのパッチを持たない、起動専用プラグインです。
本体に同等の起動方法が整ったら、そちらの利用を優先します。

起動準備では Gateway が起動して終了後も稼働する場合があり、新規セッションを保存します。
この段階で推論を送信したり、プロバイダーの認証ストアを読んだりはしません。
検証失敗時は空のセッションが残る場合があります。

全オプション・経路選択・互換性・安全性の開示・開発手順は
[技術リファレンス（英語）](docs/technical-reference.md)にまとめています。
不具合は [GitHub Issues](https://github.com/iyoda/hermes-fast-chat/issues) へ。
