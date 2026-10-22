import json


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_device_flow_lifecycle(client):
    # 1. TV requests device code
    code_res = client.post("/v1/auth/device/code", json={"client_id": "firetv-lounge-01"})
    assert code_res.status_code == 200
    code_data = code_res.json()
    device_code = code_data["device_code"]
    user_code = code_data["user_code"]
    assert code_data["interval"] == 5
    assert code_data["verification_uri"] == "/activate"

    # 2. TV polls before authorization -> authorization_pending
    pending_res = client.post("/v1/auth/device/token", json={"device_code": device_code})
    assert pending_res.status_code == 400
    assert pending_res.json()["error"]["message"] == "authorization_pending"

    # 3. User signs in on mobile/browser
    demo_login = client.post("/v1/auth/demo")
    assert demo_login.status_code == 200
    user_token = demo_login.json()["access_token"]

    # 4. User enters the 6-character user_code on /activate
    auth_res = client.post(
        "/v1/auth/device/authorize",
        headers=auth(user_token),
        json={"user_code": user_code},
    )
    assert auth_res.status_code == 200
    assert auth_res.json()["authorized"] is True

    # 5. TV polls again -> now authorized!
    token_res = client.post("/v1/auth/device/token", json={"device_code": device_code})
    assert token_res.status_code == 200
    tokens = token_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    tv_access_token = tokens["access_token"]
    tv_refresh_token = tokens["refresh_token"]

    # 6. TV accesses /v1/me with the access token
    me_res = client.get("/v1/me", headers=auth(tv_access_token))
    assert me_res.status_code == 200
    assert me_res.json()["household"]["id"] == tokens["household_id"]

    # 7. Device session cannot be re-polled once completed
    repoll = client.post("/v1/auth/device/token", json={"device_code": device_code})
    assert repoll.status_code == 400
    assert repoll.json()["error"]["code"] == "BAD_REQUEST"


def test_token_refresh_lifecycle(client):
    # Setup user
    login = client.post("/v1/auth/demo")
    assert login.status_code == 200
    demo_data = login.json()

    # Create device tokens
    code_res = client.post("/v1/auth/device/code", json={})
    user_code = code_res.json()["user_code"]
    device_code = code_res.json()["device_code"]

    client.post(
        "/v1/auth/device/authorize",
        headers=auth(demo_data["access_token"]),
        json={"user_code": user_code},
    )

    tokens = client.post("/v1/auth/device/token", json={"device_code": device_code}).json()
    refresh_token = tokens["refresh_token"]

    # Refresh
    refresh_res = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    # Verify new access token works
    me = client.get("/v1/me", headers=auth(new_tokens["access_token"]))
    assert me.status_code == 200

    # Invalid refresh token fails with 401
    bad_res = client.post("/v1/auth/refresh", json={"refresh_token": "invalid-token-here"})
    assert bad_res.status_code == 401


def test_sports_stream_endpoint(client):
    login = client.post("/v1/auth/demo")
    token = login.json()["access_token"]

    # Missing event returns 404
    missing = client.get("/v1/sports/events/non-existent-event/stream", headers=auth(token))
    assert missing.status_code == 404

    # Valid event returns streaming response
    with client.stream("GET", "/v1/sports/events/demo-football-001/stream?ticks=1&interval=0.01", headers=auth(token)) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Read the first event chunk
        first_chunk = next(response.iter_lines())
        assert "event: match_state" in first_chunk
