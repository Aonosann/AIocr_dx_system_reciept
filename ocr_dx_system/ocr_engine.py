"""
OCRエンジンモジュール
LM Studio（OpenAI互換API）にビジョンモデル経由で画像を送り、
領収書の各項目をJSON形式で抽出する
"""

import json
import re
import time

from openai import OpenAI

from config import (
    LM_STUDIO_API_KEY,
    LM_STUDIO_BASE_URL,
    LM_STUDIO_MODEL,
    OCR_MAX_RETRIES,
    OCR_RETRY_DELAY,
)

# AIに渡すプロンプト（何を抽出してほしいかを指示する）
SYSTEM_PROMPT = """あなたは領収書・レシートの情報を抽出するアシスタントです。
画像から以下の項目を読み取り、必ずJSON形式のみで返答してください。
説明文や前置きは不要です。JSONだけ返してください。

抽出項目:
{
  "date": "日付（YYYY-MM-DD形式。不明な場合はnull）",
  "store_name": "店名・事業者名（不明な場合はnull）",
  "amount": "合計金額（整数・円。不明な場合はnull）",
  "tax_amount": "消費税額（整数・円。不明な場合はnull）",
  "purpose": "用途・摘要（推測でもよい。例: 交通費、会議費など）",
  "payment_method": "支払方法（現金/カード/電子マネー/不明 のいずれか）",
  "confidence": "抽出の自信度（high/medium/low のいずれか）"
}"""

USER_PROMPT = "この領収書の画像から情報を抽出してください。"


def extract_receipt_data(base64_image: str) -> dict:
    """
    base64エンコードされた画像をLM Studioに送り、
    領収書の各項目をdictで返す
    失敗時は最大OCR_MAX_RETRIES回リトライする
    """
    client = OpenAI(
        base_url=LM_STUDIO_BASE_URL,
        api_key=LM_STUDIO_API_KEY,
    )

    last_error = None
    for attempt in range(1, OCR_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LM_STUDIO_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    },
                ],
                temperature=0.1,  # 低めにして出力を安定させる
                max_tokens=512,
            )

            raw_text = response.choices[0].message.content
            return _parse_json(raw_text)

        except Exception as e:
            last_error = e
            if attempt < OCR_MAX_RETRIES:
                time.sleep(OCR_RETRY_DELAY)

    # 全リトライ失敗
    raise RuntimeError(
        f"LM Studioへのリクエストが{OCR_MAX_RETRIES}回失敗しました: {last_error}"
    )


def _parse_json(text: str) -> dict:
    """
    AIの返答テキストからJSONを抽出してdictに変換する
    AIが余計な説明文をつけることがあるため、正規表現でJSON部分だけ取り出す
    """
    # コードブロック（```json ... ```）が含まれている場合も対応
    text = re.sub(r"```(?:json)?", "", text).strip()

    # {...} の部分だけを取り出す
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"JSONが見つかりませんでした。AIの返答: {text}")

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"JSONのパースに失敗しました: {e}\n返答内容: {text}")

    return _validate_and_normalize(data)


def _validate_and_normalize(data: dict) -> dict:
    """
    抽出したデータの型・値を正規化する
    不正な値はNoneまたはデフォルト値に置き換える
    """
    # amount / tax_amount は整数に変換（文字列で返ってくることがある）
    for key in ("amount", "tax_amount"):
        val = data.get(key)
        if val is not None:
            try:
                # カンマや円記号が含まれていても対応
                data[key] = int(str(val).replace(",", "").replace("円", "").strip())
            except (ValueError, TypeError):
                data[key] = None

    # payment_method は許可された値以外はデフォルトに
    allowed_payment = {"現金", "カード", "電子マネー", "不明"}
    if data.get("payment_method") not in allowed_payment:
        data["payment_method"] = "不明"

    # confidence は許可された値以外はデフォルトに
    allowed_confidence = {"high", "medium", "low"}
    if data.get("confidence") not in allowed_confidence:
        data["confidence"] = "low"

    return data


def get_empty_receipt() -> dict:
    """
    JSONパース失敗時など、手動入力に使う空のデータ構造を返す
    """
    return {
        "date": None,
        "store_name": None,
        "amount": None,
        "tax_amount": None,
        "purpose": None,
        "payment_method": "不明",
        "confidence": "low",
    }
