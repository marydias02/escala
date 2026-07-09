from typing import Any, Dict, List, NotRequired, Optional, TypedDict

from components.banner.banner import MessageVariant


class TableDataFrame(TypedDict):
    df: Any
    col_def: NotRequired[List[Dict[str, Any]]]
    tab: NotRequired[Optional[str]]
    columns: NotRequired[List[str]]


class MessageConfig(TypedDict):
    text: str
    variant: NotRequired[MessageVariant]
    icon: NotRequired[str]
