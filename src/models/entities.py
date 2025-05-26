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

class Sprint(BaseModel):
    """Modelo de uma Sprint"""
    name: str
    start_date: datetime
    end_date: datetime
    user_stories: List[UserStory] = Field(default_factory=list)
    team: str

    def get_all_tasks(self) -> List[Task]:
        """Retorna todas as tasks da sprint"""
        return [task for us in self.user_stories for task in us.tasks]

    def get_tasks_by_assignee(self, assignee: str) -> List[Task]:
        """Retorna todas as tasks atribuídas a um executor"""
        return [task for task in self.get_all_tasks() if task.assignee == assignee] 