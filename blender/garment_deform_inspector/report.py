"""Relatório técnico (Markdown + JSON + SVGs) seções A–G."""

import json
import os

import numpy as np

from . import svg
from .diagnosis import CONFIRMED, DISCARDED, HYPOTHESIS, NOTE
from .poses import POSES

POSE_LABEL = {p[0]: p[1] for p in POSES}
ROLE_LABEL = {"original": "Roupa original", "new": "Roupa nova"}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def _public(result):
    return {k: v for k, v in result.items() if not k.startswith("_") and k != "mapping"}


def _tbl(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def _garment_section(rep):
    t, w, sk = rep["topology"], rep["weights"], rep["shape_keys"]
    lines = [f"**Objeto:** `{rep['object']}` · malha `{rep['mesh']}`", ""]
    lines.append(_tbl(["Topologia", "Valor"], [
        ("Vértices / faces", f"{t['vertices']} / {t['faces']}"),
        ("Tris / quads / n-gons", f"{t['tris']} / {t['quads']} / {t['ngons']}"),
        ("Aresta mediana / p95", f"{t['edge_len_median_mm']} mm / {t['edge_len_p95_mm']} mm"),
        ("Bordas abertas / não-manifold", f"{t['boundary_edges']} / {t['nonmanifold_edges']}"),
        ("Vértices soltos / sobrepostos", f"{t['loose_vertices']} / {t['overlapping_vertex_pairs']}"),
    ]))
    lines.append("")
    tr = rep["transform"]
    lines.append(f"**Transformação:** escala {tr['scale']}, rotação {tr['rotation_euler_deg']}°, "
                 f"parent `{tr['parent']}` ({tr['parent_type']}).")
    lines.append("")
    lines.append("**Modificadores (ordem):** " + (" → ".join(
        f"`{m['name']}` ({m['type']}{'' if m['show_viewport'] else ', oculto'})" for m in rep["modifiers"]) or "nenhum"))
    am = rep.get("armature_modifier") or {}
    if am:
        lines.append("")
        lines.append(f"**Armature Modifier:** objeto `{am.get('object')}`, vertex groups "
                     f"{am.get('use_vertex_groups')}, envelopes {am.get('use_bone_envelopes')}, "
                     f"preserve volume (DQS) {am.get('use_deform_preserve_volume')}, "
                     f"multi modifier {am.get('use_multi_modifier')}, máscara `{am.get('vertex_group') or '-'}`.")
    lines.append("")
    lines.append(_tbl(["Pesos", "Valor"], [
        ("Vertex groups (deformantes)", f"{w['vertex_groups']} ({w['deform_groups']})"),
        ("Vértices sem peso", w["zero_weight_vertices"]),
        ("Vértices não normalizados", w["unnormalized_vertices"]),
        ("Máx. influências / vértices >4", f"{w['max_influences']} / {w['vertices_over_4_influences']}"),
        ("Grupos sem osso", ", ".join(w["groups_without_bone"][:6]) or "-"),
        ("Auxiliares de braço usados", ", ".join(w.get("helper_bones_used", [])) or "-"),
    ]))
    lines.append("")
    if sk["count"]:
        lines.append(_tbl(["Shape Key", "Relativa a", "Valor", "Vértices movidos", "Na zona do braço",
                           "Máx. mm", "Driver (ossos)"],
                          [(k["name"], k["relative_key"], k["value"], k["moved_vertices"], k["moved_in_arm_zone"],
                            k["max_offset_mm"], ", ".join(k["driver_bones"]) or ("sim" if k["driven"] else "-"))
                           for k in sk["keys"]]))
    else:
        lines.append("**Shape Keys:** nenhuma.")
    lines.append("")
    extra = []
    if rep["object_constraints"]:
        extra.append("constraints: " + ", ".join(f"{c['name']} ({c['type']})" for c in rep["object_constraints"]))
    if rep["object_drivers"]:
        extra.append(f"{len(rep['object_drivers'])} drivers no objeto/malha")
    lines.append("**Drivers/constraints do objeto:** " + ("; ".join(extra) or "nenhum."))
    lines.append("")
    rows = []
    for side, z in rep.get("weight_zones", {}).items():
        rows.append((side, z.get("transition_vertices"), z.get("transition_dist_to_joint_p50"),
                     z.get("transition_below_joint_p90"), z.get("hard_edge_dist_to_joint_p50"),
                     z.get("gradient_per_cm_p95"), z.get("edge_rings_across_transition"),
                     z.get("arm_weighted_dist_to_bone_p90")))
    if rows:
        lines.append("**Transição tronco→braço** (distâncias em múltiplos do comprimento do UpperArm):")
        lines.append("")
        lines.append(_tbl(["Lado", "Vértices na transição", "Dist. ao ombro p50", "Desce abaixo do ombro p90",
                           "Fronteira abrupta: dist. p50", "Δpeso/cm p95", "Anéis na transição",
                           "Tecido de braço: dist. ao osso p90"], rows))
    bc = rep.get("body_comparison")
    if bc:
        lines.append("")
        lines.append(f"**Em relação ao corpo (bind):** afastamento p50 {bc['offset_mm_p50']} mm, p90 "
                     f"{bc['offset_mm_p90']} mm, {bc['inside_body_at_bind_pct']}% dentro do corpo.")
        for s, v in bc["sides"].items():
            lines.append(f"- {s}: diferença média de peso de braço vs corpo na axila {v.get('mean_abs_diff_armpit')}; "
                         f"tecido solto na axila {v.get('loose_armpit_vertices')} vértices, "
                         f"{v.get('loose_copied_body_weights_pct')}% com peso igual ao do corpo.")
    return "\n".join(lines)


def _pose_table(result):
    pr = result["pose_results"]
    rows = []
    for pid in result["poses"]:
        for role in ("original", "new"):
            e = pr.get(role, {}).get(pid)
            if not e:
                continue
            for side, s in e["sides"].items():
                a = s["armpit"]
                rows.append((POSE_LABEL.get(pid, pid), ROLE_LABEL[role], side, a.get("p95"), a.get("p99"),
                             a.get("pct_over_1_5"), a.get("pct_over_2"),
                             s.get("armpit_vs_bind", {}).get("p99"), s["bridge_triangles"].get("p95"),
                             s.get("armpit_compression_p5"), s["torso_far_from_arm"].get("p95"),
                             s.get("armpit_inside_body_pct", "-")))
    return _tbl(["Pose", "Roupa", "Lado", "Axila p95", "Axila p99", "% >1.5×", "% >2×",
                 "Axila p99 vs repouso", "Ponte p95", "Compressão p5", "Tronco p95", "% dentro do corpo"], rows)


def write_images(result, out_dir, forward=(0, -1, 0)):
    arrays, posed = result["_arrays"], result["_posed"]
    roles = [r for r in ("original", "new") if r in arrays]
    files = []
    panels = []
    for r in roles:
        arr = arrays[r]
        wmax = np.max(np.stack(list(arr["arm_w"].values())), axis=0)
        panels.append((ROLE_LABEL[r], posed[r]["DOWN"], arr["tris"], wmax))
    p = os.path.join(out_dir, "pesos_braco.svg")
    svg.comparison_svg(p, "Influência dos braços — pose abaixada",
                       "Soma UpperArm + twist + LowerArm + Hand + auxiliares (Shoulder não incluído).",
                       panels, forward, "Azul 0% · verde ~33% · amarelo ~67% · vermelho 100%.")
    files.append(p)
    for pid in result["poses"]:
        if pid == "DOWN":
            continue
        panels = [(ROLE_LABEL[r], posed[r][pid], arrays[r]["tris"],
                   svg.stretch_to_unit(arrays[r]["stretch_vertex"][pid]))
                  for r in roles if "stretch_vertex" in arrays[r]]
        if not panels:
            continue
        p = os.path.join(out_dir, f"estiramento_{pid.lower()}.svg")
        svg.comparison_svg(p, f"Estiramento local — {POSE_LABEL[pid].lower()}",
                           "Maior razão de comprimento por triângulo vs pose abaixada; segmentos < 1 mm "
                           "excluídos. Azul ≤1× · vermelho ≥3×.", panels, forward,
                           "Diagnóstico geométrico, não simulação. Mesma escala nas peças.")
        files.append(p)
    return files


def write_report(result, diag, out_dir, forward=(0, -1, 0), images=True):
    os.makedirs(out_dir, exist_ok=True)
    imgs = write_images(result, out_dir, forward) if images else []
    g = result["garments"]
    rig = result["rig"]
    F, R = diag["findings"], diag["recommendations"]
    md = ["# Relatório técnico — deformação de roupa", ""]
    md.append("Gerado pelo **Garment Deform Inspector**. Nenhum dado do arquivo foi alterado; poses e "
              f"modificadores foram restaurados (verificação: **{'OK' if result['session'].get('restored') else 'FALHOU'}**).")
    if result["session"].get("disabled_modifiers"):
        md.append(f"Modificadores de topologia desligados só durante a medição: "
                  f"{', '.join(result['session']['disabled_modifiers'])}.")
    for wmsg in result.get("warnings", []):
        md.append(f"> ⚠️ {wmsg}")
    md += ["", "Legenda de status: **CONFIRMADO** (medido) · **DESCARTADO** (testado e contrariado) · "
           "**HIPÓTESE** (compatível, não provado) · **OBSERVAÇÃO** (fato relevante, não causa).", ""]

    md += ["## Rig", ""]
    md.append(f"Armature `{rig['name']}`: {rig['bones']} ossos ({rig['deform_bones']} deformantes).")
    md.append("")
    md.append(_tbl(["Lado", "UpperArm", "Pose de repouso", "Abdução em repouso", "Ossos de braço considerados"],
                   [(s, a["upper_arm"], a["rest_pose"], f"{a['rest_abduction_deg']}°", ", ".join(a["influence_bones"]))
                    for s, a in rig["arms"].items()]))
    arm_c = [c for c in rig["bone_constraints"] if c["arm_related"]]
    if arm_c:
        md.append("")
        md.append("Constraints em ossos do braço: " + "; ".join(
            f"{c['bone']}: {c['type']} → {c['target']}/{c['subtarget']} ({c['influence']})" for c in arm_c))

    if "original" in g:
        md += ["", "## A. Análise da roupa original", "", _garment_section(g["original"])]
    if "new" in g:
        md += ["", "## B. Análise da roupa nova", "", _garment_section(g["new"])]

    md += ["", "## C. Comparação nas poses de teste", ""]
    md.append("Estiramento = maior razão de comprimento por triângulo vs a pose abaixada "
              "(“vs repouso” = comparado à malha como foi modelada). "
              "1.0 = sem mudança. Axila = até 1 UpperArm do ombro e abaixo dele. "
              "Ponte = triângulos com salto de peso de braço > 0.5. Compressão < 0.5 indica sobreposição/volume.")
    md += ["", _pose_table(result)]

    md += ["", "## D. Causas confirmadas e prováveis", ""]
    for status in (CONFIRMED, DISCARDED, HYPOTHESIS, NOTE):
        items = [f for f in F if f["status"] == status]
        if not items:
            continue
        md.append(f"### {status}")
        md.append("")
        for f in items:
            comp = f" _(componente: {f['component']})_" if f.get("component") else ""
            md.append(f"- **{f['title']}** — {f['evidence']}{comp}")
        md.append("")

    md += ["## E. Evidências visuais", ""]
    for p in imgs:
        md.append(f"![{os.path.basename(p)}]({os.path.basename(p)})")
        md.append("")
    md.append("Dados completos: `dados.json`.")

    md += ["", "## F. Plano de correção priorizado", "",
           "_Recomendações — nada foi aplicado. Executar só após autorização, numa cópia._", ""]
    for r in R:
        md.append(f"**P{r['priority']} — {r['title']}**  ")
        md.append(f"Por quê: {r['why']}  ")
        md.append(f"Como: {r['how']}  ")
        md.append(f"Risco: {r['risk']}")
        md.append("")

    md += ["## G. Riscos e limitações", "",
           "- Diagnóstico geométrico (skinning), não simulação de tecido; dobras reais dependem de física.",
           "- Poses são aproximações anatômicas aplicadas a partir do repouso; Shoulder fica em repouso "
           "(a menos que o auxílio de ombro esteja ligado).",
           "- A zona da axila e os ossos de braço são detectados automaticamente; conferir o mapeamento acima.",
           "- Corretivos via driver, constraints, Corrective Smooth e Dual Quaternion **não** são exportados "
           "para VRM/Unity: a correção principal deve ficar em pesos e topologia.",
           "- Alterar topologia invalida Shape Keys e pesos daquela região; trabalhar sempre numa cópia.",
           "- “Pesos copiados do corpo” é uma assinatura estatística, não prova do método usado.", ""]
    md_path = os.path.join(out_dir, "relatorio.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    with open(os.path.join(out_dir, "dados.json"), "w", encoding="utf-8") as fh:
        json.dump({"result": _public(result), "diagnosis": diag}, fh, ensure_ascii=False, indent=1,
                  default=_json_default)
    return md_path
