"""End-to-end HTTP tests: shared topics per building, voting window, and its settings."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin
from tests.helpers.platform_accounts import SEED_PASSWORD

client = TestClient(app)


def _login(email: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": SEED_PASSWORD})
    assert response.status_code == 200, response.text


def _topic_body(title: str, **extra) -> dict:
    return {
        "title": title,
        "description": "Detalle del tema.",
        "category_key": "maintenance",
        "attachment_name": "",
        "decision": "¿Lo aprobamos?",
        "priority_id": 2,
        **extra,
    }


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def test_committee_and_client_of_the_same_building_see_the_same_topics() -> None:
    _login("comite@demo.tucomite.local")
    created = client.post("/api/v1/topics", json=_topic_body("Tema compartido"))
    assert created.status_code == 201, created.text
    topic_id = created.json()["id"]
    committee_client_id = created.json()["client_id"]
    assert committee_client_id
    committee_ids = {item["id"] for item in client.get("/api/v1/topics").json()["items"]}

    login_as_demo_admin(client)
    owner_listing = client.get("/api/v1/topics")
    assert owner_listing.status_code == 200
    owner_ids = {item["id"] for item in owner_listing.json()["items"]}

    assert topic_id in committee_ids
    assert topic_id in owner_ids
    assert owner_ids == committee_ids
    shared = next(item for item in owner_listing.json()["items"] if item["id"] == topic_id)
    assert shared["client_id"] == committee_client_id


def test_topic_created_by_the_client_is_visible_to_the_committee() -> None:
    login_as_demo_admin(client)
    created = client.post("/api/v1/topics", json=_topic_body("Tema del dueño"))
    assert created.status_code == 201, created.text
    topic_id = created.json()["id"]

    _login("comite2@demo.tucomite.local")
    listing = client.get("/api/v1/topics")

    assert topic_id in {item["id"] for item in listing.json()["items"]}


def test_voting_window_dates_are_stored_and_returned() -> None:
    login_as_demo_admin(client)
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    ends = starts + timedelta(days=2)

    created = client.post(
        "/api/v1/topics",
        json=_topic_body("Con ventana", voting_starts_at=_iso(starts), voting_ends_at=_iso(ends)),
    )

    assert created.status_code == 201, created.text
    assert datetime.fromisoformat(created.json()["voting_starts_at"]) == starts
    assert datetime.fromisoformat(created.json()["voting_ends_at"]) == ends
    listed = next(
        item for item in client.get("/api/v1/topics").json()["items"] if item["id"] == created.json()["id"]
    )
    # MySQL DATETIME keeps whole seconds.
    assert abs(datetime.fromisoformat(listed["voting_starts_at"]) - starts) < timedelta(seconds=1)
    assert abs(datetime.fromisoformat(listed["voting_ends_at"]) - ends) < timedelta(seconds=1)


def test_end_before_start_is_rejected() -> None:
    login_as_demo_admin(client)
    now = datetime.now(timezone.utc)

    response = client.post(
        "/api/v1/topics",
        json=_topic_body(
            "Ventana mala",
            voting_starts_at=_iso(now + timedelta(days=2)),
            voting_ends_at=_iso(now + timedelta(days=1)),
        ),
    )

    assert response.status_code == 422


def test_vote_outside_the_window_is_rejected_and_inside_is_accepted() -> None:
    _login("comite@demo.tucomite.local")
    now = datetime.now(timezone.utc)
    future = client.post(
        "/api/v1/topics",
        json=_topic_body(
            "Aún no abre",
            voting_starts_at=_iso(now + timedelta(days=1)),
            voting_ends_at=_iso(now + timedelta(days=2)),
        ),
    )
    ended = client.post(
        "/api/v1/topics",
        json=_topic_body(
            "Ya cerró",
            voting_starts_at=_iso(now - timedelta(days=2)),
            voting_ends_at=_iso(now - timedelta(days=1)),
        ),
    )
    open_now = client.post(
        "/api/v1/topics",
        json=_topic_body(
            "Abierta",
            voting_starts_at=_iso(now - timedelta(hours=1)),
            voting_ends_at=_iso(now + timedelta(hours=1)),
        ),
    )
    assert future.status_code == ended.status_code == open_now.status_code == 201

    early = client.post(f"/api/v1/topics/{future.json()['id']}/votes", json={"choice": "yes"})
    late = client.post(f"/api/v1/topics/{ended.json()['id']}/votes", json={"choice": "yes"})
    fine = client.post(f"/api/v1/topics/{open_now.json()['id']}/votes", json={"choice": "yes"})

    assert early.status_code == 409
    assert early.json()["detail"] == "Voting has not started yet."
    assert late.status_code == 409
    assert late.json()["detail"] == "Voting has ended."
    assert fine.status_code == 200, fine.text


def test_vote_window_settings_default_update_and_apply_to_new_topics() -> None:
    login_as_demo_admin(client)
    original = client.get("/api/v1/building-settings/vote-window")
    assert original.status_code == 200, original.text
    assert set(original.json()) == {"high_hours", "medium_hours", "low_hours"}

    try:
        saved = client.put(
            "/api/v1/building-settings/vote-window",
            json={"high_hours": 5, "medium_hours": 30, "low_hours": 200},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json() == {"high_hours": 5, "medium_hours": 30, "low_hours": 200}
        assert client.get("/api/v1/building-settings/vote-window").json() == saved.json()

        created = client.post("/api/v1/topics", json=_topic_body("Urgente", priority_id=1))
        assert created.status_code == 201, created.text
        starts = datetime.fromisoformat(created.json()["voting_starts_at"])
        ends = datetime.fromisoformat(created.json()["voting_ends_at"])
        assert ends - starts == timedelta(hours=5)
    finally:
        client.put(
            "/api/v1/building-settings/vote-window",
            json={
                "high_hours": original.json()["high_hours"],
                "medium_hours": original.json()["medium_hours"],
                "low_hours": original.json()["low_hours"],
            },
        )


def test_vote_window_settings_reject_invalid_hours() -> None:
    login_as_demo_admin(client)

    response = client.put(
        "/api/v1/building-settings/vote-window",
        json={"high_hours": 0, "medium_hours": 72, "low_hours": 168},
    )

    assert response.status_code == 422


def test_residents_cannot_change_vote_window_settings() -> None:
    _login("residente@demo.tucomite.local")

    read = client.get("/api/v1/building-settings/vote-window")
    write = client.put(
        "/api/v1/building-settings/vote-window",
        json={"high_hours": 1, "medium_hours": 1, "low_hours": 1},
    )

    assert read.status_code == 200
    assert write.status_code == 403
