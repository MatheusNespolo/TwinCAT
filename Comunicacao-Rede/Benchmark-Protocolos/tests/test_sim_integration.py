"""Integração: o benchmark completo contra os servidores simulados (OPC UA, Modbus e, se houver
Mosquitto instalado, MQTT)."""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from bench import run_all
from bench.common import load_config
from bench.sim_servers import MQTT_PORT, find_mosquitto

ROOT = Path(__file__).resolve().parent.parent
HAS_MOSQUITTO = find_mosquitto() is not None


def _wait_port(port: int, timeout: float = 25.0) -> bool:
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
    # stdin=PIPE: ao fechar o pipe o simulador encerra sozinho e derruba o Mosquitto de teste
    # (proc.kill() não executaria o finally do simulador e deixaria o Mosquitto órfão).
    proc = subprocess.Popen(
        [sys.executable, "-m", "bench.sim_servers", "--cycle-ms", "5", "--exit-on-stdin-close"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        ports = [48400, 5020] + ([MQTT_PORT] if HAS_MOSQUITTO else [])
        if not all(_wait_port(p) for p in ports):
            proc.kill()
            pytest.fail(f"simulador não subiu: {proc.stderr.read().decode(errors='replace')[:500]}")
        yield
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
            proc.wait(timeout=10)


@pytest.mark.parametrize("proto", ["opcua", "modbus"])
def test_polling_protocol_against_simulator(sim, proto):
    cfg = load_config(ROOT / "config.sim.toml")
    results = run_all.run_protocols(cfg, [proto], n=30, warmup=5, timeout_s=2.0)
    assert {r.metric for r in results} == {"echo_rtt", "read_single"}
    echo = next(r for r in results if r.metric == "echo_rtt")
    assert echo.failures == 0 and len(echo.samples_ms) == 30
    # o ciclo simulado é de 5 ms: o eco não pode voltar muito antes disso, na média
    assert sum(echo.samples_ms) / 30 > 0.2


def test_opcua_subscription_against_simulator(sim):
    cfg = load_config(ROOT / "config.sim.toml")
    (echo,) = run_all.run_protocols(cfg, ["opcua_sub"], n=30, warmup=5, timeout_s=2.0)
    assert echo.protocol == "opcua_sub" and echo.metric == "echo_rtt"
    assert echo.failures == 0 and len(echo.samples_ms) == 30
    assert sum(echo.samples_ms) / 30 > 0.2


@pytest.mark.skipif(not HAS_MOSQUITTO, reason="Mosquitto não está instalado")
def test_mqtt_against_simulator(sim):
    cfg = load_config(ROOT / "config.sim.toml")
    results = run_all.run_protocols(cfg, ["mqtt"], n=30, warmup=5, timeout_s=2.0)
    assert {r.metric for r in results} == {"echo_rtt", "publish_ack"}
    echo = next(r for r in results if r.metric == "echo_rtt")
    ack = next(r for r in results if r.metric == "publish_ack")
    assert echo.failures == 0 and len(echo.samples_ms) == 30
    assert ack.failures == 0 and len(ack.samples_ms) == 30
    # o "PLC" devolve uma mensagem por ciclo de 5 ms; o eco passa pelo broker duas vezes
    assert sum(echo.samples_ms) / 30 > 0.5
    # a confirmação do broker não envolve o PLC: tem de ser bem mais rápida que o eco
    assert sum(ack.samples_ms) < sum(echo.samples_ms)


def test_main_writes_outputs_and_analyze_runs(sim, tmp_path):
    protos = ["opcua", "opcua_sub", "modbus"] + (["mqtt"] if HAS_MOSQUITTO else [])
    rc = run_all.main(["--config", str(ROOT / "config.sim.toml"), "--protocols", *protos,
                       "--samples", "20", "--warmup", "3", "--out", str(tmp_path)])
    assert rc == 0
    run_dir = next(tmp_path.iterdir())
    assert (run_dir / "samples.csv").exists() and (run_dir / "summary.csv").exists()
    from bench import analyze
    assert analyze.main([str(run_dir)]) == 0
    md = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "opcua_sub" in md
    assert (not HAS_MOSQUITTO) or "Publicação confirmada" in md
    assert (run_dir / "rtt.png").exists()
