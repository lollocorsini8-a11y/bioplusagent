from app.db import KnowledgeDoc, SessionLocal, init_db
from app.services import KNOWLEDGE_DIR, seed_knowledge


def test_seed_knowledge_updates_changed_source_files():
    init_db()
    with SessionLocal() as session:
        seed_knowledge(session)
    with SessionLocal.begin() as session:
        doc = session.query(KnowledgeDoc).filter_by(slug="acwr").one()
        doc.text = "contenuto obsoleto"

    with SessionLocal() as session:
        assert seed_knowledge(session) == 1

    raw = (KNOWLEDGE_DIR / "acwr.md").read_text(encoding="utf-8")
    head, _, body = raw.partition("\n\n")
    meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    with SessionLocal() as session:
        doc = session.query(KnowledgeDoc).filter_by(slug="acwr").one()
        assert doc.source == meta["source"].strip()
        assert doc.text == body.strip()
