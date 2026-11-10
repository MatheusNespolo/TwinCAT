"""Servidores OPC UA e Modbus TCP simulados, com 'PLC' de eco em software.

Servem para validar o benchmark sem hardware (dry-run). NÃO representam o desempenho do
TwinCAT: o ciclo de eco aqui é só um temporizador Python.

Uso:
    python -m bench.sim_servers --cycle-ms 5
Escuta OPC UA em 127.0.0.1:48400, Modbus TCP em 127.0.0.1:5020 e, se houver um Mosquitto
instalado (variável BENCH_MOSQUITTO, PATH ou o caminho padrão do Windows), MQTT em
127.0.0.1:18830 (use config.sim.toml). O "PLC" MQTT devolve uma mensagem por ciclo, como o
DrainOneMessage do FB_DfiMqttSubscriber. Nenhuma porta do serviço Mosquitto do sistema é usada.
ADS não tem simulador: ele só pode ser medido contra um runtime TwinCAT real.

O servidor Modbus é um mínimo escrito aqui (funções 3, 4 e 6), de propósito: assim o
simulador não depende da API de servidor do pymodbus, que muda entre versões. O cliente
usado no benchmark continua sendo o pymodbus real.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

from asyncua import Server, ua

OPC_PORT = 48400
MODBUS_PORT = 5020
MQTT_PORT = 18830
MB_ADDR = 32768


async def opcua_server(cycle_s: float) -> None:
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://127.0.0.1:{OPC_PORT}")
    idx = await server.register_namespace("urn:benchmark:sim")
    obj = server.nodes.objects
    n_in = await obj.add_variable(ua.NodeId("GVL_Bench.nIn", idx), "nIn", 0, ua.VariantType.Int32)
    n_out = await obj.add_variable(ua.NodeId("GVL_Bench.nOut", idx), "nOut", 0, ua.VariantType.Int32)
    await n_in.set_writable()
    async with server:
        while True:  # "ciclo do PLC": nOut := nIn
            await n_out.write_value(ua.Variant(await n_in.read_value(), ua.VariantType.Int32))
            await asyncio.sleep(cycle_s)


class ModbusSim:
    """Holding registers (funções 3/6) e input registers (função 4), 16 bits."""

    def __init__(self) -> None:
        self.hr: dict[int, int] = {}
        self.ir: dict[int, int] = {}

    def handle(self, unit: int, pdu: bytes) -> bytes:
        fc = pdu[0]
        if fc in (3, 4) and len(pdu) == 5:
            addr, qty = struct.unpack(">HH", pdu[1:5])
            table = self.hr if fc == 3 else self.ir
            regs = [table.get(addr + i, 0) for i in range(qty)]
            return bytes([fc, 2 * qty]) + b"".join(struct.pack(">H", r) for r in regs)
        if fc == 6 and len(pdu) == 5:
            addr, val = struct.unpack(">HH", pdu[1:5])
            self.hr[addr] = val
            return pdu  # a resposta da função 6 repete a requisição
        return bytes([fc | 0x80, 1])  # exceção: função ilegal

    async def client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await reader.readexactly(7)
                tid, proto, length, unit = struct.unpack(">HHHB", head)
                pdu = await reader.readexactly(length - 1)
                resp = self.handle(unit, pdu)
                writer.write(struct.pack(">HHHB", tid, proto, len(resp) + 1, unit) + resp)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


async def modbus_server(cycle_s: float) -> None:
    sim = ModbusSim()

    async def echo() -> None:
        while True:  # mb_Input_Registers[0] := mb_Output_Registers[0]
            sim.ir[MB_ADDR] = sim.hr.get(MB_ADDR, 0)
            await asyncio.sleep(cycle_s)

    task = asyncio.create_task(echo())
    server = await asyncio.start_server(sim.client, "127.0.0.1", MODBUS_PORT)
    try:
        async with server:
            await server.serve_forever()
    finally:
        task.cancel()


def find_mosquitto() -> str | None:
    candidates = [
        os.environ.get("BENCH_MOSQUITTO"),
        shutil.which("mosquitto"),
        r"C:\Program Files\mosquitto\mosquitto.exe",
        "/usr/sbin/mosquitto",
        "/usr/local/sbin/mosquitto",
    ]
    return next((c for c in candidates if c and os.path.exists(c)), None)


def _wait_port(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


class MqttSim:
    """Mosquitto de teste (porta própria) + 'PLC' de eco: assina bench/in, devolve em bench/out."""

    def __init__(self, cycle_s: float) -> None:
        self.cycle_s = cycle_s
        self.proc: subprocess.Popen | None = None
        self.conf: str | None = None
        self.client = None
        self._stop = threading.Event()
        self._queue: collections.deque = collections.deque()

    def start(self) -> bool:
        exe = find_mosquitto()
        if not exe:
            return False
        import paho.mqtt.client as mqtt

        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write(f"listener {MQTT_PORT} 127.0.0.1" + chr(10) + "allow_anonymous true" + chr(10))
            self.conf = f.name
        self.proc = subprocess.Popen([exe, "-c", self.conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not _wait_port(MQTT_PORT):
            self.stop()
            return False
        cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bench-sim-plc")
        cl.on_message = lambda c, u, m: self._queue.append(m.payload)
        connected = threading.Event()
        cl.on_connect = lambda c, u, fl, rc, pr: (c.subscribe("bench/in", qos=1), connected.set())
        cl.connect("127.0.0.1", MQTT_PORT, keepalive=60)
        cl.loop_start()
        if not connected.wait(10):
            self.stop()
            return False
        self.client = cl
        threading.Thread(target=self._cycle, daemon=True).start()
        return True

    def _cycle(self) -> None:
        while not self._stop.is_set():  # uma mensagem por ciclo
            if self._queue:
                self.client.publish("bench/out", self._queue.popleft(), qos=1)
            time.sleep(self.cycle_s)

    def stop(self) -> None:
        self._stop.set()
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()
        if self.proc is not None:
            self.proc.kill()
            self.proc.wait(timeout=10)
        if self.conf and os.path.exists(self.conf):
            os.unlink(self.conf)


async def amain(cycle_ms: float) -> None:
    cycle_s = cycle_ms / 1000.0
    await asyncio.gather(opcua_server(cycle_s), modbus_server(cycle_s))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycle-ms", type=float, default=5.0)
    ap.add_argument(
        "--exit-on-stdin-close",
        action="store_true",
        help="encerra (e para o Mosquitto de teste) quando o stdin é fechado; usado pelos testes",
    )
    args = ap.parse_args()
    mqtt_sim = MqttSim(args.cycle_ms / 1000.0)
    mqtt_ok = mqtt_sim.start()
    if args.exit_on_stdin_close:

        def _watch_stdin() -> None:
            sys.stdin.read()  # bloqueia até o processo pai fechar o pipe (ou morrer)
            mqtt_sim.stop()
            os._exit(0)

        threading.Thread(target=_watch_stdin, daemon=True).start()
    print(
        f"Simulador ativo (ciclo de eco {args.cycle_ms} ms; MQTT "
        f"{'em 127.0.0.1:%d' % MQTT_PORT if mqtt_ok else 'indisponível: Mosquitto não encontrado'}). Ctrl+C para sair.",
        flush=True,
    )
    try:
        asyncio.run(amain(args.cycle_ms))
    except KeyboardInterrupt:
        pass
    finally:
        mqtt_sim.stop()


if __name__ == "__main__":
    main()
