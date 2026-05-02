"""
Gradio WebUI メインモジュール
領収書OCRシステムのWebインターフェースを提供する

タブ構成:
  1. アップロード・解析 - 画像をアップロードしてAIで解析・保存
  2. 一覧・検索       - 保存済みデータの検索・一覧表示
  3. 月次レポート     - 月別集計グラフ・テーブル
  4. Excel出力        - 検索結果のExcelダウンロード
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd

from config import IMAGE_DIR
from database import (
    get_monthly_summary,
    initialize_db,
    save_receipt,
    search_receipts,
)
from exporter import export_to_excel, make_filename
from ocr_engine import extract_receipt_data, get_empty_receipt
from preprocessor import image_to_base64, load_image, preprocess


# ---- ヘルパー関数 ----

def _save_image_permanently(src_path: str) -> str:
    """
    Gradioが作った一時ファイルをdata/images/に恒久コピーし、保存先パスを返す
    ファイル名は「YYYYMMDD_HHMMSS_元のファイル名」形式で重複を防ぐ
    """
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = IMAGE_DIR / f"{timestamp}_{src.name}"
    shutil.copy2(src, dest)
    return str(dest)


def _to_int_or_none(value: str | None) -> int | None:
    """文字列を整数に変換する。空文字・Noneはそのまま None を返す"""
    if not value or not str(value).strip():
        return None
    try:
        return int(str(value).replace(",", "").replace("円", "").strip())
    except ValueError:
        return None


# ---- イベントハンドラ（ボタンを押したときに呼ばれる関数）----

def analyze_image(image_path: str | None) -> tuple:
    """
    アップロード画像を前処理してLM Studioで解析し、
    各フィールドの値とステータスメッセージをタプルで返す
    """
    if image_path is None:
        return "", "", "", "", "", "不明", "low", "⚠️ 画像をアップロードしてください"

    try:
        images = load_image(image_path)
        processed = preprocess(images[0])  # PDFは1ページ目のみ解析
        b64 = image_to_base64(processed)
        data = extract_receipt_data(b64)
        status = "✅ 解析完了！内容を確認して「保存する」を押してください。"

    except RuntimeError as e:
        # リトライ上限に達した場合 → 手動入力フォームとして使ってもらう
        data = get_empty_receipt()
        status = f"⚠️ AIの読み取りに失敗しました。手動で入力してください。\nエラー: {e}"

    except Exception as e:
        data = get_empty_receipt()
        status = f"❌ 予期しないエラー: {e}"

    return (
        data.get("date") or "",
        data.get("store_name") or "",
        str(data.get("amount") or ""),
        str(data.get("tax_amount") or ""),
        data.get("purpose") or "",
        data.get("payment_method") or "不明",
        data.get("confidence") or "low",
        status,
    )


def save_to_db(
    image_path: str | None,
    date: str,
    store_name: str,
    amount: str,
    tax_amount: str,
    purpose: str,
    payment_method: str,
    confidence: str,
) -> str:
    """フォームの入力値をDBに保存してステータスメッセージを返す"""
    if image_path is None:
        return "❌ 画像がありません。先にアップロードしてください。"
    if not store_name and not amount:
        return "❌ 店名または金額を入力してください。"

    try:
        saved_path = _save_image_permanently(image_path)
        receipt_data = {
            "date":           date or None,
            "store_name":     store_name or None,
            "amount":         _to_int_or_none(amount),
            "tax_amount":     _to_int_or_none(tax_amount),
            "purpose":        purpose or None,
            "payment_method": payment_method,
            "confidence":     confidence,
            "image_path":     saved_path,
        }
        new_id = save_receipt(receipt_data)
        return f"✅ 保存しました（ID: {new_id}）"

    except Exception as e:
        return f"❌ 保存に失敗しました: {e}"


def search(
    date_from: str,
    date_to: str,
    store_name: str,
    amount_min: str,
    amount_max: str,
) -> pd.DataFrame:
    """検索条件に合う領収書をDataFrameで返す"""
    receipts = search_receipts(
        date_from=date_from or None,
        date_to=date_to or None,
        store_name=store_name or None,
        amount_min=_to_int_or_none(amount_min),
        amount_max=_to_int_or_none(amount_max),
    )
    if not receipts:
        return pd.DataFrame()

    df = pd.DataFrame(receipts)
    display_cols = ["id", "date", "store_name", "amount", "tax_amount",
                    "purpose", "payment_method", "confidence", "created_at"]
    return df[[c for c in display_cols if c in df.columns]]


def update_monthly() -> tuple[pd.DataFrame, pd.DataFrame]:
    """月次集計データを取得してグラフ用DataFrameとテーブル用DataFrameを返す"""
    summary = get_monthly_summary()
    if not summary:
        empty = pd.DataFrame(columns=["month", "count", "total"])
        return empty, empty
    df = pd.DataFrame(summary)
    return df, df


def download_excel(
    date_from: str,
    date_to: str,
    store_name: str,
    amount_min: str,
    amount_max: str,
) -> str | None:
    """現在の検索条件でExcelを生成し、一時ファイルのパスを返す"""
    receipts = search_receipts(
        date_from=date_from or None,
        date_to=date_to or None,
        store_name=store_name or None,
        amount_min=_to_int_or_none(amount_min),
        amount_max=_to_int_or_none(amount_max),
    )
    if not receipts:
        return None

    excel_bytes = export_to_excel(receipts)
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".xlsx", prefix="receipts_"
    )
    tmp.write(excel_bytes)
    tmp.close()
    return tmp.name


# ---- Gradio UI定義 ----

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="領収書OCRシステム") as app:

        gr.Markdown("# 🧾 領収書OCRシステム")
        gr.Markdown("領収書画像をアップロードするとAIが自動で項目を読み取ります。")

        with gr.Tabs():

            # ========== タブ1: アップロード・解析 ==========
            with gr.Tab("📷 アップロード・解析"):
                with gr.Row():

                    # 左カラム: 画像アップロード
                    with gr.Column(scale=1):
                        upload = gr.Image(
                            label="領収書画像（JPG / PNG / PDF）",
                            type="filepath",
                        )
                        analyze_btn = gr.Button("🔍 解析する", variant="primary")

                    # 右カラム: 抽出結果フォーム（編集可能）
                    with gr.Column(scale=1):
                        gr.Markdown("#### 抽出結果（修正できます）")
                        f_date    = gr.Textbox(label="日付（YYYY-MM-DD）")
                        f_store   = gr.Textbox(label="店名")
                        f_amount  = gr.Textbox(label="金額（円）")
                        f_tax     = gr.Textbox(label="消費税（円）")
                        f_purpose = gr.Textbox(label="用途・摘要")
                        f_payment = gr.Dropdown(
                            label="支払方法",
                            choices=["現金", "カード", "電子マネー", "不明"],
                            value="不明",
                        )
                        f_conf = gr.Dropdown(
                            label="AIの自信度",
                            choices=["high", "medium", "low"],
                            value="low",
                        )
                        save_btn  = gr.Button("💾 保存する", variant="primary")
                        status_msg = gr.Textbox(
                            label="ステータス", interactive=False, lines=2
                        )

                # 解析ボタン → analyze_image → 各フィールドとステータスに反映
                analyze_btn.click(
                    fn=analyze_image,
                    inputs=[upload],
                    outputs=[f_date, f_store, f_amount, f_tax,
                             f_purpose, f_payment, f_conf, status_msg],
                )

                # 保存ボタン → save_to_db → ステータスに反映
                save_btn.click(
                    fn=save_to_db,
                    inputs=[upload, f_date, f_store, f_amount,
                            f_tax, f_purpose, f_payment, f_conf],
                    outputs=[status_msg],
                )

            # ========== タブ2: 一覧・検索 ==========
            with gr.Tab("🔎 一覧・検索"):
                gr.Markdown("保存済みの領収書を条件で絞り込んで表示します。")
                with gr.Row():
                    s_date_from  = gr.Textbox(label="日付（開始）", placeholder="2024-01-01")
                    s_date_to    = gr.Textbox(label="日付（終了）",  placeholder="2024-12-31")
                    s_store      = gr.Textbox(label="店名（部分一致）")
                    s_amount_min = gr.Textbox(label="金額（最小）")
                    s_amount_max = gr.Textbox(label="金額（最大）")

                search_btn = gr.Button("🔍 検索", variant="primary")
                result_df  = gr.DataFrame(label="検索結果")

                search_btn.click(
                    fn=search,
                    inputs=[s_date_from, s_date_to, s_store,
                            s_amount_min, s_amount_max],
                    outputs=[result_df],
                )

            # ========== タブ3: 月次レポート ==========
            with gr.Tab("📊 月次レポート"):
                gr.Markdown("月別の合計金額と件数を集計します。")
                refresh_btn = gr.Button("🔄 集計を更新", variant="primary")

                monthly_chart = gr.BarPlot(
                    label="月別合計金額",
                    x="month",
                    y="total",
                    x_title="月",
                    y_title="合計金額（円）",
                )
                monthly_table = gr.DataFrame(label="月次集計テーブル")

                refresh_btn.click(
                    fn=update_monthly,
                    outputs=[monthly_chart, monthly_table],
                )

            # ========== タブ4: Excel出力 ==========
            with gr.Tab("📥 Excel出力"):
                gr.Markdown("検索条件を入力してExcelファイルをダウンロードします。")
                gr.Markdown("（条件を入力しない場合は全件が出力されます）")
                with gr.Row():
                    e_date_from  = gr.Textbox(label="日付（開始）", placeholder="2024-01-01")
                    e_date_to    = gr.Textbox(label="日付（終了）",  placeholder="2024-12-31")
                    e_store      = gr.Textbox(label="店名（部分一致）")
                    e_amount_min = gr.Textbox(label="金額（最小）")
                    e_amount_max = gr.Textbox(label="金額（最大）")

                export_btn  = gr.Button("📥 Excelダウンロード", variant="primary")
                export_file = gr.File(label="ダウンロードファイル")

                export_btn.click(
                    fn=download_excel,
                    inputs=[e_date_from, e_date_to, e_store,
                            e_amount_min, e_amount_max],
                    outputs=[export_file],
                )

    return app


# ---- エントリーポイント ----

if __name__ == "__main__":
    initialize_db()         # DBとテーブルを初期化（初回のみ作成、2回目以降は何もしない）
    app = build_ui()
    app.launch(
        server_name="127.0.0.1",  # ローカルのみ（外部には公開しない）
        server_port=7860,
        share=False,
    )
