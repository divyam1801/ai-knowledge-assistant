import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import ChatMessage, ChatSession, Document, DocumentStatus, FileType, Folder, MessageRole, User
from app.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    EphemeralSaveRequest,
    EphemeralUploadResponse,
)
from app.services.ephemeral import get_ephemeral_data, process_ephemeral_upload, remove_ephemeral
from app.services.rag import rag_query, rag_query_stream
from app.tasks.indexing import index_document

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


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: uuid.UUID,
    data: ChatSessionCreate,
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
    if data.title is not None:
        session.title = data.title
    if data.folder_id is not None:
        session.folder_id = data.folder_id
    await db.commit()
    await db.refresh(session)
    return session


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
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
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
    await db.flush()

    chat_history = [
        {"role": msg.role.value, "content": msg.content} for msg in session.messages
    ]

    folder_id = data.folder_id or session.folder_id

    answer, citations = await rag_query(
        db, data.content, current_user.id, folder_id, chat_history
    )

    assistant_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=answer,
        citations=citations,
    )
    db.add(assistant_message)

    if not session.title or session.title == "New chat":
        session.title = data.content[:50].strip()

    await db.commit()
    await db.refresh(assistant_message)
    return assistant_message


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: uuid.UUID,
    data: ChatMessageCreate,
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

    user_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        content=data.content,
    )
    db.add(user_message)
    await db.flush()

    chat_history = [
        {"role": msg.role.value, "content": msg.content} for msg in session.messages
    ]
    folder_id = data.folder_id or session.folder_id

    async def event_stream():
        full_response = ""
        citations = None

        try:
            async for token, cit in rag_query_stream(
                db, data.content, current_user.id, folder_id, chat_history
            ):
                if cit is not None:
                    citations = cit
                else:
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            import logging
            logger = logging.getLogger("app.chat")
            error_msg = str(e)
            logger.error("Stream error for session %s: %s", session_id, error_msg)

            if "rate_limit_error" in error_msg or ("429" in error_msg and "Rate limit exceeded" in error_msg):
                error_type = "gateway_rate_limit"
                content = "Sorry for the inconvenience, you have hit the Gateway API rate limit. Please try again in a moment."
            elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                error_type = "google_rate_limit"
                content = "Sorry for the inconvenience, you have hit the Google Gemini API rate limit. Please try again later."
            elif "503" in error_msg or "UNAVAILABLE" in error_msg:
                error_type = "service_unavailable"
                if "high demand" in error_msg:
                    content = "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."
                else:
                    content = "The AI service is temporarily unavailable. Please try again later."
            else:
                error_type = "server_error"
                content = "Something went wrong. We are investigating the issue."

            yield f"data: {json.dumps({'type': 'error', 'error_type': error_type, 'content': content})}\n\n"
            return

        assistant_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            citations=citations,
        )
        db.add(assistant_message)

        if not session.title or session.title == "New chat":
            session.title = data.content[:50].strip()

        await db.commit()
        await db.refresh(assistant_message)

        yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_message.id), 'citations': citations})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/upload", response_model=EphemeralUploadResponse)
async def ephemeral_upload(
    file: UploadFile,
    question: str,
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    result = await process_ephemeral_upload(
        file_content=content,
        filename=file.filename or "unknown",
        question=question,
        user_id=current_user.id,
    )
    return result


@router.post("/upload/save", status_code=status.HTTP_201_CREATED)
async def save_ephemeral_upload(
    data: EphemeralSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ephemeral = get_ephemeral_data(data.temp_id, current_user.id)
    if not ephemeral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ephemeral upload not found or expired")

    result = await db.execute(
        select(Folder).where(Folder.id == data.folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    doc_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir) / str(current_user.id) / str(data.folder_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}_{ephemeral['filename']}"
    file_path.write_bytes(ephemeral["file_content"])

    document = Document(
        id=doc_id,
        folder_id=data.folder_id,
        user_id=current_user.id,
        filename=ephemeral["filename"],
        file_path=str(file_path),
        file_type=ephemeral["file_type"],
        file_size_bytes=len(ephemeral["file_content"]),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    index_document.delay(str(document.id))
    remove_ephemeral(data.temp_id)

    return {"id": str(document.id), "filename": document.filename, "status": "processing"}
