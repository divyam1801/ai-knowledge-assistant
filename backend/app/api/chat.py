import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models import ChatMessage, ChatSession, MessageRole, User
from app.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(
        user_id=current_user.id,
        title=data.title,
        folder_id=data.folder_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)
    await db.commit()


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: uuid.UUID,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    user_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        content=data.content,
    )
    db.add(user_message)

    # TODO: implement RAG pipeline — retrieve context, call LLM, stream response
    assistant_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content="RAG pipeline not yet implemented.",
        citations=None,
    )
    db.add(assistant_message)

    await db.commit()
    await db.refresh(assistant_message)
    return assistant_message
