"""テスト用の教材カタログ（Python・AWS（EC2・VPC）・SQL）を DB に入れる。

アプリには初期データを入れない（教材は検索と AI で探し、育成担当が承認したものがカタログになる）。
テストでは「カタログに教材がある単元」の動きを確かめるために使う。
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import LevelGuide, Material, MaterialSection, Topic, TopicAlias

CATALOG = Path(__file__).resolve().parent / "fixtures" / "catalog.json"


def load_catalog(db: Session, path: Path = CATALOG) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for t in data["topics"]:
        topic = Topic(name=t["name"], category=t["category"], source="catalog")
        topic.aliases = [TopicAlias(alias=a) for a in t.get("aliases", [])]
        topic.level_guides = [LevelGuide(level=int(k), description=v) for k, v in t["level_guides"].items()]
        for m in t["materials"]:
            sections = m.get("sections", [])
            material = Material(
                title=m["title"],
                url=m.get("url"),
                type=m["type"],
                source="catalog",
                status="approved",
                reference_hours=m.get("reference_hours", sum(s["est_hours"] for s in sections)),
                reference_basis=m.get("reference_basis", ""),
                url_check="カタログ登録済み",
            )
            material.sections = [MaterialSection(order=i, **s) for i, s in enumerate(sections)]
            topic.materials.append(material)
        db.add(topic)
    db.commit()
