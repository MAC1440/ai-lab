from services.change_service import ChangeService
from services.workspace_service import WorkspaceService


workspace_service = WorkspaceService()
change_service = ChangeService(workspace_service)