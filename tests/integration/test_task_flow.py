"""Acceptance scenario 1 against a running Agent Relay API and real database."""

from __future__ import annotations

import os
import uuid

import httpx


BASE_URL = os.getenv("RELAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def register(client: httpx.Client, name: str) -> tuple[dict, dict[str, str]]:
    response = client.post("/api/v1/agents", json={"name": name})
    assert response.status_code == 201, response.text
    agent = response.json()
    return agent, {"Authorization": f"Bearer {agent['token']}"}


def test_two_agents_exchange_a_task_and_result() -> None:
    suffix = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        assert client.get("/ready").json() == {"status": "ready"}
        sender, sender_headers = register(client, f"sender-{suffix}")
        recipient, recipient_headers = register(client, f"worker-{suffix}")

        sent = client.post(
            "/api/v1/tasks",
            headers={**sender_headers, "Idempotency-Key": f"homework-{suffix}"},
            json={"to": recipient["agent_id"], "input": "hello agent relay"},
        )
        assert sent.status_code == 201, sent.text
        task_id = sent.json()["task_id"]
        assert sent.json()["status"] == "queued"

        claimed = client.post(
            "/api/v1/tasks/claim",
            headers=recipient_headers,
            json={"worker_id": f"integration-worker-{suffix}", "wait_seconds": 0},
        )
        assert claimed.status_code == 200, claimed.text
        assert claimed.json()["task_id"] == task_id

        completed = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            headers=recipient_headers,
            json={"claim_token": claimed.json()["claim_token"], "output": "HELLO AGENT RELAY"},
        )
        assert completed.status_code == 200, completed.text

        result = client.get(f"/api/v1/tasks/{task_id}", headers=sender_headers)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "completed"
        assert result.json()["output"] == "HELLO AGENT RELAY"
        assert result.json()["from"] == sender["agent_id"]
