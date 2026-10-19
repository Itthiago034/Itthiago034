"""Orquestra as fases 1–3: inspeção estática, testes de pose e métricas."""

import numpy as np

from . import bones as bonesmod
from . import metrics
from .inspect_static import armature_of, inspect_garment, inspect_rig
from .poses import POSES, REFERENCE_POSE, apply_pose, evaluated_coords_world, pose_session


def _body_ref(body, arm_obj, arm_sets, co=None):
    _, arr = inspect_garment(body, arm_obj, arm_sets)
    return metrics.BodyRef(co if co is not None else arr["co"], arr["tris"], arr["arm_w"])


def run_analysis(original, new, armature=None, body=None, mapping_override=None,
                 forward_world=(0.0, -1.0, 0.0), shoulder_assist=0.0, poses=None, progress=None):
    """Executa tudo sem modificar o arquivo. Retorna um dict com resultados
    e arrays usados para visualização (chave '_arrays')."""
    say = progress or (lambda *_: None)
    garments = [g for g in (original, new) if g is not None]
    arm_obj = armature or armature_of(new) or armature_of(original)
    if arm_obj is None:
        raise RuntimeError("Nenhuma armature encontrada (defina manualmente).")

    mapping = bonesmod.detect_arm_bones(arm_obj)
    if mapping_override:
        mapping.update({k: v for k, v in mapping_override.items() if v})
    arm_sets = {s: bonesmod.arm_influence_bones(arm_obj, mapping, s) for s in bonesmod.SIDES
                if (s, "upper_arm") in mapping}
    if not arm_sets:
        raise RuntimeError("UpperArm não detectado; defina os ossos manualmente.")

    say("Fase 1/2: inspeção estática")
    result = {"rig": inspect_rig(arm_obj, mapping, arm_sets), "garments": {}, "poses": [p[0] for p in POSES]}
    joints, tails, ua_len = {}, {}, {}
    for side in arm_sets:
        b = arm_obj.data.bones[mapping[(side, "upper_arm")]]
        joints[side] = np.array(arm_obj.matrix_world @ b.head_local)
        tails[side] = np.array(arm_obj.matrix_world @ b.tail_local)
        ua_len[side] = float(np.linalg.norm(tails[side] - joints[side]))

    body_bind = _body_ref(body, arm_obj, arm_sets) if body else None
    arrays = {}
    for role, ob in (("original", original), ("new", new)):
        if ob is None:
            continue
        rep, arr = inspect_garment(ob, arm_obj, arm_sets)
        rep["uses_same_armature"] = armature_of(ob) == arm_obj
        z = metrics.zones(arr["co"], arr["arm_w"], joints, ua_len)
        rep["weight_zones"] = {
            s: metrics.weight_zone_analysis(arr["co"], arr["edges"], arr["arm_w"][s], z[s],
                                            joints[s], tails[s], ua_len[s])
            for s in arr["arm_w"]
        }
        if body_bind:
            cmp_, off = metrics.body_weight_comparison(arr["co"], arr["arm_w"], body_bind, z)
            arr["body_diff"] = {s: v.pop("_diff") for s, v in cmp_["sides"].items()}
            arr["body_offset"] = off
            rep["body_comparison"] = cmp_
        arr["zones"] = z
        result["garments"][role] = rep
        arrays[role] = arr

    say("Fase 3: testes de pose")
    pose_ids = poses or [p[0] for p in POSES]
    if REFERENCE_POSE not in pose_ids:
        pose_ids = [REFERENCE_POSE] + list(pose_ids)
    posed = {role: {} for role in arrays}
    body_posed = {}
    import bpy
    with pose_session(arm_obj, garments + ([body] if body else [])) as log:
        for pid in pose_ids:
            say(f"  pose {pid}")
            apply_pose(arm_obj, mapping, pid, forward_world, shoulder_assist)
            dg = bpy.context.evaluated_depsgraph_get()
            for role, ob in (("original", original), ("new", new)):
                if role in arrays:
                    posed[role][pid] = evaluated_coords_world(ob, dg)
            if body:
                body_posed[pid] = evaluated_coords_world(body, dg)
    result["session"] = dict(log)

    pose_results = {}
    for role, arr in arrays.items():
        ref = posed[role][REFERENCE_POSE]
        if len(ref) != len(arr["co"]):
            result.setdefault("warnings", []).append(
                f"{role}: malha avaliada tem {len(ref)} vértices vs {len(arr['co'])} originais; "
                "métricas por região desativadas.")
            continue
        tris = arr["tris"]
        tri_w = {s: w[tris].mean(axis=1) for s, w in arr["arm_w"].items()}
        tri_range = {s: w[tris].max(axis=1) - w[tris].min(axis=1) for s, w in arr["arm_w"].items()}
        arr["stretch_vertex"] = {}
        pr = {}
        for pid in pose_ids:
            cur = posed[role][pid]
            smax, smin, area, valid = metrics.triangle_stretch(ref, cur, tris)
            arr["stretch_vertex"][pid] = metrics.per_vertex_max(len(ref), tris, smax, valid)
            bmax, _, _, bvalid = metrics.triangle_stretch(arr["co"], cur, tris)
            entry = {"all": metrics.stats(smax[valid]), "sides": {}}
            for s in tri_w:
                zt = arr["zones"][s]
                armpit_t = zt["armpit"][tris].any(axis=1) & valid
                bridge = (tri_range[s] > 0.5) & valid
                trans_t = (tri_w[s] > 0.05) & (tri_w[s] < 0.95) & valid
                se = {
                    "armpit": metrics.stats(smax[armpit_t]),
                    "transition": metrics.stats(smax[trans_t]),
                    "bridge_triangles": metrics.stats(smax[bridge]),
                    "armpit_compression_p5": round(float(np.percentile(smin[armpit_t], 5)), 3) if armpit_t.any() else None,
                    "armpit_area_ratio_p95": round(float(np.percentile(area[armpit_t], 95)), 3) if armpit_t.any() else None,
                    "torso_far_from_arm": metrics.stats(smax[(tri_w[s] <= 0.05) & ~armpit_t & valid]),
                    "armpit_vs_bind": metrics.stats(bmax[zt["armpit"][tris].any(axis=1) & bvalid]),
                }
                entry["sides"][s] = se
            if body:
                bp = body_posed[pid]
                bref = metrics.BodyRef(bp, body_bind.tris)
                off = metrics.clipping(cur, bref)
                arr.setdefault("clip", {})[pid] = off
                entry["inside_body_pct"] = round(float((off < -0.002).mean() * 100), 2)
                for s in tri_w:
                    zp = arr["zones"][s]["armpit"]
                    entry["sides"][s]["armpit_inside_body_pct"] = (
                        round(float((off[zp] < -0.002).mean() * 100), 2) if zp.any() else None)
            pr[pid] = entry
        pose_results[role] = pr
    result["pose_results"] = pose_results
    result["mapping"] = mapping
    result["_arrays"] = arrays
    result["_posed"] = posed
    result["_body_posed"] = body_posed
    result["_body_tris"] = body_bind.tris if body_bind else None
    return result
