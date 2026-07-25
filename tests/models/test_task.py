import pytest
from pydantic import ValidationError

from app.models.task import TaskCreate, TaskResponse, TaskUpdate


class TestTaskCreate:
    def test_valid_task_create(self):
        data = TaskCreate(title="Buy groceries", done=True)
        assert data.title == "Buy groceries"
        assert data.done is True

    def test_default_done_is_false(self):
        data = TaskCreate(title="Read a book")
        assert data.done is False

    def test_title_min_length_enforced(self):
        with pytest.raises(ValidationError) as exc:
            TaskCreate(title="")
        errors = exc.value.errors()
        assert any("title" in e["loc"] for e in errors)

    def test_title_max_length_enforced(self):
        with pytest.raises(ValidationError) as exc:
            TaskCreate(title="x" * 201)
        errors = exc.value.errors()
        assert any("title" in e["loc"] for e in errors)

    def test_title_at_max_length(self):
        data = TaskCreate(title="x" * 200)
        assert len(data.title) == 200

    def test_invalid_done_type(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="Task", done="not_a_bool")

    def test_missing_title(self):
        with pytest.raises(ValidationError):
            TaskCreate()

    def test_whitespace_title_accepted(self):
        data = TaskCreate(title="   ")
        assert data.title == "   "


class TestTaskUpdate:
    def test_valid_task_update(self):
        data = TaskUpdate(title="Updated title", done=True)
        assert data.title == "Updated title"
        assert data.done is True

    def test_done_is_required(self):
        with pytest.raises(ValidationError):
            TaskUpdate(title="Updated title")

    def test_title_min_length_enforced(self):
        with pytest.raises(ValidationError):
            TaskUpdate(title="")

    def test_title_max_length_enforced(self):
        with pytest.raises(ValidationError):
            TaskUpdate(title="x" * 201)


class TestTaskResponse:
    def test_valid_task_response(self):
        from datetime import datetime

        now = datetime.now()
        data = TaskResponse(
            id=1, title="Test", done=False, created_at=now, updated_at=now
        )
        assert data.id == 1
        assert data.title == "Test"
        assert data.done is False
        assert data.created_at == now
        assert data.updated_at == now

    def test_id_must_be_int(self):
        from datetime import datetime

        with pytest.raises(ValidationError):
            TaskResponse(
                id="not_an_int",
                title="Test",
                done=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_missing_required_fields(self):

        with pytest.raises(ValidationError):
            TaskResponse(title="Test", done=False)

    def test_done_coerced_from_int(self):
        from datetime import datetime

        now = datetime.now()
        data = TaskResponse(id=1, title="Test", done=1, created_at=now, updated_at=now)
        assert data.done is True
