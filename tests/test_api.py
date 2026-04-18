from fastapi.testclient import TestClient

from callcentre_bot.main import app


client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_session_flow_sales_turn() -> None:
    create = client.post("/v1/sessions")
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    turn = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={"text": "I want to buy family mobile plan", "channel": "voice"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["session_id"] == session_id
    assert data["intent"] == "sales"
    assert "Family Mobile Plan" in data["text"]


def test_negative_sentiment_escalates_after_threshold() -> None:
    create = client.post("/v1/sessions")
    session_id = create.json()["session_id"]

    payload = {"text": "I am upset and this is terrible", "channel": "voice"}
    first = client.post(f"/v1/sessions/{session_id}/turns", json=payload)
    second = client.post(f"/v1/sessions/{session_id}/turns", json=payload)
    third = client.post(f"/v1/sessions/{session_id}/turns", json=payload)

    assert first.json()["escalate_to_human"] is False
    assert second.json()["escalate_to_human"] is False
    assert third.json()["escalate_to_human"] is True
