"""HTTP-level tests using the real FastAPI application (no solver mocks)."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from app.scenarios import SCENARIOS

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scenarios_list():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    assert keys == {"unique", "multiple", "incompatible"}


def _payload(sc):
    return {
        "threshold": sc["threshold"],
        "outlier_quota": sc["outlier_quota"],
        "catalog": sc["catalog"],
        "observations": sc["observations"],
        "dot_measurements": sc["dot_measurements"],
    }


def test_unique_scenario():
    sc = SCENARIOS["unique"]
    r = client.post("/api/solve", json=_payload(sc))
    assert r.status_code == 200
    data = r.json()
    exp = sc["expect"]
    assert data["status"] == "optimal"
    assert data["kept_count"] == exp["kept_count"]
    assert data["residual_sum"] == exp["residual_sum"]
    assert data["multiple"] is False
    assert data["witness"] is None
    assert data["canonical"]["sequence"] == exp["canonical_sequence"]
    assert data["canonical"]["rejected"] == [5]


def test_multiple_scenario_has_distinct_witness():
    sc = SCENARIOS["multiple"]
    r = client.post("/api/solve", json=_payload(sc))
    data = r.json()
    assert data["multiple"] is True
    assert data["canonical"]["sequence"] == sc["expect"]["canonical_sequence"]
    assert data["witness"]["sequence"] == sc["expect"]["witness_sequence"]
    assert data["witness"]["sequence"] != data["canonical"]["sequence"]
    assert data["witness"]["residual_sum"] == data["residual_sum"]
    assert len(data["witness"]["assignments"]) == data["kept_count"]


def test_incompatible_scenario():
    sc = SCENARIOS["incompatible"]
    r = client.post("/api/solve", json=_payload(sc))
    data = r.json()
    assert data["status"] == "incompatible"
    assert data["message"]


def test_validation_issues_are_locatable():
    sc = SCENARIOS["unique"]
    bad = _payload(sc)
    bad["threshold"] = -1
    bad["outlier_quota"] = 5
    bad["catalog"][1] = dict(bad["catalog"][1])
    bad["catalog"][1]["id"] = ""
    r = client.post("/api/solve", json=bad)
    assert r.status_code == 422
    locs = {tuple(i["loc"]) for i in r.json()["issues"]}
    assert ("threshold",) in locs
    assert ("outlier_quota",) in locs
    assert ("catalog", 1, "id") in locs


def test_non_json_body():
    r = client.post("/api/solve", content="not-json", headers={"content-type": "text/plain"})
    assert r.status_code == 422
    assert r.json()["issues"][0]["loc"] == []
