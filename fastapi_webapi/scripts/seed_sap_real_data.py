"""Replace dim_suppliers / dim_business_units / fct_purchase_orders with real SAP data.

Reads LFA1, BUT000, T001 and EKKO from the Azure Lakehouse and truncates + reloads
the three master-data tables from them. The previous (dummy) rows are assumed to
already be preserved elsewhere (e.g. *_dummy tables) before running this script.

    python scripts/seed_sap_real_data.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl
from loguru import logger

from config.settings import settings
from utils.utils_db import get_pool, insert_rows

# is_financial = 1 -> financial supplier (banks, insurers, utilities, municipalities)
FINANCIAL_SUPPLIERS = [
    "ADS - Aguas de Santiago",
    "Ageas Portugal-Companhia Seguros, S",
    "Aguas e Energia da Boavista",
    "AIG Europe Limited-Sucursal em Port",
    "ARM-Águas e Resíduos da Madeira, S.",
    "Banco BIC Português, S.A.",
    "Banco BPI, S.A.",
    "Banco Comercial Portugues, S.A.",
    "Banco Santander Totta, S.A.",
    "BCA - Banco Comercial do Atlântico,",
    "BNP Paribas Real Estate Investment Management Germany GMBH",
    "Build - Contribuição Investimentos Imobiliária, Lda.",
    "CA Indosuez Wealth (Europe) Sucursal em Portugal",
    "Caixa Económica Montepio Geral",
    "Caixa Geral de Depósitos, S.A.",
    "Câmara Municipal de Silves",
    "Companhia Seguros Allianz Portugal,",
    "Condomínio do Edifício da Quinta do Adarse Sito em Lugar de Adarse",
    "Conservatória do Registo Comercial/ Automóvel do Funchal",
    "Conservatória Registo Predial Stª C Conservatória Reg Pred Santa Cruz",
    "COSEC - Companhia de Seguros de Créditos, S.A.",
    "CV Telecom, S.A.",
    "Dir. Reg. Ord. do Território e Ambi",
    "Döhle Assekuranzkontor GmbH & Co. K",
    "EDA - Electricidade dos Açores, S.A",
    "EDEC - Empresa Distribuição de Electricidade de Cabo Verde, S.A.",
    "EDP Comercial-Comercializ. Energia,",
    "EEM-Empresa Electricidade Madeira,",
    "Electra - Empresa de Electricidade e Água, S.A.",
    "Electra Norte, S.A.",
    "Endesa Energia, S.A. - Sucursal em Portugal",
    "EPAL-Emp. Portuguesa Águas Livres,",
    "Ergo - EUROPÄISCHE REISEVERSICHERUN Sucursal em Portugal",
    "Euler Hermes S.A. - Sucursal em Por",
    "Fidelidade-Companhia de Seguros, S.",
    "Garantia Seguros",
    "GARD AS",
    "Generali Seguros, S.A.",
    "Grupo Mais SARL",
    "Guinebis - Guiné-Bissau Seguros, S.",
    "Iberdrola Clientes Portugal Unipess Lda.",
    "Impar Comp. Caboverdiana de Seguros",
    "Indaqua Matosinhos - Gestão de Água de Matosinhos, S.A.",
    "Insure Marine Underwriting N.V",
    "MEO Energia - Comercialização de Energia, S.A.",
    "MEO-Serv. Comunicações Multimédia,",
    "MGEN Distribuição de Seguros",
    "Município da Horta",
    "Município de Condeixa-a-Nova",
    "Município de Santa Cruz.",
    "Município de São Roque do Pico",
    "Municipio de Vila Franca de Xira",
    "Município do Funchal",
    "Nível Triunfante, Lda.",
    "Nortenhazores - Indústria e Comérci Materiais de Construção, S.A. S",
    "NOS Madeira Comunicações, S.A.",
    "Novo Banco, S.A.",
    "NSIA INSSURANCES NSIA INSSURANCES",
    "Occident GCO, S.A.",
    "Onitelecom - Infocomunicacões, S.A.",
    "SDM-Soc. Desenvolvimento Madeira, S",
    "Serviços Municipalizados Agua e Saneamento Camara Municipal V Franc",
    "Serviços Municipalizados da Camara Municipal de Ponta Delgada",
    "SISP, Sarl - Sociedade Interbancári Sistemas de Pagamentos",
    "Sociedad de Previsión Bancaria Ibér SPB",
    "Spacetel Guiné-Bissau, S.A.",
    "Susana Lopes Teixeira",
    "Thunder Portugal Propco II, Unipess Lda.",
    "TT Club Mutual Insurance, LTD.",
    "UBS Europe SE - Sucursal em Portuga",
    "UBS Europe SE, Luxembourg Branch",
    "Unicre, S.A.",
    "Victória-Seguros, S.A.",
    "Vodafone Portugal-Comunicações, S.A",
]

# is_financial = 2 -> both financial and logistics supplier
BOTH_SUPPLIERS = [
    "APRAM-Administração Portos da RAM,",
    "Carlos Saraiva-Expl. Turística, S.A",
]


def _full_name() -> pl.Expr:
    """Join LFA1 NAME1-NAME4; SAP splits long names across the 35-char lines."""
    lines = []
    for col in ("NAME1", "NAME2", "NAME3", "NAME4"):
        trimmed = pl.col(col).cast(pl.String).str.strip_chars()
        # Blank dot-only placeholder lines (one supplier uses "." to fill NAME3/NAME4)
        lines.append(pl.when(trimmed.str.contains(r"^\.+$")).then(None).otherwise(trimmed))
    return (
        pl.concat_str(lines, separator=" ", ignore_nulls=True)
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .alias("name")
    )


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


async def main() -> None:
    df_lfa1 = _read_table("LFA1")
    df_but000 = _read_table("BUT000")
    df_t001 = _read_table("T001")
    df_ekko = _read_table("EKKO")

    dim_suppliers = (
        df_lfa1.select(
            pl.col("LIFNR").alias("supplier_id"),
            _full_name(),
            pl.coalesce(pl.col("STCEG"), pl.col("STCD1")).alias("vat"),
            pl.col("LAND1").alias("country"),
        )
        .join(
            df_but000.select(pl.col("PARTNER").alias("supplier_id"), pl.col("BU_LANGU").alias("preferred_language")),
            on="supplier_id",
            how="left",
        )
        .with_columns(
            pl.when(pl.col("name").is_in(BOTH_SUPPLIERS))
            .then(2)
            .when(pl.col("name").is_in(FINANCIAL_SUPPLIERS))
            .then(1)
            .otherwise(0)
            .alias("is_financial")
        )
        .unique(subset="supplier_id", keep="first")
    )

    dim_business_units = df_t001.select(
        pl.col("BUKRS").alias("bu_id"),
        pl.col("BUTXT").alias("name"),
        pl.col("STCEG").alias("vat"),
        pl.col("LAND1").alias("country"),
    ).unique(subset="bu_id", keep="first")

    fct_purchase_orders = (
        df_ekko.filter(pl.col("BEDAT") >= "20260101")
        .select(
            pl.col("EBELN").alias("po_code"),
            pl.col("LIFNR").alias("supplier_id"),
            pl.col("BUKRS").alias("bu_id"),
            pl.col("BEDAT").str.strptime(pl.Date, "%Y%m%d").alias("date"),
            pl.col("RLWRT").alias("value"),
            pl.col("WAERS").alias("currency"),
        )
        .unique(subset="po_code", keep="first")
    )
    logger.info(f"{fct_purchase_orders.height} fct_purchase_orders rows to insert")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE dim_suppliers, dim_business_units, fct_purchase_orders")
        # "dim_business_units, dim_suppliers")

    n_suppliers = await insert_rows("dim_suppliers", dim_suppliers.to_dicts())
    n_bus = await insert_rows("dim_business_units", dim_business_units.to_dicts())
    n_pos = await insert_rows("fct_purchase_orders", fct_purchase_orders.to_dicts())
    logger.info(f"Inserted {n_suppliers} supplier, {n_bus} business units and {n_pos} purchase order rows.")


if __name__ == "__main__":
    asyncio.run(main())
