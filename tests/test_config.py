import pytest
from datetime import datetime, timedelta, timezone
from src.models.config import Executor, DayOff, ExecutorsConfig

@pytest.fixture
def timezone_br():
    """Fixture para timezone de Brasília (UTC-3)"""
    return timezone(timedelta(hours=-3))

def test_executor_creation():
    """Testa a criação de um executor"""
    executor = Executor(
        email="test@example.com",
        capacity=6
    )
    
    assert executor.email == "test@example.com"
    assert executor.capacity == 6

def test_executor_validation():
    """Testa a validação de um executor"""
    # Testa criação com valores válidos
    executor = Executor(
        email="test@example.com",
        capacity=6
    )
    assert executor is not None

def test_dayoff_creation(timezone_br):
    """Testa a criação de um dayoff"""
    date = datetime(2024, 3, 18, tzinfo=timezone_br)
    
    dayoff = DayOff(
        date=date,
        period="full"
    )
    
    assert dayoff.date == date
    assert dayoff.period == "full"

def test_dayoff_validation(timezone_br):
    """Testa a validação de um dayoff"""
    date = datetime(2024, 3, 18, tzinfo=timezone_br)
    
    # Testa criação com valores válidos
    dayoff = DayOff(
        date=date,
        period="full"
    )
    assert dayoff is not None

def test_executors_config_creation():
    """Testa a criação de uma configuração de executores"""
    config = ExecutorsConfig(
        backend=[
            Executor(email="backend1@example.com", capacity=6),
            Executor(email="backend2@example.com", capacity=6)
        ],
        frontend=[
            Executor(email="frontend1@example.com", capacity=6),
            Executor(email="frontend2@example.com", capacity=6)
        ],
        qa=[
            Executor(email="qa1@example.com", capacity=6),
            Executor(email="qa2@example.com", capacity=6)
        ],
        devops=[
            Executor(email="devops1@example.com", capacity=6),
            Executor(email="devops2@example.com", capacity=6)
        ]
    )
    
    assert len(config.backend) == 2
    assert len(config.frontend) == 2
    assert len(config.qa) == 2
    assert len(config.devops) == 2

def test_executors_config_validation():
    """Testa a validação de uma configuração de executores"""
    # Testa criação com valores válidos
    config = ExecutorsConfig(
        backend=[
            Executor(email="backend1@example.com", capacity=6),
            Executor(email="backend2@example.com", capacity=6)
        ],
        frontend=[
            Executor(email="frontend1@example.com", capacity=6),
            Executor(email="frontend2@example.com", capacity=6)
        ],
        qa=[
            Executor(email="qa1@example.com", capacity=6),
            Executor(email="qa2@example.com", capacity=6)
        ],
        devops=[
            Executor(email="devops1@example.com", capacity=6),
            Executor(email="devops2@example.com", capacity=6)
        ]
    )
    assert config is not None

def test_executors_config_get_all_executors():
    """Testa a obtenção de todos os executores"""
    config = ExecutorsConfig(
        backend=[
            Executor(email="backend1@example.com", capacity=6),
            Executor(email="backend2@example.com", capacity=6)
        ],
        frontend=[
            Executor(email="frontend1@example.com", capacity=6),
            Executor(email="frontend2@example.com", capacity=6)
        ],
        qa=[
            Executor(email="qa1@example.com", capacity=6),
            Executor(email="qa2@example.com", capacity=6)
        ],
        devops=[
            Executor(email="devops1@example.com", capacity=6),
            Executor(email="devops2@example.com", capacity=6)
        ]
    )
    
    all_executors = config.backend + config.frontend + config.qa + config.devops
    assert len(all_executors) == 8

def test_executors_config_get_executor_by_email():
    """Testa a obtenção de um executor por email"""
    config = ExecutorsConfig(
        backend=[
            Executor(email="backend1@example.com", capacity=6),
            Executor(email="backend2@example.com", capacity=6)
        ],
        frontend=[
            Executor(email="frontend1@example.com", capacity=6),
            Executor(email="frontend2@example.com", capacity=6)
        ],
        qa=[
            Executor(email="qa1@example.com", capacity=6),
            Executor(email="qa2@example.com", capacity=6)
        ],
        devops=[
            Executor(email="devops1@example.com", capacity=6),
            Executor(email="devops2@example.com", capacity=6)
        ]
    )
    
    executor = next((e for e in config.backend if e.email == "backend1@example.com"), None)
    assert executor is not None
    assert executor.email == "backend1@example.com"
    assert executor.capacity == 6 