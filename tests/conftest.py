import os

os.environ["OWNER_TOKEN"] = "test-owner-token"
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from fastapi.testclient import TestClient
from app.db import Base, db_session
from app.main import app
from app.seed import seed


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        seed(session)
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[db_session] = override
    # Route tests override persistence; lifecycle/protocol are checked separately.
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def headers():
    return {"Authorization": "Bearer test-owner-token"}


@pytest.fixture
def workspace(client, headers):
    catalog = client.get("/api/catalog", headers=headers).json()
    project = client.post(
        "/api/projects", headers=headers, json={"name": "Test"}
    ).json()
    session = client.post(
        "/api/sessions",
        headers=headers,
        json={"project_id": project["id"], "board_id": catalog["board"][0]["id"]},
    ).json()
    return project, session, catalog
