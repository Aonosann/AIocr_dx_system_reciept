"""
画像前処理モジュール
アップロードされたファイルをOCRに適した状態に整える
対応形式: JPG / PNG / PDF
"""

import base64
import io
from pathlib import Path

import cv2
import fitz  # pymupdf
import numpy as np
from PIL import Image

from config import IMAGE_MAX_SIZE


def load_image(file_path: str | Path) -> list[Image.Image]:
    """
    ファイルを読み込み、PIL Imageのリストで返す
    PDFは1ページ1枚の画像に変換する
    JPG/PNGは1要素のリストで返す
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _pdf_to_images(file_path)
    elif suffix in (".jpg", ".jpeg", ".png"):
        return [Image.open(file_path).convert("RGB")]
    else:
        raise ValueError(f"対応していないファイル形式です: {suffix}")


def _pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    """PDFの各ページを画像（PIL Image）に変換して返す"""
    images = []
    doc = fitz.open(pdf_path)
    for page in doc:
        # 解像度を上げるためにmatrixでスケールアップ（2倍 = 144dpi相当）
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def preprocess(image: Image.Image) -> Image.Image:
    """
    PIL Imageを受け取り、前処理済みのPIL Imageを返す
    処理順: リサイズ → 傾き補正 → コントラスト補正
    """
    # PIL → OpenCV形式（numpy配列）に変換
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    img_cv = _resize(img_cv)
    img_cv = _deskew(img_cv)
    img_cv = _enhance_contrast(img_cv)

    # OpenCV形式 → PIL形式に戻して返す
    return Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))


def _resize(img: np.ndarray) -> np.ndarray:
    """長辺がIMAGE_MAX_SIZEを超えていたら縦横比を保ったまま縮小する"""
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side <= IMAGE_MAX_SIZE:
        return img
    scale = IMAGE_MAX_SIZE / max_side
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _deskew(img: np.ndarray) -> np.ndarray:
    """
    画像の傾きを検出して補正する
    グレースケール化 → エッジ検出 → ハフ変換で主要な線の角度を取得 → 回転
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                             minLineLength=100, maxLineGap=10)

    if lines is None:
        return img  # 線が検出できなければそのまま返す

    # 検出した線の角度の中央値を傾き角度として使う
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # ±45度以内の傾きのみ採用（大きな傾きは誤検出の可能性が高い）
            if -45 < angle < 45:
                angles.append(angle)

    if not angles:
        return img

    median_angle = np.median(angles)

    # 傾きが0.5度未満なら補正しない（わずかな誤差は無視）
    if abs(median_angle) < 0.5:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(img, matrix, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return rotated


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    """
    CLAHE（適応ヒストグラム平坦化）でコントラストを改善する
    明るさにムラがある領収書でも文字を読みやすくする
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def image_to_base64(image: Image.Image) -> str:
    """
    PIL ImageをJPEGのbase64文字列に変換して返す
    LM Studio APIに画像を渡すときに使う形式
    """
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
