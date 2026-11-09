"""Executa o benchmark e grava os resultados em results/<carimbo>/.

Uso (a partir da pasta Benchmark-Protocolos):
    python -m bench.run_all --config config.toml --protocols ads opcua modbus
"""
from __future__ import annotations

import argparse
import csv
import importlib
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .common import Result, load_config, summarize

PROTOCOLS = {"ads": "proto_ads", "opcua": "proto_opcua", "modbus": "proto_modbus"}
SUMMARY_FIELDS = [
    "protocol", "metric", "n", "failures", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "ops_per_s",
    "target", "plc_cycle_ms", "network", "host_os", "stamp",
]


def run_protocols(cfg: dict, names: list[str], n: int, warmup: int, timeout_s: float) -> list[Result]:
    results: list[Result] = []
    for name in names:
        mod = importlib.import_module(f"bench.{PROTOCOLS[name]}")
        print(f"[{name}] medindo {n} amostras (+{warmup} de aquecimento)...", flush=True)
        try:
            results.extend(mod.run(cfg, n, warmup, timeout_s))
        except KeyError as exc:  # seção ou chave ausente no arquivo de configuração
            print(f"[{name}] PULADO: a configuração não tem {exc} (seção [{name}] ausente?)", file=sys.stderr)
        except Exception as exc:  # um protocolo indisponível não deve derrubar os outros
            print(f"[{name}] FALHOU: {exc!r}", file=sys.stderr)
    return results


def write_results(cfg: dict, results: list[Result], out: Path, stamp: str, config_path: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    meta = cfg.get("meta", {})
    with open(out / "samples.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["protocol", "metric", "idx", "ms"])
        for r in results:
            for i, ms in enumerate(r.samples_ms):
                w.writerow([r.protocol, r.metric, i, f"{ms:.4f}"])
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for r in results:
            row = summarize(r)
            row.update(
                target=meta.get("target", ""),
                plc_cycle_ms=meta.get("plc_cycle_ms", ""),
                network=meta.get("network", ""),
                host_os=platform.platform(),
                stamp=stamp,
            )
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})
    # Guarda a configuração usada (sem credenciais: elas vêm do ambiente).
    shutil.copy(config_path, out / "config.toml")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--protocols", nargs="+", choices=sorted(PROTOCOLS), default=sorted(PROTOCOLS))
    ap.add_argument("--samples", type=int, help="sobrescreve [run].samples")
    ap.add_argument("--warmup", type=int, help="sobrescreve [run].warmup")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    config_path = Path(args.config)
    cfg = load_config(config_path)
    run_cfg = cfg.get("run", {})
    n = args.samples or int(run_cfg.get("samples", 1000))
    warmup = args.warmup if args.warmup is not None else int(run_cfg.get("warmup", 100))
    timeout_s = float(run_cfg.get("timeout_s", 2.0))

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = run_protocols(cfg, args.protocols, n, warmup, timeout_s)
    if not results:
        print("Nenhum protocolo produziu resultado.", file=sys.stderr)
        return 1
    out = Path(args.out) / stamp
    write_results(cfg, results, out, stamp, config_path)
    for r in results:
        s = summarize(r)
        print(
            f"{s['protocol']:7s} {s['metric']:11s} n={s['n']:5d} falhas={s['failures']:3d} "
            f"p50={s['p50_ms']:.3f} ms  p95={s['p95_ms']:.3f} ms  p99={s['p99_ms']:.3f} ms  max={s['max_ms']:.3f} ms"
        )
    print(f"\nResultados em {out}  (rode: python -m bench.analyze {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
