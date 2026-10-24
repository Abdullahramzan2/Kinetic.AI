"""API routes for LLM fitness-plan generation."""

import json
from typing import Any, Dict, List, Optional

from fastapi import (  # pyright: ignore[reportMissingImports]
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session  # pyright: ignore[reportMissingImports]

from app.database import crud_chat, models_chat
from app.database.db_session import get_db
from app.models.request_models import LLMRequest
from app.services.llm_service import LLMService
from app.utils.attach_media import attach_media_and_enrich
from app.utils.auth import oauth2_scheme, verify_token
from app.utils.summarize import generate_and_update_summary

router = APIRouter()
llm_service = LLMService()


def _parse_assistant_content(assistant_content: Any) -> Dict[str, Any]:
    """Normalize LLM output into a JSON-serializable dict."""
    try:
        if isinstance(assistant_content, dict):
            text = assistant_content.get("text")
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return assistant_content
            return assistant_content
        if isinstance(assistant_content, str):
            return json.loads(assistant_content)
        return {"text": str(assistant_content)}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[error] Error parsing assistant_content: {exc}")
        return {"error": f"Failed to parse response: {exc}"}


def _build_history(
    messages: List[models_chat.Message],
    conversation: models_chat.Conversation,
) -> List[Dict[str, str]]:
    """Build chat history for the LLM from DB messages and summary."""
    history = [{"role": m.role, "content": m.content} for m in messages]
    if conversation.summary:
        history.insert(
            0,
            {
                "role": "assistant",
                "content": (
                    "Here is a summary of previous conversation:\n"
                    f"{conversation.summary}"
                ),
            },
        )
    return history


@router.post("/generate")
async def generate_response_stream(
    request: LLMRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    """Generate a fitness plan reply, persist the turn, and return enriched JSON."""
    print("NEW LLM REQUEST")

    username = verify_token(token)
    user = (
        db.query(models_chat.Users)
        .filter(models_chat.Users.username == username)
        .first()
    )
    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_id = user.id
    conv_id: Optional[int] = getattr(request, "conversation_id", None)

    conversation = None
    if conv_id:
        conversation = (
            db.query(models_chat.Conversation)
            .filter(
                models_chat.Conversation.id == conv_id,
                models_chat.Conversation.user_id == user_id,
            )
            .first()
        )

    if not conversation:
        conversation = crud_chat.create_conversation(
            db,
            title=request.new_title or "Fitness Plan",
            user_id=user_id,
            summary="",
        )
        conv_id = conversation.id

    print(f"[ok] Conversation {conv_id} verified for user {user_id}")

    crud_chat.create_message(
        db,
        conversation_id=conv_id,
        content=request.prompt,
        role="user",
    )
    db.commit()

    messages = (
        db.query(models_chat.Message)
        .filter(models_chat.Message.conversation_id == conv_id)
        .order_by(models_chat.Message.created_at.desc())
        .limit(10)
        .all()
    )
    messages = list(reversed(messages))
    history = _build_history(messages, conversation)

    assistant_content = llm_service.generate_chatgpt_response(
        prompt=request.prompt,
        history=history,
        model=request.model,
        weight_value=request.weight_value,
        weight_unit=request.weight_unit,
        height_value=request.height_value,
        height_unit=request.height_unit,
    )

    parsed_response = attach_media_and_enrich(
        _parse_assistant_content(assistant_content)
    )

    crud_chat.create_message(
        db,
        conversation_id=conv_id,
        content=json.dumps(parsed_response),
        role="assistant",
    )
    db.commit()

    try:
        summary = generate_and_update_summary(db, conv_id)
        if summary:
            print(f"[ok] Summary updated for conversation {conv_id}")
    except (RuntimeError, ValueError, TypeError) as exc:
        print(f"[error] Error updating summary: {exc}")

    return {
        "conversation_id": conv_id,
        "response": parsed_response,
    }
