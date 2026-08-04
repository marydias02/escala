import polars as pl
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient
from loguru import logger

from config.settings import settings

TABLE_NAME = "MM"

if __name__ == "__main__":
    logger.info("🎯 Testing access to Azure Lakehouse")
    credential = ClientSecretCredential(
        settings.AZURE_TENANT_ID, settings.AZURE_CLIENT_ID, settings.AZURE_CLIENT_SECRET
    )

    service_client = DataLakeServiceClient(account_url=settings.LAKEHOUSE_STORAGE_ENDPOINT, credential=credential)
    file_system_client = service_client.get_file_system_client(file_system=settings.LAKEHOUSE_WORKSPACE_ID)

    tables_path = f"{settings.LAKEHOUSE_ID}/Tables/sap"
    logger.info(f"Listing tables under '{tables_path}'")
    lh_tables = sorted(
        p.name.split("/")[-1] for p in file_system_client.get_paths(path=tables_path, recursive=False) if p.is_directory
    )
    logger.info(f"Found {len(lh_tables)} tables: {lh_tables}")

    table_uri = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{TABLE_NAME}"
    logger.info(f"Querying '{TABLE_NAME}' table at {table_uri}")
    df = pl.read_delta(
        table_uri,
        storage_options={
            "azure_tenant_id": settings.AZURE_TENANT_ID,
            "azure_client_id": settings.AZURE_CLIENT_ID,
            "azure_client_secret": settings.AZURE_CLIENT_SECRET,
            "use_fabric_endpoint": "true",
        },
    )
    logger.info(f"'{TABLE_NAME}' has {df.height} rows and {df.width} columns")
    print(df.head())
