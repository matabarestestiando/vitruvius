import json
import pytest
from app.db import Record, Chunk, Message
from app.grounding import (
    GroundedAnswer,
    validate_evidence,
    library_documents,
    ABSTENTION,
)

QUOTE = "Synthetic fixture: Project Meridian uses PostgreSQL for durable storage."


def source(db, expert, session, author=None):
    d = Record(
        kind="context",
        data={
            "title": "SYNTHETIC TEST FIXTURE — NOT REAL LITERATURE",
            "status": "ready",
            "scope": "GLOBAL",
            "expert_ids": [],
            "session_id": session.id,
            "project_id": session.data["project_id"],
            "board_id": session.data["board_id"],
            "expires_at": None,
            "permanent_consent": True,
            "source": {
                "author": author or expert.data["name"],
                "reviewed_by_owner": True,
                "kind": "author_work",
            },
        },
    )
    db.add(d)
    db.flush()
    c = Chunk(document_id=d.id, text=QUOTE, page=1, embedding=None)
    db.add(c)
    db.commit()
    return d, c


def answer(chunk, quote=QUOTE, text="The synthetic project uses PostgreSQL."):
    return {
        "claims": [
            {
                "text": text,
                "kind": "source",
                "evidence": [{"chunk_id": chunk, "quote": quote}],
            }
        ]
    }


def test_unknown_ids_and_fabricated_quotes_are_rejected():
    sources = [
        {
            "chunk_id": "known",
            "document_id": "primary",
            "text": QUOTE,
            "title": "Synthetic fixture",
            "page": 1,
        }
    ]
    for value in (
        answer("invented"),
        answer("known", "This fabricated quotation is absent."),
    ):
        with pytest.raises(ValueError):
            validate_evidence(
                GroundedAnswer.model_validate(value), sources, {"primary"}
            )
    with pytest.raises(ValueError):
        validate_evidence(
            GroundedAnswer.model_validate(answer("known")), sources, {"other"}
        )
    assert (
        validate_evidence(
            GroundedAnswer.model_validate(answer("known")), sources, {"primary"}
        )[0]["quote"]
        == QUOTE
    )


@pytest.mark.asyncio
async def test_empty_library_never_calls_model(db, workspace):
    from app.board import BoardRunner

    _, s, cat = workspace
    session = db.get(Record, s["id"])
    experts = [db.get(Record, e["id"]) for e in cat["expert"]]
    runner = BoardRunner(db, session, experts, client=object())

    async def forbidden(*args, **kwargs):
        raise AssertionError("No model inference should occur without a foundation")

    runner.complete = forbidden
    r = await runner.graph(3).ainvoke(
        {
            "transcript": [
                {"speaker": "Propietario", "content": "Give a technical opinion"}
            ],
            "turns": 0,
            "done": False,
            "next_speaker": "",
            "summary": "",
        }
    )
    assert r["turns"] == 0 and "No se emitieron opiniones técnicas" in r["summary"]
    assert db.query(Message).filter(Message.speaker != "Moderador").count() == 0


@pytest.mark.asyncio
async def test_claim_without_semantic_support_is_not_published(db, workspace):
    from app.board import BoardRunner

    _, s, cat = workspace
    session = db.get(Record, s["id"])
    e = db.get(Record, cat["expert"][0]["id"])
    d, c = source(db, e, session)
    e.data = {**e.data, "primary_source_ids": [d.id]}
    db.commit()
    runner = BoardRunner(db, session, [e], client=object())

    async def fake(system, *args, **kwargs):
        if system.startswith("Eres el moderador"):
            return json.dumps({"next_speaker": e.id, "done": False})
        if system.startswith("Verifica"):
            return json.dumps({"accepted_claim_indices": []})
        return json.dumps(answer(c.id, text="The project uses MongoDB."))

    runner.complete = fake
    r = await runner.graph(1).ainvoke(
        {
            "transcript": [{"speaker": "Propietario", "content": "Project database"}],
            "turns": 0,
            "done": False,
            "next_speaker": "",
            "summary": "",
        }
    )
    assert r["transcript"][-1]["content"] == ABSTENTION
    expert_message = db.query(Message).filter(Message.speaker == e.data["name"]).one()
    assert not expert_message.citations and "MongoDB" not in expert_message.content


def test_library_requires_review_and_other_author_is_complementary(
    client, headers, workspace, db
):
    _, s, cat = workspace
    session = db.get(Record, s["id"])
    e = db.get(Record, cat["expert"][1]["id"])
    d, c = source(db, e, session, author="Different Synthetic Author")
    r = client.post(
        "/api/experts/" + e.id + "/sources",
        headers=headers,
        json={"document_ids": [d.id], "approved": True},
    )
    assert r.status_code == 422
    r = client.post(
        "/api/experts/" + e.id + "/sources",
        headers=headers,
        json={"document_ids": [d.id], "role": "complementary", "approved": True},
    )
    assert r.status_code == 200
    assert not library_documents(db, e, session, "primary")
    assert len(library_documents(db, e, session, "complementary")) == 1
    d.data = {**d.data, "expires_at": "2999-01-01T00:00:00+00:00"}
    db.commit()
    assert (
        client.post(
            "/api/experts/" + e.id + "/sources",
            headers=headers,
            json={"document_ids": [d.id], "role": "complementary", "approved": True},
        ).status_code
        == 422
    )


def test_official_reference_requires_provenance(client, headers, workspace):
    _, s, cat = workspace
    d = client.post(
        "/api/contexts",
        headers=headers,
        json={"session_id": s["id"], "title": "Synthetic source", "text": QUOTE},
    ).json()
    r = client.post(
        "/api/contexts/" + d["id"] + "/source",
        headers=headers,
        json={
            "kind": "official_documentation",
            "author": "Synthetic Documentation Team",
            "reviewed_by_owner": True,
        },
    )
    assert r.status_code == 422
    r = client.post(
        "/api/contexts/" + d["id"] + "/source",
        headers=headers,
        json={
            "kind": "official_documentation",
            "author": "Synthetic Documentation Team",
            "source_url": "https://docs.example.invalid/reference",
            "reviewed_by_owner": True,
        },
    )
    assert r.status_code == 200


def test_video_time_is_from_supplied_transcript_only():
    from app.grounding import video_timestamp

    source = {
        "source": {"medium": "video"},
        "text": "00:41\n" + QUOTE + "\n01:12\nAnother passage.",
    }
    assert video_timestamp(source, QUOTE) == "00:41"
    assert video_timestamp(source, "Invented quote") is None
    assert video_timestamp({**source, "source": {"medium": "text"}}, QUOTE) is None


@pytest.mark.asyncio
async def test_profile_discards_unsupported_points_without_publishing_them():
    from app.grounding import review_answer

    data = answer("known")
    data["claims"].append(
        {
            "text": "Unsupported interpretation",
            "kind": "inference",
            "evidence": [{"chunk_id": "known", "quote": QUOTE}],
        }
    )
    model = GroundedAnswer.model_validate(data)

    async def review(*args, **kwargs):
        return json.dumps({"accepted_claim_indices": [0]})

    sources = [
        {
            "chunk_id": "known",
            "document_id": "primary",
            "text": QUOTE,
            "title": "Synthetic fixture",
            "page": 1,
        }
    ]
    citations = await review_answer(
        review, model, sources, {"primary"}, allow_partial=True
    )
    assert (
        len(model.claims) == 1 and model.claims[0].text != "Unsupported interpretation"
    )
    assert all(c["claim_index"] == 0 for c in citations)


def test_author_matching_handles_accents_and_non_latin_names_without_empty_matches():
    from app.grounding import primary_author_matches
    from types import SimpleNamespace

    assert primary_author_matches(
        SimpleNamespace(data={"name": "Antonio Gulli"}), {"author": "Antonio Gullí"}
    )
    assert primary_author_matches(
        SimpleNamespace(data={"name": "张三"}), {"author": "张三"}
    )
    assert not primary_author_matches(
        SimpleNamespace(data={"name": "  "}), {"author": "Some other author"}
    )


@pytest.mark.asyncio
async def test_review_keeps_original_passages_and_claims_as_complete_records():
    from app.grounding import review_answer

    value = GroundedAnswer.model_validate(answer("first"))
    value.claims.append(value.claims[0].model_copy(deep=True))
    sources = [
        {
            "chunk_id": "first",
            "document_id": "primary",
            "text": QUOTE,
            "title": "Synthetic fixture",
        }
    ]

    async def fake(system, transcript, model=None, **kwargs):
        records = [json.loads(m["content"]) for m in transcript]
        assert any(
            r.get("chunk_id") == "first" and r.get("text") == QUOTE for r in records
        )
        assert {r["claim_index"] for r in records if "claim_index" in r} == {0, 1}
        return json.dumps({"accepted_claim_indices": [0, 1]})

    assert len(await review_answer(fake, value, sources, {"primary"})) == 2


def test_case_context_cannot_be_the_only_premise_for_professional_inference():
    sources = [
        {
            "chunk_id": "primary-chunk",
            "document_id": "primary",
            "text": QUOTE,
            "title": "Synthetic primary",
        },
        {
            "chunk_id": "case-chunk",
            "document_id": "case",
            "text": "The owner requires durable storage for current decisions.",
            "library_role": "provided_context",
            "title": "Synthetic case",
        },
    ]
    value = answer("primary-chunk")
    value["claims"].append(
        {
            "kind": "inference",
            "text": "A professional recommendation",
            "evidence": [{"chunk_id": "case-chunk", "quote": sources[1]["text"]}],
        }
    )
    with pytest.raises(ValueError, match="primary premise"):
        validate_evidence(GroundedAnswer.model_validate(value), sources, {"primary"})


@pytest.mark.asyncio
async def test_project_context_remains_visible_but_is_not_foundation(
    db, workspace, client, headers
):
    from app.board import BoardRunner

    _, s, cat = workspace
    session = db.get(Record, s["id"])
    e = db.get(Record, cat["expert"][0]["id"])
    d, c = source(db, e, session)
    e.data = {**e.data, "primary_source_ids": [d.id]}
    db.commit()
    case = "SYNTHETIC CASE: the owner requires durable storage for current decisions."
    client.post(
        "/api/contexts",
        headers=headers,
        json={
            "session_id": session.id,
            "title": "Synthetic case context",
            "text": case,
        },
    )
    observed = []

    async def fake(system, transcript, model=None, **kwargs):
        if system.startswith("Eres el moderador"):
            return json.dumps({"next_speaker": e.id, "done": False})
        if system.startswith("Verifica"):
            assert any("Current project database" in m["content"] for m in transcript)
            return json.dumps({"accepted_claim_indices": [0]})
        observed.append(system)
        assert case in system and "provided_context" in system
        return json.dumps(answer(c.id))

    runner = BoardRunner(db, session, [e], client=object())
    runner.complete = fake
    await runner.graph(1).ainvoke(
        {
            "transcript": [
                {"speaker": "Propietario", "content": "Current project database"}
            ],
            "turns": 0,
            "next_speaker": "",
            "done": False,
            "summary": "",
        }
    )
    assert observed
