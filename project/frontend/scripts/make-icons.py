"""Генерация логотипа и favicon-набора из растрового исходника.

Исходник: docs/logo-source.png (силуэт на светлом фоне).
Выход:    public/logo.svg, public/favicon.svg, public/favicon*.png,
          public/favicon.ico, public/apple-touch-icon.png

Зависимости (в проект не входят, нужны только для перегенерации):

    pip install potracer pillow numpy

Запуск из корня frontend:

    python scripts/make-icons.py

Как это работает: силуэт трассируется potrace в вектор (8 контуров),
из вектора собирается SVG с fill="currentColor" и растровые иконки.
Мелкие размеры (16/32) дополнительно обводятся, иначе тонкие лапки
теряются при уменьшении.
"""

from pathlib import Path

import numpy as np
import potrace
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "logo-source.png"
PUBLIC = ROOT / "public"

THRESHOLD = 160  # пиксели темнее этого считаются силуэтом
SUPER = 2048  # суперсэмплинг для растровых иконок
FG = (17, 17, 17, 255)


def main() -> None:
    mask = np.array(Image.open(SRC).convert("L")) < THRESHOLD
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1])
    x0, x1 = int(cols[0]), int(cols[-1])
    bw, bh = x1 - x0 + 1, y1 - y0 + 1

    # potracer считает True белым, поэтому маска инвертируется:
    # иначе первым контуром приходит фон размером с кадр.
    traced = potrace.Bitmap(~mask).trace(
        turdsize=2, alphamax=1.0, opticurve=True, opttolerance=0.2
    )

    def path_d(path) -> str:
        parts = []
        for curve in path.curves:
            s = curve.start_point
            parts.append(f"M{s.x:.2f} {s.y:.2f}")
            for seg in curve.segments:
                if seg.is_corner:
                    parts.append(f"L{seg.c.x:.2f} {seg.c.y:.2f}")
                    parts.append(f"L{seg.end_point.x:.2f} {seg.end_point.y:.2f}")
                else:
                    parts.append(
                        f"C{seg.c1.x:.2f} {seg.c1.y:.2f} "
                        f"{seg.c2.x:.2f} {seg.c2.y:.2f} "
                        f"{seg.end_point.x:.2f} {seg.end_point.y:.2f}"
                    )
            parts.append("Z")
        return "".join(parts)

    d = path_d(traced)

    (PUBLIC / "logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{x0} {y0} {bw} {bh}" fill="currentColor" role="img" aria-label="Investor">'
        f'<path fill-rule="evenodd" d="{d}"/></svg>\n',
        encoding="utf-8",
    )

    size, pad = 64, 7
    inner = size - 2 * pad
    scale = min(inner / bw, inner / bh)
    tx = (size - bw * scale) / 2
    ty = (size - bh * scale) / 2
    (PUBLIC / "favicon.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        'role="img" aria-label="Investor">'
        f'<rect width="{size}" height="{size}" rx="14" fill="#ffffff"/>'
        f'<g transform="translate({tx:.2f} {ty:.2f}) scale({scale:.4f}) translate({-x0} {-y0})">'
        f'<path fill="#111111" fill-rule="evenodd" d="{d}"/></g></svg>\n',
        encoding="utf-8",
    )

    def flatten(path, steps: int = 14) -> list[list[tuple[float, float]]]:
        polys = []
        for curve in path.curves:
            pts = [(curve.start_point.x, curve.start_point.y)]
            for seg in curve.segments:
                if seg.is_corner:
                    pts.append((seg.c.x, seg.c.y))
                    pts.append((seg.end_point.x, seg.end_point.y))
                else:
                    p0 = pts[-1]
                    c1 = (seg.c1.x, seg.c1.y)
                    c2 = (seg.c2.x, seg.c2.y)
                    p3 = (seg.end_point.x, seg.end_point.y)
                    for i in range(1, steps + 1):
                        t = i / steps
                        mt = 1 - t
                        pts.append(
                            (
                                mt**3 * p0[0]
                                + 3 * mt * mt * t * c1[0]
                                + 3 * mt * t * t * c2[0]
                                + t**3 * p3[0],
                                mt**3 * p0[1]
                                + 3 * mt * mt * t * c1[1]
                                + 3 * mt * t * t * c2[1]
                                + t**3 * p3[1],
                            )
                        )
            polys.append(pts)
        return polys

    polys = flatten(traced)

    def tile(size: int, radius_ratio: float, pad_ratio: float, stroke: int = 0) -> Image.Image:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            [0, 0, size - 1, size - 1],
            radius=int(size * radius_ratio),
            fill=(255, 255, 255, 255),
        )
        pad_px = int(size * pad_ratio)
        available = size - 2 * pad_px
        s = min(available / bw, available / bh)
        ox = (size - bw * s) / 2
        oy = (size - bh * s) / 2
        for pts in polys:
            tp = [((x - x0) * s + ox, (y - y0) * s + oy) for x, y in pts]
            draw.polygon(tp, fill=FG)
            if stroke:
                draw.line(tp + [tp[0]], fill=FG, width=stroke, joint="curve")
        return canvas

    master = tile(SUPER, 0.22, 0.11)
    master.resize((48, 48), Image.LANCZOS).save(PUBLIC / "favicon-48x48.png")
    master.resize((512, 512), Image.LANCZOS).save(PUBLIC / "favicon-512x512.png")
    master.resize((32, 32), Image.LANCZOS).save(PUBLIC / "favicon-32x32.png")
    master.resize((16, 16), Image.LANCZOS).save(PUBLIC / "favicon-16x16.png")

    # мелкие размеры перерисовываются с обводкой — иначе лапки исчезают
    tile(SUPER, 0.22, 0.11, stroke=int(SUPER * 0.014)).resize(
        (32, 32), Image.LANCZOS
    ).save(PUBLIC / "favicon-32x32.png")
    tile(SUPER, 0.22, 0.11, stroke=int(SUPER * 0.032)).resize(
        (16, 16), Image.LANCZOS
    ).save(PUBLIC / "favicon-16x16.png")

    tile(SUPER, 0.22, 0.11).resize((48, 48), Image.LANCZOS).save(
        PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )

    tile(SUPER, 0.0, 0.13).resize((180, 180), Image.LANCZOS).convert("RGB").save(
        PUBLIC / "apple-touch-icon.png"
    )

    print("contours:", len(traced.curves), "| path:", len(d), "chars")
    for name in sorted(p.name for p in PUBLIC.iterdir()):
        print(" ", name)


if __name__ == "__main__":
    main()
