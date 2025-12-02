from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
import sys
from datetime import datetime, timedelta

# Правильно добавляем путь к app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.app_orm import app, get_db, Base, Task

# Тестовая база данных
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Создаем и очищаем таблицы перед каждым тестом"""
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    yield
    # Очищаем после теста
    Base.metadata.drop_all(bind=engine)


# Фикстуры для тестовых данных
@pytest.fixture
def sample_task_data():
    return {
        "title": "Test Task",
        "details": "Test task details",
        "is_done": False,
        "priority": 2,
        "due_date": "2025-12-31T23:59:59"
    }


@pytest.fixture
def created_task(sample_task_data):
    response = client.post("/tasks", json=sample_task_data)
    return response.json()


class TestHealthCheck:
    """Тесты для эндпоинта /health"""

    def test_health_check_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_correct_status(self):
        response = client.get("/health")
        data = response.json()
        assert data == {"status": "ok"}
        assert "status" in data
        assert data["status"] == "ok"


class TestCreateTask:
    """Тесты для создания задач (POST /tasks)"""

    def test_create_task_success(self, sample_task_data):
        response = client.post("/tasks", json=sample_task_data)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["title"] == sample_task_data["title"]
        assert data["details"] == sample_task_data["details"]
        assert data["is_done"] == sample_task_data["is_done"]
        assert data["priority"] == sample_task_data["priority"]
        assert data["due_date"] == sample_task_data["due_date"]
        assert "created_at" in data
        assert data["updated_at"] is None

        # Проверка формата created_at
        try:
            datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("created_at has invalid ISO format")

    def test_create_task_minimal_data(self):
        minimal_data = {"title": "Minimal task"}
        response = client.post("/tasks", json=minimal_data)
        assert response.status_code == 201

        data = response.json()
        assert data["title"] == "Minimal task"
        assert data["priority"] == 1  # default
        assert data["is_done"] == False  # default
        assert data["details"] is None  # default
        assert data["due_date"] is None  # default

    def test_create_task_short_title(self):
        response = client.post("/tasks", json={"title": "ab"})
        assert response.status_code == 422  # FastAPI validation error

    def test_create_task_invalid_priority_high(self):
        response = client.post("/tasks", json={
            "title": "Test task",
            "priority": 5
        })
        assert response.status_code == 422  # FastAPI validation error

    def test_create_task_invalid_priority_low(self):
        response = client.post("/tasks", json={
            "title": "Test task",
            "priority": 0
        })
        assert response.status_code == 422  # FastAPI validation error

    def test_create_task_invalid_date_format(self):
        response = client.post("/tasks", json={
            "title": "Test task",
            "due_date": "invalid-date-format"
        })
        assert response.status_code == 422  # FastAPI validation error

    def test_create_task_empty_title(self):
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 422  # FastAPI validation error


class TestGetTasks:
    """Тесты для получения списка задач (GET /tasks) с фильтрацией и сортировкой"""

    def test_get_tasks_empty(self):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_tasks_with_data(self, created_task):
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == created_task["title"]
        assert data[0]["id"] == created_task["id"]

    def test_get_tasks_filter_by_status_done(self):
        # Создаем выполненные и невыполненные задачи
        client.post("/tasks", json={"title": "Done task", "is_done": True})
        client.post("/tasks", json={"title": "Pending task", "is_done": False})

        # Фильтр выполненных
        response = client.get("/tasks?is_done=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["is_done"] == True
        assert data[0]["title"] == "Done task"

        # Фильтр невыполненных
        response = client.get("/tasks?is_done=false")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["is_done"] == False
        assert data[0]["title"] == "Pending task"

    def test_get_tasks_filter_by_priority(self):
        # Создаем задачи с разными приоритетами
        client.post("/tasks", json={"title": "High priority", "priority": 3})
        client.post("/tasks", json={"title": "Medium priority", "priority": 2})
        client.post("/tasks", json={"title": "Low priority", "priority": 1})

        # Фильтр высокого приоритета
        response = client.get("/tasks?priority=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["priority"] == 3
        assert data[0]["title"] == "High priority"

        # Фильтр среднего приоритета
        response = client.get("/tasks?priority=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["priority"] == 2
        assert data[0]["title"] == "Medium priority"

    def test_get_tasks_search_by_query(self):
        client.post("/tasks", json={"title": "Buy milk", "details": "Go to supermarket"})
        client.post("/tasks", json={"title": "Learn Python", "details": "Study programming"})
        client.post("/tasks", json={"title": "Read book", "details": "Science fiction"})

        # Поиск в title
        response = client.get("/tasks?q=milk")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "milk" in data[0]["title"].lower()

        # Поиск в details
        response = client.get("/tasks?q=programming")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "programming" in data[0]["details"].lower()

    def test_get_tasks_pagination(self):
        # Создаем несколько задач
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i + 1}"})

        # Первая страница
        response = client.get("/tasks?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Вторая страница
        response = client.get("/tasks?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_tasks_invalid_sort_parameter(self):
        response = client.get("/tasks?sort=invalid_field")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "sort" in data["detail"].lower()

    def test_get_tasks_invalid_order_parameter(self):
        response = client.get("/tasks?order=invalid_direction")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "order" in data["detail"].lower()


class TestGetTaskById:
    """Тесты для получения задачи по ID (GET /tasks/{id})"""

    def test_get_existing_task(self, created_task):
        task_id = created_task["id"]
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == task_id
        assert data["title"] == created_task["title"]
        assert data["priority"] == created_task["priority"]
        assert data["is_done"] == created_task["is_done"]

    def test_get_nonexistent_task(self):
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_task_invalid_id_string(self):
        response = client.get("/tasks/abc")
        assert response.status_code == 422  # FastAPI validation error

    def test_get_task_invalid_id_negative(self):
        response = client.get("/tasks/-1")
        assert response.status_code == 404  # FastAPI validation error


class TestUpdateTask:
    """Тесты для обновления задач (PUT /tasks/{id})"""

    def test_update_task_partial_success(self, created_task):
        task_id = created_task["id"]
        update_data = {
            "title": "Updated title",
            "is_done": True,
            "priority": 1
        }

        response = client.put(f"/tasks/{task_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == task_id
        assert data["title"] == "Updated title"
        assert data["is_done"] == True
        assert data["priority"] == 1
        assert data["updated_at"] is not None

        # Поля которые не обновлялись должны сохраниться
        assert data["details"] == created_task["details"]
        assert data["due_date"] == created_task["due_date"]

    def test_update_nonexistent_task(self):
        response = client.put("/tasks/9999", json={"title": "Updated"})
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_update_task_short_title(self, created_task):
        task_id = created_task["id"]
        response = client.put(f"/tasks/{task_id}", json={"title": "ab"})
        assert response.status_code == 422  # FastAPI validation error

    def test_update_task_invalid_priority(self, created_task):
        task_id = created_task["id"]
        response = client.put(f"/tasks/{task_id}", json={"priority": 5})
        assert response.status_code == 422  # FastAPI validation error


class TestDeleteTask:
    """Тесты для удаления задач (DELETE /tasks/{id})"""

    def test_delete_task_success(self, created_task):
        task_id = created_task["id"]

        # Удаляем задачу
        response = client.delete(f"/tasks/{task_id}")
        assert response.status_code == 204
        assert response.content == b''  # No content

        # Проверяем что задача удалена
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_task(self):
        response = client.delete("/tasks/9999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_delete_task_twice(self, created_task):
        task_id = created_task["id"]

        # Первое удаление
        response = client.delete(f"/tasks/{task_id}")
        assert response.status_code == 204

        # Второе удаление - должно вернуть 404
        response = client.delete(f"/tasks/{task_id}")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])