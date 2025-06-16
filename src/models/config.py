from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AzureDevOpsConfig(BaseModel):
    """Configuração do Azure DevOps"""

    organization: str
    project: str
    token: str


class SprintConfig(BaseModel):
    """Configuração da Sprint"""

    name: str
    year: str
    quarter: str
    start_date: str
    end_date: str

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> datetime:
        """Valida e converte a string de data para datetime"""
        try:
            return datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Data inválida: {v}. Formato esperado: YYYY-MM-DD") from e


class SetupConfig(BaseModel):
    """Configuração principal do sistema"""

    azure_devops: AzureDevOpsConfig
    sprint: SprintConfig
    team: str
    executors_file: str
    dayoffs_file: str
    dependencies_file: str
    output_dir: str
    timezone: str = Field(default="America/Sao_Paulo")


class DayOff(BaseModel):
    """Modelo para ausências"""

    date: str
    period: str = Field(..., pattern="^(full|morning|afternoon)$")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> datetime:
        """Valida e converte a string de data para datetime"""
        try:
            return datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Data inválida: {v}. Formato esperado: YYYY-MM-DD") from e


class Executor(BaseModel):
    """Modelo para executor"""

    email: str
    capacity: int

    def __hash__(self) -> int:
        """Retorna o hash do executor baseado no email em lowercase"""
        return hash(self.email.lower())

    def __eq__(self, other: object) -> bool:
        """Compara dois executores baseado no email em lowercase"""
        if not isinstance(other, Executor):
            return NotImplemented
        return self.email.lower() == other.email.lower()


class ExecutorsConfig(BaseModel):
    """Configuração dos executores por frente"""

    backend: List[Executor]
    frontend: List[Executor]
    qa: List[Executor]
    devops: List[Executor]


class DependenciesConfig(BaseModel):
    """Configuração de dependências entre tasks"""

    dependencies: Dict[str, List[str]]
