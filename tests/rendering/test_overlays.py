from PIL import Image

from rendering.overlays import MarkerStyle, draw_route


def test_draw_route_fades_non_focused_legs():
    """Semi-transparent legs must be alpha-composited, not left as low-alpha pixels."""
    image = Image.new("RGBA", (200, 200), (210, 190, 150, 255))
    points = [(40.0, 100.0), (100.0, 100.0), (160.0, 100.0)]
    tags = [(False, False)] * 3
    style = MarkerStyle(radius=8, line_width=4)

    draw_route(
        image,
        points,
        tags,
        [None, None, None],
        focused_index=2,
        colour_rgb=(0, 0, 0),
        style=style,
        faded_alpha=50,
    )

    rgb = image.convert("RGB")
    faded = rgb.getpixel((70, 100))
    focused = rgb.getpixel((130, 100))
    background = rgb.getpixel((100, 40))

    assert focused == (0, 0, 0)
    assert faded != (0, 0, 0)
    assert faded != background
    assert sum(faded) > sum(focused)
