from rendering.overlays import get_font
from shared import paths


def _is_notdef(font, char: str) -> bool:
    notdef = font.getmask("\uffff")
    mask = font.getmask(char)
    return bytes(mask) == bytes(notdef) and mask.getbbox() == notdef.getbbox()


def test_bundled_font_exists():
    assert paths.font_path().is_file()


def test_bundled_font_renders_common_diacritics():
    font = get_font(24)
    for char in "éñüøåłčřßæ":
        assert not _is_notdef(font, char), f"Missing glyph for {char!r}"
