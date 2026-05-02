"""
Excel出力モジュール
検索結果の領収書データをxlsxファイルとして出力する
"""

import io
from datetime import datetime

import pandas as pd


def export_to_excel(receipts: list[dict]) -> bytes:
    """
    領収書データのリストをExcelファイル（バイト列）に変換して返す
    Gradioのファイルダウンロードに渡せる形式
    """
    df = _build_dataframe(receipts)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="領収書一覧")
        _apply_column_width(writer, df)

    return buffer.getvalue()


def _build_dataframe(receipts: list[dict]) -> pd.DataFrame:
    """
    DBから取得したdictのリストを、Excel向けに整形したDataFrameに変換する
    カラム名を日本語に変換し、不要な内部カラムは除外する
    """
    column_map = {
        "id":             "ID",
        "date":           "日付",
        "store_name":     "店名",
        "amount":         "金額（円）",
        "tax_amount":     "消費税（円）",
        "purpose":        "用途",
        "payment_method": "支払方法",
        "confidence":     "自信度",
        "document_type":  "種別",
        "created_at":     "登録日時",
    }

    df = pd.DataFrame(receipts)

    # 存在するカラムだけに絞り込んで日本語名に変換
    existing_cols = [c for c in column_map if c in df.columns]
    df = df[existing_cols].rename(columns=column_map)

    return df


def _apply_column_width(writer: pd.ExcelWriter, df: pd.DataFrame) -> None:
    """列の幅をデータの最大文字数に合わせて自動調整する"""
    worksheet = writer.sheets["領収書一覧"]
    for i, col in enumerate(df.columns):
        # ヘッダーとデータの最大文字数を取得（日本語は2倍で計算）
        header_len = len(col) * 2
        data_len = df[col].astype(str).str.len().max() if len(df) > 0 else 0
        width = max(header_len, data_len) + 2
        worksheet.column_dimensions[chr(65 + i)].width = width


def make_filename() -> str:
    """ダウンロードファイル名を「領収書_YYYYMMDD.xlsx」形式で生成する"""
    return f"領収書_{datetime.now().strftime('%Y%m%d')}.xlsx"
