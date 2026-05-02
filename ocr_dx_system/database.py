"""
データベース操作モジュール
SQLiteへの接続・テーブル作成・保存・検索・更新を担当する
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_PATH, DOC_TYPE_RECEIPT


def get_connection() -> sqlite3.Connection:
    """DBに接続して返す。行をdict形式で取得できるよう設定する"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # フォルダがなければ作成
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # カラム名でアクセスできるようにする
    return conn


def initialize_db() -> None:
    """
    初回起動時にテーブル・インデックス・VIEWを作成する
    すでに存在する場合は何もしない（IF NOT EXISTS）
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # --- receiptsテーブル ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT,               -- 日付 YYYY-MM-DD
                store_name      TEXT,               -- 店名・事業者名
                amount          INTEGER,            -- 合計金額（円）
                tax_amount      INTEGER,            -- 消費税額（円）、不明はNULL
                purpose         TEXT,               -- 用途・摘要
                payment_method  TEXT,               -- 支払方法
                confidence      TEXT,               -- AI抽出の自信度 high/medium/low
                image_path      TEXT,               -- 保存済み画像のパス
                document_type   TEXT DEFAULT 'receipt', -- 将来拡張用
                created_at      TEXT,               -- 登録日時
                updated_at      TEXT                -- 更新日時
            )
        """)

        # --- インデックス ---
        cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON receipts(date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_store_name ON receipts(store_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_document_type ON receipts(document_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON receipts(created_at)")

        # --- 月次集計VIEW ---
        cur.execute("""
            CREATE VIEW IF NOT EXISTS monthly_summary AS
            SELECT
                strftime('%Y-%m', date) AS month,
                COUNT(*)               AS count,
                SUM(amount)            AS total
            FROM receipts
            GROUP BY month
        """)

        conn.commit()
    finally:
        conn.close()


def save_receipt(data: dict) -> int:
    """
    領収書データをDBに保存し、発行されたIDを返す
    data キー: date, store_name, amount, tax_amount, purpose,
               payment_method, confidence, image_path
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO receipts
                (date, store_name, amount, tax_amount, purpose,
                 payment_method, confidence, image_path,
                 document_type, created_at, updated_at)
            VALUES
                (:date, :store_name, :amount, :tax_amount, :purpose,
                 :payment_method, :confidence, :image_path,
                 :document_type, :created_at, :updated_at)
        """, {
            **data,
            "document_type": data.get("document_type", DOC_TYPE_RECEIPT),
            "created_at": now,
            "updated_at": now,
        })
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def search_receipts(
    date_from: Optional[str] = None,   # YYYY-MM-DD
    date_to: Optional[str] = None,     # YYYY-MM-DD
    store_name: Optional[str] = None,  # 部分一致
    amount_min: Optional[int] = None,
    amount_max: Optional[int] = None,
    document_type: Optional[str] = None,
) -> list[dict]:
    """
    条件に合う領収書一覧を返す
    条件を指定しなければ全件取得
    """
    conditions = []
    params = []

    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if store_name:
        conditions.append("store_name LIKE ?")
        params.append(f"%{store_name}%")
    if amount_min is not None:
        conditions.append("amount >= ?")
        params.append(amount_min)
    if amount_max is not None:
        conditions.append("amount <= ?")
        params.append(amount_max)
    if document_type:
        conditions.append("document_type = ?")
        params.append(document_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"SELECT * FROM receipts {where} ORDER BY date DESC"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_receipt(receipt_id: int, data: dict) -> None:
    """指定IDの領収書データを更新する（手動修正用）"""
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["id"] = receipt_id

    # dataのキーからSET句を動的に生成（id と updated_at は除く）
    fields = [k for k in data if k not in ("id",)]
    set_clause = ", ".join(f"{f} = :{f}" for f in fields)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE receipts SET {set_clause} WHERE id = :id", data)
        conn.commit()
    finally:
        conn.close()


def get_monthly_summary() -> list[dict]:
    """月次集計VIEWから月別の件数・合計金額を取得する"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM monthly_summary ORDER BY month")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_receipt(receipt_id: int) -> None:
    """指定IDの領収書をDBから削除する"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
        conn.commit()
    finally:
        conn.close()
