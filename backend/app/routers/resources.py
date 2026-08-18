import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Resource, User
from app.schemas import ResourceCreate, ResourceOut, SearchResults

logger = logging.getLogger("app.resources")
router = APIRouter(prefix="/api/resources", tags=["resources"])


def _to_out(resource: Resource) -> ResourceOut:
    return ResourceOut(
        id=resource.id,
        title=resource.title,
        url=resource.url,
        description=resource.description or "",
        tags=[t for t in (resource.tags or "").split(",") if t],
        created_at=resource.created_at,
    )


@router.get("/search", response_model=SearchResults)
def search(
    q: str = Query("", max_length=200, description="Free-text query"),
    tag: str | None = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SearchResults:
    stmt = select(Resource)

    term = q.strip()
    if term:
        pattern = f"%{term.lower()}%"
        stmt = stmt.where(
            or_(
                Resource.title.ilike(pattern),
                Resource.description.ilike(pattern),
                Resource.tags.ilike(pattern),
                Resource.url.ilike(pattern),
            )
        )
    if tag:
        stmt = stmt.where(Resource.tags.ilike(f"%{tag.strip().lower()}%"))

    total = len(db.execute(stmt.with_only_columns(Resource.id).order_by(None)).all())
    rows = db.execute(stmt.order_by(Resource.created_at.desc()).limit(limit).offset(offset))
    items = [_to_out(r) for r in rows.scalars().all()]

    logger.info("search", extra={"q": term, "tag": tag, "total": total, "returned": len(items)})
    return SearchResults(query=term, total=total, limit=limit, offset=offset, items=items)


@router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceOut:
    resource = Resource(
        title=payload.title,
        url=str(payload.url),
        description=payload.description,
        tags=",".join(sorted({t.strip().lower() for t in payload.tags if t.strip()})),
        owner_id=user.id,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    logger.info("resource_created", extra={"resource_id": resource.id, "user_id": user.id})
    return _to_out(resource)
