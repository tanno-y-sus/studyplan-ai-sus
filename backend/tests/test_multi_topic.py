"""複数単元のプラン、できることのチェックリスト、実績の入力と「残り」の組み直し。"""

from app.models import TopicSkill
from app.services.skills import levels_from_checks
from tests.conftest import MEMBER
from tests.test_api import goal, plan_body


def _skills(*levels: int) -> list[TopicSkill]:
    return [TopicSkill(order=i, text=f"s{i}", level=lv) for i, lv in enumerate(levels)]


# ---------------------------------------------------------------- チェックリスト・レベル
def test_levels_from_checks():
    skills = _skills(1, 2, 2, 3, 4, 5)
    assert levels_from_checks(skills, [], ["s3"]) == (1, 3)  # 何もできない → 1
    assert levels_from_checks(skills, ["s0", "s1", "s2"], ["s4"]) == (2, 4)  # Lv2 まで全部できる
    assert levels_from_checks(skills, ["s0", "s1"], ["s5"]) == (1, 5)  # Lv2 の一部だけ → 1
    assert levels_from_checks(skills, ["s0", "s1", "s2", "s3"], ["s0"]) == (3, 3)  # 目標は現在より下げない
    assert levels_from_checks(skills, [], ["unknown"]) == (1, 2)  # 一覧にない文 → 現在＋1


def test_checklist_endpoint(client):
    assert client.get("/api/topics/checklist?topic=java").status_code == 401
    r = client.get("/api/topics/checklist?topic=java", headers=MEMBER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["topic"] == "Java"
    assert 5 <= len(body["items"]) <= 8
    levels = [i["level"] for i in body["items"]]
    assert levels == sorted(levels)  # 易しい順
    assert body["purpose_levels"]["basics"] < body["purpose_levels"]["work"]
    again = client.get("/api/topics/checklist?topic=Java", headers=MEMBER).json()
    assert again["items"] == body["items"]  # 保存したものを使い回す


def test_checklist_too_broad_topic(client):
    r = client.get("/api/topics/checklist?topic=AWS", headers=MEMBER)
    assert r.status_code == 422
    assert r.json()["detail"]["suggestions"]


# ---------------------------------------------------------------- 複数単元のプラン
def test_multi_topic_plan(client):
    items = client.get("/api/topics/checklist?topic=SQL", headers=MEMBER).json()["items"]
    sql = goal(
        "SQL", "basics", can_do=[items[0]["text"]], goals=[i["text"] for i in items if i["level"] <= 3]
    )
    body = plan_body("パイソン", start_date="2026-12-01", end_date="2027-01-29", hours_per_day=2)
    body["topics"].append(sql)
    r = client.post("/api/plans", json=body, headers=MEMBER)
    assert r.status_code == 201, r.text
    plan = r.json()

    assert plan["topic"] == "Python ＋ SQL"
    assert [t["name"] for t in plan["topics"]] == ["Python", "SQL"]
    sql_out = plan["topics"][1]
    assert sql_out["purpose_label"] == "基礎を知る" and sql_out["target_level"] == 3
    assert {m["topic"] for m in plan["materials"]} == {"Python", "SQL"}  # 両方の教材が入る
    assert plan["ai_note"]["check_passed"] is True
    assert {a["topic"] for a in plan["ai_note"]["topic_allocation"]} == {"Python", "SQL"}
    assert plan["ai_note"]["strategy"]
    task_topics = {t["topic"] for t in plan["tasks"] if t["type"] != "buffer"}
    assert {"Python", "SQL"} <= task_topics
    assert all(t["planned_hours"] > 0 for t in plan["topics"])

    summary = client.get("/api/plans", headers=MEMBER).json()[0]
    assert [t["name"] for t in summary["topics"]] == ["Python", "SQL"]


# ---------------------------------------------------------------- 実績の入力
def _plan_and_task(client):
    plan = client.post("/api/plans", json=plan_body(), headers=MEMBER).json()
    task = next(t for t in plan["tasks"] if t["type"] == "learn" and t["planned_hours"] >= 1)
    return plan, task


def _patch(client, task_id, body):
    r = client.patch(f"/api/tasks/{task_id}", json=body, headers=MEMBER)
    assert r.status_code == 200, r.text
    return r.json()


def _tasks(client, plan_id):
    return client.get(f"/api/plans/{plan_id}", headers=MEMBER).json()["tasks"]


def test_check_means_done_as_planned_and_uncheck_clears(client):
    plan, task = _plan_and_task(client)
    out = _patch(client, task["id"], {"status": "done"})
    assert out["task"]["status"] == "done" and out["task"]["actual_hours"] == task["planned_hours"]
    assert out["remainder"] is None
    out = _patch(client, task["id"], {"status": "todo"})
    assert out["task"]["status"] == "todo" and out["task"]["actual_hours"] is None


def test_actual_more_than_planned_completes(client):
    plan, task = _plan_and_task(client)
    out = _patch(client, task["id"], {"actual_hours": task["planned_hours"] + 1})
    assert out["task"]["status"] == "done"
    assert out["task"]["actual_hours"] == task["planned_hours"] + 1
    assert out["remainder"] is None and out["shortfall_hours"] == 0


def test_actual_less_than_planned_creates_remainder(client):
    plan, task = _plan_and_task(client)
    planned = task["planned_hours"]
    before = len(_tasks(client, plan["id"]))
    out = _patch(client, task["id"], {"actual_hours": planned - 0.5})
    assert out["task"]["status"] == "done"
    assert out["task"]["planned_hours"] == planned - 0.5  # 計画の合計は変えない
    assert out["shortfall_hours"] == 0.5
    rem = out["remainder"]
    assert rem["title"] == f"{task['title']}（残り）" and rem["planned_hours"] == 0.5
    assert rem["status"] == "todo" and rem["remainder_of_id"] == task["id"]
    assert len(_tasks(client, plan["id"])) == before + 1

    # 残りはリスケ案に入る
    preview = client.post(
        f"/api/plans/{plan['id']}/reschedule/preview", json={"today": "2026-12-03"}, headers=MEMBER
    ).json()
    assert any(t["title"] == rem["title"] for d in preview["days"] for t in d["tasks"])

    # 実績を入れ直すと「残り」は元に戻ってから計算し直す
    out = _patch(client, task["id"], {"actual_hours": planned})
    assert out["task"]["planned_hours"] == planned and out["remainder"] is None
    assert all(t["remainder_of_id"] != task["id"] for t in _tasks(client, plan["id"]))


def test_uncheck_merges_remainder_back(client):
    plan, task = _plan_and_task(client)
    planned = task["planned_hours"]
    _patch(client, task["id"], {"actual_hours": 0.25})
    out = _patch(client, task["id"], {"status": "todo"})
    assert out["task"]["planned_hours"] == planned and out["task"]["actual_hours"] is None
    assert len(_tasks(client, plan["id"])) == len(plan["tasks"])


def test_zero_actual_resets(client):
    plan, task = _plan_and_task(client)
    _patch(client, task["id"], {"status": "done"})
    out = _patch(client, task["id"], {"actual_hours": 0})
    assert out["task"]["status"] == "todo" and out["task"]["actual_hours"] is None
