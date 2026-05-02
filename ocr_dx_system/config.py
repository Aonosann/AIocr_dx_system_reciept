"""
設定ファイル
LM Studio・DB・画像保存先などのパスや定数をここで一元管理する
"""

from pathlib import Path

# --- プロジェクトのルートディレクトリ ---
BASE_DIR = Path(__file__).parent  # このファイルがある ocr_dx_system/ フォルダ

# --- データ保存先 ---
DB_PATH = BASE_DIR / "data" / "db" / "receipts.db"
IMAGE_DIR = BASE_DIR / "data" / "images"

# --- LM Studio API設定 ---
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"   # LM Studioは認証不要なのでダミー値でよい
LM_STUDIO_MODEL = "qwen/qwen2.5-vl-7b"  # LM Studioでロードするモデル名

# --- OCRリトライ設定 ---
OCR_MAX_RETRIES = 3       # APIリクエストの最大リトライ回数
OCR_RETRY_DELAY = 2.0     # リトライ間隔（秒）

# --- 画像前処理設定 ---
IMAGE_MAX_SIZE = 1920      # 長辺の最大ピクセル数（これ以上は縮小する）

# --- document_typeの定義（将来拡張用） ---
DOC_TYPE_RECEIPT = "receipt"       # 領収書（現在対応）
DOC_TYPE_INVOICE = "invoice"       # 請求書（フェーズ2予定）
DOC_TYPE_APPLICATION = "application"  # 申請書（フェーズ3予定）
