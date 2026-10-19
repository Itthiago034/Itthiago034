"""Fase 4/5: regras que transformam medições em achados e recomendações.

Cada achado tem um status explícito:
- CONFIRMADO: medido diretamente nos dados do arquivo.
- DESCARTADO: hipótese testada e contrariada pelos dados.
- HIPÓTESE: compatível com os dados, mas não provado pela ferramenta.
- OBSERVAÇÃO: fato que não explica o problema, mas importa (ex.: exportação).
"""

CONFIRMED, DISCARDED, HYPOTHESIS, NOTE = "CONFIRMADO", "DESCARTADO", "HIPÓTESE", "OBSERVAÇÃO"

# Limiares (razão de comprimento). Ajustáveis.
STRETCH_OK = 1.35
STRETCH_BAD = 1.8


def _g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def _worst_side(pr, role, pose, key="armpit", stat="p99"):
    sides = _g(pr, role, pose, "sides", default={}) or {}
    vals = [(_g(v, key, stat, default=0) or 0, s) for s, v in sides.items()]
    return max(vals) if vals else (0, None)


def _ratio(a, b):
    return (a / b) if b else float("inf") if a else 1.0


def diagnose(result):
    F, R = [], []
    g = result["garments"]
    orig, new = g.get("original"), g.get("new")
    pr = result.get("pose_results", {})
    poses = [p for p in result["poses"] if p != "DOWN"]

    def add(status, area, title, evidence, component=None):
        F.append({"status": status, "area": area, "title": title, "evidence": evidence, "component": component})

    if not new:
        return {"findings": F, "recommendations": R}

    # ------------------------------------------------------------ esqueleto
    if orig:
        same = orig.get("uses_same_armature") and new.get("uses_same_armature")
        o_oh, _ = _worst_side(pr, "original", "OVERHEAD")
        n_oh, _ = _worst_side(pr, "new", "OVERHEAD")
        if same and o_oh and o_oh <= STRETCH_BAD and n_oh > max(STRETCH_BAD, o_oh * 1.3):
            add(DISCARDED, "Rig", "O esqueleto não é a causa principal",
                f"Mesmo rig e mesmas poses: axila da roupa original p99 = {o_oh:.2f}× vs "
                f"moletom p99 = {n_oh:.2f}× (braços acima da cabeça).", "Rig")
        elif same and o_oh > STRETCH_BAD:
            add(HYPOTHESIS, "Rig", "O rig também pode contribuir",
                f"A roupa original também estica na axila acima da cabeça (p99 = {o_oh:.2f}×); "
                "verificar limites de rotação, roll do UpperArm e ossos auxiliares.", "Rig")
        elif not same:
            add(CONFIRMED, "Rig", "As roupas usam armatures diferentes",
                "O Armature Modifier / parent das duas roupas não aponta para o mesmo objeto.", "Armature Modifier")

    # ------------------------------------------------------------ estiramento medido
    for pose in poses:
        n_v, n_s = _worst_side(pr, "new", pose)
        o_v, _ = _worst_side(pr, "original", pose)
        if n_v > STRETCH_BAD and (not orig or n_v > o_v * 1.3):
            pct = _g(pr, "new", pose, "sides", n_s, "armpit", "pct_over_2", default=0)
            add(CONFIRMED, "Deformação", f"Estiramento excessivo na axila — {pose}",
                f"Moletom: p99 {n_v:.2f}×, {pct}% dos triângulos da axila acima de 2×"
                + (f"; original: p99 {o_v:.2f}×." if orig else "."), "Pesos / topologia")
        bt = _g(pr, "new", pose, "sides", n_s, "bridge_triangles", "p95", default=0) if n_s else 0
        if bt and bt > STRETCH_BAD:
            add(CONFIRMED, "Deformação", f"Triângulos-ponte entre tronco e braço — {pose}",
                f"Triângulos cujos vértices variam >0.5 de peso de braço esticam p95 {bt:.2f}× "
                "(efeito membrana).", "Pesos")
        comp = _g(pr, "new", pose, "sides", n_s, "armpit_compression_p5", default=None) if n_s else None
        if comp is not None and comp < 0.5:
            add(CONFIRMED, "Deformação", f"Compressão forte na axila — {pose}",
                f"5% dos triângulos da axila encolhem para ≤{comp:.2f}× numa direção: o tecido "
                "se sobrepõe e forma volume artificial.", "Pesos / volume")
        tor = max((_g(v, "torso_far_from_arm", "p95", default=0) or 0)
                  for v in (_g(pr, "new", pose, "sides", default={}) or {}).values()) if n_s else 0
        if tor > STRETCH_OK:
            add(CONFIRMED, "Deformação", f"Tronco deforma longe do braço — {pose}",
                f"Triângulos sem peso de braço e fora da axila esticam p95 {tor:.2f}× "
                "(influência do Shoulder/Chest espalhada demais).", "Pesos do tronco")
        clip_n = _g(pr, "new", pose, "inside_body_pct")
        clip_o = _g(pr, "original", pose, "inside_body_pct")
        if clip_n is not None and clip_n > 2 and (clip_o is None or clip_n > clip_o * 1.5):
            add(CONFIRMED, "Colisão", f"Roupa atravessa o corpo — {pose}",
                f"{clip_n}% dos vértices do moletom ficam dentro do corpo"
                + (f" (original: {clip_o}%)." if clip_o is not None else "."), "Pesos / offset")

    nb, nbs = _worst_side(pr, "new", "DOWN", key="armpit_vs_bind")
    ob_, _ = _worst_side(pr, "original", "DOWN", key="armpit_vs_bind")
    if nb > STRETCH_BAD and (not orig or nb > ob_ * 1.3):
        add(CONFIRMED, "Deformação", "Axila já distorce ao baixar os braços",
            f"Da malha modelada para a pose abaixada, a axila do moletom estica p99 {nb:.2f}×"
            + (f" (original: {ob_:.2f}×)." if orig else "."), "Pesos da axila")

    # ------------------------------------------------------------ pesos
    w = new["weights"]
    if w["zero_weight_vertices"]:
        add(CONFIRMED, "Pesos", "Vértices sem nenhum peso deformante",
            f"{w['zero_weight_vertices']} vértices ficam parados na pose de bind enquanto os vizinhos "
            "se movem — estica a malha ao redor.", "Vertex Groups")
    if w["groups_without_bone"]:
        add(NOTE, "Pesos", "Vertex groups sem osso correspondente",
            f"{len(w['groups_without_bone'])} grupos ignorados pelo Armature: "
            f"{', '.join(w['groups_without_bone'][:8])}" + ("…" if len(w["groups_without_bone"]) > 8 else ""),
            "Vertex Groups")
    if w["unnormalized_vertices"]:
        add(NOTE, "Pesos", "Pesos não normalizados",
            f"{w['unnormalized_vertices']} vértices com soma ≠ 1. O Blender normaliza ao deformar, "
            "mas o resultado muda se outro grupo for editado/limpo.", "Vertex Groups")
    if w["vertices_over_4_influences"]:
        add(NOTE, "Exportação", "Mais de 4 influências por vértice",
            f"{w['vertices_over_4_influences']} vértices (máx. {w['max_influences']}). Unity/VRM costumam "
            "descartar as menores: a deformação no app VTuber pode diferir do Blender.", "Vertex Groups")

    # ------------------------------------------------------------ zonas de peso (causa geométrica)
    if orig:
        for side, nz in new.get("weight_zones", {}).items():
            oz = orig.get("weight_zones", {}).get(side, {})
            nh, oh = nz.get("hard_edge_dist_to_joint_p50"), oz.get("hard_edge_dist_to_joint_p50")
            if nh and oh and nh > oh * 1.3:
                add(CONFIRMED, "Pesos", f"Fronteira tronco→braço longe do pivô do ombro ({side})",
                    f"Arestas com salto de peso >0.3 ficam a {nh:.2f}× o comprimento do UpperArm da "
                    f"articulação (original: {oh:.2f}×). Quanto mais longe do pivô, mais a fronteira se "
                    "abre ao levantar o braço.", "Pesos da axila")
            nb, ob = nz.get("transition_below_joint_p90"), oz.get("transition_below_joint_p90")
            if nb is not None and ob is not None and nb > ob + 0.25:
                add(CONFIRMED, "Pesos", f"Peso de braço desce pela lateral do tronco ({side})",
                    f"A transição chega {nb:.2f}× UpperArm abaixo do ombro (original: {ob:.2f}×).",
                    "Pesos da axila")
            ng, og = nz.get("gradient_per_cm_p95"), oz.get("gradient_per_cm_p95")
            if ng and og and ng > og * 1.5:
                add(CONFIRMED, "Pesos", f"Transição de peso abrupta ({side})",
                    f"Variação de peso por cm (p95) {ng:.2f} vs {og:.2f} na original.", "Pesos da axila")
            nr, orr = nz.get("edge_rings_across_transition"), oz.get("edge_rings_across_transition")
            if nr is not None and nr < 3 and (orr is None or nr < orr):
                add(CONFIRMED, "Topologia", f"Poucos anéis de aresta na transição ({side})",
                    f"~{nr} anéis cruzam a transição (original: {orr}). Pouca geometria para distribuir "
                    "a rotação.", "Topologia do ombro/axila")
            nd, od = nz.get("arm_weighted_dist_to_bone_p90"), oz.get("arm_weighted_dist_to_bone_p90")
            if nd and od and nd > od * 1.3:
                add(CONFIRMED, "Formato oversized", f"Tecido com peso de braço longe do osso ({side})",
                    f"p90 da distância ao eixo do UpperArm = {nd:.2f}× seu comprimento (original: {od:.2f}×). "
                    "Peso rígido de braço nesse tecido gira com alavanca longa.", "Pesos da manga")

    # ------------------------------------------------------------ comparação com o corpo
    bc = new.get("body_comparison")
    if bc:
        for side, s in bc["sides"].items():
            cp = s.get("loose_copied_body_weights_pct")
            if cp is not None and cp > 50 and s.get("loose_armpit_vertices", 0) > 10:
                add(HYPOTHESIS, "Pesos", f"Pesos copiados do corpo por proximidade ({side})",
                    f"{cp}% do tecido solto da axila (afastado {s.get('loose_offset_mm_p50')} mm do corpo) "
                    "tem pesos quase idênticos ao ponto mais próximo do corpo — assinatura de "
                    "Data Transfer/“Transfer Weights” por superfície mais próxima.", "Pesos da axila")

    # ------------------------------------------------------------ modificadores
    for issue in new.get("modifier_issues", []):
        add(CONFIRMED, "Modificadores", "Problema na pilha de modificadores", issue, "Modificadores")
    if orig and orig.get("armature_modifier") and new.get("armature_modifier"):
        oa, na = orig["armature_modifier"], new["armature_modifier"]
        for k, label in (("use_deform_preserve_volume", "Preserve Volume (Dual Quaternion)"),
                         ("use_bone_envelopes", "Bone Envelopes"),
                         ("use_multi_modifier", "Multi Modifier"),
                         ("vertex_group", "Vertex group de máscara")):
            if oa.get(k) != na.get(k):
                add(CONFIRMED, "Modificadores", f"Armature Modifier difere: {label}",
                    f"Original = {oa.get(k)!r}; moletom = {na.get(k)!r}.", "Armature Modifier")
    o_types = {m["type"] for m in (orig or {}).get("modifiers", [])}
    n_types = {m["type"] for m in new.get("modifiers", [])}
    for t in sorted((o_types - n_types) & {"CORRECTIVE_SMOOTH", "SURFACE_DEFORM", "MESH_DEFORM",
                                             "LAPLACIANSMOOTH", "SMOOTH", "CLOTH", "DATA_TRANSFER"}):
        add(CONFIRMED, "Correção", f"Original usa {t}, o moletom não", "Mecanismo de deformação ausente.",
            "Modificadores")

    # ------------------------------------------------------------ corretivos
    if orig:
        ock = orig["shape_keys"]["corrective_keys"]
        nck = new["shape_keys"]["corrective_keys"]
        if ock and not nck:
            add(CONFIRMED, "Correção", "Original tem Shape Keys corretivas; moletom não",
                f"Corretivas da original: {', '.join(ock)}.", "Shape Keys")
        oh = set(orig["weights"].get("helper_bones_used", []))
        nh = set(new["weights"].get("helper_bones_used", []))
        if oh - nh:
            add(CONFIRMED, "Pesos", "Ossos auxiliares usados só pela original",
                f"{', '.join(sorted(oh - nh))}.", "Vertex Groups")
        if not ock and not orig["object_drivers"] and not (o_types - n_types):
            add(NOTE, "Correção", "A original não depende de corretivos",
                "Sem Shape Keys corretivas, drivers ou modificadores extras: a boa deformação vem de "
                "pesos + topologia.", None)
    if new["shape_keys"]["nonzero_at_rest"]:
        add(NOTE, "Shape Keys", "Shape Keys ativas sem driver",
            ", ".join(new["shape_keys"]["nonzero_at_rest"]), "Shape Keys")

    t = new["transform"]
    if not (t["scale_applied"] and t["rotation_applied"]) or t["negative_scale"]:
        add(NOTE, "Transformação", "Transformação do objeto não aplicada",
            f"Escala {t['scale']}, rotação {t['rotation_euler_deg']}. Afeta transferências e exportação.",
            "Objeto")
    if new["topology"]["overlapping_vertex_pairs"]:
        add(NOTE, "Topologia", "Vértices sobrepostos",
            f"{new['topology']['overlapping_vertex_pairs']} pares a <0.1 mm (costuras soltas podem abrir).",
            "Topologia")

    # ------------------------------------------------------------ hipóteses fora do alcance da ferramenta
    add(HYPOTHESIS, "A verificar", "Comportamento no app VTuber (Unity/VRM)",
        "Drivers, constraints, Corrective Smooth e Dual Quaternion não são exportados para VRM/Unity; "
        "testar a roupa exportada no app final.", None)
    add(HYPOTHESIS, "A verificar", "Ossos de física (PhysBones/SpringBones) na manga",
        "Ossos secundários podem mover a manga em runtime e não aparecem nesta análise estática.", None)

    R.extend(_recommendations(F, new, orig))
    return {"findings": F, "recommendations": R}


def _has(F, *words):
    return any(f["status"] == CONFIRMED and any(w in f["title"] for w in words) for f in F)


def _recommendations(F, new, orig):
    R = []

    def rec(prio, title, why, how, risk):
        R.append({"priority": prio, "title": title, "why": why, "how": how, "risk": risk})

    if _has(F, "sem nenhum peso", "pilha de modificadores", "armatures diferentes"):
        rec(1, "Corrigir erros estruturais primeiro",
            "Vértices sem peso ou modificadores mal ordenados distorcem qualquer outra medição.",
            "Atribuir peso aos vértices órfãos (do vizinho mais próximo na própria roupa), colocar o "
            "Armature como primeiro modificador deformante e apontá-lo para o mesmo rig da original.",
            "Baixo.")
    if _has(F, "Fronteira", "desce pela lateral", "abrupta", "Triângulos-ponte", "Estiramento excessivo"):
        rec(1, "Redesenhar a transição de pesos da axila (numa cópia)",
            "A membrana nasce de uma fronteira de peso abrupta e longe do pivô do ombro.",
            "1) Lateral do tronco abaixo da axila: peso de Chest/Spine (+ um pouco de Shoulder), sem UpperArm. "
            "2) Concentrar a transição perto da articulação, em faixa larga e suave (≈0.3–0.5× UpperArm). "
            "3) Parte de baixo da manga larga: gradiente UpperArm→Shoulder/Chest, não 100% braço. "
            "4) Usar a roupa ORIGINAL como referência de distribuição (Data Transfer “Nearest Face "
            "Interpolated”, máscara só na axila) ou uma cópia do corpo inflada até o volume do moletom — "
            "nunca o corpo nu direto para tecido solto. 5) Suavizar (Smooth Vertex Weights) só na faixa.",
            "Médio: pode reduzir o acompanhamento da manga em poses baixas; validar as 5 poses.")
    if _has(F, "Poucos anéis"):
        rec(2, "Adicionar 2–3 edge loops na cava/axila",
            "Sem anéis suficientes, a rotação se concentra em um único anel de triângulos.",
            "Inserir loops ao redor da cava (ombro→axila), na direção da manga, sem mudar a silhueta.",
            "Médio: altera topologia; refazer pesos/Shape Keys dessa região depois.")
    if _has(F, "longe do osso"):
        rec(2, "Pesos da manga oversized com gradiente",
            "Tecido muito afastado do osso com peso 100% de braço gira com alavanca longa.",
            "Na parte inferior/interna da manga, misturar UpperArm com Shoulder/Chest perto da cava; "
            "manter 100% braço só a partir do meio do antebraço.",
            "Baixo/médio: manga pode 'atrasar' levemente — costuma parecer mais natural em roupas largas.")
    if _has(F, "Compressão", "atravessa o corpo"):
        rec(2, "Shape Keys corretivas para poses extremas",
            "Compressão/colisão residual depois dos pesos é melhor tratada por pose.",
            "Esculpir corretivas para braço a 90° e acima da cabeça (numa cópia), acionadas pela rotação "
            "do UpperArm. Em VRM/Unity, acionar via animação/blendshape do app ou usar osso auxiliar.",
            "Médio: drivers não exportam para Unity.")
    if _has(F, "Tronco deforma"):
        rec(3, "Limitar a influência do Shoulder no tronco",
            "O tronco estica longe do braço.",
            "Reduzir/suavizar Shoulder e UpperArm na frente/costas do tronco abaixo da clavícula.",
            "Baixo.")
    if _has(F, "Armature Modifier difere"):
        rec(3, "Igualar as opções do Armature Modifier à original",
            "Preserve Volume/Envelopes diferentes mudam a deformação no ombro.",
            "Copiar as opções da original (lembrando que Dual Quaternion não vai para Unity).", "Baixo.")
    if _has(F, "Ossos auxiliares", "Shape Keys corretivas", "Original usa"):
        rec(3, "Reaproveitar o mecanismo corretivo da original",
            "A original tem recursos de correção que o moletom não tem.",
            "Recriar os mesmos mecanismos ajustados à geometria do moletom (não copiar valores cegamente).",
            "Médio.")
    rec(4, "Validar após cada etapa",
        "Evitar regressões em outras poses.",
        "Rodar esta ferramenta de novo na cópia corrigida e comparar p95 por pose com a original.",
        "Nenhum.")
    return sorted(R, key=lambda r: r["priority"])
