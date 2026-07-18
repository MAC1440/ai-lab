import os
from pathlib import Path

from services.change_service import ChangeService
from services.project_detection_service import ProjectDetectionService
from services.project_context_service import ProjectContextService
from services.repair_service import RepairService
from services.repair_store import RepairStore
from services.scaffold_service import ScaffoldService
from services.verification_service import VerificationService
from services.verification_store import VerificationStore
from services.workspace_service import WorkspaceService


workspace_service = WorkspaceService()
project_detection_service = ProjectDetectionService(workspace_service)
project_context_service = ProjectContextService(
    workspace_service,
    project_detection_service,
)

_backend_root = Path(__file__).resolve().parent
_configured_database_path = os.getenv(
    "VERIFICATION_DB_PATH",
    "data/verification.sqlite3",
)
_database_path = Path(_configured_database_path).expanduser()
if not _database_path.is_absolute():
    _database_path = _backend_root / _database_path

verification_store = VerificationStore(_database_path)

_changes_database_path = Path(
    os.getenv("CHANGE_DB_PATH", "data/changes.sqlite3")
).expanduser()
if not _changes_database_path.is_absolute():
    _changes_database_path = _backend_root / _changes_database_path
change_service = ChangeService(
    workspace_service,
    database_path=_changes_database_path,
)
scaffold_service = ScaffoldService(workspace_service, change_service)

_repairs_database_path = Path(
    os.getenv("REPAIR_DB_PATH", "data/repairs.sqlite3")
).expanduser()
if not _repairs_database_path.is_absolute():
    _repairs_database_path = _backend_root / _repairs_database_path
repair_store = RepairStore(_repairs_database_path)
repair_service = RepairService(
    workspace_service=workspace_service,
    verification_store=verification_store,
    change_service=change_service,
    store=repair_store,
)
verification_service = VerificationService(
    workspace_service=workspace_service,
    project_detection_service=project_detection_service,
    store=verification_store,
    max_output_chars=int(
        os.getenv("VERIFICATION_MAX_OUTPUT_CHARS", "200000")
    ),
)
