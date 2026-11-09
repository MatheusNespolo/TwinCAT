"""Servidores OPC UA e Modbus TCP simulados, com 'PLC' de eco em software.

Servem para validar o benchmark sem hardware (dry-run). NÃO representam o desempenho do
TwinCAT: o ciclo de eco aqui é só um temporizador Python.

Uso:
    python -m bench.sim_servers --cycle-ms 5
Escuta OPC UA em 127.0.0.1:48400 e Modbus TCP em 127.0.0.1:5020 (use config.sim.toml).
ADS não tem simulador: ele só pode ser medido contra um runtime TwinCAT real.

O servidor Modbus é um mínimo escrito aqui (funções 3, 4 e 6), de propósito: assim o
simulador não depende da API de servidor do pymodbus, que muda entre versões. O cliente
usado no benchmark continua sendo o pymodbus real.
"""
from __future__ import annotations

import argparse
import asyncio
import struct

from asyncua import Server, ua

OPC_PORT = 48400
MODBUS_PORT = 5020
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


async def amain(cycle_ms: float) -> None:
    cycle_s = cycle_ms / 1000.0
    await asyncio.gather(opcua_server(cycle_s), modbus_server(cycle_s))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycle-ms", type=float, default=5.0)
    args = ap.parse_args()
    print(f"Simulador ativo (ciclo de eco {args.cycle_ms} ms). Ctrl+C para sair.", flush=True)
    try:
        asyncio.run(amain(args.cycle_ms))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
