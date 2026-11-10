"""OPC UA via asyncua (servidor: TF6100 no controlador).

Dois modos:
- ``run``: leitura em laço (polling) do nó de saída;
- ``run_sub``: assinatura (*subscription*) com ``subscribe_data_change``: o servidor avisa
  quando ``nOut`` muda. O intervalo de publicação e o de amostragem pedidos ao servidor vêm de
  ``[opcua] sub_period_ms`` e ``sampling_ms`` (o servidor pode revisá-los para cima: o valor
  efetivo faz parte do resultado e deve ser registrado).
"""
from __future__ import annotations

import asyncio
import os

from asyncua import Client, ua

from .common import Result, ameasure_echo, ameasure_echo_push, ameasure_read


def _make_client(c: dict, timeout_s: float) -> Client:
    client = Client(url=c["url"], timeout=max(timeout_s, 4.0))
    # Credenciais vêm do ambiente, nunca do arquivo de configuração versionado.
    user = os.environ.get("BENCH_OPCUA_USER") or c.get("username")
    password = os.environ.get("BENCH_OPCUA_PASSWORD", "")
    if user:
        client.set_user(user)
        client.set_password(password)
    return client


async def _connect(client: Client, c: dict) -> None:
    if c.get("security"):
        # Ex.: "Basic256Sha256,SignAndEncrypt,cert.der,key.pem" (exige certificado confiável no servidor)
        await client.set_security_string(c["security"])


async def _run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["opcua"]
    client = _make_client(c, timeout_s)
    await _connect(client, c)
    async with client:
        node_in = client.get_node(c["node_in"])
        node_out = client.get_node(c["node_out"])

        async def write(v: int) -> None:
            await node_in.write_value(ua.Variant(v, ua.VariantType.Int32))

        async def read() -> int:
            return await node_out.read_value()

        echo = await ameasure_echo(write, read, n=n, warmup=warmup, timeout_s=timeout_s, protocol="opcua")
        single = await ameasure_read(read, n=n, warmup=warmup, protocol="opcua")
    return [echo, single]


async def _run_sub(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["opcua"]
    client = _make_client(c, timeout_s)
    await _connect(client, c)
    async with client:
        node_in = client.get_node(c["node_in"])
        node_out = client.get_node(c["node_out"])
        loop = asyncio.get_running_loop()
        pending: dict[int, asyncio.Future] = {}

        class Handler:
            def datachange_notification(self, node, val, data):  # roda no laço de eventos
                fut = pending.get(val)
                if fut is not None and not fut.done():
                    fut.set_result(True)

        sub = await client.create_subscription(float(c.get("sub_period_ms", 1.0)), Handler())
        await sub.subscribe_data_change(node_out, sampling_interval=float(c.get("sampling_ms", 1.0)))
        try:

            async def send(v: int) -> None:
                pending[v] = loop.create_future()  # registra a espera ANTES de escrever
                await node_in.write_value(ua.Variant(v, ua.VariantType.Int32))

            async def wait(seq: int, timeout: float) -> bool:
                fut = pending[seq]
                try:
                    return await asyncio.wait_for(fut, timeout)
                except asyncio.TimeoutError:
                    return False
                finally:
                    pending.pop(seq, None)

            echo = await ameasure_echo_push(send, wait, n=n, warmup=warmup, timeout_s=timeout_s, protocol="opcua_sub")
        finally:
            await sub.delete()
    return [echo]


def run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    return asyncio.run(_run(cfg, n, warmup, timeout_s))


def run_sub(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    return asyncio.run(_run_sub(cfg, n, warmup, timeout_s))
