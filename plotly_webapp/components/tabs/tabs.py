import uuid
from typing import List, Literal, Optional, Union

from dash.dcc import Tab
from dash.dcc import Tabs as DashTabs

Size = Literal["small", "medium"]

def Tabs(
    children: List[Tab],
    id: Optional[Union[str, dict]] = None,
    value: Optional[str] = None,
    size: Size = "medium",
    **kwargs,
) -> DashTabs:
    if not children:
        raise ValueError("children cannot be empty")

    if id is None:
        generated_id = f"tabs-{uuid.uuid4()}"
        custom_id = {"type": "tabs", "tabs_id": generated_id}
    else:
        custom_id = id

    if value is None and children:
        first_tab = children[0]
        try:
            value = getattr(first_tab, "value", None)
        except Exception:
            value = None

    size_class = f"tabs--{size}" if size in ["small", "medium"] else "tabs--medium"
    class_name = f"tabs {size_class}"

    return DashTabs(id=custom_id, value=value, className=class_name, children=children, **kwargs)
