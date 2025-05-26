# Agendador de Sprint

Sistema automatizado para agendamento de tasks em sprints com integração ao Azure DevOps.

## Índice
- [Visão Geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Configuração](#configuração)
- [Como Executar](#como-executar)
- [Regras de Negócio](#regras-de-negócio)

## Visão Geral

O Agendador de Sprint é um sistema que automatiza o agendamento de tasks dentro de sprints, integrando-se com o Azure DevOps. O sistema gerencia dependências entre tasks, múltiplas frentes de trabalho (Backend, Frontend, QA, DevOps) e garante a alocação otimizada de recursos respeitando horários de trabalho e restrições de tempo.

## Funcionalidades

- ✨ Agendamento automático de tasks com gerenciamento de dependências
- 👥 Suporte a múltiplas frentes de trabalho (Backend, Frontend, QA, DevOps)
- 🔄 Tratamento especializado para tasks de QA e DevOps
- 🌎 Agendamento no fuso horário UTC-3 (Brasília)
- ⏰ Períodos de trabalho fixos (9:00-12:00 e 14:00-17:00)
- 📊 Cálculo automático de story points
- 📅 Gerenciamento de folgas dos membros da equipe
- 📋 Geração de relatórios de agendamento

## Requisitos

### Requisitos de Sistema
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Git
- Acesso à internet (para Azure DevOps)
- Token de acesso pessoal do Azure DevOps com permissões:
  - Work Items (read, write)
  - Sprint (read)

### Requisitos de Hardware
- Mínimo de 2GB de RAM
- 100MB de espaço em disco

### Dependências Python
- python-dateutil>=2.8.2
- pytz>=2024.1
- azure-devops>=7.1.0b3
- pydantic>=2.6.1
- loguru>=0.7.2
- python-dotenv>=1.0.0
- rich>=13.7.0
- typer>=0.9.0

## Instalação

1. **Instale o Python**
   - Windows: Baixe e instale do [python.org](https://www.python.org/downloads/)
   - Linux (Ubuntu/Debian):
     ```bash
     sudo apt update
     sudo apt install python3 python3-pip
     ```
   - macOS:
     ```bash
     brew install python
     ```

2. **Clone o repositório**
   ```bash
   git clone <repository-url>
   cd agendador-sprint
   ```

3. **Crie e ative um ambiente virtual**
   
   Windows:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
   
   Linux/macOS:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

5. **Verifique a instalação**
   ```bash
   python -m src.main --help
   ```
   Deve exibir a ajuda do comando com as opções disponíveis.

## Estrutura do Projeto

```
agendador-sprint/
├── src/
│   ├── main.py           # Ponto de entrada da aplicação
│   ├── models/           # Modelos de dados
│   ├── services/         # Serviços de agendamento
│   ├── azure/           # Integração com Azure DevOps
│   └── utils/           # Utilitários
├── config/              # Arquivos de configuração
│   ├── setup.json       # Configuração principal
│   ├── executors.json   # Configuração de executores
│   ├── dayoffs.json     # Configuração de folgas
│   └── dependencies.json # Configuração de dependências
├── logs/               # Logs da aplicação
└── output/            # Relatórios gerados
```

## Configuração

### 1. Configuração Principal (config/setup.json)
```json
{
    "azure_devops": {
        "organization": "sua-organizacao",
        "project": "seu-projeto",
        "token": "seu-token"
    },
    "sprint": {
        "name": "2025_S13_Jun18-Jul01",
        "year": "2025",
        "quarter": "Q2",
        "start_date": "2025-06-18",
        "end_date": "2025-07-01"
    },
    "team": "Caminho/Da/Sua/Equipe",
    "executors_file": "config/executors.json",
    "dayoffs_file": "config/dayoffs.json",
    "dependencies_file": "config/dependencies.json",
    "output_dir": "./output",
    "timezone": "America/Sao_Paulo"
}
```

### 2. Configuração de Executores (config/executors.json)
```json
{
    "backend": [
        "backend.dev1@empresa.com",
        "backend.dev2@empresa.com"
    ],
    "frontend": [
        "frontend.dev1@empresa.com"
    ],
    "qa": [
        "qa.analista1@empresa.com"
    ],
    "devops": [
        "devops.eng1@empresa.com"
    ]
}
```

### 3. Configuração de Folgas (config/dayoffs.json)
```json
{
    "backend.dev1@empresa.com": [
        {
            "date": "2025-06-20",
            "period": "full"
        }
    ]
}
```

Períodos válidos:
- `"full"`: Dia inteiro
- `"morning"`: 9:00-12:00
- `"afternoon"`: 14:00-17:00

### 4. Configuração de Dependências (config/dependencies.json)
```json
{
    "TASK-457": ["TASK-456"]
}
```

## Como Executar

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure os arquivos na pasta `config/` conforme exemplos acima

3. Execute o agendador:
```bash
python -m src.main executar --config-dir config
```

O sistema irá:
1. Carregar as configurações
2. Conectar ao Azure DevOps
3. Obter os itens da sprint
4. Realizar o agendamento
5. Atualizar os itens no Azure DevOps
6. Gerar relatório na pasta `output/`
7. Gerar logs na pasta `logs/`

## Regras de Negócio

### Horários e Períodos

- Sistema opera em UTC-3 (Brasília)
- Períodos de trabalho:
  - Manhã: 9:00-12:00 (3 horas)
  - Tarde: 14:00-17:00 (3 horas)
- Tasks devem terminar às 12:00 ou 17:00
- Sistema reutiliza tempo restante dentro dos períodos

### Tipos de Tasks e Ordem de Agendamento

1. **Tasks Regulares**
   - Tasks de desenvolvimento padrão (Backend/Frontend)
   - Agendadas primeiro, respeitando dependências

2. **Tasks de QA**
   - Identificadas por "backend" ou "frontend" no título
   - Tasks QA Backend iniciam após última task backend
   - Tasks QA Frontend iniciam após última task frontend
   - Agendadas após tasks regulares

3. **Tasks DevOps**
   - Iniciam após última task backend da US
   - Se não houver backend, usa última task frontend
   - Agendadas após tasks de QA

4. **Tasks QA Plano de Testes**
   - Agendadas por último
   - Não requerem data de término
   - Requerem executor atribuído

### Atribuição de User Stories

User Stories são atualizadas apenas quando:
- Todas as tasks estão agendadas (status = SCHEDULED)
- Todas as tasks têm executor atribuído
- Todas as tasks têm datas definidas (exceto planos de teste)

O responsável é definido por:
1. Desenvolvedor com mais tasks na US
2. Em caso de empate:
   - Prioridade para desenvolvedores Backend
   - Depois desenvolvedores Frontend
   - Por fim, primeiro desenvolvedor do empate

### Cálculo de Story Points

| Horas    | Story Points |
|----------|--------------|
| ≤ 1      | 0.5         |
| ≤ 2      | 1           |
| ≤ 3      | 2           |
| ≤ 5      | 3           |
| ≤ 9      | 5           |
| ≤ 14     | 8           |
| ≤ 23     | 13          |
| ≤ 37     | 21          |
| ≤ 60     | 34          |
| > 60     | 55          |