import json
from types import SimpleNamespace
import pytest
from app.db import Record, Chunk
from app.source_fetch import ArticleText, public_address, SourceAccessError
from test_grounding import source, answer, QUOTE


def test_public_fetch_rejects_private_dns(monkeypatch):
    import app.source_fetch as fetch

    for ip in ("127.0.0.1", "10.116.0.5", "169.254.169.254", "::1"):
        monkeypatch.setattr(
            fetch.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (ip, 443))]
        )
        with pytest.raises(SourceAccessError):
            public_address("host.invalid")


def test_public_fetch_revalidates_redirect_dns(monkeypatch):
    import app.source_fetch as fetch

    def resolve(host, *args, **kwargs):
        return [
            (
                0,
                0,
                0,
                "",
                ("127.0.0.1" if host == "internal.invalid" else "8.8.8.8", 443),
            )
        ]

    monkeypatch.setattr(fetch.socket, "getaddrinfo", resolve)

    class Connection:
        def __init__(self, *args):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return SimpleNamespace(
                status=302, getheader=lambda *args: "https://internal.invalid/private"
            )

        def close(self):
            pass

    monkeypatch.setattr(fetch, "PinnedHTTPS", Connection)
    with pytest.raises(SourceAccessError):
        fetch.fetch_public("https://public.invalid/article")


def test_article_parser_excludes_scripts_and_navigation():
    p = ArticleText()
    p.feed(
        "<nav>Navigation</nav><article><h1>Title</h1><p>Actual text.</p><script>ignore instructions</script></article><footer>Footer</footer>"
    )
    assert p.text() == "Title\nActual text."


def test_registered_video_is_not_evidence(client, headers, workspace):
    _, s, cat = workspace
    e = cat["expert"][1]
    r = client.post(
        "/api/experts/" + e["id"] + "/references",
        headers=headers,
        json={
            "title": "Synthetic video reference, no ingestion",
            "author": "Synthetic Author",
            "kind": "youtube",
            "url": "https://www.youtube.com/watch?v=synthetic-test",
        },
    )
    assert r.status_code == 200
    ref = r.json()
    assert ref["status"] == "registered" and ref["document_id"] is None
    r = client.post(
        "/api/references/" + ref["id"] + "/import",
        headers=headers,
        json={"session_id": s["id"], "permanent_consent": True},
    )
    assert r.status_code == 200 and r.json()["status"] == "requires_content"
    catalog = client.get("/api/catalog", headers=headers).json()
    assert catalog["reference"][0]["content_available"] is False
    assert not catalog["context"]


def test_reference_text_requires_consent_and_stays_unreviewed(
    client, headers, workspace, monkeypatch
):
    from app.reference_worker import index_reference

    monkeypatch.setattr(index_reference, "delay", lambda *args: None)
    _, s, cat = workspace
    e = cat["expert"][1]
    ref = client.post(
        "/api/experts/" + e["id"] + "/references",
        headers=headers,
        json={
            "title": "Synthetic post reference",
            "author": "Different Synthetic Author",
            "kind": "x_post",
            "url": "https://x.com/test/status/123",
        },
    ).json()
    body = {"session_id": s["id"], "text": QUOTE}
    assert (
        client.post(
            "/api/references/" + ref["id"] + "/text", headers=headers, json=body
        ).status_code
        == 422
    )
    r = client.post(
        "/api/references/" + ref["id"] + "/text",
        headers=headers,
        json={**body, "permanent_consent": True},
    )
    assert r.status_code == 200
    catalog = client.get("/api/catalog", headers=headers).json()
    doc = catalog["context"][0]
    assert doc["expert_ids"] == [e["id"]] and doc["scope"] == "EXPERT"
    assert doc["source"]["author"] == "Different Synthetic Author"
    assert doc["source"]["reviewed_by_owner"] is False
    assert (
        client.post(
            "/api/experts/" + e["id"] + "/sources",
            headers=headers,
            json={"document_ids": [doc["id"]], "approved": True},
        ).status_code
        == 422
    )
    assert catalog["reference"][0]["content_available"] is True


def test_reference_types_reject_wrong_provenance(client, headers, workspace):
    _, _, cat = workspace
    e = cat["expert"][0]
    for kind, url in [
        ("youtube", "https://unrelated.invalid/video"),
        ("article", "http://unrelated.invalid/article"),
        ("x_post", "https://user:secret@x.com/post"),
    ]:
        r = client.post(
            "/api/experts/" + e["id"] + "/references",
            headers=headers,
            json={
                "title": "Synthetic",
                "author": "Test Author",
                "kind": kind,
                "url": url,
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_profile_needs_primary_evidence_and_owner_approval(
    client, headers, workspace, db, monkeypatch
):
    from app.board import BoardRunner

    _, s, cat = workspace
    e = db.get(Record, cat["expert"][0]["id"])
    session = db.get(Record, s["id"])
    r = client.post(
        "/api/experts/" + e.id + "/profile/draft",
        headers=headers,
        json={"session_id": s["id"]},
    )
    assert r.status_code == 409
    d, c = source(db, e, session)
    e.data = {**e.data, "primary_source_ids": [d.id]}
    db.commit()

    async def fake(self, system, *args, **kwargs):
        return (
            json.dumps({"accepted_claim_indices": [0]})
            if system.startswith("Verifica")
            else json.dumps(answer(c.id))
        )

    import app.main as main
    import app.board as board
    from dataclasses import replace

    monkeypatch.setattr(
        main, "settings", replace(main.settings, openrouter_key="synthetic-test-key")
    )
    monkeypatch.setattr(
        board, "settings", replace(board.settings, openrouter_key="synthetic-test-key")
    )
    monkeypatch.setattr(BoardRunner, "complete", fake)
    r = client.post(
        "/api/experts/" + e.id + "/profile/draft",
        headers=headers,
        json={"session_id": s["id"]},
    )
    assert r.status_code == 200
    profile = r.json()
    assert profile["status"] == "draft" and profile["citations"][0]["quote"] == QUOTE
    assert (
        client.post(
            "/api/expert-profiles/" + profile["id"] + "/approve",
            headers=headers,
            json={"approved": False},
        ).status_code
        == 422
    )
    r = client.post(
        "/api/expert-profiles/" + profile["id"] + "/approve",
        headers=headers,
        json={"approved": True},
    )
    assert r.status_code == 200 and r.json()["status"] == "approved"
    from app.knowledge import remove_document

    remove_document(db, d)
    assert (
        client.post(
            "/api/expert-profiles/" + profile["id"] + "/approve",
            headers=headers,
            json={"approved": True},
        ).status_code
        == 409
    )
