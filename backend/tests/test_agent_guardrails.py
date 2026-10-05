"""Exercise boundary violations and allowed imports without a database."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_boundaries.py"
spec = importlib.util.spec_from_file_location("check_boundaries", SCRIPT)
boundaries = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundaries)


@pytest.mark.parametrize("layer", ["models", "repositories", "schemas"])
@pytest.mark.parametrize(
    "source",
    [
        "import app.api.routes.auth as auth",
        "from app.services.accounts import create_user_with_profile",
        "from app import services as orchestration",
        "from ..api.routes import auth",
        "from .. import services",
    ],
)
def test_rejects_upward_imports(layer, source):
    assert boundaries.check_source(source, f"backend/app/{layer}/example.py")


@pytest.mark.parametrize("method", sorted(boundaries.TRANSACTION_METHODS))
def test_rejects_repository_transaction_control(method):
    source = f"async def save(db):\n    await db.{method}()\n"
    errors = boundaries.check_source(source, "backend/app/repositories/example.py")
    assert len(errors) == 1
    assert "callers own transactions" in errors[0]


def test_allows_data_imports_flush_and_transaction_named_text():
    source = '''
from app.models import User
from ..models import Profile
from sqlalchemy.ext.asyncio import AsyncSession
# db.commit() in a comment is not a call.
async def create(db: AsyncSession):
    message = "db.rollback() in a string is not a call"
    await db.flush()
    return message
'''
    assert not boundaries.check_source(source, "backend/app/repositories/example.py")


def test_models_can_define_transaction_named_methods_without_calling_them():
    assert not boundaries.check_source(
        "class Record:\n    def commit(self): pass\n",
        "backend/app/models/example.py",
    )


def test_boundary_command_fails_on_violation_and_passes_after_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    for layer in boundaries.LOWER_LAYERS:
        (tmp_path / "backend" / "app" / layer).mkdir(parents=True)
    repository = tmp_path / "backend" / "app" / "repositories" / "example.py"
    repository.write_text("from app.services import accounts\n", encoding="utf-8")
    assert boundaries.main() == 1
    repository.write_text("from app.models import User\n", encoding="utf-8")
    assert boundaries.main() == 0


def test_boundary_command_fails_if_expected_layer_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    assert boundaries.main() == 1
