"""Gerador e validador do perfil de came do Exercício 08.

Calcula a mesma função que o gabarito (`Gabarito.TcPOU`) coloca na tabela do NC, para você
conferir os valores, ver o gráfico e saber a velocidade e a aceleração de pico do escravo.

Perfil (mestre em graus, escravo em mm), uma volta do mestre:
    0 a 120 : avança de H0 até H1, perfil cicloidal
    120 a 180 : espera em H1
    180 a 300 : recua de H1 até H0, perfil cicloidal
    300 a 360 : espera em H0

Cicloidal: S(s) = s - sin(2*pi*s) / (2*pi), com s de 0 a 1. Começa e termina com velocidade e
aceleração zero, o que evita trancos (compare com o trapezoidal do Ex07, em NC Fundamentals).

Uso:
    python tools/gen_cam_table.py                 # resumo no terminal
    python tools/gen_cam_table.py --csv perfil_came.csv --plot perfil_came.png
    python tools/gen_cam_table.py --omega 90      # velocidade do mestre em graus/s
"""
from __future__ import annotations

import argparse
import csv
import math

H0 = 5.0     # mm, repouso
H1 = 40.0    # mm, trabalho
STEP = 1.0   # graus entre pontos da tabela (equidistante)

# Fronteiras dos trechos, em graus do mestre
T_RISE_END = 120.0
T_DWELL_HIGH_END = 180.0
T_FALL_END = 300.0
T_PERIOD = 360.0


def cycloid(s: float) -> float:
    """Subida suave de 0 a 1 com velocidade e aceleração nulas nas pontas."""
    return s - math.sin(2.0 * math.pi * s) / (2.0 * math.pi)


def cycloid_d1(s: float) -> float:
    return 1.0 - math.cos(2.0 * math.pi * s)


def cycloid_d2(s: float) -> float:
    return 2.0 * math.pi * math.sin(2.0 * math.pi * s)


def profile(theta: float, h0: float = H0, h1: float = H1) -> float:
    """Posição do escravo (mm) para a posição do mestre theta (graus, qualquer valor)."""
    t = theta % T_PERIOD
    if t < T_RISE_END:
        return h0 + (h1 - h0) * cycloid(t / T_RISE_END)
    if t < T_DWELL_HIGH_END:
        return h1
    if t < T_FALL_END:
        s = (t - T_DWELL_HIGH_END) / (T_FALL_END - T_DWELL_HIGH_END)
        return h1 - (h1 - h0) * cycloid(s)
    return h0


def table(step: float = STEP, h0: float = H0, h1: float = H1) -> list[tuple[float, float]]:
    """Pontos (mestre, escravo) de 0 a 360 inclusive: 361 linhas para passo de 1 grau."""
    n = int(round(T_PERIOD / step))
    return [(i * step, profile(i * step, h0, h1)) for i in range(n + 1)]


def dynamics(omega_deg_s: float, h0: float = H0, h1: float = H1) -> dict:
    """Velocidade e aceleração de pico do escravo para o mestre a omega graus/s."""
    h = h1 - h0
    t_rise = T_RISE_END / omega_deg_s
    t_fall = (T_FALL_END - T_DWELL_HIGH_END) / omega_deg_s
    return {
        "periodo_s": T_PERIOD / omega_deg_s,
        "v_pico_mm_s": max(
            h * 2.0 / t_rise,
            h * 2.0 / t_fall,
        ),
        "a_pico_mm_s2": max(
            h * 2.0 * math.pi / t_rise**2,
            h * 2.0 * math.pi / t_fall**2,
        ),
    }


def validate(rows: list[tuple[float, float]], h0: float = H0, h1: float = H1) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia se a tabela está coerente)."""
    problems: list[str] = []
    masters = [m for m, _ in rows]
    if any(b <= a for a, b in zip(masters, masters[1:])):
        problems.append("posições do mestre não são estritamente crescentes")
    if abs(rows[0][1] - rows[-1][1]) > 1e-9:
        problems.append("a tabela não fecha: escravo no início difere do escravo no fim (tabela periódica)")
    lo, hi = min(s for _, s in rows), max(s for _, s in rows)
    if lo < h0 - 1e-9 or hi > h1 + 1e-9:
        problems.append(f"escravo fora dos limites [{h0}, {h1}] mm: de {lo:.3f} a {hi:.3f}")
    # sem saltos: a maior variação entre pontos vizinhos deve ser pequena frente ao curso
    max_jump = max(abs(b[1] - a[1]) for a, b in zip(rows, rows[1:]))
    if max_jump > 0.05 * (h1 - h0):
        problems.append(f"salto de {max_jump:.3f} mm entre pontos vizinhos (passo grande demais?)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--omega", type=float, default=60.0, help="velocidade do mestre em graus/s (padrão 60)")
    ap.add_argument("--csv", help="grava a tabela (mestre_graus, escravo_mm) neste arquivo")
    ap.add_argument("--plot", help="grava um gráfico PNG do perfil")
    args = ap.parse_args()

    rows = table()
    problems = validate(rows)
    dyn = dynamics(args.omega)

    print(f"Tabela: {len(rows)} pontos, passo {STEP} grau, escravo de {H0} a {H1} mm")
    print("Pontos de conferência (compare com a tabela no PLC):")
    for th in (0, 30, 60, 90, 120, 180, 240, 300, 360):
        print(f"  mestre {th:5.1f} graus -> escravo {profile(th):9.4f} mm")
    print(f"Com mestre a {args.omega:g} graus/s: período {dyn['periodo_s']:.2f} s, "
          f"v pico {dyn['v_pico_mm_s']:.1f} mm/s, a pico {dyn['a_pico_mm_s2']:.1f} mm/s2")
    if problems:
        print("PROBLEMAS:")
        for p in problems:
            print("  -", p)
        return 1
    print("Validação: OK (crescente, fecha, dentro dos limites, sem saltos)")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["mestre_graus", "escravo_mm"])
            w.writerows((f"{m:.1f}", f"{s:.6f}") for m, s in rows)
        print("CSV:", args.csv)
    if args.plot:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ths = [m for m, _ in rows]
        pos = [s for _, s in rows]
        vel = [  # derivada numérica por diferença central, em mm/s
            (profile(t + 0.5) - profile(t - 0.5)) / 1.0 * args.omega for t in ths
        ]
        fig, ax = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
        ax[0].plot(ths, pos)
        ax[0].set_ylabel("escravo (mm)")
        ax[0].set_title("Came eletrônico: posição do fuso x posição do mestre")
        ax[1].plot(ths, vel, color="tab:orange")
        ax[1].set_ylabel(f"velocidade (mm/s) a {args.omega:g} graus/s")
        ax[1].set_xlabel("mestre (graus)")
        for a in ax:
            a.grid(True, alpha=0.3)
            for x in (T_RISE_END, T_DWELL_HIGH_END, T_FALL_END):
                a.axvline(x, color="gray", lw=0.6, ls="--")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=140)
        print("Gráfico:", args.plot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
