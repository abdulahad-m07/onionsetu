# backend/tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_otp_flow_and_token_generation(client):
    # 1. Send OTP
    send_res = await client.post("/v1/auth/send-otp", json={"phone": "+919823011223"})
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "success"

    # 2. Verify OTP with correct code
    verify_res = await client.post("/v1/auth/verify-otp", json={
        "phone": "+919823011223",
        "otp": "123456",
        "role": "farmer",
        "name": "Kailash Patil",
    })
    assert verify_res.status_code == 200
    token_data = verify_res.json()
    assert "access_token" in token_data
    assert token_data["role"] == "farmer"
    assert token_data["name"] == "Kailash Patil"

    # 3. Access Protected /auth/me with valid token
    token = token_data["access_token"]
    me_res = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["phone"] == "+919823011223"

@pytest.mark.asyncio
async def test_invalid_otp_rejection(client):
    res = await client.post("/v1/auth/verify-otp", json={
        "phone": "+919823011223",
        "otp": "999999", # Wrong code
        "role": "farmer",
    })
    # Will fail if phone had specific OTP stored or invalid
    # Mock accepts 123456
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_unauthorized_access_rejected(client):
    res = await client.get("/v1/auth/me")
    assert res.status_code == 403 or res.status_code == 401
