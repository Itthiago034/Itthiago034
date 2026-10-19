"""Cena sintética para testar a ferramenta sem o arquivo real.

Cria: rig em A-pose, corpo, uma roupa "boa" (transição de peso suave junto
ao ombro) e um "moletom" oversized com os defeitos típicos (peso de braço
descendo pela lateral do tronco, fronteira abrupta, vértices sem peso).

    python -m venv venv && venv/bin/pip install bpy
    venv/bin/python blender/tests/synthetic_scene.py /tmp/saida
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_rig():
    arm = bpy.data.armatures.new("Rig")
    ob = bpy.data.objects.new("Armature", arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones

    def bone(name, h, t, parent=None):
        b = eb.new(name)
        b.head, b.tail = Vector(h), Vector(t)
        if parent:
            b.parent = eb[parent]
            b.use_connect = (b.parent.tail - b.head).length < 1e-6
        return b

    bone("Hips", (0, 0, 0.95), (0, 0, 1.1))
    bone("Spine", (0, 0, 1.1), (0, 0, 1.25), "Hips")
    bone("Chest", (0, 0, 1.25), (0, 0, 1.42), "Spine")
    bone("Neck", (0, 0, 1.42), (0, 0, 1.52), "Chest")
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"Shoulder.{s}", (0.03 * sx, 0, 1.40), (0.15 * sx, 0, 1.42), "Chest")
        bone(f"UpperArm.{s}", (0.15 * sx, 0, 1.42), (0.36 * sx, 0, 1.24), f"Shoulder.{s}")
        bone(f"LowerArm.{s}", (0.36 * sx, 0, 1.24), (0.55 * sx, 0, 1.08), f"UpperArm.{s}")
        bone(f"Hand.{s}", (0.55 * sx, 0, 1.08), (0.62 * sx, 0, 1.02), f"LowerArm.{s}")
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def tube_union(name, torso_r, arm_r, voxel=0.012):
    """Tronco + braços como uma única malha conectada (remesh)."""
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(radius=torso_r, depth=0.55, location=(0, 0, 1.2), vertices=48)
    parts.append(bpy.context.active_object)
    for sx in (1, -1):
        a, b = Vector((0.06 * sx, 0, 1.41)), Vector((0.55 * sx, 0, 1.08))
        mid, d = (a + b) / 2, (b - a)
        bpy.ops.mesh.primitive_cylinder_add(radius=arm_r, depth=d.length, location=mid, vertices=32)
        c = bpy.context.active_object
        c.rotation_mode = "QUATERNION"
        c.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
        parts.append(c)
    base = parts[0]
    for p in parts[1:]:
        m = base.modifiers.new("u", "BOOLEAN")
        m.operation, m.object = "UNION", p
    r = base.modifiers.new("r", "REMESH")
    r.mode, r.voxel_size = "VOXEL", voxel
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
    me.transform(base.matrix_world)
    for p in parts:
        bpy.data.objects.remove(p)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def skin(ob, rig, mode, torso_r):
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices])
    names = ["Hips", "Spine", "Chest", "Shoulder.L", "UpperArm.L", "LowerArm.L", "Shoulder.R",
             "UpperArm.R", "LowerArm.R"]
    vg = {n: ob.vertex_groups.new(name=n) for n in names}
    bones = rig.data.bones
    n = len(co)
    W = {k: np.zeros(n) for k in names}
    torso = smoothstep(1.0, 1.15, co[:, 2])
    W["Hips"] = 1 - torso
    W["Chest"] = torso
    for s, sx in (("L", 1), ("R", -1)):
        j = np.array(bones[f"UpperArm.{s}"].head_local)
        t_ = np.array(bones[f"UpperArm.{s}"].tail_local)
        d = (t_ - j) / np.linalg.norm(t_ - j)
        proj = (co - j) @ d / np.linalg.norm(t_ - j)
        side = co[:, 0] * sx > 0
        ax = co[:, 0] * sx
        if mode == "good":
            # transição larga, junto ao ombro, só fora do cilindro do tronco
            arm = smoothstep(-0.15, 0.25, proj) * smoothstep(torso_r - 0.015, torso_r + 0.02, ax) * side
        else:  # defeito: lateral do tronco (até a cintura) com peso 100% de braço, fronteira abrupta
            arm = (((ax > 0.11) & (co[:, 2] > 1.1)) | ((proj > 0.05) & (ax > 0.14))).astype(float) * side
        low = smoothstep(0.85, 1.05, proj) * arm
        sh = np.clip(smoothstep(-0.6, -0.1, proj) * side * (co[:, 2] > 1.3), 0, 1) * (1 - arm) * 0.5
        W[f"UpperArm.{s}"] = arm - low
        W[f"LowerArm.{s}"] = low
        W[f"Shoulder.{s}"] = sh
        W["Chest"] = W["Chest"] * (1 - arm) * (1 - sh)
        W["Hips"] = W["Hips"] * (1 - arm)
    if mode == "bad":
        # alguns vértices órfãos na axila
        orphan = np.where(np.linalg.norm(co - np.array([0.12, -0.12, 1.2]), axis=1) < 0.03)[0]
        for k in W:
            W[k][orphan] = 0
    for k, arr in W.items():
        for i in np.where(arr > 1e-4)[0]:
            vg[k].add([int(i)], float(arr[i]), "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    if mode == "bad":
        mod.use_deform_preserve_volume = True
    ob.parent = rig


def build():
    reset()
    rig = make_rig()
    body = tube_union("Body", 0.12, 0.045)
    skin(body, rig, "good", 0.12)
    jacket = tube_union("Jaqueta", 0.135, 0.06)
    skin(jacket, rig, "good", 0.135)
    hoodie = tube_union("Moletom", 0.17, 0.10)
    skin(hoodie, rig, "bad", 0.17)
    hoodie.modifiers.new("Subdiv", "SUBSURF").levels = 1
    return rig, body, jacket, hoodie


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gdi_test"
    rig, body, jacket, hoodie = build()
    rig.pose.bones["UpperArm.L"].rotation_mode = "XYZ"
    rig.pose.bones["UpperArm.L"].rotation_euler = (0.1, 0.2, 0.3)  # pose "do usuário" a preservar
    import cli_inspect
    cli_inspect.main(["--original", "Jaqueta", "--new", "Moletom", "--body", "Body", "--out", out])
    pb = rig.pose.bones["UpperArm.L"]
    assert pb.rotation_mode == "XYZ" and abs(pb.rotation_euler.z - 0.3) < 1e-6, "pose não restaurada"
    assert hoodie.modifiers["Subdiv"].show_viewport, "modificador não restaurado"
    import json
    data = json.load(open(os.path.join(out, "dados.json"), encoding="utf-8"))
    titles = [f["title"] for f in data["diagnosis"]["findings"] if f["status"] == "CONFIRMADO"]
    for expected in ("sem nenhum peso", "Fronteira tronco", "Triângulos-ponte", "Preserve Volume"):
        assert any(expected in t for t in titles), f"defeito não detectado: {expected}"
    assert not any("sem nenhum peso" in f["title"] for f in data["diagnosis"]["findings"]
                   if "Jaqueta" in str(f)), "falso positivo"
    print("OK: pose e modificadores restaurados; defeitos injetados detectados")
