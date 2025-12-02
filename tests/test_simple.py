import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.app_orm import app

client = TestClient(app)

def test_health():
    """Базовый тест здоровья"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    print("✅ Health check passed")

def test_create_task():
    """Базовый тест создания задачи"""
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["title"] == "Test Task"
    print("✅ Task creation passed")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])