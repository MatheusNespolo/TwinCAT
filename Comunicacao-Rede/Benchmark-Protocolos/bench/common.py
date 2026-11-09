"""Medição comum a todos os protocolos.

Duas métricas por protocolo:
- ``echo_rtt``: o cliente escreve um número de sequência N em ``nIn``; o PLC copia para
  ``nOut`` no próprio ciclo; o tempo medido vai da escrita até a leitura devolver N.
  Inclui: escrita, espera pelo ciclo do PLC e as leituras repetidas até o eco chegar.
  Como só o relógio do cliente é usado, não há necessidade de sincronizar relógios.
- ``read_single``: tempo de uma única leitura (custo puro do protocolo, sem o ciclo do PLC).
"""
from __future__ import annotations

import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

SEQ_MAX = 65535  # cabe em WORD (Modbus) e em DINT (ADS/OPC UA); valores de 1 a 65535


def load_config(path: str | Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def next_seq(i: int) -> int:
    """Sequência 1..65535, sempre diferente da anterior (evita eco 'velho' ser aceito)."""
    return (i % SEQ_MAX) + 1


@dataclass
class Result:
    protocol: str
    metric: str  # "echo_rtt" | "read_single"
    samples_ms: list[float] = field(default_factory=list)
    failures: int = 0


def percentile(sorted_vals: list[float], p: float) -> float:
    """Percentil por interpolação linear (p de 0 a 100) sobre lista já ordenada."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def summarize(r: Result) -> dict:
    s = sorted(r.samples_ms)
    n = len(s)
    mean = sum(s) / n if n else float("nan")
    return {
        "protocol": r.protocol,
        "metric": r.metric,
        "n": n,
        "failures": r.failures,
        "mean_ms": mean,
        "p50_ms": percentile(s, 50),
        "p95_ms": percentile(s, 95),
        "p99_ms": percentile(s, 99),
        "max_ms": s[-1] if n else float("nan"),
        "ops_per_s": (1000.0 / mean) if n and mean > 0 else float("nan"),
    }


def _now_ns() -> int:
    return time.perf_counter_ns()


def measure_echo(
    write: Callable[[int], None],
    read: Callable[[], int],
    *,
    n: int,
    warmup: int,
    timeout_s: float,
    protocol: str,
) -> Result:
    res = Result(protocol, "echo_rtt")
    timeout_ns = int(timeout_s * 1e9)
    for i in range(warmup + n):
        seq = next_seq(i)
        t0 = _now_ns()
        write(seq)
        ok = False
        while True:
            if read() == seq:
                ok = True
                break
            if _now_ns() - t0 > timeout_ns:
                break
        dt_ms = (_now_ns() - t0) / 1e6
        if i >= warmup:
            if ok:
                res.samples_ms.append(dt_ms)
            else:
                res.failures += 1
    return res


def measure_read(read: Callable[[], int], *, n: int, warmup: int, protocol: str) -> Result:
    res = Result(protocol, "read_single")
    for i in range(warmup + n):
        t0 = _now_ns()
        read()
        dt_ms = (_now_ns() - t0) / 1e6
        if i >= warmup:
            res.samples_ms.append(dt_ms)
    return res


async def ameasure_echo(
    write: Callable[[int], Awaitable[None]],
    read: Callable[[], Awaitable[int]],
    *,
    n: int,
    warmup: int,
    timeout_s: float,
    protocol: str,
) -> Result:
    res = Result(protocol, "echo_rtt")
    timeout_ns = int(timeout_s * 1e9)
    for i in range(warmup + n):
        seq = next_seq(i)
        t0 = _now_ns()
        await write(seq)
        ok = False
        while True:
            if await read() == seq:
                ok = True
                break
            if _now_ns() - t0 > timeout_ns:
                break
        dt_ms = (_now_ns() - t0) / 1e6
        if i >= warmup:
            if ok:
                res.samples_ms.append(dt_ms)
            else:
                res.failures += 1
    return res


async def ameasure_read(read: Callable[[], Awaitable[int]], *, n: int, warmup: int, protocol: str) -> Result:
    res = Result(protocol, "read_single")
    for i in range(warmup + n):
        t0 = _now_ns()
        await read()
        dt_ms = (_now_ns() - t0) / 1e6
        if i >= warmup:
            res.samples_ms.append(dt_ms)
    return res
