"""Gera tabela Markdown e gráfico a partir de uma pasta results/<carimbo>/.

Uso:
    python -m bench.analyze results/20261109-153000
Saídas na própria pasta: summary.md (tabela para colar nas notas) e rtt.png.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

METRIC_LABEL = {
    "echo_rtt": "Eco (ida e volta, com ciclo do PLC)",
    "read_single": "Leitura única",
    "publish_ack": "Publicação confirmada (MQTT, QoS 1, até o broker)",
}
COLS = ["protocol", "n", "failures", "p50_ms", "p95_ms", "p99_ms", "max_ms", "ops_per_s"]
HEAD = ["Protocolo", "n", "Falhas", "p50 (ms)", "p95 (ms)", "p99 (ms)", "máx (ms)", "ops/s"]


def to_markdown(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(HEAD) + " |", "| " + " | ".join(["---"] * len(HEAD)) + " |"]
    for _, r in df[COLS].iterrows():
        cells = [str(r["protocol"]), str(int(r["n"])), str(int(r["failures"]))]
        cells += [f"{r[c]:.3f}" for c in ["p50_ms", "p95_ms", "p99_ms", "max_ms"]]
        cells.append(f"{r['ops_per_s']:.0f}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    args = ap.parse_args(argv)
    folder = Path(args.folder)
    summary = pd.read_csv(folder / "summary.csv")
    samples = pd.read_csv(folder / "samples.csv")

    meta = summary.iloc[0]
    md = [
        f"Execução {meta['stamp']} — alvo: {meta['target']}; ciclo do PLC: {meta['plc_cycle_ms']} ms; "
        f"rede: {meta['network']}; cliente: {meta['host_os']}.",
        "",
    ]
    for metric, label in METRIC_LABEL.items():
        sub = summary[summary["metric"] == metric]
        if sub.empty:
            continue
        md += [f"**{label}**", "", to_markdown(sub), ""]
    (folder / "summary.md").write_text("\n".join(md), encoding="utf-8")

    metrics = [m for m in METRIC_LABEL if not samples[samples["metric"] == m].empty]
    fig, axes = plt.subplots(1, max(len(metrics), 1), figsize=(5.5 * max(len(metrics), 1), 4.4), squeeze=False)
    for ax, metric in zip(axes[0], metrics):
        sub = samples[samples["metric"] == metric]
        protos = list(sub["protocol"].unique())
        ax.boxplot([sub[sub["protocol"] == p]["ms"] for p in protos], tick_labels=protos, showfliers=True)
        ax.set_title(METRIC_LABEL[metric], fontsize=9)
        ax.set_ylabel("ms")
        ax.set_yscale("log")
        ax.tick_params(axis="x", labelrotation=30)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Benchmark de protocolos (escala log)", fontsize=11)
    fig.tight_layout()
    fig.savefig(folder / "rtt.png", dpi=140)
    print(f"Gerados: {folder / 'summary.md'} e {folder / 'rtt.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
