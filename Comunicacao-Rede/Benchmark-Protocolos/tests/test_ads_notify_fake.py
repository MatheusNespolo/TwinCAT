"""ads_notify sem hardware: troca o pyads.Connection por um falso que devolve a notificação."""
import threading

from bench import proto_ads


class FakeConn:
    def __init__(self, net_id, port):
        self.cb = None
        self.attr = None
        self.deleted = None
        self.released = []

    def open(self):
        pass

    def close(self):
        pass

    def get_handle(self, name):
        return 7

    def release_handle(self, h):
        self.released.append(h)

    def notification(self, plc_datatype=None):
        return lambda f: f

    def add_device_notification(self, name, attr, cb, user_handle=None):
        self.cb = cb
        self.attr = attr
        return (11, 22)

    def del_device_notification(self, h, u):
        self.deleted = (h, u)

    def write_by_name(self, name, value, plc_datatype=None, handle=None):
        # a "notificação" chega depois, em outra thread, como no pyads
        threading.Timer(0.001, lambda: self.cb(handle, "GVL_Bench.nOut", 0, value)).start()


def test_run_notify_end_to_end(monkeypatch):
    conns = []

    def factory(net_id, port):
        c = FakeConn(net_id, port)
        conns.append(c)
        return c

    monkeypatch.setattr(proto_ads.pyads, "Connection", factory)
    cfg = {"ads": {"net_id": "1.2.3.4.1.1", "port": 851, "symbol_in": "GVL_Bench.nIn",
                   "symbol_out": "GVL_Bench.nOut", "notify_cycle_ms": 2}}
    (echo,) = proto_ads.run_notify(cfg, n=15, warmup=3, timeout_s=1.0)
    assert echo.protocol == "ads_notify" and echo.metric == "echo_rtt"
    assert len(echo.samples_ms) == 15 and echo.failures == 0
    assert conns[0].deleted == (11, 22)          # a notificação é cancelada no fim
    # notify_cycle_ms = 2 ms deve virar 2 ms no pyads = 20000 unidades de 100 ns. Um valor
    # menor (como 20) indicaria que os milissegundos foram passados como segundos.
    assert conns[0].attr.cycle_time == 20000
