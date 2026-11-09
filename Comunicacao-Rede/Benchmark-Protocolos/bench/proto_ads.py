"""ADS via pyads (nativo do TwinCAT, sem licença adicional)."""
from __future__ import annotations

import pyads

from .common import Result, measure_echo, measure_read


def run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["ads"]
    plc = pyads.Connection(c["net_id"], int(c.get("port", pyads.PORT_TC3PLC1)))
    plc.open()
    try:
        # Handles de símbolo: evita resolver o nome a cada chamada (comparação justa).
        h_in = plc.get_handle(c["symbol_in"])
        h_out = plc.get_handle(c["symbol_out"])
        try:

            def write(v: int) -> None:
                plc.write_by_name("", v, pyads.PLCTYPE_DINT, handle=h_in)

            def read() -> int:
                return plc.read_by_name("", pyads.PLCTYPE_DINT, handle=h_out)

            echo = measure_echo(write, read, n=n, warmup=warmup, timeout_s=timeout_s, protocol="ads")
            single = measure_read(read, n=n, warmup=warmup, protocol="ads")
        finally:
            plc.release_handle(h_in)
            plc.release_handle(h_out)
    finally:
        plc.close()
    return [echo, single]
