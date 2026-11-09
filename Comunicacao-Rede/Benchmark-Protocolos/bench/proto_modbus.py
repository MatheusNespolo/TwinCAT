"""Modbus TCP via pymodbus (servidor: TF6250 no controlador).

O cliente escreve o número de sequência num holding register (função 6) e lê o eco num
input register (função 4); o PLC copia ``mb_Output_Registers[0]`` em ``mb_Input_Registers[0]``.
Registrador de 16 bits: por isso a sequência vai de 1 a 65535.
"""
from __future__ import annotations

import inspect

from pymodbus.client import ModbusTcpClient

from .common import Result, measure_echo, measure_read


def run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["modbus"]
    client = ModbusTcpClient(c["host"], port=int(c.get("port", 502)), timeout=max(timeout_s, 2.0))
    if not client.connect():
        raise ConnectionError(f"Modbus TCP: sem conexão com {c['host']}:{c.get('port', 502)}")
    # pymodbus 3.10+ usa device_id; versões antigas usam slave.
    kw = "device_id" if "device_id" in inspect.signature(client.write_register).parameters else "slave"
    dev = {kw: int(c.get("device_id", 1))}
    addr_w = int(c["register_write"])
    addr_r = int(c["register_read"])
    try:

        def write(v: int) -> None:
            rr = client.write_register(addr_w, v, **dev)
            if rr.isError():
                raise IOError(f"Modbus: erro na escrita ({rr})")

        def read() -> int:
            rr = client.read_input_registers(addr_r, count=1, **dev)
            if rr.isError():
                raise IOError(f"Modbus: erro na leitura ({rr})")
            return rr.registers[0]

        echo = measure_echo(write, read, n=n, warmup=warmup, timeout_s=timeout_s, protocol="modbus")
        single = measure_read(read, n=n, warmup=warmup, protocol="modbus")
    finally:
        client.close()
    return [echo, single]
