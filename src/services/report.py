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

from ..models.entities import Task, UserStory, Sprint, TaskStatus, WorkFront, SprintMetrics
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
        # Obtém as métricas da sprint do scheduler
        self.metrics = sprint.metrics

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
        
        # 1. Resumo Geral da Sprint
        report.append("## 1. Resumo Geral da Sprint")
        report.append("")
        report.append(f"- **Sprint:** {self.sprint.name}")
        report.append(f"- **Início:** {self.sprint.start_date.strftime('%d/%m/%Y')}")
        report.append(f"- **Término:** {self.sprint.end_date.strftime('%d/%m/%Y')}")
        report.append(f"- **Total de User Stories:** {len(self.sprint.user_stories)}")
        report.append("")
        
        # 2. User Stories Planejadas
        report.append("## 2. User Stories Planejadas")
        report.append("")
        report.append("| ID | Título | Responsável | Data de Finalização | Story Points |")
        report.append("|----|--------|-------------|---------------------|--------------|")
        
        for us in self.sprint.user_stories:
            end_date = us.end_date.strftime('%d/%m/%Y') if us.end_date else '-'
            report.append(
                f"| {us.id} | {us.title} | {us.assignee or '-'} | {end_date} | {us.story_points or '-'} |"
            )
        
        report.append("")
        
        # 3. Ausências
        report.append("## 3. Ausências")
        report.append("")
        report.append("| Responsável | Datas de Ausência |")
        report.append("|-------------|-------------------|")
        
        for executor, dayoffs in self.dayoffs.items():
            absences = []
            for dayoff in dayoffs:
                period = {
                    "full": "dia inteiro",
                    "morning": "manhã",
                    "afternoon": "tarde"
                }
                absences.append(f"{dayoff.date.strftime('%d/%m/%Y')} ({period[dayoff.period]})")
            report.append(f"| {executor} | {', '.join(absences)} |")
        
        report.append("")
        
        # 4. Tasks não planejadas
        if self.metrics.not_scheduled_tasks:
            report.append("## 4. Tasks não planejadas")
            report.append("")
            report.append("| ID | Título | User Story | Motivo |")
            report.append("|----|--------|------------|--------|")
            
            for task in self.metrics.not_scheduled_tasks:
                report.append(
                    f"| {task['task_id']} | {task['title']} | {task['user_story_id']} | {task['reason']} |"
                )
            report.append("")
            
        # 5. Capacity dos Executores
        report.append("## 5. Capacity dos Executores")
        report.append("")
        report.append("| Executor | Capacity Total | Capacity Utilizada | Capacity Disponível |")
        report.append("|----------|----------------|-------------------|---------------------|")
        
        for executor in sorted(self.metrics.total_capacity.keys()):
            total = self.metrics.total_capacity.get(executor, 0)
            used = self.metrics.used_capacity.get(executor, 0)
            available = self.metrics.available_capacity.get(executor, 0)
            report.append(
                f"| {executor} | {total:.1f}h | {used:.1f}h | {available:.1f}h |"
            )
        
        report.append("")
        
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
        
        # 1. Resumo Geral da Sprint
        elements.append(Paragraph("1. Resumo Geral da Sprint", self.styles['CustomHeading1']))
        elements.append(Paragraph(f"Sprint: {self.sprint.name}", self.styles['NormalWrap']))
        elements.append(Paragraph(
            f"Período: {self.sprint.start_date.strftime('%d/%m/%Y')} a {self.sprint.end_date.strftime('%d/%m/%Y')}",
            self.styles['NormalWrap']
        ))
        elements.append(Paragraph(f"Total de User Stories planejadas: {len(self.sprint.user_stories)}", self.styles['NormalWrap']))
        elements.append(Spacer(1, 12))
        
        # 2. User Stories Planejadas
        elements.append(Paragraph("2. User Stories Planejadas", self.styles['CustomHeading1']))
        us_data = [[
            Paragraph('ID', self.styles['TableHeader']),
            Paragraph('Título', self.styles['TableHeader']),
            Paragraph('Responsável', self.styles['TableHeader']),
            Paragraph('Data de Finalização', self.styles['TableHeader']),
            Paragraph('Story Points', self.styles['TableHeader'])
        ]]
        
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
        
        # 3. Ausências
        elements.append(Paragraph("3. Ausências", self.styles['CustomHeading1']))
        
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
                }
                absences.append(f"{dayoff.date.strftime('%d/%m/%Y')} ({period[dayoff.period]})")
            
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
        
        # 4. Tasks não planejadas
        if self.metrics.not_scheduled_tasks:
            elements.append(Paragraph("4. Tasks não planejadas", self.styles['CustomHeading1']))
            
            not_scheduled_data = [[
                Paragraph('ID', self.styles['TableHeader']),
                Paragraph('Título', self.styles['TableHeader']),
                Paragraph('User Story', self.styles['TableHeader']),
                Paragraph('Motivo', self.styles['TableHeader'])
            ]]
            
            for task in self.metrics.not_scheduled_tasks:
                not_scheduled_data.append([
                    Paragraph(task['task_id'], self.styles['NormalWrap']),
                    Paragraph(task['title'], self.styles['NormalWrap']),
                    Paragraph(task['user_story_id'], self.styles['NormalWrap']),
                    Paragraph(task['reason'], self.styles['NormalWrap'])
                ])
            
            not_scheduled_table = Table(not_scheduled_data, colWidths=[2*cm, 6*cm, 2*cm, 4*cm])
            not_scheduled_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(KeepTogether(not_scheduled_table))
            elements.append(Spacer(1, 12))
            
        # 5. Capacity dos Executores
        elements.append(Paragraph("5. Capacity dos Executores", self.styles['CustomHeading1']))
        
        capacity_data = [[
            Paragraph('Executor', self.styles['TableHeader']),
            Paragraph('Capacity Total', self.styles['TableHeader']),
            Paragraph('Capacity Utilizada', self.styles['TableHeader']),
            Paragraph('Capacity Disponível', self.styles['TableHeader'])
        ]]
        
        for executor in sorted(self.metrics.total_capacity.keys()):
            total = self.metrics.total_capacity.get(executor, 0)
            used = self.metrics.used_capacity.get(executor, 0)
            available = self.metrics.available_capacity.get(executor, 0)
            capacity_data.append([
                Paragraph(executor, self.styles['TableCell']),
                Paragraph(f"{total:.1f}h", self.styles['TableCell']),
                Paragraph(f"{used:.1f}h", self.styles['TableCell']),
                Paragraph(f"{available:.1f}h", self.styles['TableCell'])
            ])
        
        capacity_table = Table(capacity_data, colWidths=[4*cm, 3*cm, 3*cm, 3*cm])
        capacity_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(KeepTogether(capacity_table))
        elements.append(Spacer(1, 12))
        
        # Gera o PDF
        doc.build(elements)
        logger.info(f"Relatório PDF gerado em {pdf_path}") 