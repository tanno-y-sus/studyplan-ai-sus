from tests.conftest import MEMBER, MENTOR

PLAN = {
    "topic": "パイソン",
    "current_level": 2,
    "target_level": 4,
    "start_date": "2026-12-01",
    "end_date": "2026-12-19",
    "hours_per_day": 3,
}


def test_requires_login(client):
    assert client.get("/api/plans").status_code == 401


def test_full_flow(client):
    r = client.post("/api/plans", json=PLAN, headers=MEMBER)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["topic"] == "Python"  # 別名「パイソン」から正規化
    assert plan["status"] == "proposed"
    assert plan["ai_note"]["check_passed"] is True
    assert plan["tasks"] and plan["materials"]
    assert all(m["status"] == "approved" for m in plan["materials"])  # カタログ教材

    r = client.post(f"/api/plans/{plan['id']}/confirm", headers=MEMBER)
    assert r.json()["status"] == "active"

    first = plan["tasks"][0]
    r = client.patch(
        f"/api/tasks/{first['id']}",
        json={"status": "done", "actual_hours": 2.5, "memo": "OK"},
        headers=MEMBER,
    )
    assert r.json()["status"] == "done"

    preview = client.post(
        f"/api/plans/{plan['id']}/reschedule/preview", json={"today": "2026-12-03"}, headers=MEMBER
    ).json()
    assert preview["check_passed"] is True
    assert all(d["date"] >= "2026-12-03" for d in preview["days"])
    r = client.post(f"/api/plans/{plan['id']}/reschedule/apply", json=preview, headers=MEMBER)
    assert r.status_code == 200
    tasks = r.json()["tasks"]
    assert any(t["status"] == "done" for t in tasks)  # 完了済みは残る


def test_unknown_topic_uses_search_and_review(client):
    r = client.post(
        "/api/plans",
        json={**PLAN, "topic": "Kubernetes", "current_level": 1, "target_level": 3},
        headers=MEMBER,
    )
    assert r.status_code == 201, r.text
    plan = r.json()
    assert {m["status"] for m in plan["materials"]} == {"ai_pending"}
    assert any(m["type"] == "video" and "動画の長さ" in m["reference_basis"] for m in plan["materials"])

    assert client.get("/api/review/materials", headers=MEMBER).status_code == 403
    pending = client.get("/api/review/materials", headers=MENTOR).json()
    assert len(pending) == len(plan["materials"])
    for m in pending:
        client.post(f"/api/review/materials/{m['id']}/approve", json={"comment": "OK"}, headers=MENTOR)
    assert client.get("/api/review/materials", headers=MENTOR).json() == []
    usage = client.get("/api/usage", headers=MENTOR).json()
    assert any(u["provider"] == "demo" for u in usage)


def test_too_broad_and_non_it_topics(client):
    r = client.post("/api/plans", json={**PLAN, "topic": "AWS"}, headers=MEMBER)
    assert r.status_code == 422
    assert "AWS（EC2・VPC）" in r.json()["detail"]["suggestions"]
    r = client.post("/api/plans", json={**PLAN, "topic": "英語"}, headers=MEMBER)
    assert r.status_code == 422


def test_input_validation(client):
    r = client.post("/api/plans", json={**PLAN, "target_level": 1}, headers=MEMBER)
    assert r.status_code == 422
    r = client.post("/api/plans", json={**PLAN, "end_date": "2026-11-01"}, headers=MEMBER)
    assert r.status_code == 422


def test_other_member_cannot_see_plan(client):
    plan = client.post("/api/plans", json=PLAN, headers=MEMBER).json()
    assert client.get(f"/api/plans/{plan['id']}", headers={"X-User-Id": "2"}).status_code == 403
    assert client.get(f"/api/plans/{plan['id']}", headers=MENTOR).status_code == 200


def test_suggest_and_availability(client):
    assert client.get("/api/topics/suggest?q=ec2").json()[0]["name"] == "AWS（EC2・VPC）"
    a = client.get("/api/availability?start_date=2026-12-21&end_date=2027-01-08&hours_per_day=2").json()
    assert a["available_days"] == 11 and a["max_hours"] == 22  # 12/29〜1/3 と土日を除く
