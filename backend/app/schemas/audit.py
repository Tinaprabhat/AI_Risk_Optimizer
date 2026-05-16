from pydantic import BaseModel

from typing import Optional


class AuditRequest(BaseModel):

    url: str

    merchant_description: str

    category: Optional[str] = None

    store_age: Optional[str] = None

    traffic: Optional[str] = None

    challenge: Optional[str] = None

    ai_optimization: Optional[str] = None