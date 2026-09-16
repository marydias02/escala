import io

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from api.dependencies.security import has_authorization_for
from api.dependencies.services import AirExampleServiceDependency

router = APIRouter(prefix="/air", tags=["air"])

# Triggering and uploading are the only actions separating `admin` from `user`.
READ_RUNS = has_authorization_for("read", "runs")
CREATE_RUNS = has_authorization_for("create", "runs")


@router.post("/run", summary="Trigger a new run", status_code=201, dependencies=[CREATE_RUNS])
async def launch_run(service: AirExampleServiceDependency, file: UploadFile = File(...)):
    """
    Trigger a new run with an input file.
    """
    content = await file.read()

    run_id = await service.launch_run(user_id="backend", file_content=content)

    return {"run_id": run_id}


@router.get("/runs", summary="List runs", dependencies=[READ_RUNS])
async def list_runs(service: AirExampleServiceDependency):
    """List existing runs."""
    runs = await service.list_runs()

    return runs


@router.post("/template", summary="Upload an input template", status_code=201, dependencies=[CREATE_RUNS])
async def upload_template(service: AirExampleServiceDependency, file: UploadFile = File(...)):
    """Upload a template file used for future runs."""
    content = await file.read()
    an_int = await service.upload_template(file_content=content)

    return {"something": an_int}


@router.get("/template", summary="Download input template", dependencies=[READ_RUNS])
async def download_template(service: AirExampleServiceDependency):
    """Download the currently configured input template."""

    asset = await service.download_template()

    content = asset.get("content") if isinstance(asset, dict) else getattr(asset, "content", None)

    return Response(content, media_type="application/octet-stream")


@router.get("/runs/{run_id}", summary="Get run details", dependencies=[READ_RUNS])
async def get_run_details(run_id: int, service: AirExampleServiceDependency):
    """Get details for a specific run."""
    details = await service.get_run_details(run_id)

    return details


@router.get("/runs/{run_id}/input", summary="Download run input file", dependencies=[READ_RUNS])
async def download_run_input(run_id: int, service: AirExampleServiceDependency):
    asset = await service.download_run_input(run_id)

    content = asset.get("content") if isinstance(asset, dict) else getattr(asset, "content", None)

    return Response(content, media_type="application/octet-stream")


@router.get("/runs/{run_id}/output", summary="Download run output file", dependencies=[READ_RUNS])
async def download_run_output(run_id: int, service: AirExampleServiceDependency):
    asset = await service.download_run_output(run_id)

    content = asset.get("content") if isinstance(asset, dict) else getattr(asset, "content", None)

    return Response(content, media_type="application/octet-stream")


@router.get("/runs/{run_id}/output/tar", summary="Download run output as parsed tar.gz", dependencies=[READ_RUNS])
async def download_tar_output(run_id: int, service: AirExampleServiceDependency):
    """Download and parse a tar.gz output into a JSON-like structure when possible."""
    parsed = await service.download_tar_gz_output(run_id)

    return parsed


@router.get("/runs/{run_id}/output/xlsx", summary="Download XLSX output as json", dependencies=[READ_RUNS])
async def download_xlsx_output(run_id: int, service: AirExampleServiceDependency):
    data = await service.download_xlsx_output(run_id)

    # Return a placeholder representation (polars DataFrame cannot be directly streamed)
    return {k: v.to_dict(as_series=False) for k, v in data.items()}


@router.get("/runs/{run_id}/output/csv", summary="Download CSV output as text", dependencies=[READ_RUNS])
async def download_csv_output(run_id: int, service: AirExampleServiceDependency):
    df = await service.download_csv_output(run_id)
    content = io.BytesIO()
    df.write_csv(content)
    return Response(content, media_type="text/csv")
