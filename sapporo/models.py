from typing import Dict, Optional

from sqlmodel import Field, SQLModel

from sapporo.schemas import State


class Run(SQLModel, table=True):
    run_id: str = Field(primary_key=True)
    username: Optional[str]
    state: State
    start_time: Optional[str]
    end_time: Optional[str]
    tags: Dict[str, str]
