from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from loguru import logger
from ..models.entities import (
    Task,
    UserStory,
    Sprint,
    WorkFront,
    TaskStatus,
    SprintMetrics,
)
from ..models.config import DayOff, ExecutorsConfig, Executor
import random


class SprintScheduler:
    """Serviço responsável pelo agendamento de tasks na sprint"""

    def __init__(
        self,
        sprint: Sprint,
        executors: ExecutorsConfig,
        dayoffs: Dict[str, List[DayOff]],
    ):
        """
        Inicializa o agendador de sprint

        Args:
            sprint: Sprint a ser agendada
            executors: Configuração dos executores por frente
            dayoffs: Dicionário de ausências por executor
        """
        self.sprint = sprint
        self.executors = executors
        # Normaliza as chaves do dicionário de dayoffs para lowercase
        self.dayoffs = {k.lower(): v for k, v in dayoffs.items()}

        # Define timezone padrão como UTC-3 (Brasília)
        self.timezone = timezone(timedelta(hours=-3))

        # Define horários fixos para os períodos (em UTC-3)
        self.morning_start = time(9, 0)
        self.morning_end = time(12, 0)
        self.afternoon_start = time(14, 0)
        self.afternoon_end = time(17, 0)

        # Usa o objeto SprintMetrics existente na Sprint
        self.metrics = sprint.metrics

        # Inicializa o dicionário de capacity atual dos executores
        self._initialize_executor_capacity()

    def _initialize_executor_capacity(self) -> None:
        """Inicializa a capacity atual de cada executor"""
        self.executor_capacity = {}

        # Obtém todos os executores únicos de todas as frentes
        all_executors = set()
        for front in WorkFront:
            executors_list = getattr(self.executors, front.value, [])
            all_executors.update(executors_list)

        # Inicializa a capacity de cada executor
        for executor in all_executors:
            total_capacity = self._calculate_executor_availability(executor)
            self.executor_capacity[executor.email.lower()] = total_capacity
            self.metrics.update_capacity(executor.email, total_capacity, 0)
            logger.info(
                f"Capacity inicial do executor {executor.email}: {total_capacity:.1f}h"
            )

    def _update_executor_capacity(self, executor: str, hours: float) -> None:
        """
        Atualiza a capacity atual de um executor

        Args:
            executor: Email do executor
            hours: Horas a serem deduzidas da capacity
        """
        executor_key = executor.lower()
        if executor_key in self.executor_capacity:
            self.executor_capacity[executor_key] -= hours
            total = self.metrics.total_capacity.get(executor, 0)
            used = self.metrics.used_capacity.get(executor, 0) + hours
            self.metrics.update_capacity(executor, total, used)
            logger.info(
                f"Capacity atualizada do executor {executor}: {self.executor_capacity[executor_key]:.1f}h"
            )

    def _get_executor_current_capacity(self, executor: str) -> float:
        """
        Obtém a capacity atual de um executor

        Args:
            executor: Email do executor

        Returns:
            float: Capacity atual do executor
        """
        return self.executor_capacity.get(executor.lower(), 0.0)

    def _create_datetime(
        self, base_date: datetime, hour: int, minute: int = 0
    ) -> datetime:
        """
        Cria um objeto datetime com a timezone correta

        Args:
            base_date: Data base para criar o novo datetime
            hour: Hora desejada
            minute: Minuto desejado (default 0)

        Returns:
            datetime: Novo objeto datetime com timezone UTC-3
        """
        # Se a data base não tem timezone, assume UTC-3
        if base_date.tzinfo is None:
            base_date = base_date.replace(tzinfo=self.timezone)
        # Se a data base tem timezone diferente, converte para UTC-3
        elif base_date.tzinfo != self.timezone:
            base_date = base_date.astimezone(self.timezone)

        # Cria novo datetime mantendo a mesma data
        return datetime(
            base_date.year,
            base_date.month,
            base_date.day,
            hour,
            minute,
            tzinfo=self.timezone,
        )

    def schedule(self) -> None:
        """Agenda todas as tasks da sprint"""
        logger.info(f"Iniciando agendamento da sprint {self.sprint.name}")

        # Primeiro agenda todas as User Stories
        for us in self.sprint.user_stories:
            self._schedule_user_story(us)

        # Coleta todas as tasks bloqueadas da sprint
        blocked_tasks = []
        blocked_qa_plan_tasks = []
        for us in self.sprint.user_stories:
            for task in us.tasks:
                if task.status == TaskStatus.BLOCKED:
                    blocked_tasks.append(task)
                elif task.is_qa_test_plan and task.status != TaskStatus.SCHEDULED:
                    blocked_qa_plan_tasks.append(task)

        # Tenta agendar as tasks bloqueadas após todas as User Stories
        if blocked_tasks:
            logger.info(
                f"Tentando agendar {len(blocked_tasks)} tasks bloqueadas após todas as User Stories"
            )
            for task in blocked_tasks:
                if self._schedule_task(task):
                    logger.info(
                        f"Task {task.id} desbloqueada após agendamento de todas as User Stories"
                    )
                    # Tenta atualizar a User Story após desbloquear a task
                    us = next(
                        us
                        for us in self.sprint.user_stories
                        if us.id == task.parent_user_story_id
                    )
                    self._try_update_user_story(us)
                else:
                    logger.warning(
                        f"Task {task.id} permanece bloqueada após tentativa de agendamento"
                    )

        # Tenta agendar as tasks de plano de testes após desbloqueio de outras tasks
        if blocked_qa_plan_tasks:
            logger.info(
                f"Tentando agendar {len(blocked_qa_plan_tasks)} tasks de plano de testes após desbloqueio de outras tasks"
            )
            for task in blocked_qa_plan_tasks:
                us = next(
                    us
                    for us in self.sprint.user_stories
                    if us.id == task.parent_user_story_id
                )
                self._schedule_qa_plan_task(task, us)
                if task.status == TaskStatus.SCHEDULED:
                    logger.info(
                        f"Task de plano de testes {task.id} agendada após desbloqueio de outras tasks"
                    )
                    self._try_update_user_story(us)
                else:
                    logger.warning(
                        f"Task de plano de testes {task.id} permanece bloqueada"
                    )

        logger.info("Agendamento da sprint concluído")

    def _schedule_user_story(self, us: UserStory) -> None:
        """
        Agenda todas as tasks de uma User Story

        Args:
            us: User Story a ser agendada
        """
        logger.info(f"Agendando User Story {us.id}: {us.title}")

        # Lista de tasks bloqueadas por dependências
        blocked_tasks = []

        # Primeiro agenda tasks regulares (não-QA e não-DevOps)
        regular_tasks = [
            t
            for t in us.tasks
            if not (
                t.is_qa_test_plan or t.is_devops_task or t.work_front == WorkFront.QA
            )
        ]
        logger.info(
            f"US {us.id} - Tasks regulares encontradas: {[t.id for t in regular_tasks]}"
        )

        # Ordena as tasks por número de dependências (menos dependências primeiro)
        regular_tasks.sort(key=lambda t: len(t.dependencies) if t.dependencies else 0)

        # Agenda tasks em loop até que todas estejam agendadas ou não haja mais progresso
        while regular_tasks:
            progress = False
            still_to_schedule = []

            for task in regular_tasks:
                logger.info(f"Processando task {task.id} como task regular")
                if not self._schedule_task(task):
                    # Se a task não pode ser agendada, verifica se é por dependência
                    if task.dependencies:
                        blocked_tasks.append(task)
                        logger.info(
                            f"Task {task.id} bloqueada por dependências: {task.dependencies}"
                        )
                    else:
                        still_to_schedule.append(task)
                        logger.info(
                            f"Task {task.id} não pôde ser agendada, será tentada novamente"
                        )
                else:
                    progress = True
                    # Tenta agendar tasks bloqueadas após cada agendamento bem sucedido
                    still_blocked = []
                    for blocked_task in blocked_tasks:
                        logger.info(
                            f"Tentando agendar task bloqueada {blocked_task.id} após sucesso da task {task.id}"
                        )
                        if self._schedule_task(blocked_task):
                            logger.info(
                                f"Task {blocked_task.id} desbloqueada após agendamento da task {task.id}"
                            )
                            progress = True
                        else:
                            still_blocked.append(blocked_task)
                            logger.info(f"Task {blocked_task.id} permanece bloqueada")
                    blocked_tasks = still_blocked

            # Se não houve progresso e ainda há tasks para agendar, para o loop
            if not progress and regular_tasks:
                logger.info(
                    f"US {us.id} - Sem progresso no agendamento de tasks regulares, finalizando loop"
                )
                break

            regular_tasks = still_to_schedule

        # Tenta agendar tasks bloqueadas uma última vez após todas as tasks regulares
        if blocked_tasks:
            logger.info(
                f"Tentando agendar {len(blocked_tasks)} tasks bloqueadas após agendamento de todas as tasks regulares"
            )
            still_blocked = []
            for blocked_task in blocked_tasks:
                logger.info(
                    f"Tentativa final de agendamento para task bloqueada {blocked_task.id}"
                )
                if self._schedule_task(blocked_task):
                    logger.info(
                        f"Task {blocked_task.id} desbloqueada após agendamento de todas as tasks regulares"
                    )
                else:
                    still_blocked.append(blocked_task)
                    logger.info(
                        f"Task {blocked_task.id} permanece bloqueada após tentativa final"
                    )
            blocked_tasks = still_blocked

        # Depois agenda tasks de QA (exceto plano de testes)
        qa_tasks = [
            t
            for t in us.tasks
            if not t.is_qa_test_plan and t.work_front == WorkFront.QA
        ]
        logger.info(f"US {us.id} - Tasks de QA encontradas: {[t.id for t in qa_tasks]}")

        for task in qa_tasks:
            logger.info(f"Processando task {task.id} como task de QA")
            self._schedule_qa_task(task, us)

        # Depois agenda tasks DevOps
        devops_tasks = [t for t in us.tasks if t.is_devops_task]
        logger.info(
            f"US {us.id} - Tasks DevOps encontradas: {[t.id for t in devops_tasks]}"
        )

        for task in devops_tasks:
            logger.info(f"Processando task {task.id} como task DevOps")
            self._schedule_devops_task(task, us)

        # Por fim agenda tasks de QA Plano de Testes
        qa_plan_tasks = [t for t in us.tasks if t.is_qa_test_plan]
        logger.info(
            f"US {us.id} - Tasks de Plano de Testes encontradas: {[t.id for t in qa_plan_tasks]}"
        )

        for task in qa_plan_tasks:
            logger.info(f"Processando task {task.id} como task de Plano de Testes")
            self._schedule_qa_plan_task(task, us)

        # Tenta atualizar a US após agendar todas as tasks
        self._try_update_user_story(us)

        # Registra tasks que permaneceram bloqueadas
        if blocked_tasks:
            logger.warning(
                f"Tasks que permaneceram bloqueadas na US {us.id}: {[t.id for t in blocked_tasks]}"
            )

    def _try_update_user_story(self, us: UserStory) -> None:
        """
        Atualiza os dados da User Story considerando todas as tasks, mesmo as não agendadas

        Args:
            us: User Story a ser atualizada
        """
        # Considera todas as tasks ativas (exceto plano de testes que não tem data de fim)
        active_tasks = [
            t
            for t in us.tasks
            if t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]
        ]

        # Calcula responsável (executor com mais tasks agendadas)
        assignee_count = {}
        assignee_fronts = {}  # Mapeia executores para suas frentes de trabalho

        # Considera apenas tasks agendadas para definir o responsável
        scheduled_tasks = [t for t in active_tasks if t.status == TaskStatus.SCHEDULED]

        for task in scheduled_tasks:
            if task.assignee:
                assignee_count[task.assignee] = assignee_count.get(task.assignee, 0) + 1
                # Guarda a frente de trabalho do executor
                if task.assignee not in assignee_fronts:
                    assignee_fronts[task.assignee] = task.work_front

        if assignee_count:
            # Encontra o maior número de tasks
            max_tasks = max(assignee_count.values())
            # Pega todos os executores com esse número de tasks
            top_assignees = [a for a, c in assignee_count.items() if c == max_tasks]

            if len(top_assignees) == 1:
                # Se só tem um executor com mais tasks, ele é o escolhido
                us.assignee = top_assignees[0]
            else:
                # Se tem empate, prioriza backend/frontend
                priority_fronts = [WorkFront.BACKEND, WorkFront.FRONTEND]
                for front in priority_fronts:
                    # Procura executor com a frente prioritária
                    for assignee in top_assignees:
                        if assignee_fronts.get(assignee) == front:
                            us.assignee = assignee
                            break
                    if us.assignee:  # Se encontrou, para de procurar
                        break

            # Se não encontrou nenhum backend/frontend, usa o primeiro da lista
            if not us.assignee and top_assignees:
                us.assignee = top_assignees[0]

        # Calcula datas considerando apenas as tasks agendadas
        start_dates = [t.start_date for t in scheduled_tasks if t.start_date]
        end_dates = [t.azure_end_date for t in scheduled_tasks if t.azure_end_date]

        if start_dates and end_dates:
            us.start_date = min(start_dates)
            us.end_date = max(end_dates)

        # Calcula story points baseado apenas nas tasks agendadas
        total_estimated_hours = sum(
            t.estimated_hours for t in scheduled_tasks if t.estimated_hours
        )

        # Tabela de conversão de horas para story points conforme regras
        if total_estimated_hours <= 1:
            us.story_points = 0.5
        elif total_estimated_hours <= 2:
            us.story_points = 1
        elif total_estimated_hours <= 3:
            us.story_points = 2
        elif total_estimated_hours <= 5:
            us.story_points = 3
        elif total_estimated_hours <= 9:
            us.story_points = 5
        elif total_estimated_hours <= 14:
            us.story_points = 8
        elif total_estimated_hours <= 23:
            us.story_points = 13
        elif total_estimated_hours <= 37:
            us.story_points = 21
        elif total_estimated_hours <= 60:
            us.story_points = 34
        else:
            us.story_points = 55

        logger.info(
            f"User Story {us.id} atualizada: "
            f"responsável={us.assignee}, início={us.start_date}, fim={us.end_date}, "
            f"SP={us.story_points}, horas_totais={total_estimated_hours}"
        )

    def _adjust_time_to_period_end(self, date: datetime) -> datetime:
        """
        Ajusta o horário para o fim do período mais próximo

        Args:
            date: Data com horário a ser ajustado

        Returns:
            datetime: Data com horário ajustado para o fim do período
        """
        time = date.time()

        # Se está no período da manhã (9:00-12:00)
        if self.morning_start <= time <= self.morning_end:
            return self._create_datetime(date, 12)
        # Se está no período da tarde (14:00-17:00)
        elif self.afternoon_start <= time <= self.afternoon_end:
            return self._create_datetime(date, 17)
        # Se está entre os períodos, ajusta para o próximo período
        elif time < self.morning_start:
            return self._create_datetime(date, 12)
        elif time < self.afternoon_start:
            return self._create_datetime(date, 17)
        else:
            # Se passou do fim do dia, vai para o próximo dia
            next_date = date + timedelta(days=1)
            return self._create_datetime(next_date, 12)

    def _schedule_task(self, task: Task) -> bool:
        """
        Agenda uma task regular

        Args:
            task: Task a ser agendada

        Returns:
            bool: True se a task foi agendada com sucesso, False se ficou bloqueada
        """
        if task.status in [TaskStatus.CLOSED, TaskStatus.CANCELLED]:
            logger.info(f"Task {task.id} já está fechada ou cancelada")
            return True

        # Atribui executor se necessário
        if not task.assignee:
            task.assignee = self._get_best_executor(task)

        if not task.assignee:
            logger.error(f"Não foi possível encontrar executor para task {task.id}")
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem executor disponível",
                user_story_id=task.parent_user_story_id,
            )
            return False

        # Verifica se todas as dependências estão agendadas
        if not self._check_dependencies(task):
            logger.info(f"Task {task.id} aguardando agendamento de dependências")
            task.status = TaskStatus.BLOCKED
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="aguardando agendamento de dependências",
                user_story_id=task.parent_user_story_id,
            )
            return False

        # Verifica se o executor tem capacity suficiente
        current_capacity = self._get_executor_current_capacity(task.assignee)
        if current_capacity < task.estimated_hours:
            logger.warning(
                f"Executor {task.assignee} não tem capacity suficiente para task {task.id}. "
                f"Disponível: {current_capacity:.1f}h, Necessário: {task.estimated_hours:.1f}h"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="falta de capacity",
                user_story_id=task.parent_user_story_id,
            )
            return False

        # Calcula datas de início e fim usando o executor atribuído
        start_date = self._get_earliest_start_date(task)

        if not start_date:
            logger.error(
                f"Não foi possível calcular data de início para task {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem data de início disponível",
                user_story_id=task.parent_user_story_id,
            )
            return False

        end_date = self._calculate_end_date(task, start_date)

        if not end_date:
            logger.error(f"Não foi possível calcular data de fim para task {task.id}")
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem data de fim disponível",
                user_story_id=task.parent_user_story_id,
            )
            return False

        # Armazena a data real de término e a data para o Azure DevOps
        task.start_date = start_date
        task.end_date = end_date
        task.azure_end_date = self._convert_to_azure_time(end_date)
        task.status = TaskStatus.SCHEDULED

        # Atualiza a capacity do executor
        self._update_executor_capacity(task.assignee, task.estimated_hours)

        logger.info(
            f"Task {task.id} agendada para {task.assignee} de {start_date} até {task.end_date} (Azure: {task.azure_end_date})"
        )
        logger.info(
            f"Task {task.id} - Detalhes das datas: start_date={start_date}, end_date={end_date}, azure_end_date={task.azure_end_date}"
        )
        logger.info(
            f"Task {task.id} - Capacity do executor {task.assignee} após agendamento: {self._get_executor_current_capacity(task.assignee):.1f}h"
        )
        return True

    def _schedule_devops_task(self, task: Task, us: UserStory) -> bool:
        """
        Agenda uma task de DevOps

        Args:
            task: Task de DevOps a ser agendada
            us: User Story pai

        Returns:
            bool: True se a task foi agendada com sucesso, False se ficou bloqueada
        """
        if task.status in [TaskStatus.CLOSED, TaskStatus.CANCELLED]:
            logger.info(f"Task DevOps {task.id} já está fechada ou cancelada")
            return True

        # Atribui executor se necessário
        if not task.assignee:
            task.assignee = self._get_best_executor(task)

        if not task.assignee:
            logger.error(
                f"Não foi possível encontrar executor para task DevOps {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem executor disponível",
                user_story_id=us.id,
            )
            return False

        # Pega todas as tasks agendadas da US
        scheduled_tasks = [t for t in us.tasks if t.status == TaskStatus.SCHEDULED]

        # Primeiro tenta pegar data das tasks de backend
        backend_tasks = [
            t for t in scheduled_tasks if t.work_front == WorkFront.BACKEND
        ]
        start_date = None

        if backend_tasks:
            backend_dates = [t.end_date for t in backend_tasks if t.end_date]
            if backend_dates:
                start_date = max(backend_dates)
                logger.info(
                    f"Task DevOps {task.id} iniciará após última task backend em {start_date}"
                )
        else:
            # Se não tem backend, tenta frontend
            frontend_tasks = [
                t for t in scheduled_tasks if t.work_front == WorkFront.FRONTEND
            ]
            if frontend_tasks:
                frontend_dates = [t.end_date for t in frontend_tasks if t.end_date]
                if frontend_dates:
                    start_date = max(frontend_dates)
                    logger.info(
                        f"Task DevOps {task.id} iniciará após última task frontend em {start_date}"
                    )

        # Se não tem data específica, usa a data mais cedo possível
        if not start_date:
            start_date = self._get_earliest_start_date(task)
            if not start_date:
                logger.error(
                    f"Não foi possível calcular data de início para task DevOps {task.id}"
                )
                self.metrics.add_not_scheduled_task(
                    task_id=task.id,
                    title=task.title,
                    reason="sem data de início disponível",
                    user_story_id=us.id,
                )
                return False

        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            logger.error(
                f"Não foi possível calcular data de fim para task DevOps {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem data de fim disponível",
                user_story_id=us.id,
            )
            return False

        # Armazena a data real de término e a data para o Azure DevOps
        task.start_date = start_date
        task.end_date = end_date
        task.azure_end_date = self._convert_to_azure_time(end_date)
        task.status = TaskStatus.SCHEDULED

        # Atualiza a capacity do executor
        self._update_executor_capacity(task.assignee, task.estimated_hours)

        logger.info(
            f"Task DevOps {task.id} agendada para {task.assignee} de {start_date} até {task.end_date} (Azure: {task.azure_end_date})"
        )
        logger.info(
            f"Task DevOps {task.id} - Detalhes das datas: start_date={start_date}, end_date={end_date}, azure_end_date={task.azure_end_date}"
        )
        logger.info(
            f"Task DevOps {task.id} - Capacity do executor {task.assignee} após agendamento: {self._get_executor_current_capacity(task.assignee):.1f}h"
        )
        return True

    def _schedule_qa_plan_task(self, task: Task, us: UserStory) -> bool:
        """
        Agenda uma task de QA Plano de Testes

        Args:
            task: Task de QA Plano de Testes a ser agendada
            us: User Story pai

        Returns:
            bool: True se a task foi agendada com sucesso, False se ficou bloqueada
        """
        if task.status in [TaskStatus.CLOSED, TaskStatus.CANCELLED]:
            logger.info(f"Task QA Plano {task.id} já está fechada ou cancelada")
            return True

        # Verifica se a task já foi agendada
        if task.status == TaskStatus.SCHEDULED:
            logger.info(f"Task QA Plano {task.id} já está agendada, ignorando")
            return True

        # Atribui executor se necessário
        if not task.assignee:
            task.assignee = self._get_best_executor(task)

        if not task.assignee:
            logger.error(
                f"Não foi possível encontrar executor para task QA Plano {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem executor disponível",
                user_story_id=us.id,
            )
            return False

        # Se a task não tem estimativa, apenas atribui o executor e marca como agendada
        if not task.estimated_hours:
            task.status = TaskStatus.SCHEDULED
            logger.info(
                f"Task QA Plano {task.id} agendada para {task.assignee} sem data de término (sem estimativa)"
            )
            return True

        # Pega todas as tasks agendadas da US
        scheduled_tasks = [t for t in us.tasks if t.status == TaskStatus.SCHEDULED]

        # Define data de início baseada nos cenários
        start_date = None

        # Cenário 1: Se a US possui mais tasks de QA, a data de início será a maior data de finalização entre as tasks de QA
        qa_tasks = [
            t
            for t in scheduled_tasks
            if t.work_front == WorkFront.QA and t.id != task.id
        ]
        if qa_tasks:
            qa_dates = [t.end_date for t in qa_tasks if t.end_date]
            if qa_dates:
                start_date = max(qa_dates)
                logger.info(
                    f"Task QA Plano {task.id} iniciará após última task QA em {start_date}"
                )

        # Cenário 2: Se a US não possui tasks de QA, a data de início deve ser a maior data de finalização entre os itens de desenvolvimento BE e FE
        if not start_date:
            # Pega tasks de backend e frontend
            backend_tasks = [
                t for t in scheduled_tasks if t.work_front == WorkFront.BACKEND
            ]
            frontend_tasks = [
                t for t in scheduled_tasks if t.work_front == WorkFront.FRONTEND
            ]

            # Pega as datas de término
            backend_dates = [t.end_date for t in backend_tasks if t.end_date]
            frontend_dates = [t.end_date for t in frontend_tasks if t.end_date]

            # Combina as datas e pega a maior
            all_dates = backend_dates + frontend_dates
            if all_dates:
                start_date = max(all_dates)
                logger.info(
                    f"Task QA Plano {task.id} iniciará após última task de desenvolvimento em {start_date}"
                )

        # Cenário 3: Se a US não possuir outros tipo de tasks, deve considerar a data de início a data mais cedo disponível pro executor
        if not start_date:
            start_date = self._get_earliest_start_date(task)
            if not start_date:
                logger.error(
                    f"Não foi possível calcular data de início para task QA Plano {task.id}"
                )
                self.metrics.add_not_scheduled_task(
                    task_id=task.id,
                    title=task.title,
                    reason="sem data de início disponível",
                    user_story_id=us.id,
                )
                return False

        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            logger.error(
                f"Não foi possível calcular data de fim para task QA Plano {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem data de fim disponível",
                user_story_id=us.id,
            )
            return False

        # Armazena a data real de término e a data para o Azure DevOps
        task.start_date = start_date
        task.end_date = end_date
        task.azure_end_date = self._convert_to_azure_time(end_date)
        task.status = TaskStatus.SCHEDULED

        # Atualiza a capacity do executor
        self._update_executor_capacity(task.assignee, task.estimated_hours)

        logger.info(
            f"Task QA Plano {task.id} agendada para {task.assignee} de {start_date} até {task.end_date} (Azure: {task.azure_end_date})"
        )
        logger.info(
            f"Task QA Plano {task.id} - Detalhes das datas: start_date={start_date}, end_date={end_date}, azure_end_date={task.azure_end_date}"
        )
        logger.info(
            f"Task QA Plano {task.id} - Capacity do executor {task.assignee} após agendamento: {self._get_executor_current_capacity(task.assignee):.1f}h"
        )
        return True

    def _check_dependencies(self, task: Task) -> bool:
        """
        Verifica se todas as dependências de uma task estão satisfeitas

        Args:
            task: Task a ser verificada

        Returns:
            bool: True se todas as dependências estão satisfeitas
        """
        if not task.dependencies:
            return True

        all_tasks = self.sprint.get_all_tasks()
        task_dict = {t.id: t for t in all_tasks}

        for dep_id in task.dependencies:
            if dep_id not in task_dict:
                logger.error(f"Dependência {dep_id} não encontrada")
                return False

            dep_task = task_dict[dep_id]
            if dep_task.status != TaskStatus.SCHEDULED:
                return False

        return True

    def _get_best_executor(self, task: Task) -> Optional[str]:
        """
        Encontra o melhor executor para uma task, tentando todos os executores disponíveis da mesma frente

        Args:
            task: Task a ser atribuída

        Returns:
            Optional[str]: Email do melhor executor ou None se não encontrar
        """
        # Obtém lista de executores da frente
        executors_list = getattr(self.executors, task.work_front.value, [])
        if not executors_list:
            return None

        # Verifica se já existe executor para a frente na US
        us = [
            us for us in self.sprint.user_stories if us.id == task.parent_user_story_id
        ][0]
        front_tasks = [
            t
            for t in us.tasks
            if t.work_front == task.work_front
            and t.assignee
            and t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]
        ]

        # Se já existe executor para a frente, tenta primeiro ele
        if front_tasks:
            current_executor = front_tasks[0].assignee
            if (
                self._get_executor_current_capacity(current_executor)
                >= task.estimated_hours
            ):
                # Tenta agendar com o executor atual
                task.assignee = current_executor
                if self._try_schedule_task(task):
                    return current_executor
                # Se não conseguiu agendar, remove o executor e continua com os outros
                task.assignee = None

        # Randomiza a ordem dos executores para evitar sempre o mesmo primeiro
        executors_list = executors_list[:]
        random.shuffle(executors_list)

        # Tenta cada executor disponível
        for executor in executors_list:
            # Verifica se o executor tem capacity suficiente
            current_capacity = self._get_executor_current_capacity(executor.email)
            if current_capacity < task.estimated_hours:
                continue

            # Tenta agendar com este executor
            task.assignee = executor.email
            if self._try_schedule_task(task):
                return executor.email

            # Se não conseguiu agendar, remove o executor e continua com os outros
            task.assignee = None

        # Se chegou aqui, não conseguiu agendar com nenhum executor
        return None

    def _try_schedule_task(self, task: Task) -> bool:
        """
        Tenta agendar uma task com o executor atual

        Args:
            task: Task a ser agendada

        Returns:
            bool: True se conseguiu agendar, False caso contrário
        """
        # Calcula data de início
        start_date = self._get_earliest_start_date(task)
        if not start_date:
            return False

        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            return False

        # Se chegou aqui, conseguiu agendar
        return True

    def _calculate_executor_availability(self, executor: Executor) -> float:
        """
        Calcula a disponibilidade de um executor em horas

        Args:
            executor: Executor

        Returns:
            float: Horas disponíveis
        """
        # Calcula total de horas de ausência (usando email em lowercase)
        dayoff_hours = 0
        executor_dayoffs = self.dayoffs.get(executor.email.lower(), [])
        for dayoff in executor_dayoffs:
            if dayoff.period == "full":
                dayoff_hours += 6
            else:
                dayoff_hours += 3

        # Calcula total de dias úteis na sprint
        current_date = self.sprint.start_date
        working_days = 0

        while current_date <= self.sprint.end_date:
            # Verifica se é dia útil (não é fim de semana)
            if current_date.weekday() < 5:
                working_days += 1

            current_date += timedelta(days=1)

        # Calcula total de horas disponíveis (6 horas por dia útil)
        total_hours = working_days * executor.capacity

        # Subtrai apenas as horas de ausência
        return total_hours - dayoff_hours

    def _get_earliest_start_date(self, task: Task) -> Optional[datetime]:
        """
        Calcula a primeira data possível para início da task

        Args:
            task: Task a ser agendada

        Returns:
            Optional[datetime]: Data mais cedo possível ou None se não encontrar
        """
        if not task.assignee:
            logger.error(
                f"Task {task.id} sem executor atribuído ao calcular data de início"
            )
            return None

        # Primeiro verifica a última task do executor
        earliest_date = self._get_executor_earliest_date(task)

        # Depois verifica as dependências
        dep_date = self._get_dependencies_earliest_date(task)

        # Retorna a data mais tarde entre as restrições
        if earliest_date and dep_date:
            return max(earliest_date, dep_date)
        return earliest_date or dep_date or None

    def _get_executor_earliest_date(self, task: Task) -> Optional[datetime]:
        """
        Calcula a primeira data possível baseada nas tasks anteriores do executor

        Args:
            task: Task a ser agendada

        Returns:
            Optional[datetime]: Data mais cedo possível baseada no executor ou None se não encontrar
        """
        # Pega todas as tasks já agendadas do executor
        executor_tasks = [
            t
            for t in self.sprint.get_tasks_by_assignee(task.assignee)
            if t.status == TaskStatus.SCHEDULED  # Considera apenas tasks já agendadas
            and t.end_date is not None
            and t.id != task.id
        ]  # Exclui a própria task

        if executor_tasks:
            # Ordena tasks por data de término
            sorted_tasks = sorted(executor_tasks, key=lambda t: t.end_date)
            latest_task = sorted_tasks[-1]
            latest_exec_date = latest_task.end_date

            # Garante que a data está na timezone correta
            if latest_exec_date.tzinfo != self.timezone:
                latest_exec_date = latest_exec_date.astimezone(self.timezone)

            # Calcula horas restantes no período da última task
            current_time = latest_exec_date.time()

            # Se a task anterior terminou no fim do período
            if current_time == self.morning_end:
                # Se terminou às 12:00, começa às 14:00
                logger.info(
                    f"Task {task.id} iniciará à tarde após task {latest_task.id} que terminou às 12:00"
                )
                return self._create_datetime(latest_exec_date, 14)
            elif current_time == self.afternoon_end:
                # Se terminou às 17:00, começa às 9:00 do próximo dia
                next_date = latest_exec_date + timedelta(days=1)
                logger.info(
                    f"Task {task.id} iniciará no próximo dia após task {latest_task.id} que terminou às 17:00"
                )
                return self._create_datetime(next_date, 9)
            else:
                # Se terminou em outro horário, verifica se ainda há tempo no período
                if current_time < self.morning_end:
                    # Se está de manhã e ainda há tempo, continua no mesmo período
                    logger.info(
                        f"Task {task.id} iniciará após task {latest_task.id} no mesmo período da manhã"
                    )
                    return latest_exec_date
                elif current_time < self.afternoon_end:
                    # Se está à tarde e ainda há tempo, continua no mesmo período
                    logger.info(
                        f"Task {task.id} iniciará após task {latest_task.id} no mesmo período da tarde"
                    )
                    return latest_exec_date
                else:
                    # Se passou do fim do período, vai para o próximo
                    if current_time >= self.afternoon_end:
                        next_date = latest_exec_date + timedelta(days=1)
                        logger.info(
                            f"Task {task.id} iniciará no próximo dia após task {latest_task.id} que passou do fim do período"
                        )
                        return self._create_datetime(next_date, 9)
                    else:
                        logger.info(
                            f"Task {task.id} iniciará à tarde após task {latest_task.id} que passou do fim do período da manhã"
                        )
                        return self._create_datetime(latest_exec_date, 14)

        # Se não tem task anterior do executor, usa o início da sprint
        current_date = self.sprint.start_date
        # Garante que a data está na timezone correta
        if current_date.tzinfo != self.timezone:
            current_date = current_date.astimezone(self.timezone)

        # Procura o primeiro período útil para o executor
        while not self._is_working_day(current_date, task.assignee):
            current_date = current_date + timedelta(days=1)

        logger.info(
            f"Task {task.id} iniciará no primeiro dia útil da sprint para o executor {task.assignee}"
        )
        return self._create_datetime(current_date, 9)

    def _get_dependencies_earliest_date(self, task: Task) -> Optional[datetime]:
        """
        Calcula a primeira data possível baseada nas dependências da task

        Args:
            task: Task a ser agendada

        Returns:
            Optional[datetime]: Data mais cedo possível baseada nas dependências ou None se não houver
        """
        if not task.dependencies:
            return None

        all_tasks = self.sprint.get_all_tasks()
        task_dict = {t.id: t for t in all_tasks}
        dep_dates = []

        for dep_id in task.dependencies:
            if dep_id in task_dict and task_dict[dep_id].end_date:
                dep_task = task_dict[dep_id]
                dep_dates.append(dep_task.end_date)
                logger.info(
                    f"Task {task.id} depende da task {dep_id} que termina em {dep_task.end_date}"
                )

        if dep_dates:
            latest_dep_date = max(dep_dates)
            # Garante que a data está na timezone correta
            if latest_dep_date.tzinfo != self.timezone:
                latest_dep_date = latest_dep_date.astimezone(self.timezone)
            return latest_dep_date

        return None

    def _calculate_end_date(
        self, task: Task, start_date: datetime
    ) -> Optional[datetime]:
        """
        Calcula a data de término de uma task

        Args:
            task: Task a ser agendada
            start_date: Data de início

        Returns:
            Optional[datetime]: Data de término ou None se não for possível calcular
        """
        # Garante que a data de início está na timezone correta
        current_date = (
            start_date
            if start_date.tzinfo
            else start_date.replace(tzinfo=self.timezone)
        )
        if current_date.tzinfo != self.timezone:
            current_date = current_date.astimezone(self.timezone)

        remaining_hours = task.estimated_hours
        real_end_date = None

        # Pega todas as tasks já agendadas do executor
        executor_tasks = [
            t
            for t in self.sprint.get_tasks_by_assignee(task.assignee)
            if t.status == TaskStatus.SCHEDULED
            and t.end_date is not None
            and t.id != task.id
        ]

        while remaining_hours > 0:
            # Verifica se a data atual já passou do fim da sprint
            if current_date.date() > self.sprint.end_date.date():
                logger.error(
                    f"Task {task.id} não pode ser agendada pois ultrapassa a data de finalização da sprint ({self.sprint.end_date.date()})"
                )
                return None

            current_time = current_date.time()

            # Determina em qual período estamos e quantas horas disponíveis
            if current_time < self.morning_start:
                # Antes do início da manhã
                current_date = self._create_datetime(current_date, 9)
                if not self._is_working_day(current_date, task.assignee):
                    # Se não pode trabalhar de manhã, tenta a tarde
                    current_date = self._create_datetime(current_date, 14)
                    if not self._is_working_day(current_date, task.assignee):
                        # Se não pode trabalhar em nenhum período, vai para o próximo dia
                        current_date = self._create_datetime(
                            current_date + timedelta(days=1), 9
                        )
                        continue
                period_end = (
                    self.afternoon_end
                    if current_date.time() >= self.afternoon_start
                    else self.morning_end
                )

            elif self.morning_start <= current_time < self.morning_end:
                # Período da manhã
                if not self._is_working_day(current_date, task.assignee):
                    # Se não pode trabalhar de manhã, tenta a tarde
                    current_date = self._create_datetime(current_date, 14)
                    if not self._is_working_day(current_date, task.assignee):
                        # Se não pode trabalhar em nenhum período, vai para o próximo dia
                        current_date = self._create_datetime(
                            current_date + timedelta(days=1), 9
                        )
                        continue
                period_end = (
                    self.afternoon_end
                    if current_date.time() >= self.afternoon_start
                    else self.morning_end
                )

            elif self.morning_end <= current_time < self.afternoon_start:
                # Entre períodos, pula para o início da tarde
                current_date = self._create_datetime(current_date, 14)
                if not self._is_working_day(current_date, task.assignee):
                    # Se não pode trabalhar à tarde, vai para o próximo dia
                    current_date = self._create_datetime(
                        current_date + timedelta(days=1), 9
                    )
                    continue
                period_end = self.afternoon_end

            elif self.afternoon_start <= current_time < self.afternoon_end:
                # Período da tarde
                if not self._is_working_day(current_date, task.assignee):
                    # Se não pode trabalhar à tarde, vai para o próximo dia
                    current_date = self._create_datetime(
                        current_date + timedelta(days=1), 9
                    )
                    continue
                period_end = self.afternoon_end

            else:
                # Passou do horário da tarde, vai para o próximo dia de manhã
                current_date = self._create_datetime(
                    current_date + timedelta(days=1), 9
                )
                continue

            # Verifica se há alguma task do executor ocupando este período
            period_start = self._create_datetime(
                current_date, 9 if current_time < self.afternoon_start else 14
            )
            period_end_dt = datetime.combine(
                current_date.date(), period_end, tzinfo=self.timezone
            )

            for executor_task in executor_tasks:
                if executor_task.start_date and executor_task.end_date:
                    # Se a task do executor está no mesmo dia
                    if executor_task.start_date.date() == current_date.date():
                        # Se a task do executor está no mesmo período
                        if (
                            executor_task.start_date.time() < period_end
                            and executor_task.end_date.time() > period_start.time()
                        ):
                            # Se a task do executor está ocupando todo o período
                            if (
                                executor_task.start_date.time() <= period_start.time()
                                and executor_task.end_date.time() >= period_end
                            ):
                                # Pula para o próximo período
                                if period_end == self.morning_end:
                                    current_date = self._create_datetime(
                                        current_date, 14
                                    )
                                else:
                                    current_date = self._create_datetime(
                                        current_date + timedelta(days=1), 9
                                    )
                                continue

            # Corrigido: cria period_end_dt com timezone
            period_end_dt = datetime.combine(
                current_date.date(), period_end, tzinfo=self.timezone
            )
            delta = (period_end_dt - current_date).total_seconds() / 3600
            hours_left_in_period = max(0, delta)

            if remaining_hours <= hours_left_in_period:
                # Termina dentro deste período
                real_end_date = current_date + timedelta(hours=remaining_hours)
                # Ajusta para o fim do período se necessário
                if real_end_date.time() > period_end:
                    real_end_date = self._create_datetime(
                        real_end_date, period_end.hour
                    )
                # Verifica se a data de término não ultrapassa o fim da sprint
                if real_end_date.date() > self.sprint.end_date.date():
                    logger.error(
                        f"Task {task.id} não pode ser agendada pois ultrapassa a data de finalização da sprint ({self.sprint.end_date.date()})"
                    )
                    return None
                return real_end_date
            else:
                # Consome todo o período e avança
                remaining_hours -= hours_left_in_period

                # Avança para o próximo período útil
                if period_end == self.morning_end:
                    # Vai para o início da tarde do mesmo dia
                    current_date = self._create_datetime(current_date, 14)
                else:
                    # Vai para o início da manhã do próximo dia
                    current_date = self._create_datetime(
                        current_date + timedelta(days=1), 9
                    )

        # Se chegou aqui, retorna o horário atual
        return current_date

    def _is_working_day(self, date: datetime, executor: str) -> bool:
        """
        Verifica se é um dia útil para o executor em um determinado horário

        Args:
            date: Data e hora a ser verificada
            executor: Email do executor

        Returns:
            bool: True se é dia útil e não tem ausência no horário especificado
        """
        # Verifica se é fim de semana
        if date.weekday() >= 5:
            return False

        # Normaliza a data para YYYY-MM-DD
        normalized_date = date.strftime("%Y-%m-%d")
        current_time = date.time()

        # Verifica se tem ausência (usando email em lowercase)
        executor_dayoffs = self.dayoffs.get(executor.lower(), [])
        for dayoff in executor_dayoffs:
            # Normaliza a data do dayoff para YYYY-MM-DD
            normalized_dayoff_date = dayoff.date.strftime("%Y-%m-%d")

            # Se não é o mesmo dia, continua verificando
            if normalized_dayoff_date != normalized_date:
                continue

            # Se é ausência dia inteiro, retorna False
            if dayoff.period == "full":
                return False

            # Se é ausência de manhã e estamos no período da manhã
            if (
                dayoff.period == "morning"
                and self.morning_start <= current_time <= self.morning_end
            ):
                return False

            # Se é ausência de tarde e estamos no período da tarde
            if (
                dayoff.period == "afternoon"
                and self.afternoon_start <= current_time <= self.afternoon_end
            ):
                return False

        return True

    def _schedule_qa_task(self, task: Task, us: UserStory) -> bool:
        """
        Agenda uma task de QA (não plano de testes)

        Args:
            task: Task de QA a ser agendada
            us: User Story pai

        Returns:
            bool: True se a task foi agendada com sucesso, False se ficou bloqueada
        """
        if task.status in [TaskStatus.CLOSED, TaskStatus.CANCELLED]:
            logger.info(f"Task QA {task.id} já está fechada ou cancelada")
            return True

        # Verifica se a task já foi agendada
        if task.status == TaskStatus.SCHEDULED:
            logger.info(f"Task QA {task.id} já está agendada, ignorando")
            return True

        # Atribui executor se necessário
        if not task.assignee:
            task.assignee = self._get_best_executor(task)

        if not task.assignee:
            logger.error(f"Não foi possível encontrar executor para task QA {task.id}")
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem executor disponível",
                user_story_id=us.id,
            )
            return False

        # Verifica se o executor tem capacity suficiente
        current_capacity = self._get_executor_current_capacity(task.assignee)
        if current_capacity < task.estimated_hours:
            logger.warning(
                f"Executor {task.assignee} não tem capacity suficiente para task QA {task.id}. "
                f"Disponível: {current_capacity:.1f}h, Necessário: {task.estimated_hours:.1f}h"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="falta de capacity",
                user_story_id=us.id,
            )
            return False

        # Determina se é task de backend ou frontend baseado no título
        is_backend_qa = "backend" in task.title.lower()
        is_frontend_qa = "frontend" in task.title.lower()

        # Pega todas as tasks agendadas da US
        scheduled_tasks = [t for t in us.tasks if t.status == TaskStatus.SCHEDULED]

        # Define data de início baseada no tipo de QA
        start_date = None

        # Pega todas as tasks do executor
        executor_tasks = [
            t
            for t in self.sprint.get_tasks_by_assignee(task.assignee)
            if t.status == TaskStatus.SCHEDULED
        ]

        if is_backend_qa:
            # Pega a maior data entre:
            # 1. Última data de término das tasks de backend da US
            # 2. Última data de término das tasks do executor
            backend_tasks = [
                t for t in scheduled_tasks if t.work_front == WorkFront.BACKEND
            ]
            backend_dates = [t.end_date for t in backend_tasks if t.end_date]
            executor_dates = [t.end_date for t in executor_tasks if t.end_date]

            all_dates = backend_dates + executor_dates
            if all_dates:
                start_date = max(all_dates)
                logger.info(
                    f"Task QA Backend {task.id} iniciará após última task backend em {start_date}"
                )
        elif is_frontend_qa:
            # Pega a maior data entre:
            # 1. Última data de término das tasks de frontend da US
            # 2. Última data de término das tasks do executor
            frontend_tasks = [
                t for t in scheduled_tasks if t.work_front == WorkFront.FRONTEND
            ]
            frontend_dates = [t.end_date for t in frontend_tasks if t.end_date]
            executor_dates = [t.end_date for t in executor_tasks if t.end_date]

            all_dates = frontend_dates + executor_dates
            if all_dates:
                start_date = max(all_dates)
                logger.info(
                    f"Task QA Frontend {task.id} iniciará após última task frontend em {start_date}"
                )

        # Se não tem data específica, usa a data mais cedo possível
        if not start_date:
            start_date = self._get_earliest_start_date(task)
            if not start_date:
                logger.error(
                    f"Não foi possível calcular data de início para task QA {task.id}"
                )
                self.metrics.add_not_scheduled_task(
                    task_id=task.id,
                    title=task.title,
                    reason="sem data de início disponível",
                    user_story_id=us.id,
                )
                return False

        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            logger.error(
                f"Não foi possível calcular data de fim para task QA {task.id}"
            )
            self.metrics.add_not_scheduled_task(
                task_id=task.id,
                title=task.title,
                reason="sem data de fim disponível",
                user_story_id=us.id,
            )
            return False

        # Armazena a data real de término e a data para o Azure DevOps
        task.start_date = start_date
        task.end_date = end_date
        task.azure_end_date = self._convert_to_azure_time(end_date)
        task.status = TaskStatus.SCHEDULED

        # Atualiza a capacity do executor
        self._update_executor_capacity(task.assignee, task.estimated_hours)

        logger.info(
            f"Task QA {task.id} agendada para {task.assignee} de {start_date} até {task.end_date} (Azure: {task.azure_end_date})"
        )
        logger.info(
            f"Task QA {task.id} - Detalhes das datas: start_date={start_date}, end_date={end_date}, azure_end_date={task.azure_end_date}"
        )
        logger.info(
            f"Task QA {task.id} - Capacidade do executor {task.assignee} após agendamento: {self._get_executor_current_capacity(task.assignee):.1f}h"
        )
        return True

    def _convert_to_azure_time(self, date: datetime) -> datetime:
        """
        Converte o horário de término para o formato do Azure DevOps

        Args:
            date: Data com horário real de término

        Returns:
            datetime: Data com horário ajustado para o Azure DevOps
        """
        if not date:
            return None

        # Garante que a data está na timezone correta
        if date.tzinfo != self.timezone:
            date = date.astimezone(self.timezone)

        current_time = date.time()

        # Cria uma nova data mantendo o mesmo dia, mês e ano
        new_date = datetime(date.year, date.month, date.day, tzinfo=self.timezone)

        # Se está entre 10:00 e 12:00, converte para 12:00
        if time(10, 0) <= current_time <= time(12, 0):
            return new_date.replace(hour=12, minute=0)
        # Se está entre 14:00 e 17:00, converte para 17:00
        elif time(14, 0) <= current_time <= time(17, 0):
            return new_date.replace(hour=17, minute=0)
        # Se está entre 12:00 e 14:00, mantém 12:00
        elif time(12, 0) < current_time < time(14, 0):
            return new_date.replace(hour=12, minute=0)
        # Se está antes das 10:00, converte para 12:00
        elif current_time < time(10, 0):
            return new_date.replace(hour=12, minute=0)
        # Se está depois das 17:00, converte para 17:00
        else:
            return new_date.replace(hour=17, minute=0)
