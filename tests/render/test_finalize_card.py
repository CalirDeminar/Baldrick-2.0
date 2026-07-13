from PIL import Image

from rendering.output import finalize_card


def test_finalize_card_opaque_returns_rgb_jpg():
    image = Image.new("RGB", (10, 10), (100, 150, 200))
    finalized, ext = finalize_card(image, 255)
    assert ext == "jpg"
    assert finalized.mode == "RGB"


def test_finalize_card_none_resolves_to_opaque_via_255():
    image = Image.new("RGB", (10, 10), (100, 150, 200))
    finalized, ext = finalize_card(image, 255)
    assert ext == "jpg"
    assert finalized.mode == "RGB"


def test_finalize_card_partial_alpha_scales_channel():
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 200))
    finalized, ext = finalize_card(image, 128)
    assert ext == "png"
    assert finalized.mode == "RGBA"
    assert finalized.getchannel("A").getextrema() == (100, 100)


def test_finalize_card_zero_is_fully_transparent():
    image = Image.new("RGB", (4, 4), (255, 0, 0))
    finalized, ext = finalize_card(image, 0)
    assert ext == "png"
    assert finalized.mode == "RGBA"
    assert finalized.getchannel("A").getextrema() == (0, 0)
