import pytest
from datetime import datetime, timedelta, timezone
from src.models.entities import Task, UserStory, Sprint, WorkFront, TaskStatus

@pytest.fixture
def timezone_br():
    """Fixture para timezone de Brasília (UTC-3)"""
    return timezone(timedelta(hours=-3))

@pytest.fixture
def sprint_dates(timezone_br):
    """Fixture para datas da sprint"""
    start_date = datetime(2024, 3, 18, 9, 0, tzinfo=timezone_br)
    end_date = datetime(2024, 3, 29, 17, 0, tzinfo=timezone_br)
    return start_date, end_date

def test_task_creation(sprint_dates):
    """Testa a criação de uma task"""
    start_date, end_date = sprint_dates
    
    task = Task(
        id="1",
        title="[BE] Task Test",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,
        assignee="backend1@example.com",
        start_date=start_date,
        end_date=end_date,
        azure_end_date=end_date,
        parent_user_story_id="US-1"
    )
    
    assert task.id == "1"
    assert task.title == "[BE] Task Test"
    assert task.description == "Test task"
    assert task.work_front == WorkFront.BACKEND
    assert task.estimated_hours == 4.0
    assert task.assignee == "backend1@example.com"
    assert task.start_date == start_date
    assert task.end_date == end_date
    assert task.azure_end_date == end_date
    assert task.parent_user_story_id == "US-1"
    assert task.status == TaskStatus.PENDING

def test_task_validation():
    """Testa a validação de uma task"""
    # Testa criação com valores válidos
    task = Task(
        id="1",
        title="[BE] Task Test",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,
        assignee="backend1@example.com",
        start_date=datetime(2024, 3, 18, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 18, 15, 0, tzinfo=timezone(timedelta(hours=-3))),
        azure_end_date=datetime(2024, 3, 18, 17, 0, tzinfo=timezone(timedelta(hours=-3))),
        parent_user_story_id="US-1"
    )
    assert task is not None

def test_user_story_creation():
    """Testa a criação de uma user story"""
    us = UserStory(
        id="US-1",
        title="Test US",
        description="Test user story",
        assignee=None,
        start_date=None,
        end_date=None,
        story_points=5.0,
        tasks=[]
    )
    
    assert us.id == "US-1"
    assert us.title == "Test US"
    assert us.description == "Test user story"
    assert us.assignee is None
    assert us.start_date is None
    assert us.end_date is None
    assert us.story_points == 5.0
    assert len(us.tasks) == 0

def test_user_story_validation():
    """Testa a validação de uma user story"""
    # Testa criação com valores válidos
    us = UserStory(
        id="US-1",
        title="Test US",
        description="Test user story",
        assignee=None,
        start_date=None,
        end_date=None,
        story_points=5.0,
        tasks=[]
    )
    assert us is not None

def test_sprint_creation(sprint_dates):
    """Testa a criação de uma sprint"""
    start_date, end_date = sprint_dates
    
    sprint = Sprint(
        name="2024_S12_Mar18-Mar29",
        start_date=start_date,
        end_date=end_date,
        user_stories=[],
        team="Team A"
    )
    
    assert sprint.name == "2024_S12_Mar18-Mar29"
    assert sprint.start_date == start_date
    assert sprint.end_date == end_date
    assert len(sprint.user_stories) == 0
    assert sprint.team == "Team A"
    assert sprint.metrics is not None

def test_sprint_validation():
    """Testa a validação de uma sprint"""
    # Testa criação com valores válidos
    sprint = Sprint(
        name="2024_S12_Mar18-Mar29",
        start_date=datetime(2024, 3, 18, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, 17, 0, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    assert sprint is not None

def test_task_status_transition():
    """Testa a transição de status de uma task"""
    task = Task(
        id="1",
        title="[BE] Task Test",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,
        assignee="backend1@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    assert task.status == TaskStatus.PENDING
    task.status = TaskStatus.SCHEDULED
    assert task.status == TaskStatus.SCHEDULED

def test_work_front_validation():
    """Testa a validação de frente de trabalho"""
    task = Task(
        id="1",
        title="[BE] Task Test",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,
        assignee="backend1@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    assert task.work_front == WorkFront.BACKEND
    task.work_front = WorkFront.FRONTEND
    assert task.work_front == WorkFront.FRONTEND 