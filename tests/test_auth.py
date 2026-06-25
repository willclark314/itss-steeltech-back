def test_login_success(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)
    assert len(data["token"]) > 0


def test_login_empty_credentials(client):
    resp = client.post("/api/auth/login", json={"username": "", "password": ""})
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "请输入账号和密码"


def test_login_wrong_password(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "工号或密码错误"


def test_login_user_not_found(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "123456"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "工号或密码错误"
