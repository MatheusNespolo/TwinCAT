"""OPC UA via asyncua (servidor: TF6100 no controlador)."""
from __future__ import annotations

import asyncio
import os

from asyncua import Client, ua

from .common import Result, ameasure_echo, ameasure_read


async def _run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["opcua"]
    client = Client(url=c["url"], timeout=max(timeout_s, 4.0))
    # Credenciais vêm do ambiente, nunca do arquivo de configuração versionado.
    user = os.environ.get("BENCH_OPCUA_USER") or c.get("username")
    password = os.environ.get("BENCH_OPCUA_PASSWORD", "")
    if user:
        client.set_user(user)
        client.set_password(password)
    if c.get("security"):
        # Ex.: "Basic256Sha256,SignAndEncrypt,cert.der,key.pem" (exige certificado confiável no servidor)
        await client.set_security_string(c["security"])
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


def run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    return asyncio.run(_run(cfg, n, warmup, timeout_s))
