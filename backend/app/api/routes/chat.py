from fastapi import APIRouter

from pydantic import BaseModel

from app.utils.llm import ask_fix_assistant


router = APIRouter()


class ChatRequest(BaseModel):

    message: str

    failed_rules: list[str]


@router.post("/chat")

async def chat(request: ChatRequest):

    response = ask_fix_assistant(

        user_message=request.message,

        failed_rules=request.failed_rules,

    )

    return {

        "response": response

    }