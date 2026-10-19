"""Detecção dos ossos do braço e do conjunto de ossos que "puxam" a manga.

A detecção tenta, em ordem:
1. O mapeamento humanoide do add-on VRM (se existir no arquivo).
2. Nomes comuns (VRoid, Unity/VRChat, Mixamo, Rigify, MMD em japonês).
3. Estrutura (cadeia de filhos a partir do osso escolhido).

Tudo pode ser sobrescrito manualmente no painel.
"""

import re

SIDES = ("L", "R")

_SIDE_TOKENS = {
    "L": [r"(^|[._\-\s])l($|[._\-\s])", r"left", r"左", r"_l_", r"\.l$", r"_l$", r"^l_"],
    "R": [r"(^|[._\-\s])r($|[._\-\s])", r"right", r"右", r"_r_", r"\.r$", r"_r$", r"^r_"],
}

# Ossos auxiliares que também devem contar como "influência do braço"
HELPER_PATTERNS = [r"armpit", r"axil", r"wakì", r"waki", r"脇", r"ワキ", r"sleeve", r"sode", r"袖"]
TWIST_PATTERNS = [r"twist", r"捩", r"roll"]

_VRM_ROLES = {
    "shoulder": "{s}_shoulder",
    "upper_arm": "{s}_upper_arm",
    "lower_arm": "{s}_lower_arm",
    "hand": "{s}_hand",
}


def bone_side(name, head_x=None):
    low = name.lower()
    for side, pats in _SIDE_TOKENS.items():
        for p in pats:
            if re.search(p, low):
                return side
    if head_x is not None and abs(head_x) > 1e-4:
        # Convenção Blender: personagem olha para -Y, lado esquerdo em +X
        return "L" if head_x > 0 else "R"
    return None


def _strip(name):
    low = name.lower()
    low = re.sub(r"(j_bip_|j_sec_|j_adj_|def-|org-|mch-|mixamorig\d*:?|bip0?1)", "", low)
    for tok in ("left", "right", "左", "右"):
        low = low.replace(tok, "")
    low = re.sub(r"(^|[._\-\s:])[lr](?=$|[._\-\s])", " ", low)
    return re.sub(r"[\s_.\-:0-9]", "", low)


def _role_score(role, name):
    n = _strip(name)
    is_twist = any(re.search(p, name.lower()) for p in TWIST_PATTERNS)
    if role == "shoulder":
        if n in ("shoulder", "clavicle", "collar", "肩") or n.endswith("shoulder") or n.endswith("clavicle"):
            return 3
    elif role == "upper_arm":
        if is_twist:
            return 0
        if n in ("upperarm", "upperarms", "arm", "腕", "uparm", "upperarmtwist0"):
            return 3
        if "upperarm" in n:
            return 2
        if n.endswith("arm") and not any(k in n for k in ("fore", "lower", "low")):
            return 1
    elif role == "lower_arm":
        if is_twist:
            return 0
        if n in ("lowerarm", "forearm", "elbow", "ひじ", "肘"):
            return 3
        if "forearm" in n or "lowerarm" in n:
            return 2
    elif role == "hand":
        if n in ("hand", "wrist", "手首"):
            return 3
    return 0


def _vrm_mapping(arm_obj):
    """Lê o mapeamento humanoide do add-on VRM, se estiver instalado/presente."""
    out = {}
    ext = getattr(arm_obj.data, "vrm_addon_extension", None)
    if ext is None:
        return out
    try:
        hb = ext.vrm1.humanoid.human_bones
        for side_key, side in (("left", "L"), ("right", "R")):
            for role, tmpl in _VRM_ROLES.items():
                prop = getattr(hb, tmpl.format(s=side_key), None)
                name = getattr(getattr(prop, "node", None), "bone_name", "") if prop else ""
                if name and name in arm_obj.data.bones:
                    out[(side, role)] = name
    except Exception:
        pass
    return out


def detect_arm_bones(arm_obj):
    """Retorna {(lado, papel): nome_do_osso} para shoulder/upper_arm/lower_arm/hand."""
    bones = arm_obj.data.bones
    found = _vrm_mapping(arm_obj)

    for role in ("shoulder", "upper_arm", "lower_arm", "hand"):
        for side in SIDES:
            if (side, role) in found:
                continue
            best, best_score = None, 0
            for b in bones:
                if bone_side(b.name, b.head_local.x) != side:
                    continue
                s = _role_score(role, b.name)
                if s and b.use_deform:
                    s += 0.5
                if s > best_score:
                    best, best_score = b.name, s
            if best:
                found[(side, role)] = best

    # Completa pela estrutura: primeiro filho não-twist na cadeia
    for side in SIDES:
        for parent_role, child_role in (("upper_arm", "lower_arm"), ("lower_arm", "hand")):
            if (side, child_role) in found or (side, parent_role) not in found:
                continue
            parent = bones[found[(side, parent_role)]]
            queue = list(parent.children)
            while queue:
                c = queue.pop(0)
                if any(re.search(p, c.name.lower()) for p in TWIST_PATTERNS):
                    queue.extend(c.children)
                    continue
                found[(side, child_role)] = c.name
                break
    return found


def arm_influence_bones(arm_obj, mapping, side):
    """Ossos cujo peso conta como "braço" para um lado.

    = toda a subárvore deformante do UpperArm (twist, LowerArm, Hand, dedos,
    ossos de manga/física presos ao braço) + auxiliares de axila do mesmo lado.
    O Shoulder/clavícula NÃO entra (é ombro, não braço).
    """
    bones = arm_obj.data.bones
    result = set()
    ua = mapping.get((side, "upper_arm"))
    if ua and ua in bones:
        stack = [bones[ua]]
        while stack:
            b = stack.pop()
            result.add(b.name)
            stack.extend(b.children)
    for b in bones:
        low = b.name.lower()
        if bone_side(b.name, b.head_local.x) != side:
            continue
        if any(re.search(p, low) for p in HELPER_PATTERNS):
            result.add(b.name)
        elif any(re.search(p, low) for p in TWIST_PATTERNS) and "arm" in _strip(b.name):
            result.add(b.name)
    return result


def shoulder_bones(arm_obj, mapping, side):
    name = mapping.get((side, "shoulder"))
    return {name} if name else set()
