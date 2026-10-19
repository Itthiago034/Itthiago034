"""Inspeção estática (somente leitura) de uma roupa e do rig.

Nada aqui altera o arquivo: só lê malha, grupos, modificadores, shape keys,
drivers e constraints.
"""

import math

import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

# Modificadores que mudam a topologia (o resultado avaliado deixa de ter
# correspondência 1:1 com os vértices originais).
TOPOLOGY_MODIFIERS = {
    "SUBSURF", "MULTIRES", "SOLIDIFY", "MIRROR", "ARRAY", "BEVEL", "BOOLEAN",
    "DECIMATE", "REMESH", "SCREW", "SKIN", "TRIANGULATE", "WELD", "WIREFRAME",
    "EDGE_SPLIT", "MASK", "BUILD", "NODES", "WELD",
}
# Modificadores que deformam sem mudar topologia
DEFORM_MODIFIERS = {
    "ARMATURE", "CORRECTIVE_SMOOTH", "SMOOTH", "LAPLACIANSMOOTH", "SURFACE_DEFORM",
    "MESH_DEFORM", "LATTICE", "SHRINKWRAP", "CLOTH", "SOFT_BODY", "DATA_TRANSFER",
    "DISPLACE", "HOOK", "CAST", "SIMPLE_DEFORM", "WARP", "WAVE", "LAPLACIANDEFORM",
    "VERTEX_WEIGHT_EDIT", "VERTEX_WEIGHT_MIX", "VERTEX_WEIGHT_PROXIMITY",
}


def _rna_dump(struct, skip=("name", "type", "rna_type", "is_override_data_editable")):
    """Propriedades simples de um struct RNA (bool/int/float/str/enum/ponteiro)."""
    out = {}
    for prop in struct.bl_rna.properties:
        pid = prop.identifier
        if pid in skip or prop.is_hidden:
            continue
        try:
            val = getattr(struct, pid)
        except Exception:
            continue
        if prop.type in {"BOOLEAN", "INT", "FLOAT"}:
            if getattr(prop, "array_length", 0):
                try:
                    val = [round(v, 5) if isinstance(v, float) else v for v in val]
                except TypeError:
                    continue
            elif isinstance(val, float):
                val = round(val, 5)
            out[pid] = val
        elif prop.type in {"STRING", "ENUM"}:
            if isinstance(val, set):
                val = sorted(val)
            out[pid] = val
        elif prop.type == "POINTER" and hasattr(val, "name") and hasattr(val, "users"):
            out[pid] = val.name
    return out


def vertex_weight_matrix(obj):
    """Matriz densa (n_verts x n_groups) com os pesos dos vertex groups."""
    me = obj.data
    n = len(me.vertices)
    g = len(obj.vertex_groups)
    W = np.zeros((n, max(g, 1)), dtype=np.float32)
    for v in me.vertices:
        for ge in v.groups:
            if ge.group < g:
                W[v.index, ge.group] = ge.weight
    return W


def bind_coords_world(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world, dtype=np.float64)
    return co @ M[:3, :3].T + M[:3, 3]


def loop_tris(me):
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    return t.reshape(-1, 3)


def edges_array(me):
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def armature_of(obj):
    for m in obj.modifiers:
        if m.type == "ARMATURE" and m.object:
            return m.object
    if obj.parent and obj.parent.type == "ARMATURE":
        return obj.parent
    return None


def _drivers(id_data):
    out = []
    ad = getattr(id_data, "animation_data", None)
    if not ad:
        return out
    for fc in ad.drivers:
        d = fc.driver
        vars_ = []
        for var in d.variables:
            tg = []
            for t in var.targets:
                tg.append({
                    "id": t.id.name if t.id else None,
                    "bone": getattr(t, "bone_target", ""),
                    "transform": getattr(t, "transform_type", ""),
                    "space": getattr(t, "transform_space", ""),
                    "data_path": t.data_path,
                })
            vars_.append({"name": var.name, "type": var.type, "targets": tg})
        out.append({
            "data_path": fc.data_path, "index": fc.array_index,
            "type": d.type, "expression": d.expression, "variables": vars_,
            "valid": d.is_valid, "modifiers": [m.type for m in fc.modifiers],
            "keyframes": len(fc.keyframe_points),
        })
    return out


def inspect_rig(arm_obj, mapping, arm_sets):
    data = arm_obj.data
    up = Vector((0, 0, 1))
    Minv = arm_obj.matrix_world.to_3x3().inverted()
    up_local = (Minv @ up).normalized()
    arms = {}
    for side in ("L", "R"):
        ua = mapping.get((side, "upper_arm"))
        if not ua or ua not in data.bones:
            continue
        b = data.bones[ua]
        d = (b.tail_local - b.head_local).normalized()
        # ângulo entre o braço e a vertical para baixo (0 = colado, 90 = T-pose)
        abd = math.degrees((-up_local).angle(d))
        arms[side] = {
            "upper_arm": ua,
            "rest_abduction_deg": round(abd, 1),
            "rest_pose": "T-pose" if abd > 75 else ("A-pose" if abd > 20 else "braços abaixados"),
            "upper_arm_length": round(b.length * arm_obj.matrix_world.to_scale().x, 4),
            "bbone_segments": b.bbone_segments,
            "inherit_rotation": b.use_inherit_rotation,
            "influence_bones": sorted(arm_sets.get(side, [])),
        }
    constraints = []
    for pb in arm_obj.pose.bones:
        for c in pb.constraints:
            constraints.append({
                "bone": pb.name, "name": c.name, "type": c.type,
                "influence": round(c.influence, 3), "mute": c.mute,
                "target": getattr(getattr(c, "target", None), "name", None),
                "subtarget": getattr(c, "subtarget", ""),
                "arm_related": any(pb.name in s for s in arm_sets.values()),
            })
    return {
        "name": arm_obj.name,
        "bones": len(data.bones),
        "deform_bones": sum(1 for b in data.bones if b.use_deform),
        "pose_position": data.pose_position,
        "mapping": {f"{s}.{r}": n for (s, r), n in mapping.items()},
        "arms": arms,
        "bone_constraints": constraints,
        "drivers": _drivers(arm_obj) + _drivers(data),
        "object_scale": [round(v, 4) for v in arm_obj.scale],
    }


def inspect_garment(obj, arm_obj, arm_sets, body=None):
    """Coleta fatos sobre a roupa. Retorna (relatório, arrays auxiliares)."""
    me = obj.data
    rep = {"object": obj.name, "mesh": me.name}
    bones = arm_obj.data.bones if arm_obj else {}

    # ---- transformação / parentesco
    rep["transform"] = {
        "location": [round(v, 4) for v in obj.location],
        "rotation_euler_deg": [round(math.degrees(v), 2) for v in obj.rotation_euler],
        "scale": [round(v, 4) for v in obj.scale],
        "scale_applied": all(abs(s - 1) < 1e-4 for s in obj.scale),
        "rotation_applied": all(abs(r) < 1e-4 for r in obj.rotation_euler),
        "negative_scale": any(s < 0 for s in obj.scale),
        "parent": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent_type,
        "parent_bone": obj.parent_bone or None,
    }

    # ---- topologia
    polys = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_total", polys)
    tris = loop_tris(me)
    edges = edges_array(me)
    co = bind_coords_world(obj)
    elen = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1) if len(edges) else np.zeros(0)
    face_count_per_vert = np.bincount(tris.ravel(), minlength=len(me.vertices)) if len(tris) else np.zeros(len(me.vertices))
    rep["topology"] = {
        "vertices": len(me.vertices),
        "edges": len(me.edges),
        "faces": len(me.polygons),
        "triangles_eval": len(tris),
        "tris": int((polys == 3).sum()),
        "quads": int((polys == 4).sum()),
        "ngons": int((polys > 4).sum()),
        "loose_vertices": int((face_count_per_vert == 0).sum()),
        "edge_len_median_mm": round(float(np.median(elen)) * 1000, 2) if len(elen) else 0,
        "edge_len_p95_mm": round(float(np.percentile(elen, 95)) * 1000, 2) if len(elen) else 0,
    }
    # vértices sobrepostos (costuras não soldadas podem abrir com pesos diferentes)
    kd = KDTree(len(co))
    for i, p in enumerate(co):
        kd.insert(p, i)
    kd.balance()
    dup = 0
    for i, p in enumerate(co):
        for (_, j, d) in kd.find_range(p, 1e-4):
            if j > i:
                dup += 1
    rep["topology"]["overlapping_vertex_pairs"] = dup
    # bordas não-manifold
    edge_face = {}
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            k = (a, b) if a < b else (b, a)
            edge_face[k] = edge_face.get(k, 0) + 1
    rep["topology"]["boundary_edges"] = sum(1 for v in edge_face.values() if v == 1)
    rep["topology"]["nonmanifold_edges"] = sum(1 for v in edge_face.values() if v > 2)

    # ---- modificadores
    mods = []
    arm_idx = None
    for i, m in enumerate(obj.modifiers):
        entry = {"index": i, "name": m.name, "type": m.type,
                 "show_viewport": m.show_viewport, "show_render": m.show_render,
                 "settings": _rna_dump(m)}
        if m.type == "ARMATURE" and arm_idx is None:
            arm_idx = i
        mods.append(entry)
    rep["modifiers"] = mods
    issues = []
    arm_mods = [m for m in obj.modifiers if m.type == "ARMATURE"]
    if not arm_mods:
        issues.append("Sem Armature Modifier.")
    if len(arm_mods) > 1:
        issues.append(f"{len(arm_mods)} Armature Modifiers (risco de deformação dupla).")
    for m in obj.modifiers[: arm_idx or 0]:
        if m.type in TOPOLOGY_MODIFIERS:
            issues.append(f"'{m.name}' ({m.type}) está ANTES do Armature: a deformação ocorre na malha já gerada.")
        if m.type in {"DATA_TRANSFER", "SURFACE_DEFORM", "SHRINKWRAP", "CLOTH"}:
            issues.append(f"'{m.name}' ({m.type}) está ANTES do Armature.")
    for m in arm_mods:
        if m.object is None:
            issues.append(f"'{m.name}' sem objeto de armature.")
        elif arm_obj and m.object != arm_obj:
            issues.append(f"'{m.name}' aponta para '{m.object.name}', não para '{arm_obj.name}'.")
        if m.use_bone_envelopes:
            issues.append(f"'{m.name}' usa Bone Envelopes (influência por distância além dos pesos).")
        if not m.use_vertex_groups:
            issues.append(f"'{m.name}' com Vertex Groups DESLIGADO.")
    if obj.parent and obj.parent.type == "ARMATURE" and obj.parent_type == "BONE":
        issues.append("Objeto parentado a um osso (parent_type BONE) além do modificador.")
    rep["modifier_issues"] = issues
    rep["armature_modifier"] = _rna_dump(arm_mods[0]) if arm_mods else None

    # ---- pesos
    W = vertex_weight_matrix(obj)
    vg_names = [vg.name for vg in obj.vertex_groups]
    deform_cols = [i for i, n in enumerate(vg_names) if n in bones and bones[n].use_deform]
    Wd = W[:, deform_cols] if deform_cols else np.zeros((len(me.vertices), 1), np.float32)
    wsum = Wd.sum(axis=1)
    infl = (Wd > 1e-4).sum(axis=1)
    groups = []
    for i, n in enumerate(vg_names):
        col = W[:, i]
        nz = col > 1e-4
        groups.append({
            "name": n,
            "bone_exists": n in bones,
            "deform_bone": bool(n in bones and bones[n].use_deform),
            "locked": obj.vertex_groups[i].lock_weight,
            "verts": int(nz.sum()),
            "max": round(float(col.max()), 3) if len(col) else 0,
            "mean_nonzero": round(float(col[nz].mean()), 3) if nz.any() else 0,
        })
    arm_w = {}
    for side, bset in arm_sets.items():
        cols = [i for i, n in enumerate(vg_names) if n in bset and i in deform_cols]
        arm_w[side] = W[:, cols].sum(axis=1) if cols else np.zeros(len(me.vertices), np.float32)
    # pesos normalizados como o Armature Modifier faz
    norm = np.where(wsum > 1e-6, wsum, 1.0)
    arm_w_norm = {s: np.clip(w / norm, 0, 1) for s, w in arm_w.items()}

    rep["weights"] = {
        "vertex_groups": len(vg_names),
        "deform_groups": len(deform_cols),
        "groups_without_bone": [g["name"] for g in groups if not g["bone_exists"]],
        "groups_non_deform_bone": [g["name"] for g in groups if g["bone_exists"] and not g["deform_bone"]],
        "zero_weight_vertices": int((wsum < 1e-4).sum()),
        "unnormalized_vertices": int(((wsum > 1e-4) & (np.abs(wsum - 1) > 0.01)).sum()),
        "max_influences": int(infl.max()) if len(infl) else 0,
        "vertices_over_4_influences": int((infl > 4).sum()),
        "used_deform_bones": sorted(vg_names[i] for i in deform_cols if W[:, i].max() > 1e-4),
        "groups": groups,
    }
    if arm_obj:
        deform_bone_names = {b.name for b in arm_obj.data.bones if b.use_deform}
        rep["weights"]["helper_bones_used"] = sorted(
            n for n in rep["weights"]["used_deform_bones"]
            if any(n in s for s in arm_sets.values()) and n in deform_bone_names
            and any(k in n.lower() for k in ("armpit", "axil", "waki", "脇", "sleeve", "袖", "twist", "捩"))
        )

    # ---- shape keys
    sk = []
    keys = me.shape_keys
    drivers = _drivers(keys) if keys else []
    if keys:
        basis = keys.reference_key
        for kb in keys.key_blocks:
            if kb == basis:
                continue
            a = np.empty(len(kb.data) * 3)
            b = np.empty(len(kb.data) * 3)
            kb.data.foreach_get("co", a)
            kb.relative_key.data.foreach_get("co", b)
            disp = np.linalg.norm((a - b).reshape(-1, 3), axis=1)
            moved = disp > 1e-5
            drv = [d for d in drivers if f'key_blocks["{kb.name}"]' in d["data_path"]]
            drv_bones = sorted({t["bone"] for d in drv for v in d["variables"] for t in v["targets"] if t["bone"]})
            arm_moved = 0
            for s, w in arm_w_norm.items():
                arm_moved = max(arm_moved, float(((w > 0.05) & moved).sum()))
            sk.append({
                "name": kb.name, "relative_key": kb.relative_key.name,
                "value": round(kb.value, 3), "slider": [kb.slider_min, kb.slider_max],
                "vertex_group": kb.vertex_group or None, "mute": kb.mute,
                "moved_vertices": int(moved.sum()),
                "max_offset_mm": round(float(disp.max()) * 1000, 2) if len(disp) else 0,
                "moved_in_arm_zone": int(arm_moved),
                "driven": bool(drv), "driver_bones": drv_bones,
                "corrective": bool(drv_bones),
            })
    rep["shape_keys"] = {
        "count": len(sk), "use_relative": keys.use_relative if keys else None,
        "keys": sk, "drivers": drivers,
        "corrective_keys": [k["name"] for k in sk if k["corrective"]],
        "nonzero_at_rest": [k["name"] for k in sk if abs(k["value"]) > 1e-4 and not k["driven"]],
    }

    # ---- drivers e constraints no objeto
    rep["object_constraints"] = [
        {"name": c.name, "type": c.type, "influence": round(c.influence, 3),
         "target": getattr(getattr(c, "target", None), "name", None)} for c in obj.constraints
    ]
    rep["object_drivers"] = _drivers(obj) + _drivers(me)

    arrays = {
        "co": co, "tris": tris, "edges": edges, "W": W, "vg_names": vg_names,
        "arm_w": arm_w_norm, "wsum": wsum,
    }
    return rep, arrays
