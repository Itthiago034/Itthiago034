"""Execução sem interface (o .blend é aberto e NUNCA salvo).

    blender -b personagem.blend --python cli_inspect.py -- \
        --original "Jaqueta" --new "Moletom" --body "Body" --armature "Armature" \
        --out ./relatorio

Use --list para ver os objetos de malha/armature do arquivo.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from garment_deform_inspector import diagnosis, report, runner  # noqa: E402

FWD = {"-Y": (0, -1, 0), "+Y": (0, 1, 0), "-X": (-1, 0, 0), "+X": (1, 0, 0)}


def main(argv=None):
    argv = argv if argv is not None else (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    ap = argparse.ArgumentParser(prog="cli_inspect")
    ap.add_argument("--original")
    ap.add_argument("--new")
    ap.add_argument("--body")
    ap.add_argument("--armature")
    ap.add_argument("--out", default="relatorio_roupa")
    ap.add_argument("--forward", default="-Y", choices=list(FWD))
    ap.add_argument("--shoulder-assist", type=float, default=0.0)
    ap.add_argument("--bone", action="append", default=[],
                    help="Sobrescreve osso: L.upper_arm=NomeDoOsso (repetível)")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    if a.list or not a.new:
        for ob in bpy.data.objects:
            if ob.type in {"MESH", "ARMATURE"}:
                mods = ", ".join(m.type for m in getattr(ob, "modifiers", []))
                print(f"{ob.type:9s} {ob.name!r:40s} {mods}")
        return 0

    def get(name):
        if not name:
            return None
        ob = bpy.data.objects.get(name)
        if ob is None:
            raise SystemExit(f"Objeto não encontrado: {name!r} (use --list)")
        return ob

    override = {}
    for spec in a.bone:
        key, _, bone = spec.partition("=")
        side, _, role = key.partition(".")
        override[(side.upper(), role)] = bone

    res = runner.run_analysis(get(a.original), get(a.new), get(a.armature), get(a.body), override,
                              FWD[a.forward], a.shoulder_assist, progress=lambda m: print("[GDI]", m))
    diag = diagnosis.diagnose(res)
    path = report.write_report(res, diag, os.path.abspath(a.out), FWD[a.forward], images=not a.no_images)
    print(f"[GDI] restauração da pose: {'OK' if res['session'].get('restored') else 'FALHOU'}")
    for f in diag["findings"]:
        print(f"[GDI] {f['status']:11s} {f['title']}")
    print(f"[GDI] relatório: {path}")
    return 0


if __name__ == "__main__":
    main()
