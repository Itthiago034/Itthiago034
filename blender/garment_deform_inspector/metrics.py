"""Métricas numéricas: estiramento por triângulo, zonas de peso, comparação
com o corpo e interpenetração. Tudo em espaço de mundo, metros."""

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

MIN_EDGE = 0.001  # segmentos de referência menores que 1 mm são ignorados


def triangle_stretch(ref, cur, tris):
    """Maior e menor estiramento principal por triângulo (cur vs ref).

    Usa o gradiente de deformação 2D de cada triângulo: autovalores de
    C = FᵀF. 1.0 = sem alteração; 2.0 = o tecido dobrou de comprimento em
    alguma direção; < 1 = compressão (tende a formar dobras/volume).
    Retorna (max, min, razão_de_área, válido).
    """
    p0, p1, p2 = ref[tris[:, 0]], ref[tris[:, 1]], ref[tris[:, 2]]
    q0, q1, q2 = cur[tris[:, 0]], cur[tris[:, 1]], cur[tris[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    f1, f2 = q1 - q0, q2 - q0
    l1 = np.linalg.norm(e1, axis=1)
    l2 = np.linalg.norm(e2, axis=1)
    l3 = np.linalg.norm(p2 - p1, axis=1)
    n = np.cross(e1, e2)
    area2 = np.linalg.norm(n, axis=1)
    valid = (l1 > MIN_EDGE) & (l2 > MIN_EDGE) & (l3 > MIN_EDGE) & (area2 > MIN_EDGE ** 2)
    l1s = np.where(valid, l1, 1.0)
    u = e1 / l1s[:, None]
    v = np.cross(n, u)
    v /= np.where(valid, np.linalg.norm(v, axis=1), 1.0)[:, None]
    # coordenadas 2D da referência
    a0, b0, b1 = l1s, np.einsum("ij,ij->i", e2, u), np.einsum("ij,ij->i", e2, v)
    b1 = np.where(valid, b1, 1.0)
    # D = [[a0, b0], [0, b1]]  ->  D^-1 = [[1/a0, -b0/(a0 b1)], [0, 1/b1]]
    i00, i01, i11 = 1.0 / a0, -b0 / (a0 * b1), 1.0 / b1
    F0 = f1 * i00[:, None]
    F1 = f1 * i01[:, None] + f2 * i11[:, None]
    c00 = np.einsum("ij,ij->i", F0, F0)
    c11 = np.einsum("ij,ij->i", F1, F1)
    c01 = np.einsum("ij,ij->i", F0, F1)
    tr = c00 + c11
    det = np.maximum(c00 * c11 - c01 * c01, 0)
    disc = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    smax = np.sqrt(np.maximum(tr / 2 + disc, 0))
    smin = np.sqrt(np.maximum(tr / 2 - disc, 0))
    area = np.sqrt(det)
    return smax, smin, area, valid


def per_vertex_max(nv, tris, values, valid):
    out = np.zeros(nv)
    vals = np.where(valid, values, 0)
    for k in range(3):
        np.maximum.at(out, tris[:, k], vals)
    return out


def stats(arr):
    if arr is None or len(arr) == 0:
        return {"n": 0}
    return {
        "n": int(len(arr)),
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "max": round(float(arr.max()), 3),
        "pct_over_1_25": round(float((arr > 1.25).mean() * 100), 2),
        "pct_over_1_5": round(float((arr > 1.5).mean() * 100), 2),
        "pct_over_2": round(float((arr > 2.0).mean() * 100), 2),
        "pct_over_3": round(float((arr > 3.0).mean() * 100), 2),
    }


def _point_segment_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def zones(co, arm_w, joints, ua_len, up=np.array([0, 0, 1.0])):
    """Rótulos de região por lado: 'arm' (≥0.95), 'transition', 'torso' (≤0.05)
    e uma máscara 'armpit': até 1 comprimento de UpperArm da articulação do
    ombro e abaixo dela (bind pose)."""
    out = {}
    for side, w in arm_w.items():
        j = np.array(joints[side])
        L = ua_len[side]
        d = np.linalg.norm(co - j, axis=1)
        below = (co - j) @ up <= 0.1 * L
        out[side] = {
            "arm": w >= 0.95,
            "transition": (w > 0.05) & (w < 0.95),
            "torso": w <= 0.05,
            "armpit": (d <= 1.0 * L) & below,
            "dist_joint": d,
        }
    return out


def weight_zone_analysis(co, edges, arm_w, zone, joint, tail, ua_len, up=np.array([0, 0, 1.0])):
    """Onde fica a transição tronco→braço e quão abrupta ela é.

    A rotação do braço afasta pontos proporcionalmente à distância até o pivô
    (articulação do ombro). Uma fronteira de peso abrupta longe do pivô abre
    uma "membrana" muito maior do que a mesma fronteira perto dele.
    """
    w = arm_w
    j = np.array(joint)
    L = ua_len
    tr = zone["transition"]
    res = {"transition_vertices": int(tr.sum())}
    d = zone["dist_joint"]
    if tr.any():
        res["transition_dist_to_joint_p50"] = round(float(np.median(d[tr])) / L, 3)
        res["transition_dist_to_joint_p90"] = round(float(np.percentile(d[tr], 90)) / L, 3)
        drop = (j - co[tr]) @ up
        res["transition_below_joint_p90"] = round(float(np.percentile(drop, 90)) / L, 3)
    a, b = edges[:, 0], edges[:, 1]
    dw = np.abs(w[a] - w[b])
    el = np.linalg.norm(co[a] - co[b], axis=1)
    near = zone["armpit"][a] | zone["armpit"][b]
    mid = (co[a] + co[b]) * 0.5
    hard = (dw > 0.3) & near
    res["hard_edges_armpit"] = int(hard.sum())
    if hard.any():
        md = np.linalg.norm(mid[hard] - j, axis=1)
        res["hard_edge_dist_to_joint_p50"] = round(float(np.median(md)) / L, 3)
        res["hard_edge_dw_max"] = round(float(dw[hard].max()), 3)
    gz = near & (dw > 1e-4) & (el > 1e-6)
    if gz.any():
        res["gradient_per_cm_p95"] = round(float(np.percentile(dw[gz] / (el[gz] * 100), 95)), 3)
    if tr.any():
        trw = (w[a] > 0.05) & (w[a] < 0.95) & (w[b] > 0.05) & (w[b] < 0.95)
        med_e = float(np.median(el[trw])) if trw.any() else float(np.median(el))
        width = float(np.percentile(d[tr], 90) - np.percentile(d[tr], 10))
        res["transition_width_cm"] = round(width * 100, 2)
        res["edge_rings_across_transition"] = round(width / max(med_e, 1e-6), 1)
    armv = w > 0.5
    if armv.any():
        dist_axis = _point_segment_dist(co[armv], j, np.array(tail))
        res["arm_weighted_dist_to_bone_p50"] = round(float(np.median(dist_axis)) / L, 3)
        res["arm_weighted_dist_to_bone_p90"] = round(float(np.percentile(dist_axis, 90)) / L, 3)
    # densidade local
    for name in ("arm", "transition", "torso"):
        m = zone[name]
        e_m = m[a] & m[b] & near
        if e_m.any():
            res[f"edge_len_mm_{name}_armpit"] = round(float(np.median(el[e_m])) * 1000, 2)
    return res


class BodyRef:
    """BVH do corpo em espaço de mundo + pesos de braço do corpo."""

    def __init__(self, co, tris, arm_w=None):
        self.co = co
        self.tris = tris
        self.arm_w = arm_w or {}
        self.bvh = BVHTree.FromPolygons([Vector(p) for p in co], tris.tolist(), all_triangles=True)

    def nearest(self, pts):
        n = len(pts)
        loc = np.zeros((n, 3))
        nor = np.zeros((n, 3))
        idx = np.full(n, -1, dtype=np.int64)
        for i, p in enumerate(pts):
            l, nn, fi, _ = self.bvh.find_nearest(Vector(p))
            if l is not None:
                loc[i] = l
                nor[i] = nn
                idx[i] = fi
        off = np.einsum("ij,ij->i", pts - loc, nor)
        return loc, nor, idx, off

    def interp_weights(self, loc, idx, side):
        w = self.arm_w.get(side)
        out = np.zeros(len(loc))
        if w is None:
            return out
        for i, (p, fi) in enumerate(zip(loc, idx)):
            if fi < 0:
                continue
            t = self.tris[fi]
            vs = [Vector(self.co[k]) for k in t]
            bc = poly_3d_calc(vs, Vector(p))
            out[i] = sum(bc[k] * w[t[k]] for k in range(3))
        return out


def body_weight_comparison(garment_co, arm_w, body, zone_by_side):
    """Compara os pesos da roupa com os do ponto mais próximo do corpo.

    Pesos quase idênticos aos do corpo em tecido solto (afastado do corpo)
    são a assinatura de uma transferência "nearest surface" cega: a parte
    de baixo de uma manga larga herda os pesos da lateral do tronco e
    vice-versa.
    """
    loc, nor, idx, off = body.nearest(garment_co)
    res = {"offset_mm_p50": round(float(np.median(off)) * 1000, 1),
           "offset_mm_p90": round(float(np.percentile(off, 90)) * 1000, 1),
           "inside_body_at_bind_pct": round(float((off < -0.001).mean() * 100), 2)}
    per_side = {}
    for side, w in arm_w.items():
        bw = body.interp_weights(loc, idx, side)
        z = zone_by_side[side]["armpit"]
        diff = np.abs(w - bw)
        loose = off > 0.015
        s = {"armpit_vertices": int(z.sum())}
        if z.any():
            s["mean_abs_diff_armpit"] = round(float(diff[z].mean()), 3)
            s["loose_armpit_vertices"] = int((z & loose).sum())
            if (z & loose).any():
                s["loose_copied_body_weights_pct"] = round(float((diff[z & loose] < 0.05).mean() * 100), 1)
                s["loose_offset_mm_p50"] = round(float(np.median(off[z & loose])) * 1000, 1)
        per_side[side] = s
        per_side[side]["_diff"] = diff
    res["sides"] = per_side
    return res, off


def clipping(garment_co_posed, body_posed):
    _, _, _, off = body_posed.nearest(garment_co_posed)
    return off
