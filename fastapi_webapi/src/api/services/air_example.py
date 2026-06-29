import asyncio
import io
import json
import time
from typing import Any, Dict, Optional

import polars as pl
from airpy.air import Air
from airpy.asset import AssetFile
from loguru import logger


class AirExampleService:
    def __init__(self, app_id: int):
        self.air_client = Air(app_id)

    async def launch_run(self, user_id: str, file_content: bytes) -> int:
        run_name = f"API-{user_id}-{hex(int(time.time_ns()))}"
        run_notes = json.dumps({"user_id": user_id, "timestamp": time.time()})

        params = dict(user_id=user_id)

        run_id = await self.air_client.trigger_run(
            name=run_name, notes=run_notes, input_file_path=file_content, parameters=params
        )
        asyncio.create_task(self.air_client.setup_run(run_id, input_file_path=file_content, parameters=params))

        return run_id

    async def list_runs(self) -> list[Dict[str, Any]]:
        runs = await self.air_client.get_runs()

        if not runs:
            logger.warning("No runs found")
            return []

        formatted_runs = []
        for run in runs:
            formatted_runs.append(
                {"id": run.run_id, "name": run.run_name, "status": run.status, "created_at": run.created_at}
            )

        return formatted_runs

    async def upload_template(self, file_content: bytes) -> int:
        return await self.air_client.upload_input_file_template(file_content)

    async def download_template(self) -> AssetFile:
        asset = await self.air_client.download_input_file_template()

        if asset and "content" in asset:
            logger.trace(f"Template downloaded successfully, size: {len(asset['content'])} bytes")
            return asset

        raise ValueError("Failed to download template: no content in response")

    async def get_run_details(self, run_id: int) -> Dict[str, Any]:
        logger.info(f"Fetching details for run {run_id}")
        run = await self.air_client.get_run_by_id(run_id)

        if run is None:
            raise ValueError(f"Run {run_id} not found")

        run_details = {
            "run_id": run.run_id,
            "name": run.run_name,
            "status": run.status,
            "created_at": run.created_at,
            "is_successful": run.status == "success",
        }

        return run_details

    async def download_run_input(self, run_id: int) -> AssetFile:
        asset = await self.air_client.download_run_input(run_id)

        if asset and "content" in asset:
            logger.trace(f"Input file downloaded, size: {len(asset['content'])} bytes")
            return asset

        raise ValueError(f"Failed to download input for run {run_id}")

    async def download_run_output(self, run_id: int) -> AssetFile:
        run = await self.air_client.get_run_by_id(run_id)
        if run.status != "success":
            raise ValueError(f"Cannot download output: run {run_id} has status '{run.status}', expected 'success'")

        return await self.air_client.download_run_output(run_id)

    async def download_tar_gz_output(self, run_id: int) -> Optional[Dict[str, Any]]:
        try:
            import tarfile

            output = await self.download_run_output(run_id)

            files_data = {}
            with tarfile.open(fileobj=io.BytesIO(output["content"]), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        raw_content = f.read()
                        if member.name.endswith(".json"):
                            files_data[member.name] = json.loads(raw_content.decode("UTF-8"))
                        elif member.name.endswith(".csv"):
                            files_data[member.name] = pl.read_csv(io.BytesIO(raw_content))
                        elif member.name.endswith(".xlsx"):
                            files_data[member.name] = pl.read_excel(io.BytesIO(raw_content), sheet_id=0)
                        else:
                            files_data[member.name] = raw_content

            logger.trace(f"Output parsed successfully for run {run_id}")
            return files_data
        except Exception as e:
            logger.error(f"Failed to parse output for run {run_id}: {str(e)}")
            return None

    async def download_xlsx_output(self, run_id: int) -> dict[str, pl.DataFrame]:
        output = await self.download_run_output(run_id)

        try:
            return pl.read_excel(io.BytesIO(output["content"]), sheet_id=0, raise_if_empty=False)
        except Exception:
            raise

    async def download_csv_output(self, run_id: int) -> pl.DataFrame:
        output = await self.download_run_output(run_id)

        return pl.read_csv(io.BytesIO(output["content"]), has_header=True)
