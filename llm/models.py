from pydantic import BaseModel, field_validator
from datetime import date
from typing import Optional

class Ticket(BaseModel):
    ticket_id: str
    severity: str
    module: str
    title: str
    description: str
    priority: str
    status: str
    category: str
    reported_date: date
    assigned_to: Optional[str] = None
    assigned_date: Optional[date] = None
    @field_validator('severity')
    def severity_levels(cls, v):
        if v not in ['L1', 'L2', 'L3','L4','L5', 'Critical', 'High', 'Medium', 'Low', 'Planning'] :
            raise ValueError('Invalid severity')
        return v


class ProcessedTicket(BaseModel):
    ticket_id: str
    summary: str
    priority: str
    category: str
    solution: str