import math

from bench.common import Result, SEQ_MAX, measure_echo, measure_read, next_seq, percentile, summarize


def test_percentile_interpolates():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(vals, 0) == 1.0
    assert percentile(vals, 50) == 3.0
    assert percentile(vals, 100) == 5.0
    assert math.isclose(percentile(vals, 95), 4.8)


def test_percentile_edge_cases():
    assert math.isnan(percentile([], 50))
    assert percentile([7.0], 99) == 7.0


def test_next_seq_range_and_never_repeats_consecutively():
    seqs = [next_seq(i) for i in range(2 * SEQ_MAX + 5)]
    assert min(seqs) == 1 and max(seqs) == SEQ_MAX
    assert all(a != b for a, b in zip(seqs, seqs[1:]))


def test_summarize_counts_and_rate():
    r = Result("x", "echo_rtt", samples_ms=[1.0, 2.0, 3.0], failures=2)
    s = summarize(r)
    assert s["n"] == 3 and s["failures"] == 2
    assert s["p50_ms"] == 2.0 and s["max_ms"] == 3.0
    assert math.isclose(s["ops_per_s"], 500.0)


def test_summarize_empty_is_nan_not_crash():
    s = summarize(Result("x", "echo_rtt"))
    assert s["n"] == 0 and math.isnan(s["mean_ms"])


def test_measure_echo_with_instant_echo():
    store = {"v": 0}
    res = measure_echo(
        lambda v: store.__setitem__("v", v), lambda: store["v"],
        n=20, warmup=5, timeout_s=0.5, protocol="fake",
    )
    assert len(res.samples_ms) == 20 and res.failures == 0


def test_measure_echo_counts_timeouts_as_failures():
    res = measure_echo(lambda v: None, lambda: 0, n=3, warmup=0, timeout_s=0.01, protocol="fake")
    assert res.failures == 3 and res.samples_ms == []


def test_measure_echo_needs_several_reads_when_echo_is_late():
    calls = {"n": 0, "v": 0}

    def write(v):
        calls["v"], calls["n"] = v, 0

    def read():  # o eco só aparece na 3ª leitura, simulando o ciclo do PLC
        calls["n"] += 1
        return calls["v"] if calls["n"] >= 3 else -1

    res = measure_echo(write, read, n=5, warmup=0, timeout_s=0.5, protocol="fake")
    assert res.failures == 0 and len(res.samples_ms) == 5


def test_measure_read_discards_warmup():
    res = measure_read(lambda: 0, n=10, warmup=4, protocol="fake")
    assert len(res.samples_ms) == 10


# ---- modos por push ---------------------------------------------------------------------
import asyncio
import threading

from bench.common import ameasure_echo_push, measure_echo_push


def test_measure_echo_push_registers_wait_before_send():
    seen = {}
    cond = threading.Condition()

    def send(seq):
        # eco imediato, em outra thread, ANTES de send voltar: wait não pode perdê-lo
        def reply():
            with cond:
                seen["v"] = seq
                cond.notify_all()
        threading.Thread(target=reply).start()

    def wait(seq, timeout):
        with cond:
            return cond.wait_for(lambda: seen.get("v") == seq, timeout)

    res = measure_echo_push(send, wait, n=20, warmup=3, timeout_s=0.5, protocol="fake_push")
    assert res.metric == "echo_rtt" and len(res.samples_ms) == 20 and res.failures == 0


def test_measure_echo_push_counts_timeouts():
    res = measure_echo_push(lambda s: None, lambda s, t: False, n=4, warmup=1, timeout_s=0.01, protocol="x")
    assert res.failures == 4 and res.samples_ms == []


def test_ameasure_echo_push_async():
    async def send(seq):
        pass

    async def wait(seq, timeout):
        await asyncio.sleep(0.001)
        return True

    res = asyncio.run(ameasure_echo_push(send, wait, n=10, warmup=2, timeout_s=0.5, protocol="x"))
    assert len(res.samples_ms) == 10 and res.failures == 0
