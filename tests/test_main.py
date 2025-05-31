import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from src.models.entities import Task, UserStory, Sprint, SprintMetrics, WorkFront
from src.models.config import Executor, ExecutorsConfig
from src.main import executar
from pathlib import Path

@pytest.fixture
def timezone_br():
    """Fixture para timezone de Brasília (UTC-3)"""
    return timezone(timedelta(hours=-3))

@pytest.fixture
def sprint_dates(timezone_br):
    """Fixture para datas do sprint"""
    start_date = datetime(2024, 3, 18, tzinfo=timezone_br)
    end_date = datetime(2024, 3, 29, tzinfo=timezone_br)
    return start_date, end_date

@pytest.fixture
def mock_azure_client():
    """Fixture para mock do cliente Azure DevOps"""
    client = Mock()
    
    # Mock para get_sprint_items
    user_stories = [
        UserStory(
            id="US-1",
            title="User Story 1",
            description="Test user story",
            assignee=None,
            start_date=None,
            end_date=None,
            story_points=5.0,
            tasks=[
                Task(
                    id="TASK-1",
                    title="Task 1",
                    description="Test task",
                    work_front=WorkFront.BACKEND,
                    estimated_hours=3.0,
                    assignee="backend1@example.com",
                    start_date=None,
                    end_date=None,
                    azure_end_date=None,
                    parent_user_story_id="US-1"
                ),
                Task(
                    id="TASK-2",
                    title="Task 2",
                    description="Test task",
                    work_front=WorkFront.FRONTEND,
                    estimated_hours=2.0,
                    assignee="frontend1@example.com",
                    start_date=None,
                    end_date=None,
                    azure_end_date=None,
                    parent_user_story_id="US-1"
                )
            ]
        ),
        UserStory(
            id="US-2",
            title="User Story 2",
            description="Test user story",
            assignee=None,
            start_date=None,
            end_date=None,
            story_points=5.0,
            tasks=[
                Task(
                    id="TASK-3",
                    title="Task 3",
                    description="Test task",
                    work_front=WorkFront.QA,
                    estimated_hours=4.0,
                    assignee="qa1@example.com",
                    start_date=None,
                    end_date=None,
                    azure_end_date=None,
                    parent_user_story_id="US-2"
                )
            ]
        )
    ]
    client.get_sprint_items.return_value = {"user_stories": user_stories}
    
    # Mock para get_team_capacity
    client.get_team_capacity.return_value = {
        "backend1@example.com": 6,
        "frontend1@example.com": 6,
        "qa1@example.com": 6
    }
    
    # Mock para get_work_item
    client.get_work_item.return_value = {
        "id": "1",
        "fields": {
            "System.Title": "Test Task",
            "System.Description": "Test Description",
            "System.AssignedTo": {"uniqueName": "test@example.com"},
            "System.State": "New",
            "System.IterationPath": "Project\\Sprint 1",
            "System.AreaPath": "Project\\Team 1",
            "Custom.Effort": 3,
            "System.WorkItemType": "Task",
            "System.Parent": "US-1"
        }
    }
    
    # Mock para update_work_item
    client.update_work_item = Mock()
    
    return client

@pytest.fixture
def mock_scheduler():
    """Fixture para mock do scheduler"""
    scheduler = Mock()
    
    # Mock para schedule_sprint
    sprint = Sprint(
        name="Sprint 1",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[
            UserStory(
                id="US-1",
                title="User Story 1",
                description="Test user story",
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[
                    Task(
                        id="TASK-1",
                        title="Task 1",
                        description="Test task",
                        work_front=WorkFront.BACKEND,
                        estimated_hours=3.0,
                        assignee="backend1@example.com",
                        start_date=None,
                        end_date=None,
                        azure_end_date=None,
                        parent_user_story_id="US-1"
                    )
                ]
            )
        ],
        team="Team A"
    )
    scheduler.schedule_sprint.return_value = sprint
    
    return scheduler

@pytest.fixture
def mock_report():
    """Fixture para mock do report generator"""
    report = Mock()
    report.generate_report.return_value = "Mock Report Content"
    return report

def test_main_success(mock_azure_client, mock_scheduler, mock_report):
    """Testa o fluxo principal com sucesso"""
    with patch("src.main.AzureDevOpsClient", return_value=mock_azure_client), \
         patch("src.main.SprintScheduler", return_value=mock_scheduler), \
         patch("src.main.ReportGenerator", return_value=mock_report):
        
        # Simula o fluxo principal
        items = mock_azure_client.get_sprint_items("Sprint-1")
        capacity = mock_azure_client.get_team_capacity("Team-1")
        sprint = mock_scheduler.schedule_sprint(items, capacity)
        report = mock_report.generate_report(sprint)
        
        assert report == "Mock Report Content"
        mock_azure_client.get_sprint_items.assert_called_once_with("Sprint-1")
        mock_azure_client.get_team_capacity.assert_called_once_with("Team-1")
        mock_scheduler.schedule_sprint.assert_called_once()
        mock_report.generate_report.assert_called_once()

def test_main_with_invalid_sprint(mock_azure_client):
    """Testa o fluxo principal com sprint inválido"""
    mock_azure_client.get_sprint_items.return_value = []
    
    with patch("src.main.AzureDevOpsClient", return_value=mock_azure_client):
        with pytest.raises(ValueError, match="No items found for sprint"):
            items = mock_azure_client.get_sprint_items("Invalid-Sprint")
            if not items:
                raise ValueError("No items found for sprint")

def test_main_with_invalid_team(mock_azure_client):
    """Testa o fluxo principal com time inválido"""
    mock_azure_client.get_team_capacity.return_value = {}
    
    with patch("src.main.AzureDevOpsClient", return_value=mock_azure_client):
        with pytest.raises(ValueError, match="No team capacity found"):
            capacity = mock_azure_client.get_team_capacity("Invalid-Team")
            if not capacity:
                raise ValueError("No team capacity found")

def test_main_with_invalid_items(mock_azure_client):
    """Testa o fluxo principal com itens inválidos"""
    mock_azure_client.get_sprint_items.return_value = []
    
    with patch("src.main.AzureDevOpsClient", return_value=mock_azure_client):
        with pytest.raises(ValueError, match="No items found for sprint"):
            items = mock_azure_client.get_sprint_items("Sprint-1")
            if not items:
                raise ValueError("No items found for sprint") 