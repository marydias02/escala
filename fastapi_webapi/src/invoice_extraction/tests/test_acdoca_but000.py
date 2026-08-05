"""Manual smoke test for `utils.utils_lakehouse`: reads last month of ACDOCA
and the first 10 BUT000 business partners. Run directly (not via pytest) —
same convention as `lakehouse_access.py` in this folder.
"""

from datetime import date, timedelta

import polars as pl
from loguru import logger

from utils.utils_lakehouse import scan_table


def _last_month_range() -> tuple[date, date]:
    first_of_this_month = date.today().replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start, last_month_end


def _as_date(column: str, dtype: pl.DataType) -> pl.Expr:
    """ACDOCA date columns come from SAP either as an actual date/datetime
    dtype or as an unparsed 'YYYYMMDD' string, depending on the replication —
    handle both.
    """
    if dtype == pl.Utf8:
        return pl.col(column).str.strptime(pl.Date, "%Y%m%d", strict=False)
    return pl.col(column).cast(pl.Date)


if __name__ == "__main__":
    start, end = _last_month_range()
    logger.info(f"Reading ACDOCA for postings between {start} and {end}")

    acdoca = scan_table("ACDOCA")
    budat_dtype = acdoca.collect_schema()["BUDAT"]
    acdoca_last_month = acdoca.filter(_as_date("BUDAT", budat_dtype).is_between(start, end)).collect()

    logger.info(f"ACDOCA: {acdoca_last_month.height} rows, {acdoca_last_month.width} columns")
    print(acdoca_last_month.head())

    logger.info("Reading top 10 BUT000 business partners")
    but000_top10 = scan_table("BUT000").limit(10).collect()

    logger.info(f"BUT000: {but000_top10.height} rows, {but000_top10.width} columns")
    print(but000_top10)
