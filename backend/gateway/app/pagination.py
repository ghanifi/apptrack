from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list
    total: int
    page: int
    size: int
    pages: int


async def paginate(
    db: AsyncSession,
    query: Select,
    params: PaginationParams,
) -> PaginatedResponse:
    count_q = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    pages = max(1, (total + params.size - 1) // params.size)
    offset = (params.page - 1) * params.size
    result = await db.execute(query.offset(offset).limit(params.size))
    items = result.scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        size=params.size,
        pages=pages,
    )
