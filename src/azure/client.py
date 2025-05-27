from typing import Dict, List, Optional
from datetime import datetime
from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation, WorkItem
from msrest.authentication import BasicAuthentication
from loguru import logger

from ..models.entities import Task, UserStory, Sprint, WorkFront, TaskStatus

class AzureDevOpsClient:
    """Cliente para integração com o Azure DevOps"""

    def __init__(self, organization: str, project: str, token: str):
        """
        Inicializa o cliente do Azure DevOps
        
        Args:
            organization: Nome da organização
            project: Nome do projeto
            token: Token de acesso pessoal (PAT)
        """
        self.organization = organization
        self.project = project
        credentials = BasicAuthentication('', token)
        self.connection = Connection(
            base_url=f"https://dev.azure.com/{organization}",
            creds=credentials
        )
        self.wit_client = self.connection.clients.get_work_item_tracking_client()
        
        logger.info(f"Cliente Azure DevOps inicializado para {organization}/{project}")

    def get_sprint_items(self, sprint_name: str, team: str, year: str = None, quarter: str = None) -> dict:
        """
        Obtém todos os itens de trabalho de uma sprint
        
        Args:
            sprint_name: Nome da sprint (apenas o nome, ex: 2025_S13_Jun18-Jul01)
            team: Nome do time (caminho completo da área)
            year: Ano da sprint
            quarter: Quarter da sprint
            
        Returns:
            dict: Dicionário com as User Stories e suas Tasks associadas
        """
        # Monta o caminho da iteração
        iteration_path = f"{self.project}\\{year}\\{quarter}\\{sprint_name}"
        
        # Primeiro, busca as User Stories da sprint
        wiql_user_stories = f"""
        SELECT [System.Id],
               [System.Title],
               [Microsoft.VSTS.Common.BacklogPriority],
               [System.BoardColumn],
               [Microsoft.VSTS.Common.StackRank]
        FROM WorkItems
        WHERE [System.TeamProject] = '{self.project}'
        AND [System.AreaPath] = '{team}'
        AND [System.IterationPath] = '{iteration_path}'
        AND [System.WorkItemType] = 'User Story'
        ORDER BY [Microsoft.VSTS.Common.StackRank] ASC
        """
        
        # Executa query para User Stories
        us_results = self.wit_client.query_by_wiql({"query": wiql_user_stories}).work_items
        if not us_results:
            logger.warning(f"Nenhuma User Story encontrada para sprint {sprint_name}")
            return {"user_stories": [], "tasks": []}
            
        # Obtém detalhes das User Stories
        us_ids = [item.id for item in us_results]
        user_stories = self.wit_client.get_work_items(us_ids)
        for us in user_stories:
            backlog_priority = us.fields.get("Microsoft.VSTS.Common.BacklogPriority")
            stack_rank = us.fields.get("Microsoft.VSTS.Common.StackRank")
            board_column = us.fields.get("System.BoardColumn")
            logger.info(f"User Story {us.id} - BacklogPriority: {backlog_priority}, StackRank: {stack_rank}, BoardColumn: {board_column}")
        logger.info(f"Obtidas {len(user_stories)} User Stories da sprint {sprint_name}")
        
        # Agora, busca as Tasks vinculadas a essas User Stories
        tasks = []
        if us_ids:
            wiql_tasks = f"""
            SELECT [System.Id], 
                   [System.Title], 
                   [System.Parent],
                   [System.AssignedTo],
                   [System.State],
                   [Microsoft.VSTS.Scheduling.OriginalEstimate],
                   [System.Description],
                   [Microsoft.VSTS.Common.BacklogPriority],
                   [System.BoardColumn],
                   [Microsoft.VSTS.Common.StackRank]
            FROM WorkItems
            WHERE [System.TeamProject] = '{self.project}'
            AND [System.WorkItemType] = 'Task'
            AND [System.Parent] IN ({','.join(map(str, us_ids))})
            ORDER BY [Microsoft.VSTS.Common.StackRank] ASC
            """
            
            # Executa query para Tasks
            task_results = self.wit_client.query_by_wiql({"query": wiql_tasks}).work_items
            if task_results:
                task_ids = [item.id for item in task_results]
                tasks = self.wit_client.get_work_items(task_ids, expand="All")
                for task in tasks:
                    backlog_priority = task.fields.get("Microsoft.VSTS.Common.BacklogPriority")
                    stack_rank = task.fields.get("Microsoft.VSTS.Common.StackRank")
                    board_column = task.fields.get("System.BoardColumn")
                    logger.info(f"Task {task.id} - BacklogPriority: {backlog_priority}, StackRank: {stack_rank}, BoardColumn: {board_column}")
                logger.info(f"Obtidas {len(tasks)} Tasks vinculadas às User Stories")
            else:
                logger.warning("Nenhuma Task encontrada vinculada às User Stories")
        
        return {"user_stories": user_stories, "tasks": tasks}

    def convert_to_entities(self, items: dict, sprint_name: str, team: str, year: str = None, quarter: str = None) -> Sprint:
        """
        Converte itens do Azure DevOps para entidades do sistema
        
        Args:
            items: Dicionário com User Stories e Tasks do Azure DevOps
            sprint_name: Nome da sprint
            team: Nome do time
            year: Ano da sprint
            quarter: Quarter da sprint
            
        Returns:
            Sprint: Sprint com User Stories e Tasks convertidas
        """
        # Dicionário para armazenar as User Stories
        user_stories = {}
        tasks_count = 0
        
        # Processa as User Stories
        for item in items["user_stories"]:
            # Obtém as datas da User Story
            start_date = None
            end_date = None
            
            if item.fields.get("Microsoft.VSTS.Scheduling.StartDate"):
                start_date = datetime.fromisoformat(item.fields["Microsoft.VSTS.Scheduling.StartDate"].replace('Z', '+00:00'))
            
            if item.fields.get("Microsoft.VSTS.Scheduling.DueDate"):
                end_date = datetime.fromisoformat(item.fields["Microsoft.VSTS.Scheduling.DueDate"].replace('Z', '+00:00'))
            
            us = UserStory(
                id=str(item.id),
                title=item.fields["System.Title"],
                description=item.fields.get("System.Description"),
                tasks=[],
                assignee=item.fields.get("System.AssignedTo", {}).get("uniqueName") if item.fields.get("System.AssignedTo") else None,
                start_date=start_date,
                end_date=end_date,
                story_points=item.fields.get("Microsoft.VSTS.Scheduling.StoryPoints")
            )
            user_stories[us.id] = us
        
        # Processa as Tasks que já sabemos que pertencem às User Stories
        for item in items["tasks"]:
            # Log para debug
            logger.debug(f"Processando task {item.id}")
            logger.debug(f"Campos disponíveis: {item.fields}")
            
            # Verifica se a task está fechada
            state = item.fields.get("System.State", "").lower()
            if state == "closed":
                logger.info(f"Task {item.id} está fechada, ignorando")
                continue
            
            # Verifica se a task está ativa (New ou Active)
            if state not in ["new", "active"]:
                logger.info(f"Task {item.id} não está ativa (estado: {state}), ignorando")
                continue
            
            # Determina frente de trabalho pelo título
            title = item.fields["System.Title"]
            work_front = None
            if "[BE]" in title:
                work_front = WorkFront.BACKEND
            elif "[FE]" in title:
                work_front = WorkFront.FRONTEND
            elif "[QA]" in title:
                work_front = WorkFront.QA
            elif "devops" in title.lower():
                work_front = WorkFront.DEVOPS
            
            if not work_front:
                logger.warning(f"Não foi possível determinar frente de trabalho para task {item.id}: {title}")
                continue
            
            # Obtém o ID da US pai da task
            parent_ref = item.fields.get("System.Parent")
            if not parent_ref:
                logger.warning(f"Task {item.id} não tem campo System.Parent")
                continue
                
            us_id = str(parent_ref)
            if us_id not in user_stories:
                logger.warning(f"Task {item.id} tem parent_id {us_id} que não está nas User Stories obtidas")
                continue
            
            # Obtém as datas da task
            start_date = None
            end_date = None
            azure_end_date = None
            
            if item.fields.get("Microsoft.VSTS.Scheduling.StartDate"):
                start_date = datetime.fromisoformat(item.fields["Microsoft.VSTS.Scheduling.StartDate"].replace('Z', '+00:00'))
            
            if item.fields.get("Custom.CommittedDate"):
                end_date = datetime.fromisoformat(item.fields["Custom.CommittedDate"].replace('Z', '+00:00'))
                azure_end_date = end_date
            
            task = Task(
                id=str(item.id),
                title=title,
                description=item.fields.get("System.Description"),
                work_front=work_front,
                estimated_hours=float(item.fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate", 0)),
                assignee=item.fields.get("System.AssignedTo", {}).get("uniqueName") if item.fields.get("System.AssignedTo") else None,
                dependencies=[],  # Será preenchido depois
                start_date=start_date,
                end_date=end_date,
                azure_end_date=azure_end_date,
                status=TaskStatus.PENDING,  # Todas tasks ativas começam como pendentes
                parent_user_story_id=us_id
            )
            user_stories[us_id].tasks.append(task)
            tasks_count += 1
        
        # Cria sprint
        sprint = Sprint(
            name=sprint_name,
            start_date=datetime.now(),  # Será atualizado depois
            end_date=datetime.now(),    # Será atualizado depois
            user_stories=list(user_stories.values()),
            team=team
        )
        
        logger.info(f"Convertidos {len(user_stories)} User Stories e {tasks_count} Tasks")
        return sprint

    def update_work_items(self, sprint: Sprint) -> None:
        """
        Atualiza os itens de trabalho no Azure DevOps
        
        Args:
            sprint: Sprint com itens atualizados
        """
        for us in sprint.user_stories:
            # Atualiza User Story
            us_operations = []
            
            # Atualiza responsável
            if us.assignee:
                us_operations.append({
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": us.assignee
                })
                
            # Atualiza Story Points
            if us.story_points is not None:  # Permite valor 0
                us_operations.append({
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints",
                    "value": us.story_points
                })
                
            # Atualiza datas da US
            if us.start_date:
                us_operations.append({
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Scheduling.StartDate",
                    "value": us.start_date.isoformat()
                })
                
            if us.end_date:
                us_operations.extend([
                    {
                        "op": "add",
                        "path": "/fields/Custom.CommittedDate",
                        "value": us.end_date.isoformat()
                    },
                    {
                        "op": "add",
                        "path": "/fields/Microsoft.VSTS.Scheduling.DueDate",
                        "value": us.end_date.isoformat()
                    }
                ])
                
            if us_operations:
                self.wit_client.update_work_item(us_operations, int(us.id))
                logger.info(f"User Story {us.id} atualizada no Azure DevOps")
            
            # Atualiza Tasks
            for task in us.tasks:
                task_operations = []
                
                # Atualiza responsável
                if task.assignee:
                    task_operations.append({
                        "op": "add",
                        "path": "/fields/System.AssignedTo",
                        "value": task.assignee
                    })
                    
                # Atualiza datas da task
                if task.start_date:
                    task_operations.append({
                        "op": "add",
                        "path": "/fields/Microsoft.VSTS.Scheduling.StartDate",
                        "value": task.start_date.isoformat()
                    })
                    
                if task.azure_end_date:
                    task_operations.extend([
                        {
                            "op": "add",
                            "path": "/fields/Custom.CommittedDate",
                            "value": task.azure_end_date.isoformat()
                        },
                        {
                            "op": "add",
                            "path": "/fields/Microsoft.VSTS.Scheduling.DueDate",
                            "value": task.azure_end_date.isoformat()
                        }
                    ])
                    
                if task_operations:
                    self.wit_client.update_work_item(task_operations, int(task.id))
                    logger.info(f"Task {task.id} atualizada no Azure DevOps") 