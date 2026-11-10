"""ADS via pyads (nativo do TwinCAT, sem licença adicional).

Dois modos:
- ``run``: leitura em laço (polling) por *handle* de símbolo;
- ``run_notify``: notificações de dispositivo (``add_device_notification``): o runtime avisa
  o cliente quando ``nOut`` muda, sem laço de leitura.
"""
from __future__ import annotations

import ctypes
import threading

import pyads

from .common import Result, measure_echo, measure_echo_push, measure_read


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


def run_notify(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["ads"]
    plc = pyads.Connection(c["net_id"], int(c.get("port", pyads.PORT_TC3PLC1)))
    plc.open()
    try:
        h_in = plc.get_handle(c["symbol_in"])
        cv = threading.Condition()
        last = {"v": None}

        def on_change(handle, name, timestamp, value):  # roda na thread do pyads
            with cv:
                last["v"] = value
                cv.notify_all()

        # Notificação só quando o valor muda. No pyads, max_delay e cycle_time são em
        # MILISSEGUNDOS (a lib converte para unidades de 100 ns); passar segundos daria
        # um ciclo 1000 vezes menor que o configurado.
        cycle_ms = float(c.get("notify_cycle_ms", 1.0))
        attr = pyads.NotificationAttrib(
            ctypes.sizeof(pyads.PLCTYPE_DINT),
            trans_mode=pyads.ADSTRANS_SERVERONCHA,
            max_delay=0.0,
            cycle_time=cycle_ms,
        )
        handles = plc.add_device_notification(
            c["symbol_out"], attr, plc.notification(pyads.PLCTYPE_DINT)(on_change)
        )
        try:

            def send(v: int) -> None:
                plc.write_by_name("", v, pyads.PLCTYPE_DINT, handle=h_in)

            def wait(seq: int, timeout: float) -> bool:
                with cv:
                    return cv.wait_for(lambda: last["v"] == seq, timeout)

            echo = measure_echo_push(send, wait, n=n, warmup=warmup, timeout_s=timeout_s, protocol="ads_notify")
        finally:
            plc.del_device_notification(*handles)
            plc.release_handle(h_in)
    finally:
        plc.close()
    return [echo]
