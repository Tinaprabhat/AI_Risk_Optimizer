import uuid
import threading
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auditor import run_audit
from src.part2.fix_engine import (
    chatbot_first_message,
    chatbot_reply,
    get_fix_template,
)
from src.utils.db import (
    save_chat_message,
    load_chat_history,
    clear_chat_history,
)

router = APIRouter()

# ── IN-MEMORY JOB STORE ───────────────────────────────────────────────────────
# Stores audit jobs while they run. Key = job_id (uuid).
# Each job: { status, progress, result, error, created_at }
_jobs: dict = {}


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class AuditRequest(BaseModel):
    store_url: str
    free_text: str
    mcq: dict
    use_cache: bool = True


class ChatStartRequest(BaseModel):
    store_url: str
    check_code: str
    check_detail: str


class ChatReplyRequest(BaseModel):
    store_url: str
    check_code: str
    check_detail: str
    check_fix: str
    user_message: str


# ── AUDIT ENDPOINTS ───────────────────────────────────────────────────────────

@router.post("/audit/start")
def start_audit(req: AuditRequest):
    """
    Submit a store URL for auditing.
    Returns a job_id immediately — audit runs in background.
    Poll /audit/status/{job_id} for updates.
    """
    job_id = str(uuid.uuid4())

    _jobs[job_id] = {
        "job_id":     job_id,
        "store_url":  req.store_url,
        "status":     "running",
        "progress":   "Starting audit...",
        "result":     None,
        "error":      None,
        "created_at": datetime.utcnow().isoformat(),
    }

    def _run():
        try:
            def progress_cb(msg: str):
                _jobs[job_id]["progress"] = msg

            result = run_audit(
                store_url=req.store_url,
                free_text=req.free_text,
                mcq=req.mcq,
                use_cache=req.use_cache,
                progress_cb=progress_cb,
            )
            _jobs[job_id]["status"]   = "done"
            _jobs[job_id]["progress"] = "Audit complete"
            _jobs[job_id]["result"]   = result

        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "running"}


@router.get("/audit/status/{job_id}")
def audit_status(job_id: str):
    """
    Poll this every 2 seconds from your React frontend.
    Returns status: 'running' | 'done' | 'error'
    When status == 'done', result contains the full audit.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "running":
        return {
            "job_id":   job_id,
            "status":   "running",
            "progress": job["progress"],
        }

    if job["status"] == "error":
        return {
            "job_id": job_id,
            "status": "error",
            "error":  job["error"],
        }

    # Done — return full result
    return {
        "job_id":  job_id,
        "status":  "done",
        "result":  job["result"],
    }


# ── CHAT / FIX ENDPOINTS ──────────────────────────────────────────────────────

@router.post("/chat/start")
def chat_start(req: ChatStartRequest):
    """
    Start a fix conversation for a failed check.
    Clears any previous conversation for this check.
    """
    clear_chat_history(req.store_url, req.check_code)
    msg = chatbot_first_message(req.check_code, req.check_detail)
    save_chat_message(req.store_url, req.check_code, "bot", msg)
    return {
        "message":    msg,
        "check_code": req.check_code,
    }


@router.post("/chat/reply")
def chat_reply(req: ChatReplyRequest):
    """
    Send a merchant message and get advisor reply.
    History is loaded from DB and maintained automatically.
    """
    history = load_chat_history(req.store_url, req.check_code)
    save_chat_message(req.store_url, req.check_code, "user", req.user_message)

    reply, source = chatbot_reply(
        check_code=req.check_code,
        check_detail=req.check_detail,
        check_fix=req.check_fix,
        store_url=req.store_url,
        user_message=req.user_message,
        history=history,
    )
    save_chat_message(req.store_url, req.check_code, "bot", reply)

    return {
        "message": reply,
        "source":  source,   # "gemini" | "ollama_mistral" | "fallback"
    }


@router.get("/chat/history")
def chat_history(store_url: str, check_code: str):
    """Load full conversation history for a check."""
    return load_chat_history(store_url, check_code)


@router.get("/fix/template/{check_code}")
def fix_template(check_code: str):
    """Get the hardcoded fix template for a check code."""
    template = get_fix_template(check_code)
    if not template:
        raise HTTPException(status_code=404, detail=f"No template for {check_code}")
    return template




@router.delete("/audit/cache")
def clear_cache(store_url: str):
    """
    Force re-audit by deleting today's cached result for a URL.
    Useful for testing or when merchant updates their store.
    """
    from src.utils.db import _connect, url_hash
    conn = _connect()
    try:
        conn.execute(
            "DELETE FROM audits WHERE url_hash = ?",
            (url_hash(store_url),)
        )
        conn.commit()
        return {"message": f"Cache cleared for {store_url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()




# ── HEALTH ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}