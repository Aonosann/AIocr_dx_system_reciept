"""
ダミーデータ投入スクリプト
動作確認・デモ用のサンプル領収書データをDBに登録する
ocr_dx_system/ の外から実行すること
"""

import sys
from pathlib import Path

# Windowsターミナルの文字コード問題を回避
sys.stdout.reconfigure(encoding="utf-8")

# ocr_dx_system/ をimport対象に追加
sys.path.insert(0, str(Path(__file__).parent / "ocr_dx_system"))

from database import initialize_db, save_receipt

SAMPLE_RECEIPTS = [
    {
        "date": "2024-04-03",
        "store_name": "セブンイレブン 渋谷店",
        "amount": 540,
        "tax_amount": 49,
        "purpose": "会議用飲料",
        "payment_method": "電子マネー",
        "confidence": "high",
        "image_path": "data/images/dummy_001.jpg",
    },
    {
        "date": "2024-04-08",
        "store_name": "東京メトロ",
        "amount": 320,
        "tax_amount": None,
        "purpose": "交通費",
        "payment_method": "電子マネー",
        "confidence": "high",
        "image_path": "data/images/dummy_002.jpg",
    },
    {
        "date": "2024-04-15",
        "store_name": "すき家 新宿東口店",
        "amount": 980,
        "tax_amount": 89,
        "purpose": "昼食（打ち合わせ）",
        "payment_method": "カード",
        "confidence": "medium",
        "image_path": "data/images/dummy_003.jpg",
    },
    {
        "date": "2024-04-22",
        "store_name": "ヤマト運輸",
        "amount": 1200,
        "tax_amount": 109,
        "purpose": "資料送付 送料",
        "payment_method": "現金",
        "confidence": "high",
        "image_path": "data/images/dummy_004.jpg",
    },
    {
        "date": "2024-05-07",
        "store_name": "スターバックス 表参道店",
        "amount": 1650,
        "tax_amount": 150,
        "purpose": "顧客打ち合わせ 飲食費",
        "payment_method": "カード",
        "confidence": "high",
        "image_path": "data/images/dummy_005.jpg",
    },
    {
        "date": "2024-05-14",
        "store_name": "Amazon.co.jp",
        "amount": 3280,
        "tax_amount": 298,
        "purpose": "備品購入（USBケーブル）",
        "payment_method": "カード",
        "confidence": "high",
        "image_path": "data/images/dummy_006.jpg",
    },
    {
        "date": "2024-05-20",
        "store_name": "ローソン 品川駅前店",
        "amount": 428,
        "tax_amount": 38,
        "purpose": "出張時 軽食",
        "payment_method": "電子マネー",
        "confidence": "medium",
        "image_path": "data/images/dummy_007.jpg",
    },
    {
        "date": "2024-06-03",
        "store_name": "日高屋 池袋東口店",
        "amount": 750,
        "tax_amount": 68,
        "purpose": "残業時 夕食",
        "payment_method": "現金",
        "confidence": "low",
        "image_path": "data/images/dummy_008.jpg",
    },
    {
        "date": "2024-06-11",
        "store_name": "JR東日本",
        "amount": 860,
        "tax_amount": None,
        "purpose": "出張 交通費",
        "payment_method": "電子マネー",
        "confidence": "high",
        "image_path": "data/images/dummy_009.jpg",
    },
    {
        "date": "2024-06-25",
        "store_name": "ビックカメラ 有楽町店",
        "amount": 12800,
        "tax_amount": 1163,
        "purpose": "備品購入（外付けSSD）",
        "payment_method": "カード",
        "confidence": "high",
        "image_path": "data/images/dummy_010.jpg",
    },
]


if __name__ == "__main__":
    initialize_db()
    for i, receipt in enumerate(SAMPLE_RECEIPTS, start=1):
        new_id = save_receipt(receipt)
        print(f"[{i:02d}] 保存完了 ID={new_id}  {receipt['store_name']} / {receipt['amount']}円")
    print(f"\n完了: {len(SAMPLE_RECEIPTS)}件のダミーデータを登録しました。")
