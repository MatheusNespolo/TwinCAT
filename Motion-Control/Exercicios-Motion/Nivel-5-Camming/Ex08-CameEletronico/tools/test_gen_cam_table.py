import math

import gen_cam_table as g


def test_reference_points():
    assert g.profile(0) == g.H0
    assert math.isclose(g.profile(60), 22.5)            # meio da subida: s = 0,5
    assert math.isclose(g.profile(120), g.H1)
    assert g.profile(150) == g.H1                        # espera em cima
    assert math.isclose(g.profile(240), 22.5)           # meio da descida
    assert math.isclose(g.profile(300), g.H0)
    assert g.profile(330) == g.H0                        # espera embaixo
    assert math.isclose(g.profile(30), 5 + 35 * (0.25 - 1 / (2 * math.pi)))


def test_profile_is_periodic():
    for th in (0, 45, 100, 200, 310):
        assert math.isclose(g.profile(th), g.profile(th + 360))
        assert math.isclose(g.profile(th), g.profile(th - 360))


def test_table_shape_and_validation():
    rows = g.table()
    assert len(rows) == 361
    assert rows[0] == (0.0, g.H0) and rows[-1][0] == 360.0
    assert g.validate(rows) == []


def test_validate_catches_broken_tables():
    rows = g.table()
    assert g.validate(rows[:-1] + [(360.0, 20.0)])                       # não fecha
    assert g.validate(rows[:100] + rows[99:])                            # mestre repete
    jump = [(m, s) if m < 100 else (m, s + 10) for m, s in rows]
    assert g.validate(jump)                                              # salto e limite


def test_coarse_step_is_flagged_as_jump():
    assert g.validate(g.table(step=40.0))


def test_cycloid_starts_and_ends_smooth():
    assert g.cycloid(0) == 0 and math.isclose(g.cycloid(1), 1)
    assert math.isclose(g.cycloid_d1(0), 0, abs_tol=1e-12) and math.isclose(g.cycloid_d1(1), 0, abs_tol=1e-12)
    assert math.isclose(g.cycloid_d2(0), 0, abs_tol=1e-12) and math.isclose(g.cycloid_d2(1), 0, abs_tol=1e-9)


def test_cycloid_is_monotonic():
    vals = [g.cycloid(i / 200) for i in range(201)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))


def test_dynamics_match_closed_form():
    d = g.dynamics(60.0)
    assert math.isclose(d["periodo_s"], 6.0)
    # subida em 2 s: v pico = 2h/T, a pico = 2*pi*h/T^2 (h = 35 mm)
    assert math.isclose(d["v_pico_mm_s"], 2 * 35 / 2)
    assert math.isclose(d["a_pico_mm_s2"], 2 * math.pi * 35 / 4)


def test_numeric_peak_velocity_agrees_with_closed_form():
    omega = 60.0
    num = max(abs(g.profile(t + 0.01) - g.profile(t - 0.01)) / 0.02 * omega for t in [i * 0.1 for i in range(3600)])
    assert math.isclose(num, g.dynamics(omega)["v_pico_mm_s"], rel_tol=1e-3)


def test_rest_zone_is_flat_so_camout_there_leaves_slave_stopped():
    # O gabarito só desacopla (MC_CamOut) com o mestre entre 300 e 360 graus.
    zone = [g.profile(t) for t in (300 + i * 0.5 for i in range(121))]
    assert all(z == g.H0 for z in zone)


def test_start_and_end_of_each_segment_have_zero_slope():
    for t in (0.0, 120.0, 180.0, 300.0):
        slope = (g.profile(t + 1e-4) - g.profile(t - 1e-4)) / 2e-4
        assert abs(slope) < 1e-3
