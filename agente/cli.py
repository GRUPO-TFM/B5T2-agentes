"""Línea de comandos del harness.

    uv run python -m agente.cli ejecutar  --arq baseline --rep 1 [--ids gX-001,gX-002] [--forzar]
    uv run python -m agente.cli puntuar   --arq baseline --rep 1 [--sin-recall]
    uv run python -m agente.cli todo      --arq baseline [--reps 3]      # ejecutar+puntuar ×reps, y comparar
    uv run python -m agente.cli comparar
    uv run python -m agente.cli recall                                    # tabla del retrieval
    uv run python -m agente.cli traza     --arq baseline --rep 1 --id gX-013   # ver una trayectoria guardada
    uv run python -m agente.cli pregunta  "¿Cuál fue el revenue de NVIDIA en FY2025?" [--arq final]
"""

from __future__ import annotations

import argparse
import json
import sys

from agente.config import ARQUITECTURAS, REPETICIONES

GOLDEN = "data/golden_set.jsonl"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agente", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="orden", required=True)

    def arq_arg(sp, default="final"):
        sp.add_argument("--arq", default=default, choices=list(ARQUITECTURAS))

    sp = sub.add_parser("ejecutar"); arq_arg(sp, "baseline")
    sp.add_argument("--rep", type=int, default=1); sp.add_argument("--golden", default=GOLDEN)
    sp.add_argument("--ids", default=None, help="coma-separados"); sp.add_argument("--forzar", action="store_true")

    sp = sub.add_parser("puntuar"); arq_arg(sp, "baseline")
    sp.add_argument("--rep", type=int, default=1); sp.add_argument("--sin-recall", action="store_true")

    sp = sub.add_parser("todo"); arq_arg(sp, "baseline")
    sp.add_argument("--reps", type=int, default=REPETICIONES); sp.add_argument("--golden", default=GOLDEN)
    sp.add_argument("--sin-recall", action="store_true")

    sub.add_parser("comparar")
    sp = sub.add_parser("recall"); sp.add_argument("--golden", default=GOLDEN); sp.add_argument("--k", type=int, default=5)

    sp = sub.add_parser("traza"); arq_arg(sp, "baseline")
    sp.add_argument("--rep", type=int, default=1); sp.add_argument("--id", required=True)

    sp = sub.add_parser("pregunta"); sp.add_argument("texto"); arq_arg(sp, "final")

    a = p.parse_args(argv)

    if a.orden == "ejecutar":
        from agente.interfaz import ejecutar
        ejecutar(a.golden, a.arq, a.rep, solo_ids=a.ids.split(",") if a.ids else None, forzar=a.forzar)
    elif a.orden == "puntuar":
        from agente.interfaz import puntuar, resumir
        t = puntuar(a.arq, a.rep, con_recall=not a.sin_recall)
        print(t[["id", "familia", "acierto", "cita", "cifra", "trayectoria", "n_llamadas", "coste_usd"]].to_string(index=False))
        print(); print(json.dumps(resumir(t, a.arq), ensure_ascii=False, indent=1, default=float))
    elif a.orden == "todo":
        from agente.interfaz import ejecutar_todo
        print(ejecutar_todo(a.golden, a.arq, reps=a.reps, con_recall=not a.sin_recall).to_string(index=False))
    elif a.orden == "comparar":
        from agente.interfaz import comparar, dir_resultados
        c = comparar()
        print(c.to_string(index=False)); print(f"\n→ {dir_resultados() / 'comparativa.md'}")
    elif a.orden == "recall":
        from agente.recall import medir_recall
        print(medir_recall(ruta_jsonl=a.golden, k=a.k).to_string(index=False))
    elif a.orden == "traza":
        from agente.interfaz import dir_rep
        from agente.resultado import pretty_trace
        reg = json.loads((dir_rep(a.arq, a.rep) / "crudo" / f"{a.id}.json").read_text(encoding="utf-8"))
        print(reg["item"]["pregunta"]); print(f"esperado: {reg['item'].get('respuesta_esperada')}\n")
        print(reg.get("error") or pretty_trace(reg["resultado"]))
    elif a.orden == "pregunta":
        from agente.interfaz import responder
        from agente.resultado import pretty_trace
        r = responder(a.texto, arquitectura=a.arq)
        print(pretty_trace(r)); print(f"\n  [{r['latencia_s']:.1f} s · {r['coste_usd']*100:.2f} ¢]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
