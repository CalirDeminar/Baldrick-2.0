"""High-definition overlay compositing.

Each HD overlay shares lat/long anchor points with the base map, so we can fit
an affine transform mapping overlay pixels to base pixels and resample the HD
image onto the (already scaled) board canvas, compositing it over the base map.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rendering.geometry import BoardLayout

if TYPE_CHECKING:
    from domain.map import MapLayer, MapSelection


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Solve a 3x3 linear system via Gaussian elimination with partial pivoting."""
    m = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    n = 3
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        pivot_val = m[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col] / pivot_val
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit_affine(
    src: list[tuple[float, float]], dst: list[tuple[float, float]]
) -> tuple[float, float, float, float, float, float] | None:
    """Least-squares affine mapping src -> dst as (a, b, c, d, tx, ty):
    dst_x = a*x + b*y + tx ; dst_y = c*x + d*y + ty."""
    if len(src) < 3:
        return None
    sxx = sxy = sx = syy = sy = s1 = 0.0
    for (x, y) in src:
        sxx += x * x
        sxy += x * y
        sx += x
        syy += y * y
        sy += y
        s1 += 1.0
    normal = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, s1]]

    rhs_x = [0.0, 0.0, 0.0]
    rhs_y = [0.0, 0.0, 0.0]
    for (x, y), (u, v) in zip(src, dst):
        rhs_x[0] += x * u
        rhs_x[1] += y * u
        rhs_x[2] += u
        rhs_y[0] += x * v
        rhs_y[1] += y * v
        rhs_y[2] += v

    sol_x = _solve3(normal, rhs_x)
    sol_y = _solve3(normal, rhs_y)
    if sol_x is None or sol_y is None:
        return None
    return sol_x[0], sol_x[1], sol_y[0], sol_y[1], sol_x[2], sol_y[2]


def _rects_intersect(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1) -> bool:
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def composite_overlays(
    base_canvas: Any,
    layout: BoardLayout,
    selection: "MapSelection",
) -> Any:
    """Return the base canvas with any applicable HD overlays composited on top."""
    import pyvips

    base = selection.base
    crop_x0, crop_y0 = layout.crop_x, layout.crop_y
    crop_x1 = crop_x0 + layout.crop_w
    crop_y1 = crop_y0 + layout.crop_h
    interpolate = pyvips.Interpolate.new("bicubic")

    result = base_canvas
    for overlay in selection.overlays:  # already sorted by priority ascending
        pairs = overlay.correspondence_to(base)
        if len(pairs) < 3:
            continue
        base_xs = [b[0] for _, b in pairs]
        base_ys = [b[1] for _, b in pairs]
        if not _rects_intersect(
            min(base_xs), min(base_ys), max(base_xs), max(base_ys),
            crop_x0, crop_y0, crop_x1, crop_y1,
        ):
            continue

        transform = fit_affine([s for s, _ in pairs], [b for _, b in pairs])
        if transform is None:
            continue
        a, b, c, d, tx, ty = transform
        scale = layout.scale
        matrix = [scale * a, scale * b, scale * c, scale * d]
        odx = scale * (tx - crop_x0)
        ody = scale * (ty - crop_y0)

        overlay_img = overlay.load_image()
        if overlay_img.bands == 3:
            overlay_img = overlay_img.bandjoin(255)
        warped = overlay_img.affine(
            matrix,
            interpolate=interpolate,
            oarea=[0, 0, result.width, result.height],
            odx=odx,
            ody=ody,
            extend="background",
            background=[0, 0, 0, 0],
        )
        result = result.composite2(warped, "over")
    return result
