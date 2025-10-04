"""
ユーティリティモジュール
キャッシュ管理と絵文字処理機能を提供
"""

from .cache import (
    load_json_cache,
    save_json_cache,
    get_reference_data_label,
)

from .emoji import (
    strip_tone_modifiers,
    normalize_emoji_name,
    normalize_emoji_and_variants,
    emoji_name_to_unicode,
)

__all__ = [
    "load_json_cache",
    "save_json_cache",
    "get_reference_data_label",
    "strip_tone_modifiers",
    "normalize_emoji_name",
    "normalize_emoji_and_variants",
    "emoji_name_to_unicode",
]
