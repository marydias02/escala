import polars as pl
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient
from loguru import logger

from config.settings import settings

TABLE_NAME_PO = "EKKO"
TABLE_NAME_PO_LINES = "EKPO"

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

    # with xlsxwriter.Workbook("src/invoice_extraction/output/tables.xlsx") as wb:
    #     for table in lh_tables:
    #         table_uri = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{table}"
    #         logger.info(f"Querying '{table}' table at {table_uri}")
    #         df = pl.read_delta(
    #             table_uri,
    #             storage_options={
    #                 "azure_tenant_id": settings.AZURE_TENANT_ID,
    #                 "azure_client_id": settings.AZURE_CLIENT_ID,
    #                 "azure_client_secret": settings.AZURE_CLIENT_SECRET,
    #                 "use_fabric_endpoint": "true",
    #             },
    #         )
    #         logger.info(f"'{table}' has {df.height} rows and {df.width} columns")
    #         preview = df.head(10)
    #         binary_cols = [name for name, dtype in preview.schema.items() if dtype == pl.Binary]
    #         if binary_cols:
    #             preview = preview.with_columns(pl.col(c).bin.encode("hex") for c in binary_cols)
    #         preview.write_excel(workbook=wb, worksheet=table)

    table_uri_ekko = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{TABLE_NAME_PO}"
    df_ekko = pl.read_delta(
        table_uri_ekko,
        storage_options={
            "azure_tenant_id": settings.AZURE_TENANT_ID,
            "azure_client_id": settings.AZURE_CLIENT_ID,
            "azure_client_secret": settings.AZURE_CLIENT_SECRET,
            "use_fabric_endpoint": "true",
        },
    )

    table_uri_epko = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{TABLE_NAME_PO_LINES}"
    df_epko = pl.read_delta(
        table_uri_epko,
        storage_options={
            "azure_tenant_id": settings.AZURE_TENANT_ID,
            "azure_client_id": settings.AZURE_CLIENT_ID,
            "azure_client_secret": settings.AZURE_CLIENT_SECRET,
            "use_fabric_endpoint": "true",
        },
    )

    df_ekko_reduced = df_ekko.select(["MANDT", "EBELN", "LIFNR", "BUKRS", "BEDAT", "WAERS"])

    df_epko_reduced = df_epko.select(["MANDT", "EBELN", "EBELP", "MENGE", "MEINS", "NETPR", "PEINH", "NETWR", "LOEKZ"])

    df_pos_final = df_ekko_reduced.join(df_epko_reduced, on=["MANDT", "EBELN"], how="left")

    df_pos_final = df_pos_final.with_columns((pl.col("LOEKZ").str.strip_chars() != "").alias("is_deleted"))

    df_pos_final = df_pos_final.filter(pl.col("BEDAT") > "20260101")

    print(df_pos_final.head())

    df_pos_final.write_csv("src/invoice_extraction/output/purchase_orders_2026.csv")
