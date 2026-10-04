"""
Course material endpoints.

Materials are the standing context for a subject: the outline says what the
module covers and how it's assessed, past papers and problem sheets show how
it gets examined. They're added over time, so everything here is editable.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.material import CourseMaterial, MaterialKind
from app.models.profile import SubjectProfile
from app.services.extraction import extract_document_text

router = APIRouter()


class MaterialResponse(BaseModel):
    id: int
    profile_id: int
    kind: MaterialKind
    title: str
    file_path: Optional[str]
    content: Optional[str]
    content_chars: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialListResponse(BaseModel):
    materials: list[MaterialResponse]
    total: int


class MaterialUpdate(BaseModel):
    """Every field optional: edits are partial."""
    title: Optional[str] = None
    kind: Optional[MaterialKind] = None
    content: Optional[str] = None


def _to_response(material: CourseMaterial) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        profile_id=material.profile_id,
        kind=material.kind,
        title=material.title,
        file_path=material.file_path,
        content=material.content,
        content_chars=len(material.content or ""),
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


@router.post("/", response_model=MaterialResponse, status_code=201)
async def create_material(
    profile_id: int = Form(...),
    title: str = Form(...),
    kind: MaterialKind = Form(MaterialKind.OTHER),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a material, either as a file (pdf, pptx, docx, txt, md) or as typed
    text. Text is extracted on upload so generation never re-reads the file.
    """
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == profile_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Profile not found")

    typed = content.strip() if content else None
    if not file and not typed:
        raise HTTPException(
            status_code=400, detail="Provide a file or some text"
        )

    material = CourseMaterial(
        profile_id=profile_id,
        kind=kind,
        title=title,
        content=typed,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    if file:
        upload_dir = Path(settings.UPLOAD_DIR) / "materials" / str(material.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved = upload_dir / file.filename

        with open(saved, "wb") as f:
            f.write(await file.read())

        material.file_path = str(saved)

        try:
            extracted = extract_document_text(str(saved)).strip()
        except Exception as e:
            await db.delete(material)
            await db.commit()
            raise HTTPException(
                status_code=400, detail=f"Couldn't read that file: {e}"
            )

        # Typed text wins if both were given, with the file appended
        material.content = f"{typed}\n\n{extracted}" if typed else extracted
        await db.commit()
        await db.refresh(material)

    return _to_response(material)


@router.get("/", response_model=MaterialListResponse)
async def list_materials(
    profile_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(CourseMaterial)
    if profile_id:
        query = query.where(CourseMaterial.profile_id == profile_id)

    result = await db.execute(query.order_by(CourseMaterial.created_at))
    materials = result.scalars().all()

    return MaterialListResponse(
        materials=[_to_response(m) for m in materials],
        total=len(materials),
    )


@router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: int,
    update: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Edit a material — retitle, reclassify, or correct its text."""
    result = await db.execute(
        select(CourseMaterial).where(CourseMaterial.id == material_id)
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if update.title is not None:
        material.title = update.title
    if update.kind is not None:
        material.kind = update.kind
    if update.content is not None:
        material.content = update.content

    await db.commit()
    await db.refresh(material)
    return _to_response(material)


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CourseMaterial).where(CourseMaterial.id == material_id)
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if material.file_path and os.path.exists(material.file_path):
        os.remove(material.file_path)

    await db.delete(material)
    await db.commit()
