import dash
from dash import html, dcc
from dash_iconify import DashIconify
from dash.dcc import Tab

from components.page_header.page_header import PageHeader
from components.banner.banner import TableBanner
from components.tabs.tabs import Tabs
from components.button.button import Button
from components.section.section import Section
from components.label.label import Label
from components.checkbox.checkbox import Checkbox
from components.cards.indicator_card.indicator_card import IndicatorCard
from utils.base.grid_system.grid import Col, Container, Row

from components.table.V1.table import Table as TableV1
from callbacks.table.V1.secondary_actions_callback import (
    create_quickfilter_secondary, create_sort_secondary, create_reset_secondary )
from callbacks.table.V1.primary_action_callback import (
    create_export_csv_callback_v1 )
from utils.table.data_loader import get_brand_and_year_columns, load_group_table_data
from components.table.shared.col_def_config import (
    create_simple_table_column_defs , create_demo_tab_table )
from components.table.shared.action_bar import action_bar

import pandas as pd
from functools import partial


dash.register_page(
    __name__,
    path_template="/detail/<ref_number>",
    title="Detalhe do Email",
)



######  TABLES  ######
fields_df = pd.read_csv("assets/data/email_fields.csv")

df = pd.read_csv("assets/data/dummy_all_processes.csv")




def layout(ref_number=None, **kwargs):
    match = df.loc[df["Número de Referência"].astype(str) == str(ref_number)]
    
    if not match.empty:
        data_recepcao = pd.to_datetime(match.iloc[0]["Data de Receção"], dayfirst=True).date()
        business_unit = match.iloc[0]["Unidade de Negócio"]
        supplier_name = match.iloc[0]["Fornecedor"]
    else:
        data_recepcao = None
        business_unit = None
        supplier_name = None
        
    
    return html.Div(
    [  
        html.Div( 
            className="email_detail__container",
            children=[
                html.Section(
                    className="email_detail__top_section",
                    children=[
                      html.Section(
                        className="email_detail__top_left_section",
                        children = [
                            PageHeader(
                                title = f"Número de Referência: {ref_number}",  
                            ),
                            TableBanner(
                                message="Carregada em SAP",
                                variant = "positive",
                                icon = "lucide:check"
                            )
                        ]
                      ),
                      html.Section(
                        className="email_detail__top_right_section",
                            children = [
                              Button("Detalhes do Email", icon="lucide:eye", variant="outline")
                            ]
                      )
                    ],                  
                ),
                html.Section(
                    className="email_detail__content_section",
                    children=[
                        # html.H1("Validação"),
                        # html.P("Extração dos campos da fatura original", className="body-sm subtitle"),
                        html.Section(
                          className="email_detail__inside_content_section",
                          children=[
                            html.Section(
                              className="email_detail__content_left_section",
                              children=[
                                Section(
                                  title="Alertas",
                                  content=[
                                    html.Ul(
                                        className="email_detail__invoice_errors",
                                        children = [
                                      html.Li([
                                        html.Div([
                                          html.Div(
                                              [
                                                  html.H4("Campo Errado", className="body-sm"),
                                                  Label("VAT do Fornecedor Errado"),
                                              ],
                                              className="email_detail__invoice_text",
                                          ),
                                          html.Div([
                                          Button("Correção", icon="lucide:chevron-right", variant="outline"),
                                          TableBanner(
                                            message="",
                                            variant = "positive",
                                            icon = "lucide:check",
                                          ),
                                          ],
                                          className="email_detail__invoice_button_icon"
                                          )
                                      ],
                                      className="email_detail__invoice_item",
                                  )
                                      ]
                                  ),
                                  html.Li([
                                    html.Div([
                                      html.Div(
                                          [
                                              html.H4("Campo Errado", className="body-sm"),
                                              Label("Número do Fornecedor Errado"),
                                          ],
                                          className="email_detail__invoice_text",
                                      ),
                                      html.Div([
                                      Button("Ver erro", icon="lucide:chevron-right", variant="outline"),
                                      TableBanner(
                                        message="",
                                        variant = "negative",
                                        icon = "lucide:x",
                                      ),
                                      ],
                                      className="email_detail__invoice_button_icon"
                                      )
                                  ],
                                  className="email_detail__invoice_item",
                              )
                                  ]
                              ),
                              html.Li([
                                html.Div([
                                  html.Div(
                                      [
                                          html.H4("Campo Errado", className="body-sm"),
                                          Label("VAT do Fornecedor Errado"),
                                      ],
                                      className="email_detail__invoice_text",
                                  ),
                                  html.Div([
                                  Button("Correção", icon="lucide:chevron-right", variant="outline"),
                                  TableBanner(
                                    message="",
                                    variant = "negative",
                                    icon = "lucide:x",
                                  ),
                                  ],
                                  className="email_detail__invoice_button_icon"
                                  )
                              ],
                              className="email_detail__invoice_item",
                          )
                              ]
                          )
                                      ],
                                  )
                                  ],
                                  open=True
                                ),
                                html.Section(
                                  className="email_detail__field_extraction_section",
                                  children=[
                                      html.H1("Extração dos Campos"),
                                        html.Section(
                                            className="email_detail__field_grid",
                                            children=[
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                        Label(label_text="Número do Fornecedor"),
                              
                                        dcc.Input(id='supplier_num', value=ref_number, type='number', className="email_detail__input"),
                                         ],
                ),
                html.Div(
                    className="email_detail__field",
                    children=[
                                        Label(label_text="Unidade de Negócio"),
                                       
                                        dcc.Input(id='company_code', value=business_unit, type='text', className="email_detail__input"),
                                         ],
                ),
                 html.Div(
                                    className="email_detail__field",
                                    children=[
                                                        Label(label_text="Nome do Fornecedor"),
                                                       
                                                        dcc.Input(id='company_code', value=supplier_name, type='text', className="email_detail__input"),
                                                         ],
                                ),
                html.Div(
                    className="email_detail__field",
                    children=[
                                        Label(label_text="NIF do Fornecedor"),
                                        
                                        dcc.Input(id='supplier_vat', value='5100000809', type='number', className="email_detail__input"),
                                         ],
                ),
                    html.Div(
                                    className="email_detail__field",
                                    children=[
                                                        Label(label_text="Data da Fatura"),
                                                              

dcc.DatePickerSingle(
    date=data_recepcao,
)
                                          # dcc.Dropdown(
                                          #     options=[
                                          #         {"label": "€", "value": "EUR"},
                                          #         {"label": "$", "value": "USD"},
                                          #     ],
                                          #     value="EUR",
                                          #     clearable=False,
                                          # )
                                                         ],
                                ),
                html.Div(
                    className="email_detail__field",
                    children=[
                                        Label(label_text="Nota de Crédito"),
                                        
                                        Checkbox(label_text="Sim")
                                         ]
                                        )
                                      ]
                                    )
                                  ]
                                )
                              ]
                            ),
                            html.Section(
                              className="email_detail__content_right_section",
                              children=[
                                html.Iframe(
                                    src="/assets/pdf-viewer.html?file=/assets/invoices/Fatura-Exemplo-pdf.pdf",
                                    style={
                                        "width": "100%",
                                        "height":"100%",
                                        "border": "none",
                                    },
                                )
                              ]
                            )
                          ]
                        )
                    ]
                ),
                html.Section(
                    className="email_detail__bottom_section",
                    children=[
                        Button("Exportar", icon="lucide:file-down", variant="outline"),
                        Button("Guardar", icon="lucide:circle-check", variant="outline"),
                        Button("Enviar para SAP", icon="lucide:chevron-right")
                    ]
                )
            ]           
        )
    ]
)


