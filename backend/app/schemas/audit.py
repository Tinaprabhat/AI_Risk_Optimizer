from pydantic import BaseModel
from typing import Optional


class AuditRequest(BaseModel):
    url: str
    merchant_description: str

    category: Optional[str] = None
    customer: Optional[str] = None
    differentiator: Optional[str] = None
    tone: Optional[str] = None