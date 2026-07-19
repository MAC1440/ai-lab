from io import BytesIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from dependencies import system_service


router = APIRouter(prefix="/system", tags=["System"])


@router.get("/diagnostics")
def diagnostics():
    return system_service.diagnostics()


@router.get("/backup")
def download_backup():
    filename, content = system_service.create_backup()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
