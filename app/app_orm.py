from fastapi import FastAPI, HTTPException, Depends, Query, status, Request
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///../lab.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# SQLAlchemy Model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    details = Column(String, nullable=True)
    is_done = Column(Integer, default=0)
    priority = Column(Integer, default=1)
    due_date = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic Schemas with comprehensive validation
class TaskBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description="Task title must be at least 3 characters")
    details: Optional[str] = Field(None, max_length=1000, description="Task details")
    is_done: bool = Field(False, description="Task completion status")
    priority: int = Field(default=1, ge=1, le=3, description="Priority: 1=Low, 2=Medium, 3=High")
    due_date: Optional[str] = Field(None, description="Due date in ISO format")

    @validator('title')
    def validate_title(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError('Title must be at least 3 characters long')
        return v

    @validator('details')
    def validate_details(cls, v):
        if v is not None:
            v = v.strip()
            if v == "":
                return None
        return v

    @validator('due_date')
    def validate_due_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid ISO 8601 date format. Use: YYYY-MM-DDTHH:MM:SS')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError('Priority must be 1 (low), 2 (medium) or 3 (high)')
        return v


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    details: Optional[str] = Field(None, max_length=1000)
    is_done: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    due_date: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) < 3:
                raise ValueError('Title must be at least 3 characters long')
        return v

    @validator('due_date')
    def validate_due_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Invalid ISO 8601 date format. Use: YYYY-MM-DDTHH:MM:SS')
        return v


class TaskResponse(TaskBase):
    id: int
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# FastAPI App
app = FastAPI(
    title="TODO List API",
    version="1.0.0",
    description="A comprehensive TODO list application with FastAPI and SQLAlchemy ORM"
)

# Templates setup
templates = Jinja2Templates(directory="templates")


# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/tasks-page", response_class=HTMLResponse)
async def read_tasks_page(
        request: Request,
        db: Session = Depends(get_db),
        q: Optional[str] = Query(None),
        is_done: Optional[bool] = Query(None),
        priority: Optional[int] = Query(None, ge=1, le=3)
):
    # Build query with filters
    query = db.query(Task)

    if q:
        query = query.filter(Task.title.contains(q) | Task.details.contains(q))

    if is_done is not None:
        query = query.filter(Task.is_done == (1 if is_done else 0))

    if priority:
        query = query.filter(Task.priority == priority)

    tasks = query.order_by(Task.created_at.desc()).all()
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks})


@app.get("/create-task", response_class=HTMLResponse)
async def create_task_page(request: Request):
    return templates.TemplateResponse("create_task.html", {"request": request})


# API routes
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
        db: Session = Depends(get_db),
        q: Optional[str] = Query(None, description="Search in title and details"),
        is_done: Optional[bool] = Query(None, description="Filter by completion status"),
        priority: Optional[int] = Query(None, ge=1, le=3, description="Filter by priority"),
        due_before: Optional[str] = Query(None, description="Tasks due before date"),
        due_after: Optional[str] = Query(None, description="Tasks due after date"),
        sort: Optional[str] = Query("created_at", description="Sort by: created_at, due_date, priority"),
        order: Optional[str] = Query("asc", description="Order: asc, desc"),
        offset: Optional[int] = Query(0, ge=0, description="Pagination offset"),
        limit: Optional[int] = Query(10, ge=1, le=100, description="Pagination limit")
):
    # Validate sort parameter
    if sort not in ["created_at", "due_date", "priority"]:
        raise HTTPException(status_code=400, detail="Invalid sort parameter. Use: created_at, due_date, priority")

    # Validate order parameter
    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid order parameter. Use: asc, desc")

    # Build query
    query = db.query(Task)

    # Apply filters
    if q:
        query = query.filter(Task.title.contains(q) | Task.details.contains(q))

    if is_done is not None:
        query = query.filter(Task.is_done == (1 if is_done else 0))

    if priority:
        query = query.filter(Task.priority == priority)

    if due_before:
        query = query.filter(Task.due_date <= due_before)

    if due_after:
        query = query.filter(Task.due_date >= due_after)

    # Apply sorting
    if sort == "created_at":
        order_by_field = Task.created_at
    elif sort == "due_date":
        order_by_field = Task.due_date
    else:  # priority
        order_by_field = Task.priority

    if order == "desc":
        query = query.order_by(order_by_field.desc())
    else:
        query = query.order_by(order_by_field.asc())

    # Apply pagination
    tasks = query.offset(offset).limit(limit).all()

    return tasks


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    # Pydantic автоматически валидирует данные
    now = datetime.now().isoformat()
    db_task = Task(
        title=task.title,
        details=task.details,
        is_done=1 if task.is_done else 0,
        priority=task.priority,
        due_date=task.due_date,
        created_at=now,
        updated_at=None
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Pydantic автоматически валидирует данные
    update_data = task_update.dict(exclude_unset=True)

    # Update fields
    for field, value in update_data.items():
        if field == 'is_done':
            setattr(db_task, field, 1 if value else 0)
        else:
            setattr(db_task, field, value)

    db_task.updated_at = datetime.now().isoformat()

    db.commit()
    db.refresh(db_task)

    return db_task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(db_task)
    db.commit()

    return None


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)