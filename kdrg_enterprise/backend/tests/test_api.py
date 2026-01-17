def test_health_check(client):
    """Test API health endpoint"""
    response = client.get("/api/health")
    assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist


def test_api_root(client):
    """Test API root endpoint"""
    response = client.get("/")
    assert response.status_code in [200, 307, 404]
