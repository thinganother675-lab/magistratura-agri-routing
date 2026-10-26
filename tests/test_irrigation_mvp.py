import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest

from agro_route.irrigation_mvp import (
    Config, InputError, analyse, choose_irrigation, config_from_dict,
    csv_text, fit_model, generate_demo, parse_csv, validate_rows, water_step,
)
from agro_route.irrigation_web import make_server


def test_water_units_and_capacity_accounting():
    cfg = Config(kc=1, efficiency=.8, capacity_mm=90)
    # 60 + 5 + .8*10 - 4 = 69; 1 mm over 1 ha is 10 m3.
    assert water_step(60, 5, 4, 10, cfg) == (69, 0)
    assert water_step(88, 10, 1, 10, cfg) == (90, 15)
    assert water_step(1, 0, 5, 0, cfg) == (0, 0)
    one = analyse({"config": {"area_ha": 1}})
    for policy in one["comparisons"].values():
        assert policy["water_m3"] == pytest.approx(policy["water_mm"] * 10, abs=.01)


def test_temporal_holdout_does_not_train_on_future_targets():
    rows = generate_demo()
    original = analyse({"source": "csv", "csv": csv_text(rows)})
    changed = copy.deepcopy(rows)
    for row in changed[84:]:
        row["next_soil_mm"] = 0
    altered = analyse({"source": "csv", "csv": csv_text(changed)})
    assert original["model"]["coefficients"] == altered["model"]["coefficients"]
    assert original["model"]["mean"] == altered["model"]["mean"]
    assert original["model"]["scale"] == altered["model"]["scale"]
    assert original["model"]["mae_mm"] != altered["model"]["mae_mm"]
    assert original["model"]["train_end"] < original["model"]["test_start"]
    assert original["comparisons"] == altered["comparisons"]


def test_learned_model_recovers_independent_linear_observations():
    rng = np.random.default_rng(7)
    rows = []
    for _ in range(100):
        soil, rain, et0, irrigation = rng.uniform(30, 60), rng.uniform(0, 5), rng.uniform(1, 5), rng.uniform(0, 15)
        rows.append({"soil_mm": soil, "rain_forecast_mm": rain, "et0_forecast_mm": et0,
                     "irrigation_mm": irrigation,
                     "next_soil_mm": soil + .8 * rain - 1.1 * et0 + .75 * irrigation})
    model = fit_model(rows)
    assert model.predict([45, 3, 4, 8]) == pytest.approx(49, abs=.2)
    assert np.isfinite(model.coefficients).all()


@pytest.mark.parametrize("key,value", [
    ("area_ha", float("nan")), ("efficiency", 0), ("season_days", 1.5),
    ("calendar_interval_days", True), ("capacity_mm", "90"),
    ("target_fraction", .5), ("calendar_amount_mm", 60),
])
def test_invalid_parameters_are_rejected(key, value):
    with pytest.raises(InputError):
        config_from_dict({key: value})


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "gap", "infinite", "outside"])
def test_bad_observations_fail_instead_of_imputing_zero(mutation):
    rows = generate_demo(days=60)
    if mutation == "missing":
        del rows[3]["soil_mm"]
    elif mutation == "duplicate":
        rows[3]["date"] = rows[2]["date"]
    elif mutation == "gap":
        rows[3]["date"] = "2026-06-08"
    elif mutation == "infinite":
        rows[3]["next_soil_mm"] = float("inf")
    else:
        rows[3]["soil_mm"] = 91
    with pytest.raises(InputError):
        validate_rows(rows, Config())


def test_csv_forecasts_only_does_not_invent_actual_weather_or_economics():
    rows = generate_demo()
    for row in rows:
        del row["rain_actual_mm"], row["et0_actual_mm"]
    report = analyse({"source": "csv", "csv": csv_text(rows)})
    assert report["economics"] is None
    assert report["comparisons"] == {}
    assert report["data"]["simulation_available"] is False
    assert report["model"]["mae_mm"] >= 0
    assert report["recommendation"]["irrigation_mm"] >= 0


def test_csv_roundtrip_and_missing_required_value():
    rows = generate_demo(days=60)
    assert parse_csv("\ufeff" + csv_text(rows)) == rows
    bad = csv_text(rows).replace(str(rows[0]["soil_mm"]), "", 1)
    with pytest.raises(InputError, match="пропуск не равен нулю"):
        parse_csv(bad)


def test_replay_deterministic_and_policy_constraints():
    report = analyse({"seed": 11, "scenario": "dry"})
    assert report == analyse({"seed": 11, "scenario": "dry"})
    for policy in report["comparisons"].values():
        for day in policy["daily"]:
            assert 0 <= day["irrigation_mm"] <= report["config"]["max_irrigation_mm"]
            assert 0 <= day["soil_end_mm"] <= report["config"]["capacity_mm"]
    assert report["economics"]["comparable_deficit"] == (
        report["comparisons"]["ml"]["deficit_days"] <= report["comparisons"]["calendar"]["deficit_days"])


def test_unprofitable_scenario_does_not_show_finite_payback():
    report = analyse({"config": {"water_rub_m3": 0, "annual_opex_rub": 18000}})
    assert report["economics"]["annual_net_rub"] == -18000
    assert report["economics"]["payback_years"] is None


def test_implausible_learned_response_falls_back_to_balance():
    class BadModel:
        def predict(self, x):
            return 20 - x[3]
    cfg = Config()
    row = {"soil_mm": 25, "rain_forecast_mm": 0, "et0_forecast_mm": 5, "irrigation_mm": 0}
    amount, reason = choose_irrigation("ml", 0, 25, row, cfg, BadModel())
    assert amount == cfg.max_irrigation_mm
    assert "резервный" in reason


def test_plan_dose_cannot_exceed_hard_limit_even_under_extreme_deficit():
    cfg = Config(max_irrigation_mm=2, calendar_amount_mm=2)
    row = {"soil_mm": 0, "rain_forecast_mm": 0, "et0_forecast_mm": 15, "irrigation_mm": 0}
    model = fit_model(generate_demo(cfg=cfg))
    for policy in ("calendar", "rule", "ml"):
        assert 0 <= choose_irrigation(policy, 0, 0, row, cfg, model)[0] <= 2


@pytest.fixture
def http_server():
    server = make_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield "http://127.0.0.1:" + str(server.server_address[1])
    server.shutdown()
    server.server_close()
    worker.join(timeout=3)


def test_http_full_data_path_and_bad_upload(http_server):
    with urlopen(http_server + "/") as response:
        assert b"AgroPlan" in response.read()
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    with urlopen(http_server + "/api/sample.csv") as response:
        sample = response.read().decode("utf-8-sig")
    request = Request(http_server + "/api/analyse", data=json.dumps({"source": "csv", "csv": sample}).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        report = json.load(response)
    assert report["source"] == "csv"
    assert report["model"]["train_rows"] == 84
    assert len(report["comparisons"]["ml"]["daily"]) == 36
    bad = Request(http_server + "/api/analyse", data=b'{"source":"csv","csv":"date,soil_mm"}',
                  headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as err:
        urlopen(bad)
    assert err.value.code == 400
    assert "Нужны колонки" in json.load(err.value)["error"]


def test_server_rejects_foreign_origin_and_dns_rebinding(http_server):
    for headers in ({"Origin": "https://foreign.example"}, {"Host": "foreign.example"}):
        request = Request(http_server + "/api/analyse", data=b"{}", headers={"Content-Type": "application/json", **headers})
        with pytest.raises(HTTPError) as err:
            urlopen(request)
        assert err.value.code == 403


def test_server_rejects_oversized_body_before_reading(http_server):
    request = Request(http_server + "/api/analyse", data=b"{}", headers={"Content-Type": "application/json", "Content-Length": "220001"})
    with pytest.raises(HTTPError) as err:
        urlopen(request)
    assert err.value.code == 400
