def test_health_check_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
