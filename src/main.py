import json
import os
import sys
from datetime import datetime
from pathlib import Path
import typer
from loguru import logger
from rich.console import Console

# Configurando o ambiente
WORKSPACE_ROOT = Path(__file__).parent.parent
os.chdir(WORKSPACE_ROOT)
sys.path.append(str(WORKSPACE_ROOT))

# Importando módulos do projeto
from src.models.config import SetupConfig, ExecutorsConfig, DependenciesConfig, DayOff
from src.azure.client import AzureDevOpsClient
from src.services.scheduler import SprintScheduler
from src.services.report import ReportGenerator

app = typer.Typer(help="Agendador de Sprint - Sistema de Gerenciamento")
console = Console()

def configurar_logger(output_dir: Path = Path("logs")):
    """Configura o sistema de logs"""
    output_dir.mkdir(exist_ok=True)
    
    logger.remove()  # Remove handlers padrão
    logger.add(
        output_dir / "agendador_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        encoding='utf-8'
    )
    logger.add(lambda msg: console.print(msg, style="blue"), level="INFO")

def verificar_diretorios():
    """Verifica e cria diretórios necessários"""
    diretorios = ["logs", "output"]
    for dir_name in diretorios:
        Path(dir_name).mkdir(exist_ok=True)

def load_json_file(path: Path) -> dict:
    """
    Carrega um arquivo JSON
    
    Args:
        path: Caminho do arquivo
        
    Returns:
        dict: Conteúdo do arquivo
    """
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo {path}: {str(e)}")
        raise typer.Exit(1)

@app.command()
def executar(
    config_dir: Path = typer.Option(
        "config",
        help="Diretório com os arquivos de configuração",
        exists=True,
        dir_okay=True,
        file_okay=False
    )
):
    """Executa o agendamento da sprint"""
    try:
        # Configuração inicial
        verificar_diretorios()
        configurar_logger()
        
        logger.info("Iniciando execução do agendador de sprint")
        logger.info(f"Usando diretório de configuração: {config_dir}")
        
        # Carrega configurações
        logger.info("Carregando configurações...")
        setup_file = config_dir / "setup.json"
        setup_data = load_json_file(setup_file)
        setup = SetupConfig(**setup_data)
        
        # Carrega executores
        executors_data = load_json_file(Path(setup.executors_file))
        executors = ExecutorsConfig(**executors_data)
        
        # Carrega dependências
        dependencies_data = load_json_file(Path(setup.dependencies_file))
        dependencies = DependenciesConfig(**dependencies_data)
        
        # Carrega dayoffs
        dayoffs_data = load_json_file(Path(setup.dayoffs_file))
        dayoffs = {
            email: [DayOff(**d) for d in days]
            for email, days in dayoffs_data.items()
        }
        
        # Inicializa cliente do Azure DevOps
        logger.info("Conectando ao Azure DevOps...")
        azure_client = AzureDevOpsClient(
            organization=setup.azure_devops.organization,
            project=setup.azure_devops.project,
            token=setup.azure_devops.token
        )
        
        # Obtém itens da sprint
        logger.info(f"Obtendo itens da sprint {setup.sprint.name}...")
        sprint_items = azure_client.get_sprint_items(
            sprint_name=setup.sprint.name,
            team=setup.team,
            year=setup.sprint.year,
            quarter=setup.sprint.quarter
        )
        if not sprint_items["user_stories"]:
            logger.error("Nenhuma User Story encontrada na sprint")
            raise typer.Exit(1)
            
        # Converte para entidades do sistema
        sprint = azure_client.convert_to_entities(
            items=sprint_items,
            sprint_name=setup.sprint.name,
            team=setup.team,
            year=setup.sprint.year,
            quarter=setup.sprint.quarter
        )
        sprint.start_date = setup.sprint.start_date
        sprint.end_date = setup.sprint.end_date
        
        # Adiciona dependências às tasks
        all_tasks = sprint.get_all_tasks()
        task_dict = {t.id: t for t in all_tasks}
        for task_id, deps in dependencies.dependencies.items():
            if task_id in task_dict:
                task_dict[task_id].dependencies = deps
        
        # Executa agendamento
        logger.info("Iniciando agendamento...")
        scheduler = SprintScheduler(sprint, executors, dayoffs)
        scheduler.schedule()
        
        # Atualiza itens no Azure DevOps
        logger.info("Atualizando itens no Azure DevOps...")
        azure_client.update_work_items(sprint)
        
        # Gera relatório
        logger.info("Gerando relatório...")
        report_generator = ReportGenerator(sprint, dayoffs, setup.output_dir)
        report_generator.generate()
        
        logger.info("Processo concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante execução: {str(e)}")
        raise typer.Exit(1)

if __name__ == "__main__":
    # Configura e executa a aplicação
    app() 