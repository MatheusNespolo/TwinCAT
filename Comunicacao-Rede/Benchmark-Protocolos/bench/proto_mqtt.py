"""MQTT via paho-mqtt (lado PLC: TF6701, Tc3_IotBase; broker: por exemplo o Mosquitto do DFI).

Caminho medido: cliente Python -> broker -> PLC -> broker -> cliente Python. Por isso o
resultado inclui **duas passagens pelo broker**; não é comparável a ADS, OPC UA e Modbus
sem essa ressalva.

Métricas:
- ``echo_rtt``: publica N em ``topic_in`` e espera N voltar em ``topic_out`` (o PLC assina
  ``topic_in`` e devolve o mesmo payload);
- ``publish_ack``: tempo até o broker confirmar (PUBACK) um publish com QoS 1 num tópico
  sem assinantes; é o custo puro do protocolo até o broker, sem o PLC.

O payload é o número em ASCII decimal (de 1 a 65535).
"""
from __future__ import annotations

import os
import threading
import time

import paho.mqtt.client as mqtt

from .common import Result, measure_echo_push, next_seq

CONNECT_TIMEOUT_S = 10.0


def _make_client(c: dict) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=c.get("client_id", "bench-client"),
        protocol=mqtt.MQTTv311,
    )
    # Credenciais vêm do ambiente, nunca do arquivo de configuração versionado.
    user = os.environ.get("BENCH_MQTT_USER") or c.get("username")
    if user:
        client.username_pw_set(user, os.environ.get("BENCH_MQTT_PASSWORD", ""))
    if c.get("tls"):
        client.tls_set(ca_certs=c.get("ca_cert") or None)
    return client


def run(cfg: dict, n: int, warmup: int, timeout_s: float) -> list[Result]:
    c = cfg["mqtt"]
    topic_in = c.get("topic_in", "bench/in")
    topic_out = c.get("topic_out", "bench/out")
    topic_probe = c.get("topic_probe", "bench/probe")
    qos = int(c.get("qos", 1))

    client = _make_client(c)
    connected = threading.Event()
    subscribed = threading.Event()
    cv = threading.Condition()
    last = {"payload": None}

    def on_connect(cl, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            connected.set()

    def on_subscribe(cl, userdata, mid, reason_codes, properties):
        subscribed.set()

    def on_message(cl, userdata, msg):  # thread de rede do paho
        with cv:
            last["payload"] = msg.payload
            cv.notify_all()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.connect(c["host"], int(c.get("port", 1883)), keepalive=60)
    client.loop_start()
    try:
        if not connected.wait(CONNECT_TIMEOUT_S):
            raise ConnectionError(f"MQTT: sem conexão com {c['host']}:{c.get('port', 1883)}")
        client.subscribe(topic_out, qos=qos)
        if not subscribed.wait(CONNECT_TIMEOUT_S):
            raise ConnectionError("MQTT: assinatura de topic_out não confirmada")

        def send(seq: int) -> None:
            client.publish(topic_in, str(seq), qos=qos)

        def wait(seq: int, timeout: float) -> bool:
            want = str(seq).encode()
            with cv:
                return cv.wait_for(lambda: last["payload"] == want, timeout)

        echo = measure_echo_push(send, wait, n=n, warmup=warmup, timeout_s=timeout_s, protocol="mqtt")

        # publish_ack: QoS 1 num tópico sem assinantes (o broker confirma sem envolver o PLC).
        ack = Result("mqtt", "publish_ack")
        for i in range(warmup + n):
            t0 = time.perf_counter_ns()
            info = client.publish(topic_probe, str(next_seq(i)), qos=1)
            try:
                info.wait_for_publish(timeout_s)  # no paho 2.x não devolve valor
                ok = info.is_published()
            except (RuntimeError, ValueError):
                ok = False
            dt_ms = (time.perf_counter_ns() - t0) / 1e6
            if i >= warmup:
                if ok:
                    ack.samples_ms.append(dt_ms)
                else:
                    ack.failures += 1
    finally:
        client.loop_stop()
        client.disconnect()
    return [echo, ack]
