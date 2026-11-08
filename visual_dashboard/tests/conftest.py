from pathlib import Path
import pytest
from src.data_access import load_data

@pytest.fixture(scope="session")
def full_data():
    return load_data(Path(__file__).resolve().parents[1]/"data/processed")[0]
