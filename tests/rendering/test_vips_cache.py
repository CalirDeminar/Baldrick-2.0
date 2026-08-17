from __future__ import annotations

from pathlib import Path

import pyvips

from rendering import vips_util
from shared import paths


def _write_png(path, colour=(10, 20, 30)):
    image = (pyvips.Image.black(32, 24, bands=3) + list(colour)).cast("uchar")
    image.write_to_file(str(path))


def test_configure_tmpdir_points_libvips_at_app_scratch():
    import os

    scratch = vips_util.configure_tmpdir()
    assert scratch == paths.tmp_dir() / "scratch"
    assert scratch.is_dir()
    assert vips_util.map_cache_dir().is_dir()
    assert Path(os.environ["TMPDIR"]).resolve() == scratch.resolve()


def test_load_map_image_writes_tiled_cache_once(tmp_path):
    source = tmp_path / "overlay.png"
    _write_png(source)

    first = vips_util.load_map_image(source)
    cached = list(vips_util.map_cache_dir().glob("overlay-*.tif"))
    assert len(cached) == 1
    assert first.width == 32
    assert first.height == 24

    mtime = cached[0].stat().st_mtime_ns
    second = vips_util.load_map_image(source)
    assert second is first
    assert cached[0].stat().st_mtime_ns == mtime


def test_load_map_image_reopens_disk_cache_after_clear(tmp_path):
    source = tmp_path / "base.png"
    _write_png(source, colour=(1, 2, 3))

    first = vips_util.load_map_image(source)
    cache_file = next(vips_util.map_cache_dir().glob("base-*.tif"))
    mtime = cache_file.stat().st_mtime_ns

    vips_util.clear_image_cache()
    second = vips_util.load_map_image(source)

    assert second is not first
    assert cache_file.stat().st_mtime_ns == mtime
    assert [round(v) for v in second(0, 0)][:3] == [1, 2, 3]


def test_stale_cache_is_replaced_when_source_changes(tmp_path):
    source = tmp_path / "map.png"
    _write_png(source, colour=(9, 9, 9))
    vips_util.load_map_image(source)
    old = next(vips_util.map_cache_dir().glob("map-*.tif"))

    vips_util.clear_image_cache()
    larger = (pyvips.Image.black(40, 24, bands=3) + [4, 5, 6]).cast("uchar")
    larger.write_to_file(str(source))
    image = vips_util.load_map_image(source)

    remaining = list(vips_util.map_cache_dir().glob("map-*.tif"))
    assert len(remaining) == 1
    assert remaining[0] != old
    assert not old.exists()
    assert [round(v) for v in image(0, 0)][:3] == [4, 5, 6]
