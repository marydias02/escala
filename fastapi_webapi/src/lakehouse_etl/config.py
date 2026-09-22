"""Constants for the lakehouse ETL. No I/O, no polars."""

# Target Postgres tables.
SUPPLIERS_TABLE = "dim_suppliers"
BUSINESS_UNITS_TABLE = "dim_business_units"
PURCHASE_ORDERS_TABLE = "fct_purchase_orders"

# The lakehouse replicates two SAP clients: 100 (productive) and 000 (SAP's
# reference client). Dropping this filter makes T001 return a duplicate bu_id —
# 0001 is "SAP SE" in 000 and "SAP A.G." in 100 — which collides on the PK.
# EKKO and LFA1 are 100% client 100.
SAP_CLIENT = "100"

# T001 rows are kept unless SAP flags them as a template. This leaves 137 rows:
# 133 real companies plus 0001, EG01, PT00 and PT03, which XTEMPLT does not flag
# and which we deliberately keep. F_OBSOLETE rows stay too — POs reference them.
TEMPLATE_FLAG = "X"

# EKKO floor, applied on every run so an old PO touched today does not appear.
PO_DATE_FLOOR = "20260101"

# EKKO.MEMORY = 'X' marks a held, never-posted draft.
PO_HELD_FLAG = "X"

# Rows per INSERT/DELETE batch.
UPSERT_CHUNK_SIZE = 1000

# pg_try_advisory_lock key. Distinct from the email cron's RUN_LOCK_KEY
# (3_141_592) in invoice_extraction/config.py, so the two never block each other.
LAKEHOUSE_RUN_LOCK_KEY = 2_718_281

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
