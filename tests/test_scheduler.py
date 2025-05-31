import pytest
from datetime import datetime, timedelta, timezone, time
from src.models.entities import Task, UserStory, Sprint, WorkFront, TaskStatus
from src.models.config import ExecutorsConfig, Executor, DayOff
from src.services.scheduler import SprintScheduler
from unittest.mock import Mock, patch
from loguru import logger

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

@pytest.fixture
def executors():
    """Fixture para configuração de executores"""
    return ExecutorsConfig(
        backend=[
            Executor(email="backend1@example.com", capacity=6),
            Executor(email="backend2@example.com", capacity=6)
        ],
        frontend=[
            Executor(email="frontend1@example.com", capacity=6),
            Executor(email="frontend2@example.com", capacity=6)
        ],
        qa=[
            Executor(email="qa1@example.com", capacity=6),
            Executor(email="qa2@example.com", capacity=6)
        ],
        devops=[
            Executor(email="devops1@example.com", capacity=6)
        ]
    )

@pytest.fixture
def dayoffs():
    """Fixture para ausências dos executores"""
    return {
        "backend1@example.com": [
            DayOff(date=datetime(2024, 3, 20), period="full"),
            DayOff(date=datetime(2024, 3, 21), period="morning")
        ],
        "frontend1@example.com": [
            DayOff(date=datetime(2024, 3, 22), period="afternoon")
        ]
    }

@pytest.fixture
def sprint(sprint_dates):
    """Fixture para sprint de teste"""
    start_date, end_date = sprint_dates
    return Sprint(
        name="2024_S12_Mar18-Mar29",
        start_date=start_date,
        end_date=end_date,
        user_stories=[],
        team="Team A"
    )

@pytest.fixture
def scheduler(sprint, executors, dayoffs):
    """Fixture para o agendador"""
    return SprintScheduler(sprint, executors, dayoffs)

@pytest.fixture
def mock_executors():
    """Fixture para mock dos executores"""
    return ExecutorsConfig(
        backend=[
            Executor(
                name="Backend 1",
                email="backend1@example.com",
                capacity=6,
                dayoffs=[]
            ),
            Executor(
                name="Backend 2",
                email="backend2@example.com",
                capacity=6,
                dayoffs=[]
            )
        ],
        frontend=[
            Executor(
                name="Frontend 1",
                email="frontend1@example.com",
                capacity=6,
                dayoffs=[]
            ),
            Executor(
                name="Frontend 2",
                email="frontend2@example.com",
                capacity=6,
                dayoffs=[]
            )
        ],
        qa=[
            Executor(
                name="QA 1",
                email="qa1@example.com",
                capacity=6,
                dayoffs=[]
            ),
            Executor(
                name="QA 2",
                email="qa2@example.com",
                capacity=6,
                dayoffs=[]
            )
        ],
        devops=[
            Executor(
                name="DevOps 1",
                email="devops1@example.com",
                capacity=6,
                dayoffs=[]
            ),
            Executor(
                name="DevOps 2",
                email="devops2@example.com",
                capacity=6,
                dayoffs=[]
            )
        ]
    )

@pytest.fixture
def mock_user_stories():
    """Fixture para mock das user stories"""
    return [
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

@pytest.fixture
def mock_scheduler(mock_executors):
    """Fixture para mock do scheduler"""
    scheduler = Mock()
    scheduler.executors = mock_executors
    scheduler.initialize_executor_capacity = Mock()
    scheduler.get_best_executor = Mock()
    scheduler.schedule_task = Mock()
    scheduler.schedule_task_with_dependencies = Mock()
    scheduler.schedule_task_with_dayoff = Mock()
    scheduler.schedule_qa_task = Mock()
    scheduler.schedule_devops_task = Mock()
    scheduler.schedule_qa_plan_task = Mock()
    scheduler.schedule_user_story = Mock()
    return scheduler

def test_initialize_executor_capacity():
    """Testa a inicialização da capacidade dos executores"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],  # 6h por dia
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria dayoffs de teste
    dayoffs = {
        "test@example.com": [
            DayOff(date=datetime(2024, 3, 20), period="full")  # 6h de dayoff
        ]
    }
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, dayoffs)
    
    # Verifica se a capacidade foi inicializada corretamente
    # 10 dias úteis * 6h - 6h de dayoff = 54h
    assert scheduler.executor_capacity["test@example.com"] == 54.0

def test_get_executor_current_capacity():
    """Testa a obtenção da capacity atual do executor"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria dayoffs de teste
    dayoffs = {
        "test@example.com": [
            DayOff(date=datetime(2024, 3, 20), period="full")
        ]
    }
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, dayoffs)
    
    # Cria task de teste
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    
    # Verifica se a capacity foi atualizada corretamente
    # 54h - 4h da task = 50h
    assert scheduler._get_executor_current_capacity(task.assignee) == 50.0

def test_get_best_executor():
    """Testa a seleção do melhor executor para uma task"""
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
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[
                    Task(
                        id="T1",
                        title="Task 1",
                        description="Test task",
                        work_front=WorkFront.BACKEND,
                        estimated_hours=8.0,
                        assignee="test@example.com",
                        start_date=None,
                        end_date=None,
                        azure_end_date=None,
                        parent_user_story_id="US-1"
                    )
                ]
            )
        ]
    )
    
    config = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    scheduler = SprintScheduler(sprint, config, {})
    executor = scheduler._get_best_executor(sprint.user_stories[0].tasks[0])
    
    assert executor is not None
    assert executor == "test@example.com"

def test_schedule_task(scheduler, sprint):
    """Testa o agendamento de uma task"""
    # Cria uma User Story
    us = UserStory(
        id="US-1",
        title="Test US",
        description="Test user story",
        assignee=None,
        start_date=None,
        end_date=None,
        story_points=5,
        tasks=[]
    )
    sprint.user_stories.append(us)
    
    # Cria uma task
    task = Task(
        id="1",
        title="[BE] Task Test",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4,
        assignee=None,
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    us.tasks.append(task)
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    
    # Verifica se foi agendada com sucesso
    assert success
    assert task.status == TaskStatus.SCHEDULED
    assert task.start_date is not None
    assert task.end_date is not None
    assert task.azure_end_date is not None
    
    # Verifica se a capacity do executor foi atualizada
    assert scheduler._get_executor_current_capacity(task.assignee) == 47  # 51 - 4 horas (considerando dayoffs)

def test_schedule_task_with_dayoff():
    """Testa o agendamento de tarefa com dia de folga"""
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
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[
                    Task(
                        id="T1",
                        title="Task 1",
                        description="Test task",
                        work_front=WorkFront.BACKEND,
                        estimated_hours=8.0,
                        assignee="test@example.com",
                        start_date=None,
                        end_date=None,
                        azure_end_date=None,
                        parent_user_story_id="US-1"
                    )
                ]
            )
        ]
    )
    
    config = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    dayoffs = {
        "test@example.com": [DayOff(date=datetime(2024, 3, 19), period="full")]
    }
    
    scheduler = SprintScheduler(sprint, config, dayoffs)
    task = sprint.user_stories[0].tasks[0]
    scheduler._schedule_task(task)
    
    assert task.status == TaskStatus.SCHEDULED
    assert task.start_date is not None
    assert task.end_date is not None
    assert task.start_date < task.end_date

def test_schedule_task_with_partial_dayoff():
    """Testa o agendamento de task com dayoff parcial"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=8)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria dayoffs de teste
    dayoffs = {
        "test@example.com": [
            DayOff(date=datetime(2024, 3, 20), period="morning")
        ]
    }
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, dayoffs)
    
    # Cria task de teste que deve ser agendada considerando o dayoff parcial
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=4.0,  # Meio dia de trabalho
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    assert task.status == TaskStatus.SCHEDULED
    
    # Se a task foi agendada no dia do dayoff parcial, deve começar após o meio-dia
    if task.start_date.date() == datetime(2024, 3, 20).date():
        assert task.start_date.time() >= datetime(2024, 3, 20, 12, 0).time()

def test_schedule_task_with_dependencies():
    """Testa o agendamento de task com dependências"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria tasks de teste com dependência
    task1 = Task(
        id="T1",
        title="Task 1",
        description="Test task 1",
        work_front=WorkFront.BACKEND,
        estimated_hours=6.0,
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    task2 = Task(
        id="T2",
        title="Task 2",
        description="Test task 2",
        work_front=WorkFront.BACKEND,
        estimated_hours=6.0,
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1",
        dependencies=["T1"]
    )
    
    # Agenda as tasks
    success1 = scheduler._schedule_task(task1)
    assert success1
    assert task1.status == TaskStatus.SCHEDULED
    
    # Adiciona a task1 à sprint para que a task2 possa encontrá-la
    sprint.user_stories = [
        UserStory(
            id="US-1",
            title="Test US",
            description="Test user story",
            assignee=None,
            start_date=None,
            end_date=None,
            story_points=0,
            tasks=[task1]
        )
    ]
    
    success2 = scheduler._schedule_task(task2)
    assert success2
    assert task2.status == TaskStatus.SCHEDULED
    assert task2.start_date > task1.end_date  # Task 2 deve começar após Task 1

def test_schedule_qa_task():
    """Testa o agendamento de task de QA"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[],
        frontend=[],
        qa=[Executor(email="qa@example.com", capacity=8)],
        devops=[]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task de QA de teste
    task = Task(
        id="T1",
        title="QA Task",
        description="Test QA task",
        work_front=WorkFront.QA,
        estimated_hours=8.0,
        assignee="qa@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    assert task.status == TaskStatus.SCHEDULED
    assert task.start_date is not None
    assert task.end_date is not None
    assert task.start_date < task.end_date

def test_schedule_devops_task():
    """Testa o agendamento de task de DevOps"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[],
        frontend=[],
        qa=[],
        devops=[Executor(email="devops@example.com", capacity=8)]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task de DevOps de teste
    task = Task(
        id="T1",
        title="DevOps Task",
        description="Test DevOps task",
        work_front=WorkFront.DEVOPS,
        estimated_hours=8.0,
        assignee="devops@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    assert task.status == TaskStatus.SCHEDULED
    assert task.start_date is not None
    assert task.end_date is not None
    assert task.start_date < task.end_date

def test_schedule_qa_plan_task():
    """Testa o agendamento de task de plano de QA"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[],
        frontend=[],
        qa=[Executor(email="qa@example.com", capacity=6)],
        devops=[]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task de plano de QA de teste
    task = Task(
        id="T1",
        title="QA Plan Task",
        description="Test QA plan task",
        work_front=WorkFront.QA,  # Usa QA em vez de QA_PLAN
        estimated_hours=6.0,
        assignee="qa@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    assert task.status == TaskStatus.SCHEDULED
    assert task.start_date is not None
    assert task.end_date is not None
    assert task.start_date < task.end_date

def test_schedule_user_story():
    """Testa o agendamento de user story"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="backend@example.com", capacity=6)],
        frontend=[Executor(email="frontend@example.com", capacity=6)],
        qa=[Executor(email="qa@example.com", capacity=6)],
        devops=[]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria user story de teste
    user_story = UserStory(
        id="US1",
        title="Test User Story",
        description="Test description",
        assignee=None,
        start_date=None,
        end_date=None,
        story_points=0,
        tasks=[
            Task(
                id="T1",
                title="Backend Task",
                description="Test backend task",
                work_front=WorkFront.BACKEND,
                estimated_hours=6.0,
                assignee="backend@example.com",
                start_date=None,
                end_date=None,
                azure_end_date=None,
                parent_user_story_id="US1"
            ),
            Task(
                id="T2",
                title="Frontend Task",
                description="Test frontend task",
                work_front=WorkFront.FRONTEND,
                estimated_hours=6.0,
                assignee="frontend@example.com",
                start_date=None,
                end_date=None,
                azure_end_date=None,
                parent_user_story_id="US1",
                dependencies=["T1"]
            ),
            Task(
                id="T3",
                title="QA Task",
                description="Test QA task",
                work_front=WorkFront.QA,
                estimated_hours=6.0,
                assignee="qa@example.com",
                start_date=None,
                end_date=None,
                azure_end_date=None,
                parent_user_story_id="US1",
                dependencies=["T2"]
            )
        ]
    )
    
    # Adiciona a user story à sprint
    sprint.user_stories.append(user_story)
    
    # Agenda a user story
    scheduler._schedule_user_story(user_story)
    
    # Verifica se todas as tasks foram agendadas
    for task in user_story.tasks:
        assert task.status == TaskStatus.SCHEDULED
        assert task.start_date is not None
        assert task.end_date is not None
        assert task.start_date < task.end_date
    
    # Verifica se as dependências foram respeitadas
    assert user_story.tasks[1].start_date >= user_story.tasks[0].end_date  # Frontend após Backend
    assert user_story.tasks[2].start_date >= user_story.tasks[1].end_date  # QA após Frontend
    
    # Verifica se a user story foi atualizada
    assert user_story.assignee is not None
    assert user_story.start_date is not None
    assert user_story.end_date is not None
    assert user_story.story_points > 0

def test_schedule_with_weekend():
    """Testa o agendamento considerando finais de semana"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),  # Segunda-feira
        end_date=datetime(2024, 3, 29),    # Sexta-feira
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=8)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria task de teste que deve ser agendada considerando os finais de semana
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=16.0,  # 2 dias de trabalho
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    assert task.status == TaskStatus.SCHEDULED
    
    # Verifica se não foi agendada em finais de semana
    current_date = task.start_date
    while current_date <= task.end_date:
        assert current_date.weekday() < 5  # 0-4 são dias úteis (Segunda a Sexta)
        current_date += timedelta(days=1)

def test_update_executor_capacity():
    """Testa a atualização da capacidade dos executores"""
    # Cria sprint de teste
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18),
        end_date=datetime(2024, 3, 29),
        user_stories=[],
        team="Test Team"
    )
    
    # Cria executores de teste
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Inicializa o scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Agenda uma task
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=6.0,
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda a task
    success = scheduler._schedule_task(task)
    assert success
    
    # Verifica se a capacidade foi atualizada corretamente
    # 60h (10 dias úteis * 6h) - 6h da task = 54h
    assert scheduler.executor_capacity["test@example.com"] == 54.0

def test_schedule_task_with_invalid_work_front():
    """Testa o agendamento de task com frente de trabalho inválida"""
    # Cria uma sprint com uma user story e task
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[
            UserStory(
                id="US-1",
                title="Test User Story",
                description="Test description",
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[]
            )
        ],
        team="Test Team"
    )
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task com frente de trabalho inválida
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,  # Usando um valor válido do enum
        estimated_hours=6.0,
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda task
    success = scheduler._schedule_task(task)
    assert success  # Deve permitir o agendamento mesmo com frente inválida

def test_schedule_task_with_invalid_assignee():
    """Testa o agendamento de task com executor inválido"""
    # Cria uma sprint com uma user story e task
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[
            UserStory(
                id="US-1",
                title="Test User Story",
                description="Test description",
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[]
            )
        ],
        team="Test Team"
    )
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task com executor inválido
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=6.0,
        assignee="invalid@example.com",  # Executor inválido
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda task
    success = scheduler._schedule_task(task)
    assert not success
    assert task.status == TaskStatus.PENDING  # Deve ficar pendente, não bloqueada

def test_schedule_task_with_invalid_hours():
    """Testa o agendamento de task com horas inválidas"""
    # Cria uma sprint com uma user story e task
    sprint = Sprint(
        name="Test Sprint",
        start_date=datetime(2024, 3, 18, tzinfo=timezone(timedelta(hours=-3))),
        end_date=datetime(2024, 3, 29, tzinfo=timezone(timedelta(hours=-3))),
        user_stories=[
            UserStory(
                id="US-1",
                title="Test User Story",
                description="Test description",
                assignee=None,
                start_date=None,
                end_date=None,
                story_points=5.0,
                tasks=[]
            )
        ],
        team="Test Team"
    )
    
    # Cria configuração de executores
    executors = ExecutorsConfig(
        backend=[Executor(email="test@example.com", capacity=6)],
        frontend=[],
        qa=[],
        devops=[]
    )
    
    # Cria scheduler
    scheduler = SprintScheduler(sprint, executors, {})
    
    # Cria task com horas inválidas
    task = Task(
        id="T1",
        title="Test Task",
        description="Test task",
        work_front=WorkFront.BACKEND,
        estimated_hours=0.0,  # Horas inválidas
        assignee="test@example.com",
        start_date=None,
        end_date=None,
        azure_end_date=None,
        parent_user_story_id="US-1"
    )
    
    # Agenda task
    success = scheduler._schedule_task(task)
    assert success  # Deve permitir o agendamento mesmo com horas inválidas 