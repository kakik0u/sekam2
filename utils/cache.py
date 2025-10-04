"""
キャッシュ管理
JSONキャッシュファイルの読み書きと管理
"""

import json
import os
from datetime import date, datetime

from config import CACHE_DIR, REFERENCE_DATA_DEFAULT_LABEL, debug
from database.connection import run_db_query


def _ensure_cache_dir() -> None:
    """cacheディレクトリを作成する"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        pass


def load_json_cache(path: str, default):
    """
    JSONキャッシュの読み込み

    Args:
        path (str): ファイルパス
        default: 読み込み失敗時のデフォルト値

    Returns:
        読み込んだデータ、または default
    """
    try:
        path = f"cache/{path}"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if data is not None else default
    except Exception:
        return default


def save_json_cache(path: str, data) -> bool:
    """
    JSONキャッシュの保存

    Args:
        path (str): ファイルパス
        data: 保存するデータ

    Returns:
        bool: 成功時True、失敗時False
    """
    try:
        path = f"cache/{path}"
        _ensure_cache_dir()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        if debug:
            print(f"cache保存失敗: {path}: {e}")
        return False


def get_reference_data_label() -> str:
    """
    config.dblastupdateの値を参照ラベルとして取得する

    Returns:
        str: 参照データのラベル（例: "-# 参照データ:2025/10/1まで"）
    """
    row = run_db_query(
        "SELECT dblastupdate FROM `config` WHERE id = %s LIMIT 1",
        (1,),
        fetch="one",
    )
    target = row[0] if row else None
    if target is None:
        return REFERENCE_DATA_DEFAULT_LABEL

    try:
        if isinstance(target, datetime):
            ref_date = target.date()
        elif isinstance(target, date):
            ref_date = target
        else:
            ref_date = datetime.fromisoformat(str(target)).date()
        formatted = f"{ref_date.year}/{ref_date.month}/{ref_date.day}"
        return f"-# 参照データ:{formatted}まで"
    except Exception as e:
        if debug:
            print(f"参照日付取得エラー: {e}")
        return REFERENCE_DATA_DEFAULT_LABEL
