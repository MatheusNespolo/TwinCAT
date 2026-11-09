"""Integração: o benchmark completo (OPC UA e Modbus) contra os servidores simulados."""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from bench import run_all
from bench.common import load_config

ROOT = Path(__file__).resolve().parent.parent


def _wait_port(port: int, timeout: float = 20.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def sim():
    proc = subprocess.Popen(
        [sys.executable, "-m", "bench.sim_servers", "--cycle-ms", "5"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        if not (_wait_port(48400) and _wait_port(5020)):
            proc.kill()
            pytest.fail(f"simulador não subiu: {proc.stderr.read().decode(errors='replace')[:500]}")
        yield
    finally:
        proc.kill()
        proc.wait(timeout=10)


@pytest.mark.parametrize("proto", ["opcua", "modbus"])
def test_protocol_against_simulator(sim, proto):
    cfg = load_config(ROOT / "config.sim.toml")
    results = run_all.run_protocols(cfg, [proto], n=30, warmup=5, timeout_s=2.0)
    assert {r.metric for r in results} == {"echo_rtt", "read_single"}
    echo = next(r for r in results if r.metric == "echo_rtt")
    assert echo.failures == 0 and len(echo.samples_ms) == 30
    # o ciclo simulado é de 5 ms: o eco não pode voltar muito antes disso, na média
    assert sum(echo.samples_ms) / 30 > 0.2


def test_main_writes_outputs_and_analyze_runs(sim, tmp_path):
    rc = run_all.main(["--config", str(ROOT / "config.sim.toml"), "--protocols", "opcua", "modbus",
                       "--samples", "20", "--warmup", "3", "--out", str(tmp_path)])
    assert rc == 0
    run_dir = next(tmp_path.iterdir())
    assert (run_dir / "samples.csv").exists() and (run_dir / "summary.csv").exists()
    from bench import analyze
    assert analyze.main([str(run_dir)]) == 0
    assert (run_dir / "summary.md").exists() and (run_dir / "rtt.png").exists()
