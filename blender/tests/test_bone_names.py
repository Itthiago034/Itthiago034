"""Detecção de ossos com convenções de nomes comuns (VRoid, Mixamo, MMD, Rigify, VRChat)."""

import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from garment_deform_inspector import bones  # noqa: E402

RIGS = {
    "vroid": ["J_Bip_C_Chest", "J_Bip_{s}_Shoulder", "J_Bip_{s}_UpperArm", "J_Bip_{s}_LowerArm", "J_Bip_{s}_Hand"],
    "mixamo": ["mixamorig:Spine2", "mixamorig:{S}Shoulder", "mixamorig:{S}Arm", "mixamorig:{S}ForeArm", "mixamorig:{S}Hand"],
    "mmd": ["上半身2", "{J}肩", "{J}腕", "{J}ひじ", "{J}手首"],
    "rigify": ["DEF-spine.003", "DEF-shoulder.{s}", "DEF-upper_arm.{s}", "DEF-forearm.{s}", "DEF-hand.{s}"],
    "vrchat": ["Chest", "Left shoulder" , "Left arm", "Left elbow", "Left wrist"],
}


def build(names, side):
    arm = bpy.data.armatures.new("A")
    ob = bpy.data.objects.new("A", arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    sx = 1 if side == "L" else -1
    pts = [(0, 1.3), (0.03, 1.4), (0.15, 1.42), (0.36, 1.24), (0.55, 1.08), (0.62, 1.02)]
    prev = None
    for i, n in enumerate(names):
        b = arm.edit_bones.new(n)
        b.head = Vector((pts[i][0] * sx, 0, pts[i][1]))
        b.tail = Vector((pts[i + 1][0] * sx, 0, pts[i + 1][1]))
        b.parent = prev
        prev = b
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


fails = 0
for rig, tmpl in RIGS.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    side = "L"
    names = [t.format(s=side, S="Left", J="左") for t in tmpl]
    ob = build(names, side)
    m = bones.detect_arm_bones(ob)
    got = [m.get((side, r)) for r in ("shoulder", "upper_arm", "lower_arm", "hand")]
    ok = got == names[1:]
    fails += not ok
    print(f"{'OK ' if ok else 'ERR'} {rig:7s} {got}")
sys.exit(1 if fails else 0)
