from fastapi.testclient import TestClient

from odmrp_sim.api.app import app
from odmrp_sim.services.scenarios import script_horizon


client = TestClient(app)


def test_health_and_scenario():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "version" in r.json()

    r = client.post("/api/network/scenario?name=basic-mesh")
    assert r.status_code == 200
    snap = r.json()
    assert len(snap["topology"]["nodes"]) == 6
    assert snap["sim"]["scenario"] == "basic-mesh"
    assert snap["sim"]["t"] == 0.0
    assert snap["sim"]["mode"] == "paused"
    # Script is scheduled, not executed — no FG yet
    fg = [
        int(i)
        for i, n in snap["nodes"].items()
        if "demo" in n.get("forwarding_groups", {})
    ]
    assert fg == []

    # Advance through the script (joins at 0, text at 1) plus settle
    horizon = script_horizon({"script": [{"at": 0.0}, {"at": 1.0}]}) + 0.5
    r = client.post("/api/sim/step", json={"dt": horizon})
    assert r.status_code == 200
    snap = r.json()
    fg = [
        int(i)
        for i, n in snap["nodes"].items()
        if "demo" in n.get("forwarding_groups", {})
    ]
    assert sorted(fg) == [1, 3]

    r = client.post("/api/messages", json={"source": 0, "group": "demo", "text": "hello again"})
    assert r.status_code == 200
    mid = r.json()["message_id"]
    report = client.get(f"/api/messages/{mid}/report").json()
    assert 3 in report["delivered_to"] or 5 in report["delivered_to"]


def test_reset_reloads_scenario_at_t0():
    client.post("/api/network/scenario?name=basic-mesh")
    client.post("/api/sim/step", json={"dt": 1.5})
    r = client.post("/api/sim/reset")
    assert r.status_code == 200
    snap = r.json()
    assert snap["sim"]["t"] == 0.0
    assert snap["sim"]["mode"] == "paused"
    assert snap["sim"]["scenario"] == "basic-mesh"
    fg = [
        int(i)
        for i, n in snap["nodes"].items()
        if "demo" in n.get("forwarding_groups", {})
    ]
    assert fg == []
