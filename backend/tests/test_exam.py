"""資格試験の単元：絞り込みをしない、出題範囲の網羅、試験日、S08 での確認。"""

import datetime as dt
import json

import httpx

from app.ai.demo import DemoAI
from app.ai.gemini import GeminiAI
from app.schemas import AIDay, AITask
from app.services.validator import ExamRule, validate_days
from tests.conftest import MEMBER, MENTOR
from tests.test_api import goal, plan_body

EXAM = "基本情報技術者試験"


def exam_goal(name=EXAM, exam_date=None) -> dict:
    return {"topic": name, "kind": "exam", "exam_date": exam_date}


def exam_plan(*extra_topics, exam_date="2027-01-22", **kw) -> dict:
    body = plan_body(start_date="2026-12-01", end_date="2027-01-29", hours_per_day=2, **kw)
    body["topics"] = [exam_goal(exam_date=exam_date), *[goal(t) for t in extra_topics]]
    return body


# ---------------------------------------------------------------- 単元の扱い
def test_exam_is_not_narrowed_down(client):
    r = client.get(f"/api/topics/checklist?topic={EXAM}&kind=exam", headers=MEMBER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["topic"] == EXAM and body["kind"] == "exam"
    assert len(body["areas"]) >= 6
    assert any("データベース" in a["name"] for a in body["areas"])
    assert body["areas_reviewed"] is False
    assert body["syllabus_url"]
    assert body["items"] == []  # 技術のチェックリストは出さない


def test_same_name_as_skill_would_be_narrowed(client):
    # 技術として入れると絞り込み、資格試験として入れるとそのまま
    assert client.get("/api/topics/checklist?topic=AWS", headers=MEMBER).status_code == 422
    r = client.get("/api/topics/checklist?topic=AWS 認定ソリューションアーキテクト&kind=exam", headers=MEMBER)
    assert r.status_code == 200 and r.json()["areas"]


def test_exam_areas_are_reused(client):
    a = client.get(f"/api/topics/checklist?topic={EXAM}&kind=exam", headers=MEMBER).json()
    b = client.get(f"/api/topics/checklist?topic={EXAM}&kind=exam", headers=MEMBER).json()
    assert a["areas"] == b["areas"]


# ---------------------------------------------------------------- プラン
def test_exam_plan_covers_all_areas_before_exam_date(client):
    r = client.post("/api/plans", json=exam_plan("パイソン"), headers=MEMBER)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["ai_note"]["check_passed"] is True, plan["ai_note"]["check_issues"]

    exam = plan["topics"][0]
    assert exam["kind"] == "exam" and exam["exam_date"] == "2027-01-22"
    area_names = {a["name"] for a in exam["areas"]}
    covered = {t["area"] for t in plan["tasks"] if t["area"]}
    assert area_names <= covered  # 全分野を網羅
    assert all(a["planned_hours"] > 0 for a in exam["areas"])

    exam_tasks = [t for t in plan["tasks"] if t["topic"] == EXAM and t["type"] != "buffer"]
    assert all(t["date"] <= "2027-01-22" for t in exam_tasks)  # 試験日より後に入れない
    titles = " ".join(t["title"] for t in exam_tasks if t["type"] == "exercise")
    assert "過去問" in titles and "模擬試験" in titles
    assert "試験日" in plan["ai_note"]["strategy"]
    assert any("確認前" in w for w in plan["warnings"])  # 出題範囲は育成担当の確認前

    # Python（技術）も入る
    assert any(t["topic"] == "Python" for t in plan["tasks"])


def test_exam_date_defaults_to_end_date_and_must_be_in_period(client):
    r = client.post("/api/plans", json=exam_plan(exam_date=None), headers=MEMBER)
    assert r.status_code == 201, r.text
    assert r.json()["topics"][0]["exam_date"] == "2027-01-29"
    r = client.post("/api/plans", json=exam_plan(exam_date="2027-03-01"), headers=MEMBER)
    assert r.status_code == 422


def test_exam_reschedule_keeps_exam_date(client):
    plan = client.post("/api/plans", json=exam_plan("パイソン"), headers=MEMBER).json()
    preview = client.post(
        f"/api/plans/{plan['id']}/reschedule/preview", json={"today": "2026-12-20"}, headers=MEMBER
    ).json()
    exam_materials = {m["id"] for m in plan["materials"] if m["topic"] == EXAM}
    late = [
        t
        for d in preview["days"]
        if d["date"] > "2027-01-22"
        for t in d["tasks"]
        if t["material_id"] in exam_materials and t["type"] != "buffer"
    ]
    assert late == []
    assert preview["check_passed"] is True, preview["check_issues"]
    assert any(t.get("area") for d in preview["days"] for t in d["tasks"])  # 分野名は残る


# ---------------------------------------------------------------- 確認の仕組み
def test_validator_exam_rules():
    d = dt.date
    rule = ExamRule(topic="試験", exam_date=d(2026, 12, 10), areas=["A", "B"], material_ids={1})
    days = [
        AIDay(date=d(2026, 12, 8), tasks=[AITask(type="learn", title="A", hours=1, material_id=1, area="A")]),
        AIDay(date=d(2026, 12, 11), tasks=[AITask(type="learn", title="x", hours=1, material_id=1)]),
    ]
    issues = validate_days(
        days,
        start=d(2026, 12, 1),
        end=d(2026, 12, 31),
        available=[d(2026, 12, 8), d(2026, 12, 11)],
        hours_per_day=3,
        exam_rules=[rule],
    )
    text = " ".join(issues)
    assert "B がスケジュールに入っていません" in text
    assert "試験日（2026-12-10）より後" in text
    assert "過去問演習・模擬試験" in text


def test_demo_ai_never_breaks_exam_rules_in_short_period(client):
    # 試験日まで短くても、全分野が入り試験日を越えない（時間は縮める）
    body = exam_plan(exam_date="2026-12-11")
    body["end_date"] = "2026-12-18"
    r = client.post("/api/plans", json=body, headers=MEMBER)
    assert r.status_code == 201, r.text
    assert r.json()["ai_note"]["check_passed"] is True, r.json()["ai_note"]["check_issues"]


# ---------------------------------------------------------------- S08
def test_mentor_reviews_exam_areas(client):
    client.get(f"/api/topics/checklist?topic={EXAM}&kind=exam", headers=MEMBER)
    assert client.get("/api/review/exam-areas", headers=MEMBER).status_code == 403
    pending = client.get("/api/review/exam-areas", headers=MENTOR).json()
    assert [p["topic"] for p in pending] == [EXAM]
    topic_id = pending[0]["topic_id"]
    members = client.get("/api/mentor/members", headers=MENTOR).json()
    assert members["pending_reviews"] >= 1

    new_areas = [
        {"name": "テクノロジ系", "description": "", "weight": 60, "est_hours": 40},
        {"name": "マネジメント系", "description": "", "weight": 15, "est_hours": 10},
        {"name": "ストラテジ系", "description": "", "weight": 25, "est_hours": 15},
    ]
    dup = client.put(
        f"/api/review/topics/{topic_id}/areas", json={"areas": new_areas + [new_areas[0]]}, headers=MENTOR
    )
    assert dup.status_code == 422
    r = client.put(
        f"/api/review/topics/{topic_id}/areas",
        json={"areas": new_areas, "syllabus_url": "https://www.ipa.go.jp/"},
        headers=MENTOR,
    )
    assert r.status_code == 200, r.text
    assert client.get("/api/review/exam-areas", headers=MENTOR).json() == []

    c = client.get(f"/api/topics/checklist?topic={EXAM}&kind=exam", headers=MEMBER).json()
    assert [a["name"] for a in c["areas"]] == ["テクノロジ系", "マネジメント系", "ストラテジ系"]
    assert c["areas_reviewed"] is True

    plan = client.post("/api/plans", json=exam_plan(), headers=MEMBER).json()
    assert {a["name"] for a in plan["topics"][0]["areas"]} == {
        "テクノロジ系",
        "マネジメント系",
        "ストラテジ系",
    }
    assert not any("確認前" in w for w in plan["warnings"])


# ---------------------------------------------------------------- AI
def test_demo_normalize_exam_is_never_too_broad():
    assert DemoAI().normalize_topic("AWS", "exam").too_broad is False
    assert DemoAI().normalize_topic("AWS").too_broad is True


def test_gemini_exam_areas():
    payload = {
        "areas": [{"name": f"分野{i}", "description": "", "weight": 20, "est_hours": 5} for i in range(5)],
        "syllabus_url": "https://www.ipa.go.jp/",
    }

    def handler(request: httpx.Request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert EXAM in prompt and "出題範囲" in prompt
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
        )

    out = GeminiAI("k", "m", client=httpx.Client(transport=httpx.MockTransport(handler))).exam_areas(EXAM)
    assert len(out.areas) == 5 and out.syllabus_url
