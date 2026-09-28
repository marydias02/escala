import sys; sys.path.insert(0, r"C:\Users\ANDRE~1.MOR\AppData\Local\Temp\claude\C--Users-andre-morim-Desktop-escala-fastapi-webapi\c8898757-0615-4414-b8fd-8ba85a6865e6\scratchpad")
import polars as pl
from load_ar import load
from utils.utils_lakehouse import scan_table
pl.Config.set_tbl_cols(-1); pl.Config.set_tbl_width_chars(250); pl.Config.set_tbl_rows(40)
ar = load()
print(ar.height, "lines;", ar["document_nr"].n_unique(), "docs;", ar["client_id"].n_unique(), "clients; sum", round(ar["amount"].sum(),2))
print(ar.group_by("doc_type","special_gl", (pl.col("amount")<0).alias("neg")).agg(n=pl.len(), s=pl.col("amount").sum().round(2)).sort("n",descending=True))
print(ar.group_by("sym","due_sym").len())
print("dup doc numbers:", ar.group_by("document_nr").len().filter(pl.col("len")>1).height)
docs = ar["document_nr"].unique().to_list()
b = scan_table("BSEG").filter((pl.col("MANDT")=="100") & (pl.col("KOART")=="D") & pl.col("BELNR").is_in(docs)).select("BUKRS","GJAHR","BELNR","KUNNR","AUGBL").collect()
print(b.join(ar.select(pl.col("document_nr").alias("BELNR"), pl.col("client_id").alias("KUNNR")).unique(), on=["BELNR","KUNNR"]).group_by("BUKRS").agg(n=pl.len(), docs=pl.col("BELNR").n_unique()).sort("n",descending=True))
t = scan_table("T001").filter(pl.col("MANDT")=="100").filter(pl.col("BUTXT").str.to_lowercase().str.contains("marfrete")).select("BUKRS","BUTXT").collect(); print(t)
