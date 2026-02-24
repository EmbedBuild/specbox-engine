# Arquitectura Python - Overview

## Stack Principal

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| Python | 3.12+ | Runtime |
| FastAPI | 0.115+ | Web framework |
| Pydantic | 2.x | Validacion y schemas |
| SQLAlchemy | 2.x | ORM (async) |
| asyncpg | - | PostgreSQL async driver |
| Alembic | 1.x | Migraciones |
| pytest | 8.x | Testing |
| Ruff | 0.9+ | Linter + formatter |
| mypy | 1.x | Type checking |

## Principios

### 1. Async por defecto

Todo endpoint y operacion de I/O debe ser async:
```python
@router.get("/items")
async def list_items(db: AsyncSession = Depends(get_db)):
    ...
```

### 2. Dependency Injection

FastAPI Depends() para inyectar:
- Database sessions
- Current user (auth)
- Services
- Config

### 3. Pydantic para TODO

- Request bodies (schemas de entrada)
- Response models (schemas de salida)
- Settings (pydantic-settings)
- Validacion de datos externos

## Estructura de Carpetas

```
src/
├── api/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py          # /auth/*
│   │   ├── users.py         # /users/*
│   │   └── {feature}.py     # /{feature}/*
│   ├── deps/
│   │   ├── auth.py          # get_current_user
│   │   └── database.py      # get_db session
│   └── middleware/
│       └── error_handler.py
│
├── core/
│   ├── config.py            # Settings (env vars)
│   ├── security.py          # JWT, hashing
│   └── database.py          # Engine, SessionLocal
│
├── models/                  # SQLAlchemy models
│   ├── base.py              # Base model con timestamps
│   ├── user.py
│   └── {feature}.py
│
├── schemas/                 # Pydantic schemas
│   ├── user.py              # UserCreate, UserRead, UserUpdate
│   └── {feature}.py
│
├── services/                # Business logic
│   ├── auth_service.py
│   └── {feature}_service.py
│
├── repositories/            # Data access layer
│   ├── base.py              # BaseRepository[T]
│   └── {feature}_repository.py
│
├── tests/
│   ├── conftest.py          # Fixtures (test db, client, user)
│   ├── api/
│   │   └── test_{feature}.py
│   ├── services/
│   │   └── test_{feature}_service.py
│   └── repositories/
│       └── test_{feature}_repository.py
│
├── alembic/                 # Migraciones
│   ├── versions/
│   └── env.py
│
├── main.py                  # App factory
└── pyproject.toml           # Dependencies (uv/poetry)
```

## Patrones Clave

### Base Model (SQLAlchemy)

```python
# models/base.py
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Pydantic Schemas

```python
# schemas/{feature}.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ItemBase(BaseModel):
    name: str
    description: str | None = None
    price: float

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None

class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime | None
```

### Repository Pattern

```python
# repositories/base.py
from typing import Generic, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_all(self) -> list[T]:
        result = await self.db.execute(select(self.model))
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> T | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def create(self, obj: T) -> T:
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> None:
        obj = await self.get_by_id(id)
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
```

### Service Layer

```python
# services/{feature}_service.py
from uuid import UUID
from repositories.{feature}_repository import ItemRepository
from schemas.{feature} import ItemCreate, ItemUpdate

class ItemService:
    def __init__(self, repository: ItemRepository):
        self.repository = repository

    async def list_items(self) -> list:
        return await self.repository.get_all()

    async def create_item(self, data: ItemCreate):
        item = Item(**data.model_dump())
        return await self.repository.create(item)
```

### Router

```python
# api/routes/{feature}.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from api.deps.database import get_db
from api.deps.auth import get_current_user
from schemas.{feature} import ItemCreate, ItemRead
from services.{feature}_service import ItemService

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_model=list[ItemRead])
async def list_items(db = Depends(get_db)):
    service = ItemService(ItemRepository(Item, db))
    return await service.list_items()

@router.post("/", response_model=ItemRead, status_code=201)
async def create_item(
    data: ItemCreate,
    db = Depends(get_db),
    user = Depends(get_current_user),
):
    service = ItemService(ItemRepository(Item, db))
    return await service.create_item(data)
```

## Reglas

1. **Async** en todo endpoint y operacion I/O
2. **Pydantic** para toda validacion (nunca validar manualmente)
3. **Repository pattern** para acceso a datos
4. **Service layer** para logica de negocio
5. **Ruff** para lint + format, **mypy** para types
6. **Alembic** para migraciones (nunca SQL directo en produccion)
7. Tests con **pytest-asyncio** y **httpx.AsyncClient**

## Anti-Patrones

| Anti-Patron | Alternativa |
|-------------|-------------|
| Sync database calls | async SQLAlchemy + asyncpg |
| Dict validation manual | Pydantic schemas |
| SQL raw en endpoints | Repository pattern |
| Global db session | Depends(get_db) |
| print() debugging | logging module |
| requirements.txt | pyproject.toml (uv/poetry) |
