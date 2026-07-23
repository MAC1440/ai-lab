import os
from pathlib import Path

from services.agent_service import AgentService
from services.change_service import ChangeService
from services.conversation_service import ConversationService
from services.conversation_store import ConversationStore
from services.knowledge_source_service import KnowledgeSourceService
from services.mcp_service import MCPService
from services.model_benchmark_service import ModelBenchmarkService
from services.model_capability_service import ModelCapabilityService
from services.project_context_service import ProjectContextService
from services.project_detection_service import ProjectDetectionService
from services.project_repair_orchestrator import ProjectRepairOrchestrator
from services.project_task_completion_service import ProjectTaskCompletionService
from services.project_task_orchestrator import ProjectTaskOrchestrator
from services.project_task_service import ProjectTaskService
from services.project_task_store import ProjectTaskStore
from services.provider_settings_service import ProviderSettingsService
from services.reliability_benchmark_service import ReliabilityBenchmarkService
from services.reliability_benchmark_store import ReliabilityBenchmarkStore
from services.repair_service import RepairService
from services.repair_store import RepairStore
from services.run_cancellation_service import RunCancellationService
from services.scaffold_service import ScaffoldService
from services.source_validation_service import SourceValidationService
from services.system_service import SystemService
from services.task_model_client import PydanticTaskModelClient
from services.unity_docs_service import UnityDocsService
from services.verification_service import VerificationService
from services.verification_store import VerificationStore
from services.workspace_service import WorkspaceService

workspace_service = WorkspaceService()
_backend_root = Path(__file__).resolve().parent
project_detection_service = ProjectDetectionService(workspace_service)
project_context_service = ProjectContextService(
    workspace_service,
    project_detection_service,
)

_provider_settings_path = Path(
    os.getenv("PROVIDER_SETTINGS_PATH", "data/provider-settings.json")
).expanduser()
if not _provider_settings_path.is_absolute():
    _provider_settings_path = _backend_root / _provider_settings_path
provider_settings_service = ProviderSettingsService(_provider_settings_path)

_model_capabilities_path = Path(
    os.getenv("MODEL_CAPABILITIES_PATH", "data/model-capabilities.json")
).expanduser()
if not _model_capabilities_path.is_absolute():
    _model_capabilities_path = _backend_root / _model_capabilities_path
model_capability_service = ModelCapabilityService(_model_capabilities_path)

_mcp_settings_path = Path(
    os.getenv("MCP_SETTINGS_PATH", "data/mcp-settings.json")
).expanduser()
if not _mcp_settings_path.is_absolute():
    _mcp_settings_path = _backend_root / _mcp_settings_path
mcp_service = MCPService(_mcp_settings_path)

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

_conversations_database_path = Path(
    os.getenv("CONVERSATION_DB_PATH", "data/conversations.sqlite3")
).expanduser()
if not _conversations_database_path.is_absolute():
    _conversations_database_path = _backend_root / _conversations_database_path
conversation_store = ConversationStore(_conversations_database_path)
conversation_service = ConversationService(
    workspace_service,
    AgentService(),
    conversation_store,
)

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

_project_tasks_database_path = Path(
    os.getenv("PROJECT_TASK_DB_PATH", "data/project-tasks.sqlite3")
).expanduser()
if not _project_tasks_database_path.is_absolute():
    _project_tasks_database_path = _backend_root / _project_tasks_database_path
project_task_store = ProjectTaskStore(_project_tasks_database_path)
project_task_service = ProjectTaskService(
    workspace_service=workspace_service,
    change_service=change_service,
    store=project_task_store,
)
task_model_client = PydanticTaskModelClient(
    provider_settings_service=provider_settings_service,
    model_capability_service=model_capability_service,
    agent_service=AgentService(),
)
source_validation_service = SourceValidationService(workspace_service)
project_task_orchestrator = ProjectTaskOrchestrator(
    task_service=project_task_service,
    project_context_service=project_context_service,
    change_service=change_service,
    model_client=task_model_client,
    source_validation_service=source_validation_service,
)
verification_service = VerificationService(
    workspace_service=workspace_service,
    project_detection_service=project_detection_service,
    store=verification_store,
    max_output_chars=int(
        os.getenv("VERIFICATION_MAX_OUTPUT_CHARS", "200000")
    ),
)
project_task_completion_service = ProjectTaskCompletionService(
    task_service=project_task_service,
    change_service=change_service,
    project_detection_service=project_detection_service,
    verification_service=verification_service,
    repair_service=repair_service,
)
project_repair_orchestrator = ProjectRepairOrchestrator(
    task_service=project_task_service,
    change_service=change_service,
    repair_service=repair_service,
    verification_store=verification_store,
    model_client=task_model_client,
    source_validation_service=source_validation_service,
)
model_benchmark_service = ModelBenchmarkService(
    model_client=task_model_client,
    capability_service=model_capability_service,
)

_reliability_database_path = Path(
    os.getenv(
        "RELIABILITY_BENCHMARK_DB_PATH",
        "data/reliability-benchmarks.sqlite3",
    )
).expanduser()
if not _reliability_database_path.is_absolute():
    _reliability_database_path = _backend_root / _reliability_database_path
_reliability_work_root = Path(
    os.getenv(
        "RELIABILITY_BENCHMARK_WORK_ROOT",
        "data/reliability-workspaces",
    )
).expanduser()
if not _reliability_work_root.is_absolute():
    _reliability_work_root = _backend_root / _reliability_work_root
reliability_benchmark_store = ReliabilityBenchmarkStore(
    _reliability_database_path
)
reliability_benchmark_service = ReliabilityBenchmarkService(
    model_client=task_model_client,
    store=reliability_benchmark_store,
    work_root=_reliability_work_root,
)

system_service = SystemService(
    workspace_service=workspace_service,
    provider_settings_service=provider_settings_service,
    mcp_service=mcp_service,
    agent_ids=[agent["id"] for agent in AgentService().list_agents()],
    database_paths={
        "verification": _database_path,
        "changes": _changes_database_path,
        "conversations": _conversations_database_path,
        "repairs": _repairs_database_path,
        "project-tasks": _project_tasks_database_path,
        "reliability-benchmarks": _reliability_database_path,
    },
    config_paths={
        "provider-settings": _provider_settings_path,
        "mcp-settings": _mcp_settings_path,
        "model-capabilities": _model_capabilities_path,
    },
    data_directory=_backend_root / "data",
)

unity_docs_service = UnityDocsService()
run_cancellation_service = RunCancellationService()
knowledge_source_service = KnowledgeSourceService(
    _backend_root / "data/knowledge-sources.json"
)
