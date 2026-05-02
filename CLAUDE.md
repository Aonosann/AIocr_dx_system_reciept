以下の仕様でPythonの領収書OCRシステムを作ってください。
将来的にフェーズ2（請求書）・フェーズ3（申請書ワークフロー）への
拡張を見越した設計にしてください。

## 概要
LM Studio（ローカルLLM）のビジョン対応モデルを使って
領収書画像を解析・構造化し、SQLiteに蓄積するDXツール。
GradioでWebUIを提供する。

## 機能一覧
1. JPG / PNG / PDF ファイルを入力として受け取る
2. PDFの場合は pymupdf（fitz）で画像に変換する（Poppler不要）
3. OpenCV で傾き補正・コントラスト補正などの前処理を行う
4. LM Studio（OpenAI互換APIサーバー）にビジョンモデル経由で画像を渡し、
   以下の項目をJSON形式で抽出する
   - date         : 日付（YYYY-MM-DD形式に統一）
   - store_name   : 店名・事業者名
   - amount       : 合計金額（整数・円）
   - tax_amount   : 消費税額（整数・円、不明な場合はnull）
   - purpose      : 用途・摘要（推測でもよい）
   - payment_method: 支払方法（現金/カード/電子マネー/不明）
   - confidence   : 抽出の自信度（high/medium/low）
5. 抽出結果をSQLiteのreceiptsテーブルに保存する
6. GradioのWebUIで以下の画面を提供する
   - アップロード画面（画像をドロップ→解析→確認→保存）
   - 一覧・検索画面（日付範囲・金額・店名でフィルタ）
   - 月次レポート画面（月別集計グラフ・合計金額）
   - Excel出力ボタン（現在の検索結果をxlsxでダウンロード）

## DB設計
receiptsテーブルに以下のカラムを含めること：
- id, date, store_name, amount, tax_amount, purpose,
  payment_method, confidence, image_path, created_at, updated_at
将来の拡張用に document_type カラム（デフォルト: 'receipt'）も追加する

## DBの追加要件
- receiptsテーブルのdocument_typeカラムは
  将来 'receipt'/'invoice'/'application' を格納する想定
- 月次集計用のVIEW（monthly_summary）も作成する
  SELECT strftime('%Y-%m', date) as month,
         COUNT(*) as count,
         SUM(amount) as total
  FROM receipts GROUP BY month

## インデックス
以下のカラムにインデックスを張ること：
- date
- store_name
- document_type
- created_at

## ディレクトリ構成
ocr_dx_system/
├── main.py              # Gradio UI
├── ocr_engine.py        # LM Studio API呼び出し・JSON抽出
├── preprocessor.py      # OpenCV前処理
├── database.py          # SQLite操作
├── exporter.py          # Excel出力
├── config.py            # 設定（モデル名・APIエンドポイントなど）
├── data/
│   ├── db/              # SQLiteファイル
│   └── images/          # 保存済み画像
└── requirements.txt

## 使用ライブラリ
openai, pymupdf, opencv-python, Pillow,
openpyxl, pandas, gradio, sqlite3（標準）

## 環境
- Windows 11
- RTX 3070Ti（VRAM 8GB）
- LM Studioをローカルで起動・ビジョン対応モデルをロード済み想定
- LM StudioのLocal Server URL: http://localhost:1234/v1
- 仮想環境（venv）を使用すること
- Pythonは3.12

## 注意事項
- LM Studio APIへのリクエストはリトライ処理（最大3回）を入れること
- JSONパースに失敗した場合はエラーをUIに表示し、手動入力できるようにする
- 画像は data/images/ にコピー保存し、DBにはパスを記録する
- requirements.txt も作成すること
- コードにはすべて日本語コメントを入れること
- LM StudioのAPIキーはダミー値（"lm-studio"）でよい（認証不要）
