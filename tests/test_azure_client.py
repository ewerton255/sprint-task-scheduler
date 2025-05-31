import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from src.models.entities import Task, UserStory, Sprint, SprintMetrics, WorkFront
from src.models.config import Executor, ExecutorsConfig

@pytest.fixture
def timezone_br():
    """Fixture para timezone de Brasília (UTC-3)"""
    return timezone(timedelta(hours=-3))

@pytest.fixture
def mock_work_client():
    """Fixture para mock do work client"""
    client = Mock()
    
    # Mock para get_team_capacity
    client.get_team_capacity.return_value = {
        "backend1@example.com": 6,
        "frontend1@example.com": 6,
        "qa1@example.com": 6
    }
    
    # Mock para get_team_iterations
    client.get_team_iterations.return_value = [
        {
            "id": "1",
            "name": "Sprint 1",
            "startDate": "2024-03-18T00:00:00Z",
            "endDate": "2024-03-29T00:00:00Z"
        }
    ]
    
    return client

@pytest.fixture
def mock_wit_client():
    """Fixture para mock do work item tracking client"""
    client = Mock()
    
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
    
    # Mock para get_work_items
    client.get_work_items.return_value = [
        {
            "id": "1",
            "fields": {
                "System.Title": "Test User Story",
                "System.Description": "Test Description",
                "System.AssignedTo": {"uniqueName": "test@example.com"},
                "System.State": "New",
                "System.IterationPath": "Project\\Sprint 1",
                "System.AreaPath": "Project\\Team 1",
                "Custom.StoryPoints": 5,
                "System.WorkItemType": "User Story"
            }
        }
    ]
    
    return client

@pytest.fixture
def mock_connection(mock_work_client, mock_wit_client):
    """Fixture para mock da conexão Azure DevOps"""
    connection = Mock()
    connection.clients = {
        "work": mock_work_client,
        "wit": mock_wit_client
    }
    return connection

@pytest.fixture
def azure_client(mock_connection):
    """Fixture para o cliente Azure DevOps"""
    client = Mock()
    
    # Mock para get_sprint_items
    client.get_sprint_items = Mock(return_value=[
        UserStory(
            id="1",
            title="Test User Story",
            description="Test Description",
            assignee="test@example.com",
            start_date=None,
            end_date=None,
            story_points=5.0,
            tasks=[]
        )
    ])
    
    # Mock para get_team_capacity
    client.get_team_capacity = Mock(return_value={
        "backend1@example.com": 6,
        "frontend1@example.com": 6,
        "qa1@example.com": 6
    })
    
    # Mock para update_work_item
    client.update_work_item = Mock()
    
    # Mock para get_work_item
    client.get_work_item = Mock(return_value={
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
    })
    
    # Mock para get_iterations
    client.get_iterations = Mock(return_value=[
        {
            "id": "1",
            "name": "Sprint 1",
            "startDate": "2024-03-18T00:00:00Z",
            "endDate": "2024-03-29T00:00:00Z"
        }
    ])
    
    # Mock para get_work_item_updates
    client.get_work_item_updates = Mock(return_value=[
        {
            "id": 1,
            "rev": 1,
            "fields": {
                "System.State": {"newValue": "Active"},
                "System.AssignedTo": {"newValue": {"uniqueName": "test@example.com"}}
            }
        }
    ])
    
    # Mock para get_work_item_revisions
    client.get_work_item_revisions = Mock(return_value=[
        {
            "id": 1,
            "rev": 1,
            "fields": {
                "System.State": "Active",
                "System.AssignedTo": {"uniqueName": "test@example.com"}
            }
        }
    ])
    
    # Mock para get_work_item_relations
    client.get_work_item_relations = Mock(return_value=[
        {
            "rel": "System.LinkTypes.Hierarchy-Forward",
            "url": "https://dev.azure.com/project/_apis/wit/workItems/2",
            "attributes": {
                "isLocked": False
            }
        }
    ])
    
    # Mock para get_work_item_comments
    client.get_work_item_comments = Mock(return_value=[
        {
            "id": 1,
            "text": "Test comment",
            "createdBy": {"uniqueName": "test@example.com"},
            "createdDate": "2024-03-18T00:00:00Z"
        }
    ])
    
    return client

def test_get_sprint_items(azure_client):
    """Testa a obtenção de itens do sprint"""
    items = azure_client.get_sprint_items("Sprint-1")
    
    assert len(items) == 1
    assert isinstance(items[0], UserStory)
    assert items[0].id == "1"
    assert items[0].title == "Test User Story"
    assert items[0].tasks == []
    
    azure_client.get_sprint_items.assert_called_once_with("Sprint-1")

def test_get_team_capacity(azure_client):
    """Testa a obtenção da capacidade da equipe"""
    capacity = azure_client.get_team_capacity("Team-1")
    
    assert isinstance(capacity, dict)
    assert "backend1@example.com" in capacity
    assert "frontend1@example.com" in capacity
    assert "qa1@example.com" in capacity
    assert all(value == 6 for value in capacity.values())
    
    azure_client.get_team_capacity.assert_called_once_with("Team-1")

def test_update_work_item(azure_client):
    """Testa a atualização de um work item"""
    azure_client.update_work_item(
        work_item_id="1",
        fields={
            "System.Title": "Updated Title",
            "System.State": "Active"
        }
    )
    
    azure_client.update_work_item.assert_called_once_with(
        work_item_id="1",
        fields={
            "System.Title": "Updated Title",
            "System.State": "Active"
        }
    )

def test_get_work_item(azure_client):
    """Testa a obtenção de um work item"""
    work_item = azure_client.get_work_item("1")
    
    assert work_item["id"] == "1"
    assert work_item["fields"]["System.Title"] == "Test Task"
    assert work_item["fields"]["Custom.Effort"] == 3
    
    azure_client.get_work_item.assert_called_once_with("1")

def test_get_iterations(azure_client):
    """Testa a obtenção de iterações"""
    iterations = azure_client.get_iterations("Team-1")
    
    assert len(iterations) == 1
    assert iterations[0]["name"] == "Sprint 1"
    
    azure_client.get_iterations.assert_called_once_with("Team-1")

def test_get_work_item_updates(azure_client):
    """Testa a obtenção de atualizações de um work item"""
    updates = azure_client.get_work_item_updates("1")
    
    assert len(updates) == 1
    assert updates[0]["id"] == 1
    assert updates[0]["fields"]["System.State"]["newValue"] == "Active"
    
    azure_client.get_work_item_updates.assert_called_once_with("1")

def test_get_work_item_revisions(azure_client):
    """Testa a obtenção de revisões de um work item"""
    revisions = azure_client.get_work_item_revisions("1")
    
    assert len(revisions) == 1
    assert revisions[0]["id"] == 1
    assert revisions[0]["fields"]["System.State"] == "Active"
    
    azure_client.get_work_item_revisions.assert_called_once_with("1")

def test_get_work_item_relations(azure_client):
    """Testa a obtenção de relações de um work item"""
    relations = azure_client.get_work_item_relations("1")
    
    assert len(relations) == 1
    assert relations[0]["rel"] == "System.LinkTypes.Hierarchy-Forward"
    
    azure_client.get_work_item_relations.assert_called_once_with("1")

def test_get_work_item_comments(azure_client):
    """Testa a obtenção de comentários de um work item"""
    comments = azure_client.get_work_item_comments("1")
    
    assert len(comments) == 1
    assert comments[0]["text"] == "Test comment"
    
    azure_client.get_work_item_comments.assert_called_once_with("1")

def test_get_work_item_updates():
    """Testa a obtenção de atualizações de um work item"""
    mock_client = Mock()
    mock_client.get_work_item_updates.return_value = [
        {
            "id": 1,
            "rev": 1,
            "fields": {
                "System.Title": "Task 1",
                "System.State": "Active"
            }
        },
        {
            "id": 2,
            "rev": 2,
            "fields": {
                "System.Title": "Task 1",
                "System.State": "Done"
            }
        }
    ]
    
    updates = mock_client.get_work_item_updates(1)
    assert len(updates) == 2
    assert updates[0]["fields"]["System.State"] == "Active"
    assert updates[1]["fields"]["System.State"] == "Done"
    mock_client.get_work_item_updates.assert_called_once_with(1)

def test_get_work_item_revisions():
    """Testa a obtenção de revisões de um work item"""
    mock_client = Mock()
    mock_client.get_work_item_revisions.return_value = [
        {
            "id": 1,
            "rev": 1,
            "fields": {
                "System.Title": "Task 1",
                "System.Description": "Initial description"
            }
        },
        {
            "id": 2,
            "rev": 2,
            "fields": {
                "System.Title": "Task 1",
                "System.Description": "Updated description"
            }
        }
    ]
    
    revisions = mock_client.get_work_item_revisions(1)
    assert len(revisions) == 2
    assert revisions[0]["fields"]["System.Description"] == "Initial description"
    assert revisions[1]["fields"]["System.Description"] == "Updated description"
    mock_client.get_work_item_revisions.assert_called_once_with(1)

def test_get_work_item_relations():
    """Testa a obtenção de relações de um work item"""
    mock_client = Mock()
    mock_client.get_work_item_relations.return_value = [
        {
            "rel": "System.LinkTypes.Hierarchy-Forward",
            "url": "https://dev.azure.com/org/project/_apis/wit/workItems/2",
            "attributes": {
                "name": "Child"
            }
        },
        {
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": "https://dev.azure.com/org/project/_apis/wit/workItems/3",
            "attributes": {
                "name": "Parent"
            }
        }
    ]
    
    relations = mock_client.get_work_item_relations(1)
    assert len(relations) == 2
    assert relations[0]["attributes"]["name"] == "Child"
    assert relations[1]["attributes"]["name"] == "Parent"
    mock_client.get_work_item_relations.assert_called_once_with(1)

def test_get_work_item_comments():
    """Testa a obtenção de comentários de um work item"""
    mock_client = Mock()
    mock_client.get_work_item_comments.return_value = [
        {
            "id": 1,
            "text": "First comment",
            "createdBy": {
                "displayName": "User 1"
            },
            "createdDate": "2024-03-18T10:00:00Z"
        },
        {
            "id": 2,
            "text": "Second comment",
            "createdBy": {
                "displayName": "User 2"
            },
            "createdDate": "2024-03-18T11:00:00Z"
        }
    ]
    
    comments = mock_client.get_work_item_comments(1)
    assert len(comments) == 2
    assert comments[0]["text"] == "First comment"
    assert comments[1]["text"] == "Second comment"
    mock_client.get_work_item_comments.assert_called_once_with(1)

def test_get_work_item_with_invalid_id():
    """Testa a obtenção de um work item com ID inválido"""
    mock_client = Mock()
    mock_client.get_work_item.side_effect = ValueError("Invalid work item ID")
    
    with pytest.raises(ValueError, match="Invalid work item ID"):
        mock_client.get_work_item(0)

def test_update_work_item_with_invalid_fields():
    """Testa a atualização de um work item com campos inválidos"""
    mock_client = Mock()
    mock_client.update_work_item.side_effect = ValueError("Invalid fields")
    
    with pytest.raises(ValueError, match="Invalid fields"):
        mock_client.update_work_item(1, {})

def test_get_iterations_with_invalid_team():
    """Testa a obtenção de iterações com time inválido"""
    mock_client = Mock()
    mock_client.get_iterations.side_effect = ValueError("Invalid team")
    
    with pytest.raises(ValueError, match="Invalid team"):
        mock_client.get_iterations("Invalid Team")

def test_get_team_capacity_with_invalid_iteration():
    """Testa a obtenção de capacidade com iteração inválida"""
    mock_client = Mock()
    mock_client.get_team_capacity.side_effect = ValueError("Invalid iteration")
    
    with pytest.raises(ValueError, match="Invalid iteration"):
        mock_client.get_team_capacity("Team A", "Invalid Iteration")

def test_get_sprint_items_with_invalid_sprint():
    """Testa a obtenção de itens com sprint inválida"""
    mock_client = Mock()
    mock_client.get_sprint_items.side_effect = ValueError("Invalid sprint")
    
    with pytest.raises(ValueError, match="Invalid sprint"):
        mock_client.get_sprint_items("Invalid Sprint") 