from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

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
    start_date: datetime
    end_date: datetime

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
    date: datetime
    period: str = Field(..., pattern="^(full|morning|afternoon)$")

class ExecutorsConfig(BaseModel):
    """Configuração dos executores por frente"""
    backend: List[str]
    frontend: List[str]
    qa: List[str]
    devops: List[str]

class DependenciesConfig(BaseModel):
    """Configuração de dependências entre tasks"""
    dependencies: Dict[str, List[str]] 