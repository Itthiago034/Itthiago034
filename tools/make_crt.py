"""Generate assets/crt.svg: a phosphor CRT showing a pixelated avatar and a
neofetch-style info panel. Animations are SMIL, so they play inside <img> on GitHub.

Usage: python tools/make_crt.py path/to/avatar.jpg [--theme green|amber]
"""
import argparse
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

INFO = [
    ("Name", "Thiago Santos"),
    ("Location", "Uberlândia, Brazil"),
    ("OS", "Linux, Windows"),
    ("Focus", "Rust, TUI/CLI tools,"),
    ("", "MCP servers, local AI"),
    ("Languages", "Rust, TypeScript,"),
    ("", "Python, C, Bash"),
    ("Building", "mcp-crunchyroll"),
    ("Speaks", "English, Português"),
]
PROMPT = "thiago@linux:~$"

THEMES = {
    # background, dim, mid, bright, hot (text / brightest pixels)
    "green": ("#061206", "#163a16", "#3f8a3a", "#8fdc84", "#d9ffd0"),
    "amber": ("#140b02", "#3d2306", "#9a5a12", "#f2a33a", "#ffe1b0"),
}
SWATCHES = ["#ff2d46", "#f97316", "#facc15", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#e5e7eb"]

W, H = 1000, 560
SCREEN = (40, 40, 920, 480)  # x, y, w, h of the glass
GRID = 48                    # portrait is GRID x GRID cells
CELL = 8                     # px per cell
PX, PY = 80, 72              # portrait origin
TX, TY = 520, 104            # text origin
FS, LH, CW = 19, 31, 11.4    # font size, line height, approx char width
VALUE_COL = 11               # value column, in characters


def portrait_cells(path: Path):
    img = Image.open(path).convert("L")
    w, h = img.size
    # Square crop around the face, then shrink to the grid.
    img = img.crop((int(w * 0.10), int(h * 0.04), int(w * 0.98), int(h * 0.92)))
    # Equalizing keeps the face readable; plain contrast crushes it into the balaclava.
    img = ImageOps.equalize(img).resize((GRID, GRID), Image.LANCZOS)
    levels = []
    for y in range(GRID):
        row = []
        for x in range(GRID):
            row.append(min(4, img.getpixel((x, y)) * 5 // 256))
        levels.append(row)
    return levels


def discrete_widths(n_chars: int):
    return ";".join(str(round(i * CW, 1)) for i in range(n_chars + 1))


def build(avatar: Path, theme: str) -> str:
    bg, dim, mid, bright, hot = THEMES[theme]
    shades = [None, dim, mid, bright, hot]
    sx, sy, sw, sh = SCREEN
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'role="img" aria-label="Retro CRT terminal: pixel-art portrait of Thiago and a neofetch-style summary">')
    a("<title>thiago@linux — neofetch</title>")
    a("<defs>")
    a(f'<radialGradient id="glass" cx="50%" cy="50%" r="75%">'
      f'<stop offset="0%" stop-color="{bg}"/><stop offset="70%" stop-color="{bg}"/>'
      f'<stop offset="100%" stop-color="#000"/></radialGradient>')
    a('<radialGradient id="vignette" cx="50%" cy="50%" r="70%">'
      '<stop offset="60%" stop-color="#000" stop-opacity="0"/>'
      '<stop offset="100%" stop-color="#000" stop-opacity="0.65"/></radialGradient>')
    a('<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
      '<rect width="4" height="2" fill="#000" fill-opacity="0.28"/></pattern>')
    a('<filter id="glow" x="-10%" y="-10%" width="120%" height="120%">'
      '<feGaussianBlur stdDeviation="2.2" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    a(f'<clipPath id="screen"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="28"/></clipPath>')

    # Portrait reveals row by row, like a slow raster scan.
    rows = ";".join(str(r * CELL) for r in range(GRID + 1))
    a(f'<clipPath id="rev"><rect x="{PX}" y="{PY}" width="{GRID * CELL}" height="0">'
      f'<animate attributeName="height" values="{rows}" calcMode="discrete" begin="0.3s" dur="1.3s" fill="freeze"/>'
      f'</rect></clipPath>')

    # One typing clip per text line.
    t = 1.7
    starts = []
    for i, (k, v) in enumerate(INFO):
        n = VALUE_COL + len(v)
        dur = max(0.2, n * 0.014)
        y = TY + i * LH
        a(f'<clipPath id="l{i}"><rect x="{TX}" y="{y - FS - 4}" height="{LH}" width="0">'
          f'<animate attributeName="width" values="{discrete_widths(n)}" calcMode="discrete" '
          f'begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        starts.append(t)
        t += dur + 0.05
    swatch_t, prompt_t = t + 0.1, t + 0.5
    a("</defs>")

    # Bezel and glass.
    a(f'<rect width="{W}" height="{H}" rx="34" fill="#0b0d0b"/>')
    a(f'<rect x="{sx - 14}" y="{sy - 14}" width="{sw + 28}" height="{sh + 28}" rx="38" fill="#030403" '
      f'stroke="#1b1f1b" stroke-width="2"/>')
    a(f'<g clip-path="url(#screen)">')
    a(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#glass)"/>')

    # Portrait: each cell is a short horizontal bar, which reads as scanlines.
    a(f'<g clip-path="url(#rev)" filter="url(#glow)">')
    for y, row in enumerate(portrait_cells(avatar)):
        x = 0
        while x < GRID:
            lvl = row[x]
            run = 1
            while x + run < GRID and row[x + run] == lvl:
                run += 1
            if lvl:
                a(f'<rect x="{PX + x * CELL}" y="{PY + y * CELL}" width="{run * CELL}" '
                  f'height="{CELL - 2}" fill="{shades[lvl]}"/>')
            x += run
    a("</g>")

    # neofetch-style text.
    a(f'<g font-family="\'Fira Code\',\'JetBrains Mono\',\'Cascadia Code\',Consolas,\'DejaVu Sans Mono\',monospace" '
      f'font-size="{FS}" filter="url(#glow)">')
    for i, (k, v) in enumerate(INFO):
        label = f"{k}:" if k else ""
        # Values get their own x: whitespace padding collapses when the SVG is shown via <img>.
        a(f'<text y="{TY + i * LH}" clip-path="url(#l{i})">'
          f'<tspan x="{TX}" fill="{bright}">{escape(label)}</tspan>'
          f'<tspan x="{TX + VALUE_COL * CW}" fill="{hot}">{escape(v)}</tspan></text>')
    a("</g>")

    # Colour swatches, like neofetch's palette rows.
    sw_y = TY + len(INFO) * LH + 4
    a(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{swatch_t:.2f}s" dur="0.3s" fill="freeze"/>')
    for i, c in enumerate(SWATCHES):
        a(f'<rect x="{TX + i * 34}" y="{sw_y}" width="34" height="22" fill="{c}" fill-opacity="0.75"/>')
        a(f'<rect x="{TX + i * 34}" y="{sw_y + 22}" width="34" height="12" fill="{c}" fill-opacity="0.4"/>')
    a("</g>")

    # Prompt with a blinking block cursor.
    py = sy + sh - 30
    a(f'<g opacity="0" font-family="\'Fira Code\',Consolas,monospace" font-size="{FS}" filter="url(#glow)">'
      f'<animate attributeName="opacity" from="0" to="1" begin="{prompt_t:.2f}s" dur="0.01s" fill="freeze"/>'
      f'<text x="{sx + 34}" y="{py}" fill="{bright}">{PROMPT}</text>'
      f'<rect x="{sx + 34 + len(PROMPT) * CW + 8}" y="{py - FS + 2}" width="11" height="{FS + 2}" fill="{hot}">'
      f'<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1.06s" repeatCount="indefinite"/>'
      f'</rect></g>')

    # Glass effects on top.
    a(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#scan)"/>')
    a(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#vignette)"/>')
    a(f'<rect x="{sx}" y="{sy - 40}" width="{sw}" height="40" fill="{hot}" fill-opacity="0.04">'
      f'<animate attributeName="y" from="{sy - 40}" to="{sy + sh}" dur="6s" repeatCount="indefinite"/></rect>')
    a("</g>")
    a("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("avatar", type=Path)
    p.add_argument("--theme", choices=THEMES, default="green")
    p.add_argument("--out", type=Path, default=Path("assets/crt.svg"))
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build(args.avatar, args.theme), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB)")
