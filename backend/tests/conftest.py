import os
import tempfile

# Isolated SQLite database for the whole test session (must be set before app imports).
_DB = os.path.join(tempfile.mkdtemp(prefix="apexvision-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["AI_PROVIDER"] = "offline"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.simulation.assumptions import VehicleAssumptions  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def a() -> VehicleAssumptions:
    return VehicleAssumptions()
