"""Garment Deform Inspector — análise comparativa de deformação de roupas.

Painel: View3D ▸ Sidebar (N) ▸ aba "Roupa 3D".
"""

bl_info = {
    "name": "Garment Deform Inspector",
    "author": "Itthiago034",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Roupa 3D",
    "description": "Compara a deformação de duas roupas no mesmo rig e gera relatório técnico (somente leitura)",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib

    for _m in (bones, inspect_static, poses, metrics, runner, diagnosis, svg, report):  # noqa: F821
        importlib.reload(_m)

import os

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, PointerProperty, StringProperty

from . import bones, diagnosis, inspect_static, metrics, poses, report, runner, svg  # noqa: F401

_LAST = {"result": None, "diag": None}
_PREVIEW_STATE = {}

FORWARD_ITEMS = [
    ("-Y", "-Y (padrão Blender/VRM)", ""), ("+Y", "+Y", ""),
    ("-X", "-X", ""), ("+X", "+X", ""),
]
_FWD = {"-Y": (0, -1, 0), "+Y": (0, 1, 0), "-X": (-1, 0, 0), "+X": (1, 0, 0)}


def _poll_mesh(self, ob):
    return ob.type == "MESH"


def _poll_arm(self, ob):
    return ob.type == "ARMATURE"


class GDI_Settings(bpy.types.PropertyGroup):
    armature: PointerProperty(name="Armature", type=bpy.types.Object, poll=_poll_arm)
    body: PointerProperty(name="Corpo", type=bpy.types.Object, poll=_poll_mesh,
                          description="Malha do corpo (opcional): habilita colisão e comparação de pesos")
    original: PointerProperty(name="Roupa original", type=bpy.types.Object, poll=_poll_mesh)
    new: PointerProperty(name="Roupa nova", type=bpy.types.Object, poll=_poll_mesh)
    forward: EnumProperty(name="Frente do personagem", items=FORWARD_ITEMS, default="-Y")
    shoulder_assist: FloatProperty(name="Auxílio do ombro", min=0, max=1, default=0,
                                   description="Fração de elevação da clavícula nas poses acima de 90°")
    out_dir: StringProperty(name="Pasta do relatório", subtype="DIR_PATH", default="//relatorio_roupa/")
    preview_pose: EnumProperty(name="Pose", items=[(p[0], p[1], "") for p in poses.POSES])
    l_upper_arm: StringProperty(name="UpperArm L")
    r_upper_arm: StringProperty(name="UpperArm R")
    l_lower_arm: StringProperty(name="LowerArm L")
    r_lower_arm: StringProperty(name="LowerArm R")
    l_shoulder: StringProperty(name="Shoulder L")
    r_shoulder: StringProperty(name="Shoulder R")


def _override(st):
    m = {}
    for side, pre in (("L", "l_"), ("R", "r_")):
        for role in ("upper_arm", "lower_arm", "shoulder"):
            v = getattr(st, pre + role)
            if v:
                m[(side, role)] = v
    return m


def _arm(st):
    if st.armature:
        return st.armature
    return inspect_static.armature_of(st.new) if st.new else None


class GDI_OT_detect(bpy.types.Operator):
    bl_idname = "gdi.detect_bones"
    bl_label = "Detectar ossos"
    bl_description = "Preenche os ossos do braço automaticamente (pode ser editado depois)"

    def execute(self, context):
        st = context.scene.gdi
        arm = _arm(st)
        if not arm:
            self.report({"ERROR"}, "Defina a armature ou a roupa nova")
            return {"CANCELLED"}
        st.armature = arm
        mp = bones.detect_arm_bones(arm)
        for side, pre in (("L", "l_"), ("R", "r_")):
            for role in ("upper_arm", "lower_arm", "shoulder"):
                setattr(st, pre + role, mp.get((side, role), ""))
        return {"FINISHED"}


class GDI_OT_analyze(bpy.types.Operator):
    bl_idname = "gdi.analyze"
    bl_label = "Analisar e gerar relatório"
    bl_description = "Fases 1–5 sem modificar o arquivo; restaura poses ao final"

    def execute(self, context):
        st = context.scene.gdi
        if not st.new:
            self.report({"ERROR"}, "Defina a roupa nova")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "Use o Object Mode")
            return {"CANCELLED"}
        try:
            res = runner.run_analysis(st.original, st.new, _arm(st), st.body, _override(st),
                                      _FWD[st.forward], st.shoulder_assist,
                                      progress=lambda m: print("[GDI]", m))
        except Exception as e:  # noqa: BLE001
            self.report({"ERROR"}, f"Falha: {e}")
            raise
        diag = diagnosis.diagnose(res)
        out = bpy.path.abspath(st.out_dir) if st.out_dir else ""
        if not out or out.startswith("//"):
            import tempfile
            out = os.path.join(tempfile.gettempdir(), "relatorio_roupa")
        path = report.write_report(res, diag, out, _FWD[st.forward])
        _LAST.update(result=res, diag=diag, path=path)
        n = sum(1 for f in diag["findings"] if f["status"] == diagnosis.CONFIRMED)
        self.report({"INFO"}, f"{n} problemas confirmados. Relatório: {path}")
        return {"FINISHED"}


class GDI_OT_diag_copy(bpy.types.Operator):
    bl_idname = "gdi.diagnostic_copy"
    bl_label = "Criar cópias diagnósticas"
    bl_description = ("Duplica as roupas numa coleção separada com atributos de cor "
                      "(peso de braço, estiramento por pose). Os originais não são tocados")

    def execute(self, context):
        res = _LAST.get("result")
        st = context.scene.gdi
        if not res:
            self.report({"ERROR"}, "Rode a análise primeiro")
            return {"CANCELLED"}
        coll = bpy.data.collections.get("GDI_Diagnostico") or bpy.data.collections.new("GDI_Diagnostico")
        if coll.name not in context.scene.collection.children:
            context.scene.collection.children.link(coll)
        for role, src in (("original", st.original), ("new", st.new)):
            arr = res["_arrays"].get(role)
            if src is None or arr is None:
                continue
            ob = src.copy()
            ob.data = src.data.copy()
            ob.name = f"{src.name}_GDI"
            coll.objects.link(ob)
            me = ob.data
            n = len(me.vertices)

            def put(name, values):
                rgb = svg._ramp(np.asarray(values)) / 255.0
                col = np.ones((n, 4), dtype=np.float32)
                col[:, :3] = rgb
                attr = me.color_attributes.get(name) or me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
                attr.data.foreach_set("color", col.ravel())

            put("GDI_peso_braco", np.max(np.stack(list(arr["arm_w"].values())), axis=0))
            for pid, v in arr.get("stretch_vertex", {}).items():
                if pid != "DOWN":
                    put(f"GDI_estir_{pid}", svg.stretch_to_unit(v))
            if "body_diff" in arr:
                put("GDI_dif_corpo", np.max(np.stack(list(arr["body_diff"].values())), axis=0))
            me.color_attributes.active_color_name = "GDI_peso_braco"
        self.report({"INFO"}, "Cópias em 'GDI_Diagnostico' (oculte os originais para comparar). "
                              "Viewport Shading ▸ Color ▸ Attribute")
        return {"FINISHED"}


class GDI_OT_preview(bpy.types.Operator):
    bl_idname = "gdi.preview_pose"
    bl_label = "Pré-visualizar pose"
    bl_description = "Aplica uma pose de teste; use 'Restaurar pose' para voltar exatamente ao estado anterior"

    def execute(self, context):
        st = context.scene.gdi
        arm = _arm(st)
        if not arm:
            return {"CANCELLED"}
        if arm.name not in _PREVIEW_STATE:
            _PREVIEW_STATE[arm.name] = poses._snapshot(arm)
            ad = arm.animation_data
            if ad:
                ad.action = None
                ad.use_nla = False
        arm.data.pose_position = "POSE"
        mp = bones.detect_arm_bones(arm)
        mp.update(_override(st))
        poses.apply_pose(arm, mp, st.preview_pose, _FWD[st.forward], st.shoulder_assist)
        return {"FINISHED"}


class GDI_OT_restore(bpy.types.Operator):
    bl_idname = "gdi.restore_pose"
    bl_label = "Restaurar pose"

    @classmethod
    def poll(cls, context):
        return bool(_PREVIEW_STATE)

    def execute(self, context):
        for name, state in list(_PREVIEW_STATE.items()):
            ob = bpy.data.objects.get(name)
            if ob:
                poses._restore(ob, state)
            del _PREVIEW_STATE[name]
        context.view_layer.update()
        return {"FINISHED"}


class GDI_PT_panel(bpy.types.Panel):
    bl_label = "Garment Deform Inspector"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Roupa 3D"

    def draw(self, context):
        st = context.scene.gdi
        L = self.layout
        col = L.column(align=True)
        col.prop(st, "original")
        col.prop(st, "new")
        col.prop(st, "body")
        col.prop(st, "armature")
        box = L.box()
        box.label(text="Ossos do braço")
        box.operator("gdi.detect_bones", icon="BONE_DATA")
        if st.armature:
            for p in ("l_shoulder", "l_upper_arm", "l_lower_arm", "r_shoulder", "r_upper_arm", "r_lower_arm"):
                box.prop_search(st, p, st.armature.data, "bones")
        L.prop(st, "forward")
        L.prop(st, "shoulder_assist")
        row = L.row(align=True)
        row.prop(st, "preview_pose", text="")
        row.operator("gdi.preview_pose", text="", icon="ARMATURE_DATA")
        row.operator("gdi.restore_pose", text="", icon="LOOP_BACK")
        if _PREVIEW_STATE:
            L.label(text="Pose de teste ativa — restaure antes de salvar", icon="ERROR")
        L.prop(st, "out_dir")
        L.operator("gdi.analyze", icon="VIEWZOOM")
        L.operator("gdi.diagnostic_copy", icon="DUPLICATE")
        if _LAST.get("diag"):
            box = L.box()
            for f in _LAST["diag"]["findings"][:12]:
                if f["status"] in (diagnosis.CONFIRMED, diagnosis.DISCARDED):
                    box.label(text=f"{f['status']}: {f['title']}",
                              icon="ERROR" if f["status"] == diagnosis.CONFIRMED else "CHECKMARK")
            if _LAST.get("path"):
                box.label(text=_LAST["path"])


classes = (GDI_Settings, GDI_OT_detect, GDI_OT_analyze, GDI_OT_diag_copy, GDI_OT_preview,
           GDI_OT_restore, GDI_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.gdi = PointerProperty(type=GDI_Settings)


def unregister():
    del bpy.types.Scene.gdi
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
