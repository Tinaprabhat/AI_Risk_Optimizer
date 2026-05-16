from fastapi import APIRouter
from app.schemas.audit import AuditRequest
from app.services.auditor import run_audit

router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)


@router.post("/")
def run_audit_api(payload: AuditRequest):

    mcq = {
        "category": payload.category,
        "customer": payload.customer,
        "differentiator": payload.differentiator,
        "tone": payload.tone,
    }

    result = run_audit(
        store_url=payload.url,
        free_text=payload.merchant_description,
        mcq=mcq,
    )
    
    return result