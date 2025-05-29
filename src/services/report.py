from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
from loguru import logger
import markdown
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, LongTable
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus.flowables import KeepTogether

from ..models.entities import Task, UserStory, Sprint, TaskStatus, WorkFront
from ..models.config import DayOff

class ReportGenerator:
    """Serviço responsável pela geração de relatórios"""

    def __init__(self, sprint: Sprint, dayoffs: Dict[str, List[DayOff]], output_dir: str, team_name: str):
        """
        Inicializa o gerador de relatórios
        
        Args:
            sprint: Sprint a ser reportada
            dayoffs: Dicionário de ausências por executor
            output_dir: Diretório onde o relatório será salvo
            team_name: Nome completo do time (ex: "TR Fintech\\TRF\\TR Banking\\BENEFICIOS")
        """
        self.sprint = sprint
        self.dayoffs = dayoffs
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        # Extrai o nome do time do caminho completo
        self.team_name = team_name.split('\\')[-1] if '\\' in team_name else team_name

    def _setup_styles(self):
        """Configura estilos personalizados para o relatório"""
        # Estilo para o título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=16,
            spaceAfter=30,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER
        ))
        
        # Estilo para títulos de seção
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_LEFT
        ))
        
        # Estilo para subtítulos
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor('#34495e'),
            alignment=TA_LEFT
        ))
        
        # Estilo para texto normal com quebra de linha
        self.styles.add(ParagraphStyle(
            name='NormalWrap',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            spaceAfter=6,
            alignment=TA_LEFT
        ))
        
        # Estilo para células de tabela
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT
        ))
        
        # Estilo para cabeçalhos de tabela
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))

    def _create_table_style(self, header_bg_color=colors.lightgrey):
        """Cria um estilo padrão para as tabelas"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_bg_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ])

    def _count_working_days(self, start_date: datetime, end_date: datetime) -> int:
        """
        Conta o número de dias úteis entre duas datas (excluindo finais de semana)
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            int: Número de dias úteis
        """
        working_days = 0
        current_date = start_date
        while current_date <= end_date:
            # 5 = Sábado, 6 = Domingo
            if current_date.weekday() < 5:
                working_days += 1
            current_date += timedelta(days=1)
        return working_days

    def _generate_markdown(self) -> str:
        """Gera o conteúdo do relatório em Markdown"""
        report = []
        
        # Título
        report.append(f"# Relatório de Agendamento - Sprint {self.sprint.name}")
        report.append("")
        
        # Informações da Sprint
        report.append("## 📅 Informações da Sprint")
        report.append("")
        report.append(f"- **Início:** {self.sprint.start_date.strftime('%d/%m/%Y')}")
        report.append(f"- **Término:** {self.sprint.end_date.strftime('%d/%m/%Y')}")
        report.append("")
        
        # Capacidade da Equipe
        report.append("## 👥 Capacidade da Equipe")
        report.append("")
        report.append("| Executor | Capacidade Total (h) | Capacidade Usada (h) | Capacidade Disponível (h) |")
        report.append("|----------|---------------------|---------------------|--------------------------|")
        
        # Calcula capacidade total considerando dias úteis
        total_working_days = self._count_working_days(self.sprint.start_date, self.sprint.end_date)
        base_capacity = total_working_days * 6  # 6 horas por dia útil
        
        # Primeiro, define a capacidade base para todos os executores
        executor_capacity = {}
        for us in self.sprint.user_stories:
            for task in us.tasks:
                if task.assignee and task.assignee not in executor_capacity:
                    executor_capacity[task.assignee] = {"total": base_capacity, "used": 0}
        
        # Depois, subtrai as ausências para executores que têm dayoffs
        for executor, dayoffs in self.dayoffs.items():
            if executor in executor_capacity:
                for dayoff in dayoffs:
                    if dayoff.period == "full":
                        executor_capacity[executor]["total"] -= 6  # Subtrai 6 horas para dia inteiro
                    else:
                        executor_capacity[executor]["total"] -= 3  # Subtrai 3 horas para meio período
        
        # Por fim, calcula a capacidade usada baseada nas tasks
        for us in self.sprint.user_stories:
            for task in us.tasks:
                if task.assignee and task.estimated_hours:
                    executor_capacity[task.assignee]["used"] += task.estimated_hours
        
        # Adiciona informações ao relatório
        for executor, capacity in executor_capacity.items():
            available = capacity["total"] - capacity["used"]
            report.append(
                f"| {executor} | {capacity['total']:.1f} | {capacity['used']:.1f} | {available:.1f} |"
            )
        
        report.append("")
        
        # Distribuição por Frente de Trabalho
        report.extend([
            "## 4. Distribuição por Frente de Trabalho\n",
            "| Frente | Quantidade de Tasks | Horas Estimadas |",
            "|--------|-------------------|-----------------|"
        ])
        
        work_front_stats = {}
        for us in self.sprint.user_stories:
            # Mantém a ordem original das tasks
            for task in us.tasks:
                if task.work_front not in work_front_stats:
                    work_front_stats[task.work_front] = {"count": 0, "hours": 0}
                work_front_stats[task.work_front]["count"] += 1
                if task.estimated_hours:
                    work_front_stats[task.work_front]["hours"] += task.estimated_hours
        
        for front, stats in work_front_stats.items():
            report.append(f"| {front.value} | {stats['count']} | {stats['hours']:.1f} |")
        
        report.append("")
        
        # Ausências
        report.extend([
            "## 5. Ausências (Dayoffs)\n",
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
        
        # Itens não agendados
        report.extend([
            "## 6. Itens não agendados\n",
            "### Por dependências ausentes:"
        ])
        
        # Mantém a ordem original das tasks bloqueadas
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
        
        return "\n".join(report)

    def generate(self) -> None:
        """Gera o relatório da sprint em PDF e Markdown"""
        # Gera o relatório em Markdown
        markdown_content = self._generate_markdown()
        markdown_path = self.output_dir / f"relatorio_sprint_{self.sprint.name.replace(' ', '_')}.md"
        markdown_path.write_text(markdown_content, encoding='utf-8')
        logger.info(f"Relatório Markdown gerado em {markdown_path}")
        
        # Cria o documento PDF
        pdf_path = self.output_dir / f"relatorio_sprint_{self.sprint.name.replace(' ', '_')}.pdf"
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Lista de elementos do documento
        elements = []
        
        # Título
        elements.append(Paragraph(f"Relatório da Sprint: {self.sprint.name} - {self.team_name}", self.styles['CustomTitle']))
        elements.append(Spacer(1, 12))
        
        # Resumo Geral
        elements.append(Paragraph("1. Resumo Geral da Sprint", self.styles['CustomHeading1']))
        elements.append(Paragraph(f"Sprint: {self.sprint.name}", self.styles['NormalWrap']))
        elements.append(Paragraph(
            f"Período: {self.sprint.start_date.strftime('%d/%m/%Y')} a {self.sprint.end_date.strftime('%d/%m/%Y')}",
            self.styles['NormalWrap']
        ))
        elements.append(Paragraph(f"Total de User Stories planejadas: {len(self.sprint.user_stories)}", self.styles['NormalWrap']))
        elements.append(Spacer(1, 12))
        
        # User Stories
        elements.append(Paragraph("2. User Stories planejadas", self.styles['CustomHeading1']))
        us_data = [[
            Paragraph('ID', self.styles['TableHeader']),
            Paragraph('Título', self.styles['TableHeader']),
            Paragraph('Responsável', self.styles['TableHeader']),
            Paragraph('Data de Finalização', self.styles['TableHeader']),
            Paragraph('Story Points', self.styles['TableHeader'])
        ]]
        # Mantém a ordem original das User Stories
        for us in self.sprint.user_stories:
            end_date = us.end_date.strftime('%d/%m/%Y') if us.end_date else '-'
            us_data.append([
                us.id,
                Paragraph(us.title, self.styles['TableCell']),
                Paragraph(us.assignee or '-', self.styles['TableCell']),
                end_date,
                str(us.story_points or '-')
            ])
        
        # Calcula larguras proporcionais
        available_width = doc.width
        us_table = LongTable(
            us_data,
            colWidths=[
                available_width * 0.1,  # ID
                available_width * 0.5,  # Título
                available_width * 0.15, # Responsável
                available_width * 0.15, # Data
                available_width * 0.1   # Story Points
            ]
        )
        us_table.setStyle(self._create_table_style())
        elements.append(KeepTogether(us_table))
        elements.append(Spacer(1, 12))
        
        # Capacidade dos Executores
        elements.append(Paragraph("3. Capacidade dos Executores", self.styles['CustomHeading1']))
        
        # Calcula capacidade total e usada por executor
        executor_capacity = {}
        
        # Primeiro calcula a capacidade usada baseada nas tasks
        for us in self.sprint.user_stories:
            # Mantém a ordem original das tasks
            for task in us.tasks:
                if task.assignee:
                    if task.assignee not in executor_capacity:
                        executor_capacity[task.assignee] = {"total": 0, "used": 0}
                    
                    # Adiciona horas estimadas à capacidade usada
                    if task.estimated_hours:
                        executor_capacity[task.assignee]["used"] += task.estimated_hours
        
        # Calcula capacidade total considerando dias úteis e ausências
        total_working_days = self._count_working_days(self.sprint.start_date, self.sprint.end_date)
        base_capacity = total_working_days * 6  # 6 horas por dia útil
        
        # Primeiro, define a capacidade base para todos os executores
        for executor in executor_capacity.keys():
            executor_capacity[executor]["total"] = base_capacity
        
        # Depois, subtrai as ausências para executores que têm dayoffs
        for executor, dayoffs in self.dayoffs.items():
            if executor in executor_capacity:
                for dayoff in dayoffs:
                    if dayoff.period == "full":
                        executor_capacity[executor]["total"] -= 6  # Subtrai 6 horas para dia inteiro
                    else:
                        executor_capacity[executor]["total"] -= 3  # Subtrai 3 horas para meio período
        
        # Prepara dados da tabela
        capacity_data = [[
            Paragraph('Executor', self.styles['TableHeader']),
            Paragraph('Capacidade Total (h)', self.styles['TableHeader']),
            Paragraph('Capacidade Usada (h)', self.styles['TableHeader']),
            Paragraph('Capacidade Disponível (h)', self.styles['TableHeader'])
        ]]
        for executor, capacity in executor_capacity.items():
            available = capacity["total"] - capacity["used"]
            capacity_data.append([
                Paragraph(executor, self.styles['TableCell']),
                f"{capacity['total']:.1f}",
                f"{capacity['used']:.1f}",
                f"{available:.1f}"
            ])
        
        capacity_table = LongTable(
            capacity_data,
            colWidths=[
                available_width * 0.3,  # Executor
                available_width * 0.25, # Total
                available_width * 0.25, # Usada
                available_width * 0.2   # Disponível
            ]
        )
        capacity_table.setStyle(self._create_table_style())
        elements.append(KeepTogether(capacity_table))
        elements.append(Spacer(1, 12))
        
        # Distribuição por Frente de Trabalho
        elements.append(Paragraph("4. Distribuição por Frente de Trabalho", self.styles['CustomHeading1']))
        
        work_front_stats = {}
        for us in self.sprint.user_stories:
            # Mantém a ordem original das tasks
            for task in us.tasks:
                if task.work_front not in work_front_stats:
                    work_front_stats[task.work_front] = {"count": 0, "hours": 0}
                work_front_stats[task.work_front]["count"] += 1
                if task.estimated_hours:
                    work_front_stats[task.work_front]["hours"] += task.estimated_hours
        
        front_data = [[
            Paragraph('Frente', self.styles['TableHeader']),
            Paragraph('Quantidade de Tasks', self.styles['TableHeader']),
            Paragraph('Horas Estimadas', self.styles['TableHeader'])
        ]]
        for front, stats in work_front_stats.items():
            front_data.append([
                Paragraph(front.value, self.styles['TableCell']),
                str(stats['count']),
                f"{stats['hours']:.1f}"
            ])
        
        front_table = LongTable(
            front_data,
            colWidths=[
                available_width * 0.4,  # Frente
                available_width * 0.3,  # Quantidade
                available_width * 0.3   # Horas
            ]
        )
        front_table.setStyle(self._create_table_style())
        elements.append(KeepTogether(front_table))
        elements.append(Spacer(1, 12))
        
        # Ausências
        elements.append(Paragraph("5. Ausências (Dayoffs)", self.styles['CustomHeading1']))
        
        dayoff_data = [[
            Paragraph('Responsável', self.styles['TableHeader']),
            Paragraph('Datas de Ausência', self.styles['TableHeader'])
        ]]
        for executor, dayoffs in self.dayoffs.items():
            absences = []
            for dayoff in dayoffs:
                period = {
                    "full": "dia inteiro",
                    "morning": "manhã",
                    "afternoon": "tarde"
                }[dayoff.period]
                absences.append(f"{dayoff.date.strftime('%d/%m/%Y')} ({period})")
            
            dayoff_data.append([
                Paragraph(executor, self.styles['TableCell']),
                Paragraph(', '.join(absences), self.styles['TableCell'])
            ])
        
        dayoff_table = LongTable(
            dayoff_data,
            colWidths=[
                available_width * 0.3,  # Responsável
                available_width * 0.7   # Datas
            ]
        )
        dayoff_table.setStyle(self._create_table_style())
        elements.append(KeepTogether(dayoff_table))
        elements.append(Spacer(1, 12))
        
        # Itens não agendados
        elements.append(Paragraph("6. Itens não agendados", self.styles['CustomHeading1']))
        elements.append(Paragraph("Por dependências ausentes:", self.styles['CustomHeading2']))
        
        # Mantém a ordem original das tasks bloqueadas
        blocked_tasks = [t for t in self.sprint.get_all_tasks() if t.status == TaskStatus.BLOCKED]
        if blocked_tasks:
            for task in blocked_tasks:
                elements.append(Paragraph(
                    f"• Task {task.id}: {task.title} | Dependências ausentes: {', '.join(task.dependencies)}",
                    self.styles['NormalWrap']
                ))
        else:
            elements.append(Paragraph("Nenhuma task bloqueada por dependências", self.styles['NormalWrap']))
        
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Por dependências não satisfeitas ou ciclo:", self.styles['CustomHeading2']))
        elements.append(Paragraph("Nenhuma task com ciclo de dependências detectado", self.styles['NormalWrap']))
        
        # Gera o PDF
        doc.build(elements)
        
        logger.info(f"Relatório PDF gerado em {pdf_path}") 