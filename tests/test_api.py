from fastapi.testclient import TestClient
from geolens.app import app


def test_health_does_not_require_model():
    with TestClient(app) as client:
        assert client.get('/healthz').json()['status'] == 'alive'


def test_invalid_radius_is_rejected_before_inference():
    with TestClient(app) as client:
        assert client.post('/v1/recommend', json={'question':'run near Powai', 'radius_km':999}).status_code == 422


def test_missing_model_does_not_produce_fictional_answer(monkeypatch):
    from geolens.app import model
    async def unavailable():
        return False
    monkeypatch.setattr(model,'ready',unavailable)
    with TestClient(app) as client:
        response = client.post('/v1/recommend', json={'question':'run near Powai'})
        assert response.status_code == 503
        assert response.json()['detail']['code'] == 'model_unavailable'
