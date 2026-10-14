from fastapi.testclient import TestClient

from odmrp_sim.api.app import app


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

    # FG should already be formed after scenario settle
    fg = [
        int(i)
        for i, n in snap["nodes"].items()
        if "demo" in n.get("forwarding_groups", {})
    ]
    assert sorted(fg) == [1, 3]

    r = client.post("/api/sim/step", json={"dt": 0.1})
    assert r.status_code == 200

    r = client.post("/api/messages", json={"source": 0, "group": "demo", "text": "hello again"})
    assert r.status_code == 200
    mid = r.json()["message_id"]
    report = client.get(f"/api/messages/{mid}/report").json()
    assert 3 in report["delivered_to"] or 5 in report["delivered_to"]
