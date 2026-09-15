import polars as pl
import xlsxwriter
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

    # table_uri_ekko = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{TABLE_NAME_PO}"
    # df_ekko = pl.read_delta(
    #     table_uri_ekko,
    #     storage_options={
    #         "azure_tenant_id": settings.AZURE_TENANT_ID,
    #         "azure_client_id": settings.AZURE_CLIENT_ID,
    #         "azure_client_secret": settings.AZURE_CLIENT_SECRET,
    #         "use_fabric_endpoint": "true",
    #     },
    # )

    # table_uri_epko = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{TABLE_NAME_PO_LINES}"
    # df_epko = pl.read_delta(
    #     table_uri_epko,
    #     storage_options={
    #         "azure_tenant_id": settings.AZURE_TENANT_ID,
    #         "azure_client_id": settings.AZURE_CLIENT_ID,
    #         "azure_client_secret": settings.AZURE_CLIENT_SECRET,
    #         "use_fabric_endpoint": "true",
    #     },
    # )

    # df_ekko_reduced = df_ekko.select(["MANDT", "EBELN", "LIFNR", "BUKRS", "BEDAT", "WAERS"])

    # df_epko_reduced = df_epko.select(["MANDT", "EBELN", "EBELP", "MENGE", "MEINS", "NETPR", "PEINH", "NETWR", "LOEKZ"])

    # df_pos_final = df_ekko_reduced.join(df_epko_reduced, on=["MANDT", "EBELN"], how="left")

    # df_pos_final = df_pos_final.with_columns((pl.col("LOEKZ").str.strip_chars() != "").alias("is_deleted"))

    # df_pos_final = df_pos_final.filter(pl.col("BEDAT") > "20260101")

    # print(df_pos_final.head())

    # df_pos_final.write_csv("src/invoice_extraction/output/purchase_orders_2026.csv")

    # TABLE_NAME_VENDORS = "LFA1"
    # TABLE_NAME_COMPANY_CODES = "T001"

    # with xlsxwriter.Workbook("src/invoice_extraction/output/tables.xlsx") as wb:
    #     tables_to_export = lh_tables + [t for t in (TABLE_NAME_VENDORS, TABLE_NAME_COMPANY_CODES) if t not in lh_tables]
    #     for table in tables_to_export:
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

    def _read_table(table_name: str) -> pl.DataFrame:
        table_uri = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{table_name}"
        logger.info(f"Querying '{table_name}' table at {table_uri}")
        return pl.read_delta(
            table_uri,
            storage_options={
                "azure_tenant_id": settings.AZURE_TENANT_ID,
                "azure_client_id": settings.AZURE_CLIENT_ID,
                "azure_client_secret": settings.AZURE_CLIENT_SECRET,
                "use_fabric_endpoint": "true",
            },
        )

    df_lfa1 = _read_table("LFA1")
    df_but000 = _read_table("BUT000")
    df_t001 = _read_table("T001")
    df_ekko = _read_table("EKKO")

    dim_suppliers = (
        df_lfa1.select(
            pl.col("LIFNR").alias("supplier_id"),
            pl.col("NAME1").alias("name"),
            pl.coalesce(pl.col("STCEG"), pl.col("STCD1")).alias("vat"),
            pl.col("LAND1").alias("country"),
        )
        .join(
            df_but000.select(pl.col("PARTNER").alias("supplier_id"), pl.col("BU_LANGU").alias("preferred_language")),
            on="supplier_id",
            how="left",
        )
        .with_columns(pl.lit(0).alias("is_financial"))
    )

    dim_business_units = df_t001.select(
        pl.col("BUKRS").alias("bu_id"),
        pl.col("BUTXT").alias("name"),
        pl.col("STCEG").alias("vat"),
        pl.col("LAND1").alias("country"),
    )

    fct_purchase_orders = df_ekko.select(
        pl.col("EBELN").alias("po_code"),
        pl.col("LIFNR").alias("supplier_id"),
        pl.col("BUKRS").alias("bu_id"),
        pl.col("BEDAT").alias("date"),
        pl.col("RLWRT").alias("value"),
        pl.col("WAERS").alias("currency"),
    )

    with xlsxwriter.Workbook("src/invoice_extraction/output/dim_fct_sample.xlsx") as wb:
        for sheet_name, df in (
            ("fct_purchase_orders", fct_purchase_orders),
            ("dim_suppliers", dim_suppliers),
            ("dim_business_units", dim_business_units),
        ):
            preview = df.head(50)
            binary_cols = [name for name, dtype in preview.schema.items() if dtype == pl.Binary]
            if binary_cols:
                preview = preview.with_columns(pl.col(c).bin.encode("hex") for c in binary_cols)
            preview.write_excel(workbook=wb, worksheet=sheet_name)
