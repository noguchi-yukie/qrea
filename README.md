# qr-linker-app

FastAPI 製の QR コード紐付けアプリ。既存の QR シールと資料配布/返却の履歴を 1:1 で追跡し、在庫や回収状況を即座に把握できます。スマホ/PC ブラウザからアクセスして QR スキャン・配布登録・返却登録・一覧/CSV 出力まで完結します。

## 機能ハイライト

- **FastAPI + SQLAlchemy + SQLite**: aiosqlite を使った非同期対応 DB。単一バイナリで完結。
- **カスタム項目 5 つ**: タイトル直下に「項目1〜5」を追加入力可能。ラベル名は /settings (ナビの「初期設定」) で任意に変更できます。
- **リアルタイム QR スキャン**: ZXing の BrowserMultiFormatReader を使ってブラウザ内でカメラ読み取り。
- **画像アップロード読取**: HTTPS 制約等でカメラが使えない端末向けに、撮影済み JPG/PNG をアップロードして解析。
- **ダッシュボード / 一覧 / 詳細 / CSV**: 最新配布状況の確認や CSV エクスポートがワンクリック。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- 起動後は `http://127.0.0.1:8000` を開きます。
- **ブラウザの getUserMedia 制約により、リアルタイムスキャンは HTTPS もしくは `http://localhost` でのみ動作** します。LAN 内で他デバイスからアクセスする場合は ngrok / Cloudflare Tunnel などで HTTPS を用意してください。
- 画像アップロード読取は JPG/PNG でテスト済みですが、端末やブラウザによっては認識に失敗することがあります。うまくいかない場合は別のブラウザ/端末で試すか、実際のカメラ読み取りをご利用ください。

## Docker

```bash
docker build -t qr-linker-app .
docker run --rm -p 8000:8000 qr-linker-app
```

## QR コード仕様

- QR には一意な `qr_id` をエンコードしてください（例: `DOC-2025-000123`）。
- URL をエンコードしている場合は末尾パスまたは `qr_id`/`id` クエリを自動抽出します。ID 文字列のみでもOK。

## ディレクトリ構成

```
qr-linker-app/
├── app/
│   ├── main.py          # FastAPI ルーティング & ビジネスロジック
│   ├── db.py            # SQLAlchemy モデル・設定テーブル
│   ├── templates/       # Jinja2 テンプレート
│   └── static/          # style.css, scan.js
├── requirements.txt
└── Dockerfile
```

## 画面

1. `/scan?mode=assign|return` — ZXing で QR を読み取り、Assign/Return 画面へ遷移。
2. `/assign/{qr_id}` — 必須/任意項目 + カスタム項目 5 つを入力して配布登録。
3. `/return/{qr_id}` — 返却者や備考を記録し、状態を returned に更新。
4. `/list` — 絞り込み + クライアントサイド検索。
5. `/detail/{qr_id}` — 単票表示。
6. `/settings` — カスタム項目のラベル変更。
7. `/export.csv` — 全件 CSV。

## 既知の制限 / FAQ

| 質問 | 答え |
| --- | --- |
| カメラが起動しない | HTTPS または `http://localhost` でアクセスしてください。ブラウザ仕様で IP アドレス経由の HTTP では getUserMedia が拒否されます。 |
| 画像アップロードが失敗する | ブラウザや画像の解像度に依存します。PNG/JPG で明るい環境・ピントの合った画像をアップロードしてください。改善予定。 |
| 認証を付けたい | FastAPI の Depends + セッション/トークンを追加してください（現状は公開用）。 |

## GitHub へのデプロイ手順

1. GitHub で空のリポジトリを作成（例: `qr-linker-app`）。
2. このディレクトリで `git init && git branch -M main`。
3. `git add . && git commit -m "Initial commit"`。
4. `git remote add origin https://github.com/<your-account>/qr-linker-app.git`
5. `git push -u origin main`

Issue / PR 歓迎です 😄
