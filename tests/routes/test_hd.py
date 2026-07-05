import pyvips
import pytest

import paths
from routes.map import MapLayer, MapSet, PixelMapPoint
from routes.position import Position
from routes.render.compositor import composite_overlays, fit_affine
from routes.render.geometry import BoardLayout


def _grid_layer(name, lat_range, lon_range, px_scale=100, priority=0, image="x.jpg"):
    pixel_map = {}
    for lat in lat_range:
        for lon in lon_range:
            pos = Position.new((lat, 0, 0), (lon, 0, 0))
            pixel_map[pos] = PixelMapPoint(
                position=pos,
                x_pixel=(lon - lon_range[0]) * px_scale,
                y_pixel=(lat - lat_range[0]) * px_scale,
            )
    return MapLayer(
        name=name, pixel_map=pixel_map, image_file=image, layer_priority=priority
    )


class TestAssociation:
    def test_overlay_associated_by_bounds(self):
        base = _grid_layer("GERMANY", (0, 4), (0, 4))
        overlay = _grid_layer("HD1", (1, 2), (1, 2))
        mapset = MapSet([base, overlay])
        assert mapset.overlays_for(base) == [overlay]

    def test_priority_ordering(self):
        base = _grid_layer("GERMANY", (0, 4), (0, 4))
        high = _grid_layer("HD_HIGH", (1, 2), (1, 2), priority=5)
        low = _grid_layer("HD_LOW", (1, 2), (1, 2), priority=1)
        mapset = MapSet([base, high, low])
        assert [o.layer_priority for o in mapset.overlays_for(base)] == [1, 5]

    def test_contains_bounds(self):
        base = _grid_layer("GERMANY", (0, 4), (0, 4))
        overlay = _grid_layer("HD1", (1, 2), (1, 2))
        assert base.contains_bounds(overlay)
        assert not overlay.contains_bounds(base)


class TestAffine:
    def test_recovers_known_transform(self):
        src = [(0, 0), (100, 0), (0, 100), (100, 100)]
        dst = [(2 * x + 10, 2 * y + 20) for (x, y) in src]
        a, b, c, d, tx, ty = fit_affine(src, dst)
        assert a == pytest.approx(2)
        assert d == pytest.approx(2)
        assert b == pytest.approx(0)
        assert c == pytest.approx(0)
        assert tx == pytest.approx(10)
        assert ty == pytest.approx(20)


class TestComposite:
    def test_hd_overlay_is_pasted_on_top(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "map_image_dir", lambda: tmp_path)

        base = _grid_layer("GERMANY", (0, 4), (0, 4), px_scale=100)
        overlay = _grid_layer("HD1", (1, 2), (1, 2), px_scale=100, image="hd.png")

        overlay_img = (pyvips.Image.black(100, 100, bands=3) + [200, 100, 50]).cast("uchar")
        overlay_img.write_to_file(str(tmp_path / "hd.png"))

        base_canvas = (pyvips.Image.black(400, 400, bands=3) + [10, 20, 30]).cast("uchar")

        selection = MapSet([base, overlay]).select_for(
            [type("W", (), {"position": Position.new((1, 30, 0), (1, 30, 0)), "tags": []})()]
        )
        layout = BoardLayout(
            prev_xy=(0, 0), cur_xy=(0, 0), centre=(0, 0), angle_deg=0.0,
            board_w=400, board_h=400, crop_x=0, crop_y=0, crop_w=400, crop_h=400, scale=1.0,
        )
        result = composite_overlays(base_canvas, layout, selection)

        centre = [round(v) for v in result(150, 150)][:3]
        outside = [round(v) for v in result(10, 10)][:3]
        assert centre == [200, 100, 50]
        assert outside == [10, 20, 30]
