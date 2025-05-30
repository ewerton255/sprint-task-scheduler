from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class WorkFront(str, Enum):
    """Frentes de trabalho disponíveis"""
    BACKEND = "backend"
    FRONTEND = "frontend"
    QA = "qa"
    DEVOPS = "devops"

class TaskStatus(str, Enum):
    """Status possíveis para uma task"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    BLOCKED = "blocked"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    """Modelo de uma task"""
    id: str
    title: str
    description: Optional[str]
    work_front: WorkFront
    estimated_hours: float
    assignee: Optional[str]
    dependencies: List[str] = Field(default_factory=list)
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    azure_end_date: Optional[datetime]
    status: TaskStatus = TaskStatus.PENDING
    parent_user_story_id: str

    @property
    def is_qa_test_plan(self) -> bool:
        """Verifica se é uma task de plano de testes"""
        return self.work_front == WorkFront.QA and "[QA] Elaboração de Plano de Testes" in self.title

    @property
    def is_devops_task(self) -> bool:
        """Verifica se é uma task de DevOps"""
        return self.work_front == WorkFront.DEVOPS

class UserStory(BaseModel):
    """Modelo de uma User Story"""
    id: str
    title: str
    description: Optional[str]
    tasks: List[Task] = Field(default_factory=list)
    assignee: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    story_points: Optional[float]

    def calculate_story_points(self) -> float:
        """Calcula os story points baseado na soma das horas das tasks"""
        total_hours = sum(task.estimated_hours for task in self.tasks if task.status != TaskStatus.CANCELLED)
        
        # Tabela de conversão de horas para story points
        if total_hours <= 1: return 0.5
        elif total_hours <= 2: return 1
        elif total_hours <= 3: return 2
        elif total_hours <= 5: return 3
        elif total_hours <= 9: return 5
        elif total_hours <= 14: return 8
        elif total_hours <= 23: return 13
        elif total_hours <= 37: return 21
        elif total_hours <= 60: return 34
        else: return 55

    def get_tasks_by_work_front(self, work_front: WorkFront) -> List[Task]:
        """Retorna todas as tasks de uma determinada frente de trabalho"""
        return [task for task in self.tasks if task.work_front == work_front]

class Sprint:
    """Representa uma sprint do projeto"""
    
    def __init__(self, name: str, start_date: datetime, end_date: datetime, user_stories: List[UserStory] = None, team: str = None):
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.user_stories: List[UserStory] = user_stories or []
        self.team = team
        self.metrics = SprintMetrics()
    
    def add_user_story(self, user_story: UserStory) -> None:
        """Adiciona uma user story à sprint"""
        self.user_stories.append(user_story)
    
    def get_all_tasks(self) -> List[Task]:
        """Retorna todas as tasks da sprint"""
        tasks = []
        for us in self.user_stories:
            tasks.extend(us.tasks)
        return tasks
        
    def get_tasks_by_assignee(self, assignee: str) -> List[Task]:
        """Retorna todas as tasks atribuídas a um executor"""
        tasks = []
        for us in self.user_stories:
            for task in us.tasks:
                if task.assignee and task.assignee.lower() == assignee.lower():
                    tasks.append(task)
        return tasks

class SprintMetrics(BaseModel):
    """Métricas globais da sprint"""
    total_capacity: Dict[str, float] = {}  # Capacidade total por executor
    used_capacity: Dict[str, float] = {}   # Capacidade utilizada por executor
    available_capacity: Dict[str, float] = {}  # Capacidade disponível por executor
    not_scheduled_tasks: List[Dict] = []  # Tasks não agendadas com seus motivos

    def update_capacity(self, executor: str, total: float, used: float) -> None:
        """Atualiza as métricas de capacidade de um executor"""
        self.total_capacity[executor] = total
        self.used_capacity[executor] = used
        self.available_capacity[executor] = total - used

    def add_not_scheduled_task(self, task_id: str, title: str, reason: str, user_story_id: Optional[str] = None) -> None:
        """Adiciona uma task não agendada com seu motivo"""
        self.not_scheduled_tasks.append({
            "task_id": task_id,
            "title": title,
            "reason": reason,
            "user_story_id": user_story_id
        }) 