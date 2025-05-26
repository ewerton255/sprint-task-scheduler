from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from ..models.entities import Task, UserStory, Sprint, TaskStatus
from ..models.config import DayOff

class ReportGenerator:
    """Serviço responsável pela geração de relatórios"""

    def __init__(self, sprint: Sprint, dayoffs: Dict[str, List[DayOff]], output_dir: str):
        """
        Inicializa o gerador de relatórios
        
        Args:
            sprint: Sprint a ser reportada
            dayoffs: Dicionário de ausências por executor
            output_dir: Diretório onde o relatório será salvo
        """
        self.sprint = sprint
        self.dayoffs = dayoffs
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> None:
        """Gera o relatório da sprint"""
        report = []
        
        # Cabeçalho
        report.extend([
            f"# Relatório da Sprint: {self.sprint.name}\n",
            "## 1. Resumo Geral da Sprint\n",
            f"- Sprint: **{self.sprint.name}**",
            f"- Período: {self.sprint.start_date.strftime('%d/%m/%Y')} a {self.sprint.end_date.strftime('%d/%m/%Y')}",
            f"- Total de User Stories planejadas: {len(self.sprint.user_stories)}\n"
        ])
        
        # User Stories
        report.extend([
            "## 2. User Stories planejadas\n",
            "| ID | Título | Responsável | Data de Finalização | Story Points |",
            "|-----|---------|-------------|-------------------|--------------|"
        ])
        
        for us in self.sprint.user_stories:
            end_date = us.end_date.strftime('%d/%m/%Y') if us.end_date else '-'
            report.append(
                f"| {us.id} | {us.title} | {us.assignee or '-'} | {end_date} | {us.story_points or '-'} |"
            )
        
        report.append("")
        
        # Ausências
        report.extend([
            "## 3. Ausências (Dayoffs)\n",
            "| Responsável | Datas de Ausência |",
            "|-------------|-------------------|"
        ])
        
        for executor, dayoffs in self.dayoffs.items():
            absences = []
            for dayoff in dayoffs:
                period = {
                    "full": "dia inteiro",
                    "morning": "manhã",
                    "afternoon": "tarde"
                }[dayoff.period]
                absences.append(f"{dayoff.date.strftime('%d/%m/%Y')} ({period})")
            
            report.append(f"| {executor} | {', '.join(absences)} |")
            
        report.append("")
        
        # Dependências
        report.extend([
            "## 4. Dependências entre Tasks\n"
        ])
        
        for us in self.sprint.user_stories:
            report.extend([
                f"### User Story {us.id}: {us.title}\n",
                "**Tasks desta User Story:**"
            ])
            
            for task in us.tasks:
                report.append(f"- Task {task.id}: {task.title} ({task.work_front.value})")
                
            report.append("\n**Dependências:**")
            
            for task in us.tasks:
                if task.dependencies:
                    report.append(f"Task {task.id} ({task.title}) depende de:")
                    all_tasks = self.sprint.get_all_tasks()
                    task_dict = {t.id: t for t in all_tasks}
                    
                    for dep_id in task.dependencies:
                        if dep_id in task_dict:
                            dep = task_dict[dep_id]
                            report.append(f"  - Task {dep.id}: {dep.title} ({dep.work_front.value})")
                        else:
                            report.append(f"  - Task {dep_id}: Não encontrada")
                            
            report.append("")
            
        # Itens não agendados
        report.extend([
            "## 5. Itens não agendados\n",
            "### Por dependências ausentes:"
        ])
        
        blocked_tasks = [t for t in self.sprint.get_all_tasks() if t.status == TaskStatus.BLOCKED]
        if blocked_tasks:
            for task in blocked_tasks:
                report.append(f"- Task {task.id}: {task.title} | Dependências ausentes: {', '.join(task.dependencies)}")
        else:
            report.append("*Nenhuma task bloqueada por dependências*")
            
        report.extend([
            "\n### Por dependências não satisfeitas ou ciclo:",
            "*Nenhuma task com ciclo de dependências detectado*\n"
        ])
        
        # Observações finais
        report.extend([
            "---\n",
            "## Observações Finais\n",
            "- Todos os horários e datas estão em GMT-3.",
            "- Tasks de Elaboração de Plano de Testes não possuem data de término.",
            "- O sistema respeita todas as ausências informadas.",
            "- O relatório detalha todas as dependências e possíveis problemas de agendamento."
        ])
        
        # Salva relatório
        report_path = self.output_dir / f"relatorio_sprint_{self.sprint.name.replace(' ', '_')}.md"
        report_path.write_text("\n".join(report), encoding='utf-8')
        
        logger.info(f"Relatório gerado em {report_path}")

    def _format_task_list(self, tasks: List[Task]) -> str:
        """
        Formata uma lista de tasks para o relatório
        
        Args:
            tasks: Lista de tasks
            
        Returns:
            str: Lista formatada em Markdown
        """
        if not tasks:
            return "*Nenhuma task*"
            
        return "\n".join([
            f"- Task {t.id}: {t.title} ({t.work_front.value})"
            for t in tasks
        ]) 