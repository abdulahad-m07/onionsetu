# backend/tests/test_health.py
import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "OnionSetu" in data["app_name"]
