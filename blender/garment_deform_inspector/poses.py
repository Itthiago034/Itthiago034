"""Poses de teste e sessão que SEMPRE restaura o estado original.

As poses são definidas em termos anatômicos (abdução/flexão do braço e
flexão do cotovelo) e convertidas para rotações dos ossos a partir da
pose de repouso, então funcionam com rigs em T-pose ou A-pose.
"""

import math
from contextlib import contextmanager

import bpy
from mathutils import Matrix, Vector

from .inspect_static import TOPOLOGY_MODIFIERS

# id, rótulo, abdução do braço (0 = colado ao corpo, 90 = horizontal,
# 180 = vertical para cima), flexão para frente, flexão do cotovelo
POSES = [
    ("DOWN", "Braços abaixados", 8.0, 0.0, 0.0),
    ("RAISE45", "Braços a 45°", 45.0, 0.0, 0.0),
    ("HORIZONTAL", "Braços abertos na horizontal", 90.0, 0.0, 0.0),
    ("OVERHEAD", "Braços acima da cabeça", 160.0, 0.0, 0.0),
    ("FRONT_FLEX", "Braços flexionados diante do corpo", 18.0, 40.0, 115.0),
]
REFERENCE_POSE = "DOWN"


def _snapshot(arm_obj):
    state = {"pose_position": arm_obj.data.pose_position, "bones": {}}
    for pb in arm_obj.pose.bones:
        state["bones"][pb.name] = (
            pb.rotation_mode, pb.location.copy(), pb.rotation_quaternion.copy(),
            pb.rotation_euler.copy(), tuple(pb.rotation_axis_angle), pb.scale.copy(),
        )
    ad = arm_obj.animation_data
    if ad:
        state["anim"] = {
            "action": ad.action,
            "slot": getattr(ad, "action_slot", None),
            "use_nla": ad.use_nla,
        }
    return state


def _restore(arm_obj, state):
    arm_obj.data.pose_position = state["pose_position"]
    for name, (mode, loc, q, e, aa, s) in state["bones"].items():
        pb = arm_obj.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = mode
        pb.location = loc
        pb.rotation_quaternion = q
        pb.rotation_euler = e
        pb.rotation_axis_angle = aa
        pb.scale = s
    anim = state.get("anim")
    if anim:
        ad = arm_obj.animation_data
        ad.action = anim["action"]
        if anim["slot"] is not None and hasattr(ad, "action_slot"):
            try:
                ad.action_slot = anim["slot"]
            except Exception:
                pass
        ad.use_nla = anim["use_nla"]


def _state_equal(arm_obj, state, eps=1e-6):
    if arm_obj.data.pose_position != state["pose_position"]:
        return False
    for name, (mode, loc, q, e, aa, s) in state["bones"].items():
        pb = arm_obj.pose.bones.get(name)
        if pb is None or pb.rotation_mode != mode:
            return False
        if (pb.location - loc).length > eps or (pb.scale - s).length > eps:
            return False
        if (Vector(pb.rotation_quaternion) - Vector(q)).length > eps:
            return False
        if (Vector(pb.rotation_euler) - Vector(e)).length > eps:
            return False
    return True


@contextmanager
def pose_session(arm_obj, garments=(), disable_topology_mods=True):
    """Guarda pose, animação e visibilidade de modificadores; restaura no fim.

    Modificadores que mudam topologia (Subdivision, Solidify...) ficam
    desligados só durante a medição para manter correspondência 1:1 entre
    vértices. Tudo volta ao estado original mesmo em caso de erro.
    """
    state = _snapshot(arm_obj)
    mod_state = []
    log = {"restored": False, "disabled_modifiers": []}
    try:
        ad = arm_obj.animation_data
        if ad:
            ad.action = None
            ad.use_nla = False
        arm_obj.data.pose_position = "POSE"
        if disable_topology_mods:
            for ob in garments:
                if ob is None:
                    continue
                for m in ob.modifiers:
                    if m.type in TOPOLOGY_MODIFIERS and m.show_viewport:
                        mod_state.append((m, m.show_viewport))
                        m.show_viewport = False
                        log["disabled_modifiers"].append(f"{ob.name}:{m.name}")
        yield log
    finally:
        for m, vis in mod_state:
            m.show_viewport = vis
        _restore(arm_obj, state)
        bpy.context.view_layer.update()
        log["restored"] = _state_equal(arm_obj, state)


def reset_to_rest(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_axis_angle = (0, 0, 1, 0)
        pb.scale = (1, 1, 1)


def _aim(arm_obj, pb, target_dir):
    """Gira o osso (em torno da cabeça) para apontar na direção dada (espaço da armature)."""
    bpy.context.view_layer.update()
    cur = (pb.tail - pb.head)
    if cur.length < 1e-9 or target_dir.length < 1e-9:
        return
    q = cur.normalized().rotation_difference(target_dir.normalized())
    head = pb.head.copy()
    M = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ pb.matrix
    pb.matrix = M
    bpy.context.view_layer.update()


def axes(arm_obj, forward_world=(0.0, -1.0, 0.0)):
    R = arm_obj.matrix_world.to_3x3().inverted()
    up = (R @ Vector((0, 0, 1))).normalized()
    fwd = (R @ Vector(forward_world)).normalized()
    return up, fwd


def apply_pose(arm_obj, mapping, pose_id, forward_world=(0.0, -1.0, 0.0), shoulder_assist=0.0):
    """Coloca o rig numa das POSES. Shoulder fica em repouso, a menos que
    shoulder_assist > 0 (fração da elevação aplicada à clavícula)."""
    pose = next(p for p in POSES if p[0] == pose_id)
    _, _, abd, flex, elbow = pose
    reset_to_rest(arm_obj)
    bpy.context.view_layer.update()
    up, fwd = axes(arm_obj, forward_world)
    for side in ("L", "R"):
        ua = arm_obj.pose.bones.get(mapping.get((side, "upper_arm"), ""))
        if ua is None:
            continue
        rest_dir = ua.bone.tail_local - ua.bone.head_local
        lat = rest_dir - up * rest_dir.dot(up) - fwd * rest_dir.dot(fwd)
        lat = lat.normalized() if lat.length > 1e-6 else Vector((1 if side == "L" else -1, 0, 0))

        sh = arm_obj.pose.bones.get(mapping.get((side, "shoulder"), ""))
        if sh is not None and shoulder_assist > 0 and abd > 90:
            lift = math.radians((abd - 90) * shoulder_assist * 0.35)
            sdir = (sh.bone.tail_local - sh.bone.head_local).normalized()
            _aim(arm_obj, sh, sdir * math.cos(lift) + up * math.sin(lift))

        a = math.radians(abd)
        d = -up * math.cos(a) + lat * math.sin(a)
        f = math.radians(flex)
        d = (d * math.cos(f) + fwd * math.sin(f)).normalized()
        _aim(arm_obj, ua, d)

        la = arm_obj.pose.bones.get(mapping.get((side, "lower_arm"), ""))
        if la is not None and elbow > 0:
            bend = fwd - lat * 0.35
            bend = (bend - d * bend.dot(d)).normalized()
            e = math.radians(elbow)
            _aim(arm_obj, la, d * math.cos(e) + bend * math.sin(e))
    bpy.context.view_layer.update()


def evaluated_coords_world(obj, depsgraph=None):
    """Coordenadas avaliadas (após modificadores) em espaço de mundo."""
    import numpy as np

    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    ob_eval = obj.evaluated_get(dg)
    me = ob_eval.to_mesh()
    try:
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ob_eval.matrix_world, dtype=np.float64)
        return co @ M[:3, :3].T + M[:3, 3]
    finally:
        ob_eval.to_mesh_clear()


def joint_world(arm_obj, bone_name, pose=False):
    if pose:
        p = arm_obj.pose.bones[bone_name].head
    else:
        p = arm_obj.data.bones[bone_name].head_local
    return arm_obj.matrix_world @ p
