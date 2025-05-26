from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from loguru import logger
from ..models.entities import Task, UserStory, Sprint, WorkFront, TaskStatus
from ..models.config import DayOff, ExecutorsConfig

class SprintScheduler:
    """Serviço responsável pelo agendamento de tasks na sprint"""

    def __init__(self, sprint: Sprint, executors: ExecutorsConfig, dayoffs: Dict[str, List[DayOff]]):
        """
        Inicializa o agendador de sprint
        
        Args:
            sprint: Sprint a ser agendada
            executors: Configuração dos executores por frente
            dayoffs: Dicionário de ausências por executor
        """
        self.sprint = sprint
        self.executors = executors
        self.dayoffs = dayoffs
        
        # Define timezone padrão como UTC-3 (Brasília)
        self.timezone = timezone(timedelta(hours=-3))
        
        # Define horários fixos para os períodos (em UTC-3)
        self.morning_start = time(9, 0)
        self.morning_end = time(12, 0)
        self.afternoon_start = time(14, 0)
        self.afternoon_end = time(17, 0)

    def _create_datetime(self, base_date: datetime, hour: int, minute: int = 0) -> datetime:
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
            
        return datetime(
            base_date.year,
            base_date.month,
            base_date.day,
            hour,
            minute,
            tzinfo=self.timezone
        )

    def schedule(self) -> None:
        """Agenda todas as tasks da sprint"""
        logger.info(f"Iniciando agendamento da sprint {self.sprint.name}")
        
        # Agenda tasks por User Story
        for us in self.sprint.user_stories:
            self._schedule_user_story(us)
            
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
        regular_tasks = [t for t in us.tasks if not (t.is_qa_test_plan or t.is_devops_task)]
        for task in regular_tasks:
            if not self._schedule_task(task):
                blocked_tasks.append(task)
            else:
                # Tenta agendar tasks bloqueadas após cada agendamento bem sucedido
                still_blocked = []
                for blocked_task in blocked_tasks:
                    if self._schedule_task(blocked_task):
                        logger.info(f"Task {blocked_task.id} desbloqueada após agendamento da task {task.id}")
                    else:
                        still_blocked.append(blocked_task)
                blocked_tasks = still_blocked
            
        # Depois agenda tasks de QA (exceto plano de testes)
        qa_tasks = [t for t in us.tasks 
                    if not t.is_qa_test_plan 
                    and t.work_front == WorkFront.QA]
        for task in qa_tasks:
            self._schedule_qa_task(task, us)
            
        # Depois agenda tasks DevOps
        devops_tasks = [t for t in us.tasks if t.is_devops_task]
        for task in devops_tasks:
            self._schedule_devops_task(task, us)
            
        # Por fim agenda tasks de QA Plano de Testes
        qa_plan_tasks = [t for t in us.tasks if t.is_qa_test_plan]
        for task in qa_plan_tasks:
            self._schedule_qa_plan_task(task, us)
        
        # Tenta atualizar a US após agendar todas as tasks
        self._try_update_user_story(us)
        
        # Registra tasks que permaneceram bloqueadas
        if blocked_tasks:
            logger.warning(f"Tasks que permaneceram bloqueadas na US {us.id}: {[t.id for t in blocked_tasks]}")

    def _try_update_user_story(self, us: UserStory) -> None:
        """
        Tenta atualizar os dados da User Story se todas as tasks estiverem agendadas
        
        Args:
            us: User Story a ser atualizada
        """
        # Considera todas as tasks ativas (exceto plano de testes que não tem data de fim)
        active_tasks = [t for t in us.tasks 
                       if t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]
                       and not t.is_qa_test_plan]
        
        # Verifica se todas as tasks ativas têm responsável e datas definidas
        all_tasks_ready = all(
            t.status == TaskStatus.SCHEDULED and 
            t.assignee is not None and 
            t.start_date is not None and 
            t.end_date is not None 
            for t in active_tasks
        )
        
        if not all_tasks_ready:
            logger.info(f"User Story {us.id} ainda tem tasks pendentes de agendamento")
            return
        
        # Calcula responsável (executor com mais tasks)
        assignee_count = {}
        assignee_fronts = {}  # Mapeia executores para suas frentes de trabalho
        
        for task in active_tasks:
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
        
        # Calcula datas considerando todas as tasks agendadas
        start_dates = [t.start_date for t in active_tasks]
        end_dates = [t.end_date for t in active_tasks]
        
        if start_dates and end_dates:
            us.start_date = min(start_dates)
            us.end_date = max(end_dates)
        
        # Calcula story points baseado nas horas estimadas
        total_estimated_hours = sum(t.estimated_hours for t in active_tasks)
        
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
        
        logger.info(f"User Story {us.id} atualizada após todas as tasks agendadas: "
                    f"responsável={us.assignee}, início={us.start_date}, fim={us.end_date}, "
                    f"SP={us.story_points}, horas_totais={total_estimated_hours}")

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
            return False
        
        # Verifica se todas as dependências estão agendadas
        if not self._check_dependencies(task):
            logger.info(f"Task {task.id} aguardando agendamento de dependências")
            task.status = TaskStatus.BLOCKED
            return False
            
        # Calcula datas de início e fim usando o executor atribuído
        start_date = self._get_earliest_start_date(task)
        
        if not start_date:
            logger.error(f"Não foi possível calcular data de início para task {task.id}")
            return False
        
        end_date = self._calculate_end_date(task, start_date)
        
        if not end_date:
            logger.error(f"Não foi possível calcular data de fim para task {task.id}")
            return False
            
        task.start_date = start_date
        task.end_date = end_date
        task.status = TaskStatus.SCHEDULED
        
        logger.info(f"Task {task.id} agendada para {task.assignee} de {start_date} até {end_date}")
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
            logger.error(f"Não foi possível encontrar executor para task DevOps {task.id}")
            return False
        
        # Pega todas as tasks agendadas da US
        scheduled_tasks = [t for t in us.tasks if t.status == TaskStatus.SCHEDULED]
        
        # Primeiro tenta pegar data das tasks de backend
        backend_tasks = [t for t in scheduled_tasks if t.work_front == WorkFront.BACKEND]
        start_date = None
        
        if backend_tasks:
            backend_dates = [t.end_date for t in backend_tasks if t.end_date]
            if backend_dates:
                start_date = max(backend_dates)
                logger.info(f"Task DevOps {task.id} iniciará após última task backend em {start_date}")
        else:
            # Se não tem backend, tenta frontend
            frontend_tasks = [t for t in scheduled_tasks if t.work_front == WorkFront.FRONTEND]
            if frontend_tasks:
                frontend_dates = [t.end_date for t in frontend_tasks if t.end_date]
                if frontend_dates:
                    start_date = max(frontend_dates)
                    logger.info(f"Task DevOps {task.id} iniciará após última task frontend em {start_date}")
        
        # Se não tem data específica, usa a data mais cedo possível
        if not start_date:
            start_date = self._get_earliest_start_date(task)
            if not start_date:
                logger.error(f"Não foi possível calcular data de início para task DevOps {task.id}")
                return False
        
        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            logger.error(f"Não foi possível calcular data de fim para task DevOps {task.id}")
            return False
            
        task.start_date = start_date
        task.end_date = end_date
        task.status = TaskStatus.SCHEDULED
        
        logger.info(f"Task DevOps {task.id} agendada para {task.assignee} de {start_date} até {end_date}")
        return True

    def _schedule_qa_plan_task(self, task: Task, us: UserStory) -> None:
        """
        Agenda uma task de QA Plano de Testes
        
        Args:
            task: Task de QA Plano de Testes a ser agendada
            us: User Story pai
        """
        # Verifica se todas as outras tasks estão agendadas
        other_tasks = [t for t in us.tasks 
                      if not t.is_qa_test_plan 
                      and t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]]
        
        if not all(t.status == TaskStatus.SCHEDULED for t in other_tasks):
            logger.warning(f"Task QA Plano {task.id} aguardando conclusão das outras tasks")
            return
        
        # Procura executor QA que já tenha tasks na US
        qa_tasks = [t for t in us.tasks 
                    if t.work_front == WorkFront.QA 
                    and not t.is_qa_test_plan
                    and t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]]
        
        if qa_tasks:
            # Usa o mesmo executor das outras tasks QA
            task.assignee = qa_tasks[0].assignee
        else:
            # Se não tem tasks QA, escolhe executor com maior disponibilidade
            qa_executors = getattr(self.executors, WorkFront.QA.value, [])
            best_executor = None
            best_availability = -1
            
            for executor in qa_executors:
                availability = self._calculate_executor_availability(executor)
                if availability > best_availability:
                    best_executor = executor
                    best_availability = availability
            
            task.assignee = best_executor
        
        if not task.assignee:
            logger.error(f"Não foi possível encontrar executor QA para task {task.id}")
            return
        
        # Task de plano não tem data de término
        task.start_date = None
        task.end_date = None
        task.status = TaskStatus.SCHEDULED
        
        logger.info(f"Task QA Plano {task.id} agendada para {task.end_date}")

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
        Encontra o melhor executor para uma task
        
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
        us = [us for us in self.sprint.user_stories if us.id == task.parent_user_story_id][0]
        front_tasks = [t for t in us.tasks 
                      if t.work_front == task.work_front 
                      and t.assignee 
                      and t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]]
        
        if front_tasks:
            # Se já existe executor para a frente, mantém o mesmo
            return front_tasks[0].assignee
            
        # Calcula carga de trabalho atual de cada executor
        executor_loads = {}
        for executor in executors_list:
            # Considera apenas tasks agendadas e ativas
            assigned_tasks = [t for t in self.sprint.get_tasks_by_assignee(executor) 
                            if t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED]]
            
            # Calcula horas totais e horas na mesma frente
            total_hours = sum(t.estimated_hours for t in assigned_tasks)
            front_hours = sum(t.estimated_hours for t in assigned_tasks 
                            if t.work_front == task.work_front)
            
            # Calcula disponibilidade considerando ausências
            availability = self._calculate_executor_availability(executor)
            
            # Pontuação considera balanceamento geral e por frente
            executor_loads[executor] = {
                'total_hours': total_hours,
                'front_hours': front_hours,
                'availability': availability
            }
        
        # Escolhe executor com menor carga na frente e maior disponibilidade
        best_executor = None
        best_score = float('inf')
        
        for executor, load in executor_loads.items():
            # Penaliza mais a carga na mesma frente
            if load['availability'] <= 0:  # Ignora executores sem disponibilidade
                continue
            
            score = (load['front_hours'] * 2 + load['total_hours']) / load['availability']
            
            if score < best_score:
                best_executor = executor
                best_score = score
        
        return best_executor

    def _calculate_executor_availability(self, executor: str) -> float:
        """
        Calcula a disponibilidade de um executor em horas
        
        Args:
            executor: Email do executor
            
        Returns:
            float: Horas disponíveis
        """
        # Calcula total de horas já alocadas (apenas de tasks ativas)
        assigned_tasks = self.sprint.get_tasks_by_assignee(executor)
        allocated_hours = sum(t.estimated_hours for t in assigned_tasks 
                             if t.status not in [TaskStatus.CLOSED, TaskStatus.CANCELLED])
        
        # Calcula total de horas de ausência
        dayoff_hours = 0
        executor_dayoffs = self.dayoffs.get(executor, [])
        for dayoff in executor_dayoffs:
            if dayoff.period == "full":
                dayoff_hours += 6
            else:
                dayoff_hours += 3
                
        # Calcula total de horas disponíveis na sprint
        sprint_days = (self.sprint.end_date - self.sprint.start_date).days + 1
        total_hours = sprint_days * 6
        
        return total_hours - allocated_hours - dayoff_hours

    def _get_earliest_start_date(self, task: Task) -> Optional[datetime]:
        """
        Calcula a primeira data possível para início da task
        
        Args:
            task: Task a ser agendada
            
        Returns:
            Optional[datetime]: Data mais cedo possível ou None se não encontrar
        """
        if not task.assignee:
            logger.error(f"Task {task.id} sem executor atribuído ao calcular data de início")
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
        executor_tasks = [t for t in self.sprint.get_tasks_by_assignee(task.assignee)
                         if t.status == TaskStatus.SCHEDULED  # Considera apenas tasks já agendadas
                         and t.end_date is not None
                         and t.id != task.id]  # Exclui a própria task
        
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
            if current_time == self.morning_end:
                # Se terminou às 12:00, começa às 14:00
                logger.info(f"Task {task.id} iniciará à tarde após task {latest_task.id} que terminou às 12:00")
                return self._create_datetime(latest_exec_date, 14)
            elif current_time == self.afternoon_end:
                # Se terminou às 17:00, começa às 9:00 do próximo dia
                next_date = latest_exec_date + timedelta(days=1)
                logger.info(f"Task {task.id} iniciará no próximo dia após task {latest_task.id} que terminou às 17:00")
                return self._create_datetime(next_date, 9)
            else:
                # Se terminou em outro horário, começa imediatamente após
                logger.info(f"Task {task.id} iniciará após task {latest_task.id} no mesmo período")
                return latest_exec_date
    
        # Se não tem task anterior do executor, usa o início da sprint
        current_date = self.sprint.start_date
        # Garante que a data está na timezone correta
        if current_date.tzinfo != self.timezone:
            current_date = current_date.astimezone(self.timezone)
            
        # Procura o primeiro período útil para o executor
        while not self._is_working_day(current_date, task.assignee):
            current_date = current_date + timedelta(days=1)
            
        logger.info(f"Task {task.id} iniciará no primeiro dia útil da sprint para o executor {task.assignee}")
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
                logger.info(f"Task {task.id} depende da task {dep_id} que termina em {dep_task.end_date}")
                
        if dep_dates:
            latest_dep_date = max(dep_dates)
            # Garante que a data está na timezone correta
            if latest_dep_date.tzinfo != self.timezone:
                latest_dep_date = latest_dep_date.astimezone(self.timezone)
            return latest_dep_date
        
        return None

    def _calculate_end_date(self, task: Task, start_date: datetime) -> Optional[datetime]:
        """
        Calcula a data de término de uma task
        
        Args:
            task: Task a ser agendada
            start_date: Data de início
            
        Returns:
            Optional[datetime]: Data de término ou None se não for possível calcular
        """
        # Garante que a data de início está na timezone correta
        current_date = start_date if start_date.tzinfo else start_date.replace(tzinfo=self.timezone)
        remaining_hours = task.estimated_hours
        
        # Controle de horas disponíveis no período atual
        hours_left_in_period = 0
        
        while remaining_hours > 0:
            # Verifica se é dia útil e não tem ausência
            if self._is_working_day(current_date, task.assignee):
                current_time = current_date.time()
                
                # Determina em qual período estamos e quantas horas disponíveis
                if current_time <= self.morning_end:
                    # Período da manhã
                    if current_time < self.morning_start:
                        # Se está antes do início, considera todo o período
                        hours_left_in_period = 3
                        current_date = self._create_datetime(current_date, 9)
                    else:
                        # Calcula horas restantes até 12:00
                        hours_left_in_period = (
                            (self.morning_end.hour - current_time.hour) * 60 +
                            (self.morning_end.minute - current_time.minute)
                        ) / 60
                        
                elif current_time <= self.afternoon_end:
                    if current_time < self.afternoon_start:
                        # Se está antes do início da tarde, considera todo o período
                        hours_left_in_period = 3
                        current_date = self._create_datetime(current_date, 14)
                    else:
                        # Calcula horas restantes até 17:00
                        hours_left_in_period = (
                            (self.afternoon_end.hour - current_time.hour) * 60 +
                            (self.afternoon_end.minute - current_time.minute)
                        ) / 60
                else:
                    # Passou do horário da tarde, vai para o próximo dia
                    current_date = self._create_datetime(current_date + timedelta(days=1), 9)
                    hours_left_in_period = 3
                    continue
                
                # Se tem menos horas restantes que o disponível no período
                if remaining_hours <= hours_left_in_period:
                    # Calcula o horário exato de término
                    if current_time <= self.morning_end:
                        # Se estamos de manhã, termina no horário calculado
                        if remaining_hours == hours_left_in_period:
                            # Se usa exatamente todas as horas, termina às 12:00
                            return self._create_datetime(current_date, 12)
                        else:
                            # Se sobram horas, registra término às 12:00 mas guarda saldo
                            return self._create_datetime(current_date, 12)
                    else:
                        # Se estamos à tarde, termina no horário calculado
                        if remaining_hours == hours_left_in_period:
                            # Se usa exatamente todas as horas, termina às 17:00
                            return self._create_datetime(current_date, 17)
                        else:
                            # Se sobram horas, registra término às 17:00 mas guarda saldo
                            return self._create_datetime(current_date, 17)
                            
                # Se precisa de mais horas que o disponível no período
                remaining_hours -= hours_left_in_period
                
                # Passa para o próximo período
                if current_time < self.afternoon_start:
                    # Se estava de manhã, passa para tarde
                    current_date = self._create_datetime(current_date, 14)
                    hours_left_in_period = 3
                else:
                    # Se estava à tarde, passa para próximo dia
                    current_date = self._create_datetime(current_date + timedelta(days=1), 9)
                    hours_left_in_period = 3
                    
            else:
                # Se não é dia útil ou tem ausência, passa para o próximo dia
                current_date = self._create_datetime(current_date + timedelta(days=1), 9)
                hours_left_in_period = 3
                
        # Se chegou aqui, termina no fim do último dia
        return self._create_datetime(current_date, 17)

    def _is_working_day(self, date: datetime, executor: str) -> bool:
        """
        Verifica se é um dia útil para o executor
        
        Args:
            date: Data a ser verificada
            executor: Email do executor
            
        Returns:
            bool: True se é dia útil e não tem ausência
        """
        # Verifica se é fim de semana
        if date.weekday() >= 5:
            return False
            
        # Verifica se tem ausência
        executor_dayoffs = self.dayoffs.get(executor, [])
        for dayoff in executor_dayoffs:
            if dayoff.date.date() == date.date():
                if dayoff.period == "full":
                    return False
                elif dayoff.period == "morning" and date.time() <= self.morning_end:
                    return False
                elif dayoff.period == "afternoon" and date.time() >= self.afternoon_start:
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
        
        # Atribui executor se necessário
        if not task.assignee:
            task.assignee = self._get_best_executor(task)
        
        if not task.assignee:
            logger.error(f"Não foi possível encontrar executor para task QA {task.id}")
            return False
        
        # Determina se é task de backend ou frontend baseado no título
        is_backend_qa = "backend" in task.title.lower()
        is_frontend_qa = "frontend" in task.title.lower()
        
        # Pega todas as tasks agendadas da US
        scheduled_tasks = [t for t in us.tasks if t.status == TaskStatus.SCHEDULED]
        
        # Define data de início baseada no tipo de QA
        start_date = None
        if is_backend_qa:
            # Pega a última data de término das tasks de backend
            backend_tasks = [t for t in scheduled_tasks if t.work_front == WorkFront.BACKEND]
            if backend_tasks:
                backend_dates = [t.end_date for t in backend_tasks if t.end_date]
                if backend_dates:
                    start_date = max(backend_dates)
                    logger.info(f"Task QA Backend {task.id} iniciará após última task backend em {start_date}")
        elif is_frontend_qa:
            # Pega a última data de término das tasks de frontend
            frontend_tasks = [t for t in scheduled_tasks if t.work_front == WorkFront.FRONTEND]
            if frontend_tasks:
                frontend_dates = [t.end_date for t in frontend_tasks if t.end_date]
                if frontend_dates:
                    start_date = max(frontend_dates)
                    logger.info(f"Task QA Frontend {task.id} iniciará após última task frontend em {start_date}")
        
        # Se não tem data específica, usa a data mais cedo possível
        if not start_date:
            start_date = self._get_earliest_start_date(task)
            if not start_date:
                logger.error(f"Não foi possível calcular data de início para task QA {task.id}")
                return False
        
        # Calcula data de término
        end_date = self._calculate_end_date(task, start_date)
        if not end_date:
            logger.error(f"Não foi possível calcular data de fim para task QA {task.id}")
            return False
            
        task.start_date = start_date
        task.end_date = end_date
        task.status = TaskStatus.SCHEDULED
        
        logger.info(f"Task QA {task.id} agendada para {task.assignee} de {start_date} até {end_date}")
        return True 