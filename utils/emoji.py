"""
絵文字処理
絵文字名の正規化とUnicode変換
"""

import os
import json

from config import TONE_SUFFIX_RE, SPECIAL_OK, EMOJI_JSON_PATH, debug, _CUSTOM_EMOJI_RE


# 絵文字キャッシュ

_EMOJI_CACHE = {
    "name_to_base": None,
    "valid_names": None,
    "surrogate_to_base": None,
}


def strip_tone_modifiers(s: str) -> str:
    """
    トーン修飾子とVS16を除去

    Args:
        s (str): 入力文字列

    Returns:
        str: トーン修飾子を除去した文字列
    """
    try:
        tone_range = set(range(0x1F3FB, 0x1F400))
        return "".join(
            ch for ch in s if (ord(ch) not in tone_range and ord(ch) != 0xFE0F)
        )
    except Exception:
        return s


def normalize_emoji_name(name: str) -> str:
    """
    絵文字名を正規化

    Args:
        name (str): 絵文字名

    Returns:
        str: 正規化された絵文字名
    """
    try:
        return TONE_SUFFIX_RE.sub("", (name or "").lower())
    except Exception:
        return (name or "").lower()


def _load_emoji_master():
    """
    discord-emojis.pretty.jsonの読み込みとキャッシュ

    Returns:
        tuple: (name_to_base, valid_names, surrogate_to_base)
    """
    if _EMOJI_CACHE["name_to_base"] is not None:
        return (
            _EMOJI_CACHE["name_to_base"],
            _EMOJI_CACHE["valid_names"],
            _EMOJI_CACHE["surrogate_to_base"],
        )

    name_to_base = {}
    valid_names = set()
    surrogate_to_base = {}

    try:
        with open(EMOJI_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            for _, arr in data.items():
                if isinstance(arr, list):
                    for item in arr:
                        try:
                            names = item.get("names", []) or []
                            sur = item.get("surrogates")
                            for nm in names:
                                valid_names.add(nm)
                                name_to_base[nm] = normalize_emoji_name(nm)
                            if isinstance(sur, str) and names:
                                stripped_sur = strip_tone_modifiers(sur)
                                base_primary = normalize_emoji_name(names[0])
                                if stripped_sur and base_primary:
                                    surrogate_to_base[stripped_sur] = base_primary
                        except Exception:
                            continue
    except Exception as e:
        if debug:
            print(f"emoji JSON読込エラー(common): {e}")

    _EMOJI_CACHE["name_to_base"] = name_to_base
    _EMOJI_CACHE["valid_names"] = valid_names
    _EMOJI_CACHE["surrogate_to_base"] = surrogate_to_base

    return (name_to_base, valid_names, surrogate_to_base)


def normalize_emoji_and_variants(input_str: str):
    """
    入力文字列からベース絵文字名と派生トーン名リストを返す

    返り値: (base_name or None, variants(list[str]))
    - :name: 形式は name に正規化
    - <:name:id> は name を抽出（SPECIAL_OK のみ許可）
    - Unicode絵文字はトーン/VS16除去してマスタ照合
    - SPECIAL_OK はマスタに無くても許可

    Args:
        input_str (str): 入力文字列

    Returns:
        tuple: (base_name or None, variants(list[str]))
    """
    raw = (input_str or "").strip()

    if len(raw) >= 3 and raw.startswith(":") and raw.endswith(":"):
        raw = raw[1:-1]

    m = _CUSTOM_EMOJI_RE.match(raw)
    if m:
        nm = m.group(1)
        nm_low = nm.lower()
        if nm_low in SPECIAL_OK:
            base_name = nm_low
            variants = [base_name]
            return (base_name, variants)
        return (None, [])

    name_to_base, valid_names, surrogate_to_base = _load_emoji_master()
    base_names_available = set(name_to_base.values())

    base_name = None
    if raw in name_to_base:
        base_name = name_to_base[raw]
    elif raw in SPECIAL_OK:
        base_name = raw
    else:
        stripped = strip_tone_modifiers(raw)
        if stripped in surrogate_to_base:
            base_name = surrogate_to_base[stripped]

    if not base_name:
        return (None, [])
    if base_name not in base_names_available and base_name not in SPECIAL_OK:
        return (None, [])

    variants = [n for n in valid_names if name_to_base.get(n) == base_name]
    if base_name in SPECIAL_OK and base_name not in variants:
        variants.append(base_name)
    if base_name not in variants:
        variants.append(base_name)

    return (base_name, variants)


def emoji_name_to_unicode(emoji_name: str) -> str:
    """
    絵文字の英名からUnicode絵文字文字列に変換する
    見つからない場合は元の英名を返す

    Args:
        emoji_name (str): 絵文字の英名（例: "grin", "joy"）

    Returns:
        str: Unicode絵文字文字列（例: "😁", "😂"）、見つからない場合は元の英名
    """
    if not emoji_name:
        return emoji_name

    try:
        with open(EMOJI_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            for category, emoji_list in data.items():
                if isinstance(emoji_list, list):
                    for emoji_item in emoji_list:
                        try:
                            names = emoji_item.get("names", [])
                            surrogates = emoji_item.get("surrogates", "")

                            if emoji_name.lower() in [n.lower() for n in names]:
                                return surrogates if surrogates else emoji_name
                        except Exception:
                            continue
    except Exception as e:
        if debug:
            print(f"emoji_name_to_unicode エラー: {e}")

    return emoji_name
