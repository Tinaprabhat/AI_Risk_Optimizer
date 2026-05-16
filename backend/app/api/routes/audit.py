from fastapi import APIRouter

from app.schemas.audit import AuditRequest

from app.services.auditor import run_audit


router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)


@router.post("/")
def run_audit_api(
    payload: AuditRequest
):

    # NEW MCQ STRUCTURE
    mcq = {

        "category":
            payload.category,

        "store_age":
            payload.store_age,

        "traffic":
            payload.traffic,

        "challenge":
            payload.challenge,

        "ai_optimization":
            payload.ai_optimization,

    }

    result = run_audit(

        store_url=payload.url,

        free_text=
            payload.merchant_description,

        mcq=mcq,

    )

    return result