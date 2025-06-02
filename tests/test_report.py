import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from src.models.entities import Task, UserStory, Sprint, SprintMetrics, WorkFront, TaskStatus
from src.models.config import Executor, ExecutorsConfig, DayOff
from src.services.report import ReportGenerator
from reportlab.platypus.tables import TableStyle

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
def mock_sprint(sprint_dates):
    """Fixture para mock do sprint"""
    start_date, end_date = sprint_dates
    return Sprint(
        name="Sprint 1",
        start_date=start_date,
        end_date=end_date,
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
        ],
        team="Team A"
    )

@pytest.fixture
def mock_report():
    """Fixture para mock do gerador de relatórios"""
    report = Mock()
    report.generate_report = Mock(return_value="Mock Report Content")
    report.generate_summary = Mock(return_value="Mock Summary Content")
    report.generate_details = Mock(return_value="Mock Details Content")
    report.generate_metrics = Mock(return_value="Mock Metrics Content")
    report.generate_tasks = Mock(return_value="Mock Tasks Content")
    report.generate_user_stories = Mock(return_value="Mock User Stories Content")
    report.generate_team = Mock(return_value="Mock Team Content")
    report.generate_dates = Mock(return_value="Mock Dates Content")
    return report

def test_generate_report(mock_report, mock_sprint):
    """Testa a geração do relatório completo"""
    report = mock_report.generate_report(mock_sprint)
    assert report == "Mock Report Content"
    mock_report.generate_report.assert_called_once_with(mock_sprint)

def test_generate_summary(mock_report, mock_sprint):
    """Testa a geração do resumo do relatório"""
    summary = mock_report.generate_summary(mock_sprint)
    assert summary == "Mock Summary Content"
    mock_report.generate_summary.assert_called_once_with(mock_sprint)

def test_generate_details(mock_report, mock_sprint):
    """Testa a geração dos detalhes do relatório"""
    details = mock_report.generate_details(mock_sprint)
    assert details == "Mock Details Content"
    mock_report.generate_details.assert_called_once_with(mock_sprint)

def test_generate_metrics(mock_report, mock_sprint):
    """Testa a geração das métricas do relatório"""
    metrics = mock_report.generate_metrics(mock_sprint)
    assert metrics == "Mock Metrics Content"
    mock_report.generate_metrics.assert_called_once_with(mock_sprint)

def test_generate_tasks(mock_report, mock_sprint):
    """Testa a geração das tarefas do relatório"""
    tasks = mock_report.generate_tasks(mock_sprint)
    assert tasks == "Mock Tasks Content"
    mock_report.generate_tasks.assert_called_once_with(mock_sprint)

def test_generate_user_stories(mock_report, mock_sprint):
    """Testa a geração das user stories do relatório"""
    user_stories = mock_report.generate_user_stories(mock_sprint)
    assert user_stories == "Mock User Stories Content"
    mock_report.generate_user_stories.assert_called_once_with(mock_sprint)

def test_generate_team(mock_report, mock_sprint):
    """Testa a geração da equipe do relatório"""
    team = mock_report.generate_team(mock_sprint)
    assert team == "Mock Team Content"
    mock_report.generate_team.assert_called_once_with(mock_sprint)

def test_generate_dates(mock_report, mock_sprint):
    """Testa a geração das datas do relatório"""
    dates = mock_report.generate_dates(mock_sprint)
    assert dates == "Mock Dates Content"
    mock_report.generate_dates.assert_called_once_with(mock_sprint)

def test_generate_report_with_empty_sprint(mock_report):
    """Testa a geração do relatório com sprint vazio"""
    empty_sprint = Sprint(
        name="Empty Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    mock_report.generate_report.side_effect = ValueError("Empty sprint")
    with pytest.raises(ValueError, match="Empty sprint"):
        mock_report.generate_report(empty_sprint)

def test_generate_report_with_invalid_dates(mock_report):
    """Testa a geração do relatório com datas inválidas"""
    invalid_sprint = Sprint(
        name="Invalid Sprint",
        start_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    mock_report.generate_report.side_effect = ValueError("Invalid dates")
    with pytest.raises(ValueError, match="Invalid dates"):
        mock_report.generate_report(invalid_sprint)

def test_generate_report_with_invalid_team(mock_report):
    """Testa a geração do relatório com equipe inválida"""
    invalid_sprint = Sprint(
        name="Invalid Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team=""
    )
    mock_report.generate_report.side_effect = ValueError("Invalid team")
    with pytest.raises(ValueError, match="Invalid team"):
        mock_report.generate_report(invalid_sprint)

def test_generate_report_with_invalid_user_story(mock_report):
    """Testa a geração do relatório com user story inválida"""
    invalid_sprint = Sprint(
        name="Invalid Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[
            UserStory(
                id="",
                title="",
                description="",
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=0.0,
                tasks=[]
            )
        ],
        team="Team A"
    )
    mock_report.generate_report.side_effect = ValueError("Invalid user story")
    with pytest.raises(ValueError, match="Invalid user story"):
        mock_report.generate_report(invalid_sprint)

def test_generate_report_with_invalid_task(mock_report):
    """Testa a geração do relatório com tarefa inválida"""
    invalid_sprint = Sprint(
        name="Invalid Sprint",
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
                        id="",
                        title="",
                        description="",
                        work_front=WorkFront.BACKEND,
                        estimated_hours=0.0,
                        assignee="",
                        start_date=None,
                        end_date=None,
                        azure_end_date=None,
                        parent_user_story_id=""
                    )
                ]
            )
        ],
        team="Team A"
    )
    mock_report.generate_report.side_effect = ValueError("Invalid task")
    with pytest.raises(ValueError, match="Invalid task"):
        mock_report.generate_report(invalid_sprint)

def test_setup_styles():
    """Testa a configuração dos estilos do relatório"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    report = ReportGenerator(sprint, {}, "output", "Team A")
    
    # Verifica se os estilos foram criados
    assert "CustomTitle" in report.styles
    assert "CustomHeading1" in report.styles
    assert "CustomHeading2" in report.styles
    assert "NormalWrap" in report.styles
    assert "TableCell" in report.styles
    assert "TableHeader" in report.styles

def test_create_table_style():
    """Testa a criação do estilo de tabela"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    report = ReportGenerator(sprint, {}, "output", "Team A")
    
    # Verifica se o estilo da tabela foi criado
    style = report._create_table_style()
    assert isinstance(style, TableStyle)
    assert len(style.getCommands()) > 0

def test_count_working_days():
    """Testa a contagem de dias úteis"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    report = ReportGenerator(sprint, {}, "output", "Team A")
    
    # Testa contagem de dias úteis em uma semana
    start_date = datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3)))  # Segunda
    end_date = datetime(2024, 3, 22, tzinfo=timezone(timedelta(hours=-3)))   # Sexta
    working_days = report._count_working_days(start_date, end_date)
    assert working_days == 5
    
    # Testa contagem incluindo fim de semana
    end_date = datetime(2024, 3, 24, tzinfo=timezone(timedelta(hours=-3)))   # Domingo
    working_days = report._count_working_days(start_date, end_date)
    assert working_days == 5

def test_generate_markdown():
    """Testa a geração do relatório em markdown"""
    sprint = Sprint(
        name="Sprint 1",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        team="Team 1",
        user_stories=[
            UserStory(
                id="US-1",
                title="User Story 1",
                description="Test user story",
                assignee="test@example.com",
                start_date=datetime(2024, 3, 18),
                end_date=datetime(2024, 3, 22),
                story_points=5.0,
                tasks=[
                    Task(
                        id="T1",
                        title="Task 1",
                        description="Test task",
                        work_front=WorkFront.BACKEND,
                        estimated_hours=8.0,
                        assignee="test@example.com",
                        start_date=datetime(2024, 3, 18),
                        end_date=datetime(2024, 3, 19),
                        azure_end_date=None,
                        parent_user_story_id="US-1"
                    )
                ]
            )
        ]
    )
    
    report = ReportGenerator(sprint, {}, "output", "Test Team")
    markdown = report._generate_markdown()
    
    assert "# Relatório de Agendamento - Sprint Sprint 1" in markdown
    assert "**Sprint:** Sprint 1" in markdown
    assert "**Início:** 18/03/2024" in markdown
    assert "**Término:** 29/03/2024" in markdown
    assert "| US-1 | User Story 1 | test@example.com | 22/03/2024 | 5.0 |" in markdown

def test_generate_with_metrics():
    """Testa a geração do relatório com métricas"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    sprint.metrics = SprintMetrics()
    sprint.metrics.add_not_scheduled_task(
        task_id="TASK-1",
        title="Task 1",
        reason="Test reason",
        user_story_id="US-1"
    )
    sprint.metrics.update_capacity("test@example.com", 40, 20)
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    report = ReportGenerator(sprint, {}, "output", "Team A", executors)
    
    # Gera o relatório em Markdown
    markdown_content = report._generate_markdown()
    
    # Verifica se o conteúdo contém as métricas
    assert "## 3. Tasks não planejadas" in markdown_content
    assert "TASK-1" in markdown_content
    assert "Test reason" in markdown_content
    assert "40.0h" in markdown_content
    assert "20.0h" in markdown_content
    
    # Verifica se o conteúdo contém a seção de percentual de capacity
    assert "## 5. Percentual de Capacity Preenchida" in markdown_content
    assert "**Percentual de Capacity Preenchida:** 50.00%" in markdown_content
    assert "*Total de Capacity Disponível:* 40.0h" in markdown_content
    assert "*Total de Capacity Utilizada:* 20.0h" in markdown_content

def test_generate_with_empty_metrics():
    """Testa a geração do relatório sem métricas"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    sprint.metrics = SprintMetrics()
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    report = ReportGenerator(sprint, {}, "output", "Team A", executors)
    
    # Gera o relatório em Markdown
    markdown_content = report._generate_markdown()
    
    # Verifica se o conteúdo não contém a seção de tasks não planejadas
    assert "## 3. Tasks não planejadas" not in markdown_content
    
    # Verifica se o conteúdo contém a seção de percentual de capacity com valores zerados
    assert "## 5. Percentual de Capacity Preenchida" in markdown_content
    assert "**Percentual de Capacity Preenchida:** 0.00%" in markdown_content
    assert "*Total de Capacity Disponível:* 0.0h" in markdown_content
    assert "*Total de Capacity Utilizada:* 0.0h" in markdown_content

def test_generate_with_invalid_team_name():
    """Testa a geração do relatório com nome de time inválido"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    
    # Testa com nome de time vazio
    report = ReportGenerator(sprint, {}, "output", "")
    assert report.team_name == ""
    
    # Testa com nome de time com caminho completo
    report = ReportGenerator(sprint, {}, "output", "TR Fintech\\TRF\\TR Banking\\BENEFICIOS")
    assert report.team_name == "BENEFICIOS"

def test_generate_with_multiple_executors():
    """Testa a geração do relatório com múltiplos executores"""
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[],
        team="Team A"
    )
    sprint.metrics = SprintMetrics()
    sprint.metrics.update_capacity("executor1@example.com", 40, 30)
    sprint.metrics.update_capacity("executor2@example.com", 40, 10)
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[
            Executor(email="executor1@example.com", capacity=6),
            Executor(email="executor2@example.com", capacity=6)
        ],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    report = ReportGenerator(sprint, {}, "output", "Team A", executors)
    
    # Gera o relatório em Markdown
    markdown_content = report._generate_markdown()
    
    # Verifica se o conteúdo contém a seção de percentual de capacity com os valores corretos
    assert "## 5. Percentual de Capacity Preenchida" in markdown_content
    assert "**Percentual de Capacity Preenchida:** 50.00%" in markdown_content
    assert "*Total de Capacity Disponível:* 80.0h" in markdown_content
    assert "*Total de Capacity Utilizada:* 40.0h" in markdown_content 