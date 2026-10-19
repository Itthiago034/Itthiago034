"""Imagens SVG geradas direto da malha (sem render/GPU): projeção frontal,
painter's algorithm, cor por valor. Mesma escala para todos os painéis."""

import numpy as np

BG, PANEL, TEXT, MUTED = "#101722", "#1b2533", "#e8edf3", "#9aa7b6"
_STOPS = [(0.0, (43, 92, 196)), (0.33, (44, 170, 140)), (0.66, (240, 196, 64)), (1.0, (226, 72, 64))]


def _ramp(t):
    t = np.clip(t, 0, 1)
    out = np.zeros((len(t), 3))
    for (a, ca), (b, cb) in zip(_STOPS, _STOPS[1:]):
        m = (t >= a) & (t <= b)
        f = ((t[m] - a) / (b - a))[:, None]
        out[m] = np.array(ca) * (1 - f) + np.array(cb) * f
    return out.astype(int)


def stretch_to_unit(v):
    """1× → 0 (azul), 3× → 1 (vermelho)."""
    return (np.asarray(v) - 1.0) / 2.0


def _project(co, forward):
    up = np.array([0, 0, 1.0])
    d = -np.asarray(forward, dtype=float)
    d /= np.linalg.norm(d)
    right = np.cross(d, up)
    return co @ right, co @ up, co @ d


def comparison_svg(path, title, subtitle, panels, forward=(0, -1, 0), footer="", wire=True):
    """panels: lista de (rótulo, coords Nx3, tris Mx3, valores_por_vértice 0..1)."""
    W, H, top, pad = 500 * len(panels), 600, 110, 12
    proj = [(_project(c, forward), t, v, lbl) for lbl, c, t, v in panels]
    ys = np.concatenate([p[0][1] for p in proj])
    # escala única
    span = max(np.ptp(np.concatenate([p[0][0] - p[0][0].mean() for p in proj])), np.ptp(ys), 1e-6)
    pw, ph = 500 - 2 * pad, H - top - 50
    s = min(pw, ph) / span * 0.92
    ymax = ys.max()
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="DejaVu Sans, Arial, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           f'<text x="24" y="36" fill="{TEXT}" font-size="22">{_esc(title)}</text>',
           f'<text x="24" y="60" fill="{MUTED}" font-size="12">{_esc(subtitle)}</text>']
    for i, ((x, y, depth), tris, vals, lbl) in enumerate(proj):
        ox = i * 500 + pad
        out.append(f'<text x="{ox + 12}" y="{top - 14}" fill="{TEXT}" font-size="16">{_esc(lbl)}</text>')
        out.append(f'<rect x="{ox}" y="{top}" width="{pw}" height="{ph}" fill="{PANEL}" stroke="#2c3a4d"/>')
        cx = ox + pw / 2 - x.mean() * s
        cy = top + 20 - (-ymax) * s
        sx, sy = cx + x * s, cy - y * s
        tri_depth = depth[tris].mean(axis=1)
        order = np.argsort(-tri_depth)
        cols = _ramp(np.asarray(vals)[tris].max(axis=1))
        stroke = ' stroke="#0b1018" stroke-width="0.3"' if wire else ""
        out.append(f'<g{stroke} stroke-linejoin="round">')
        for k in order:
            a, b, c = tris[k]
            r, g, bl = cols[k]
            out.append(f'<path d="M{sx[a]:.1f} {sy[a]:.1f}L{sx[b]:.1f} {sy[b]:.1f}L{sx[c]:.1f} {sy[c]:.1f}Z" '
                       f'fill="#{r:02x}{g:02x}{bl:02x}"/>')
        out.append("</g>")
    out.append(f'<text x="30" y="{H - 16}" fill="{TEXT}" font-size="13">{_esc(footer)}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
