"""Integration tests for task API routes — Phase 3."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.db.task import Task


@pytest.mark.asyncio
async def test_list_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/tasks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_and_get_task(client: AsyncClient, auth_headers):
    payload = {
        "title": "Write Phase 3 report",
        "priority": "high",
        "project": "chief-of-staff",
        "tags": ["reporting"],
    }
    resp = await client.post("/api/v1/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["title"] == "Write Phase 3 report"
    assert created["priority"] == "high"
    assert created["status"] == "pending"

    resp = await client.get(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_invalid_priority(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/v1/tasks", json={"title": "x", "priority": "banana"}, headers=auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_filters_by_status(client: AsyncClient, auth_headers):
    await client.post("/api/v1/tasks", json={"title": "Pending one"}, headers=auth_headers)
    created = (await client.post(
        "/api/v1/tasks", json={"title": "Done one"}, headers=auth_headers
    )).json()
    await client.post(f"/api/v1/tasks/{created['id']}/complete", headers=auth_headers)

    resp = await client.get("/api/v1/tasks?status=pending", headers=auth_headers)
    titles = [t["title"] for t in resp.json()["items"]]
    assert "Pending one" in titles
    assert "Done one" not in titles

    resp = await client.get("/api/v1/tasks?status=completed", headers=auth_headers)
    titles = [t["title"] for t in resp.json()["items"]]
    assert "Done one" in titles


@pytest.mark.asyncio
async def test_patch_task(client: AsyncClient, auth_headers):
    created = (await client.post(
        "/api/v1/tasks", json={"title": "Adjust me"}, headers=auth_headers
    )).json()

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"priority": "urgent", "status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["priority"] == "urgent"
    assert updated["status"] == "in_progress"


@pytest.mark.asyncio
async def test_patch_invalid_status(client: AsyncClient, auth_headers):
    created = (await client.post(
        "/api/v1/tasks", json={"title": "x"}, headers=auth_headers
    )).json()
    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}", json={"status": "vaporized"}, headers=auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_complete_sets_completed_at(client: AsyncClient, auth_headers):
    created = (await client.post(
        "/api/v1/tasks", json={"title": "Finish me"}, headers=auth_headers
    )).json()
    resp = await client.post(f"/api/v1/tasks/{created['id']}/complete", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_delete_cancels(client: AsyncClient, auth_headers):
    created = (await client.post(
        "/api/v1/tasks", json={"title": "Remove me"}, headers=auth_headers
    )).json()
    resp = await client.delete(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_task_not_found(client: AsyncClient, auth_headers):
    resp = await client.get(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_overdue_reminders_flow(client: AsyncClient, auth_headers, db_session, test_user):
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.add(Task(user_id=test_user.id, title="Overdue A", due_date=past))
    db_session.add(Task(user_id=test_user.id, title="Not yet due", due_date=future))
    db_session.add(Task(user_id=test_user.id, title="No due date"))
    await db_session.commit()

    # First read without marking
    resp = await client.get("/api/v1/tasks/overdue", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Overdue A"

    # Mark reminded — second call returns nothing
    resp = await client.get("/api/v1/tasks/overdue?mark_reminded=true", headers=auth_headers)
    assert resp.json()["total"] == 1
    resp = await client.get("/api/v1/tasks/overdue", headers=auth_headers)
    assert resp.json()["total"] == 0
