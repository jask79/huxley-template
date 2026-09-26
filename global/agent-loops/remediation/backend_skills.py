"""
Backend-specific remediation skills.

Provides 10 specialized skills for common backend error patterns:
- SQLAlchemy query issues
- Pydantic validation errors
- FastAPI async endpoint problems
- API error handling
- Database migrations
- CORS configuration
- Request validation
- Authentication middleware
- Database query optimization
- JSON serialization
"""

import time

from .skill import RemediationSkill, SkillMetadata, SkillType


def get_backend_skills():
    """Get all backend-specific remediation skills."""

    skills = [
        # 1. Fix SQLAlchemy Query
        RemediationSkill(
            skill_id="fix_sqlalchemy_query",
            name="Fix SQLAlchemy Query Error",
            description="Resolve SQLAlchemy query syntax and relationship errors",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"sqlalchemy.*DetachedInstanceError",
                r"sqlalchemy.*InvalidRequestError",
                r"Multiple rows were found",
                r"No row was found",
                r"relationship.*not found",
                r"Can't locate attribute.*on mapped class",
            ],
            applicable_categories=["runtime_error", "type_error"],
            fix_template="""
Fix SQLAlchemy query error at line {line_number} in {file_path}:

Common issues and fixes:

1. **DetachedInstanceError**: Session expired or object not in session
   - Use `session.refresh(obj)` or `session.merge(obj)`
   - Keep session open or use lazy='joined' for relationships

2. **Multiple/No rows found**: Use correct query method
   - Use `.all()` for multiple results
   - Use `.first()` or `.one_or_none()` for single result
   - Use `.one()` only when exactly one row expected

3. **Relationship not found**: Check model definitions
   - Ensure relationship is defined on both models
   - Use correct `backref` or `back_populates`
   - Check foreign key constraints match

Example fixes:
```python
# Fix DetachedInstanceError
session.refresh(user)  # Reload from database
# Or use eager loading
users = session.query(User).options(joinedload(User.posts)).all()

# Fix query methods
user = session.query(User).filter_by(email=email).first()  # Can be None
users = session.query(User).filter(User.active == True).all()  # List

# Fix relationship
class User(Base):
    posts = relationship("Post", back_populates="author")

class Post(Base):
    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "sqlalchemy", "database", "backend"],
        ),
        # 2. Fix Pydantic Validation
        RemediationSkill(
            skill_id="fix_pydantic_validation",
            name="Fix Pydantic Model Validation Error",
            description="Resolve Pydantic schema validation and type conversion issues",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"pydantic.*ValidationError",
                r"validation error for",
                r"field required",
                r"value is not a valid",
                r"extra fields not permitted",
            ],
            applicable_categories=["validation_error", "type_error"],
            fix_template=r"""
Fix Pydantic validation error at line {line_number} in {file_path}:

Common issues and fixes:

1. **Field required**: Add required field or make optional
   ```python
   # Make field optional
   from typing import Optional
   field: Optional[str] = None
   ```

2. **Type mismatch**: Use correct type or add validator
   ```python
   from pydantic import validator, Field

   email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')

   @validator('age')
   def validate_age(cls, v):
       if v < 0:
           raise ValueError('Age must be positive')
       return v
   ```

3. **Extra fields**: Configure model or remove extra fields
   ```python
   class Config:
       extra = 'forbid'  # Raise error
       # extra = 'ignore'  # Ignore extra fields
       # extra = 'allow'  # Allow extra fields
   ```

4. **Nested validation**: Ensure nested models are defined
   ```python
   class Address(BaseModel):
       street: str
       city: str

   class User(BaseModel):
       name: str
       address: Address  # Nested model
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "pydantic", "validation", "backend", "fastapi"],
        ),
        # 3. Fix Async Endpoint
        RemediationSkill(
            skill_id="fix_async_endpoint",
            name="Fix FastAPI Async Endpoint",
            description="Resolve async/await issues in FastAPI endpoint handlers",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"coroutine .* was never awaited",
                r"cannot await.*not awaitable",
                r"Event loop is closed",
                r"asyncio.*RuntimeError",
            ],
            applicable_categories=["runtime_error", "build_error"],
            fix_template="""
Fix async endpoint error at line {line_number} in {file_path}:

Common issues and fixes:

1. **Coroutine not awaited**: Add await keyword
   ```python
   @app.get("/users")
   async def get_users():
       # Wrong: users = get_users_from_db()
       users = await get_users_from_db()  # Correct
       return users
   ```

2. **Mixing sync/async**: Use proper async database driver
   ```python
   # Use async SQLAlchemy
   from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

   async def get_user(session: AsyncSession, user_id: int):
       result = await session.execute(select(User).where(User.id == user_id))
       return result.scalar_one_or_none()
   ```

3. **Blocking operations in async**: Use run_in_executor
   ```python
   import asyncio
   from concurrent.futures import ThreadPoolExecutor

   executor = ThreadPoolExecutor()

   async def process_file(file_path: str):
       loop = asyncio.get_event_loop()
       result = await loop.run_in_executor(executor, sync_file_operation, file_path)
       return result
   ```

4. **Dependency injection**: Use async dependencies
   ```python
   async def get_db() -> AsyncGenerator[AsyncSession, None]:
       async with AsyncSessionLocal() as session:
           yield session

   @app.get("/users/{user_id}")
   async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
       return await get_user(db, user_id)
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "async", "fastapi", "backend"],
        ),
        # 4. Add API Error Handling
        RemediationSkill(
            skill_id="add_api_error_handling",
            name="Add API Error Handling",
            description="Implement proper error responses and exception handlers in API endpoints",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Unhandled exception in endpoint",
                r"500 Internal Server Error",
                r"No response returned",
                r"HTTPException not raised",
            ],
            applicable_categories=["runtime_error", "validation_error"],
            fix_template="""
Add error handling at line {line_number} in {file_path}:

FastAPI error handling patterns:

1. **Use HTTPException for expected errors**:
   ```python
   from fastapi import HTTPException, status

   @app.get("/users/{user_id}")
   async def get_user(user_id: int, db: Session = Depends(get_db)):
       user = db.query(User).filter(User.id == user_id).first()
       if not user:
           raise HTTPException(
               status_code=status.HTTP_404_NOT_FOUND,
               detail="User not found"
           )
       return user
   ```

2. **Create custom exception handlers**:
   ```python
   from fastapi import Request
   from fastapi.responses import JSONResponse

   class DatabaseError(Exception):
       pass

   @app.exception_handler(DatabaseError)
   async def database_exception_handler(request: Request, exc: DatabaseError):
       return JSONResponse(
           status_code=500,
           content={"message": "Database error occurred", "detail": str(exc)}
       )
   ```

3. **Use try-except for external services**:
   ```python
   @app.post("/send-email")
   async def send_email(email_data: EmailSchema):
       try:
           await email_service.send(email_data)
           return {"status": "sent"}
       except EmailServiceError as e:
           raise HTTPException(
               status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
               detail=f"Email service unavailable: {str(e)}"
           )
   ```

4. **Add request validation error handler**:
   ```python
   from fastapi.exceptions import RequestValidationError

   @app.exception_handler(RequestValidationError)
   async def validation_exception_handler(request: Request, exc: RequestValidationError):
       return JSONResponse(
           status_code=422,
           content={"detail": exc.errors(), "body": exc.body}
       )
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "fastapi", "error-handling", "backend"],
        ),
        # 5. Fix Database Migration
        RemediationSkill(
            skill_id="fix_database_migration",
            name="Fix Database Migration Error",
            description="Resolve Alembic migration conflicts and schema issues",
            skill_type=SkillType.BUILD_FIX,
            error_patterns=[
                r"alembic.*CommandError",
                r"Target database is not up to date",
                r"Can't locate revision",
                r"Multiple head revisions",
                r"migration.*conflict",
            ],
            applicable_categories=["build_error", "runtime_error"],
            fix_template="""
Fix migration error at line {line_number} in {file_path}:

Alembic migration fixes:

1. **Multiple heads**: Merge migration branches
   ```bash
   alembic heads  # Show all heads
   alembic merge -m "merge heads" head1 head2
   alembic upgrade head
   ```

2. **Target not up to date**: Check current revision
   ```bash
   alembic current  # Show current revision
   alembic history  # Show migration history
   alembic upgrade head  # Upgrade to latest
   ```

3. **Can't locate revision**: Check revision IDs
   ```bash
   alembic history  # Find correct revision
   alembic stamp <revision>  # Mark database at revision (dangerous!)
   ```

4. **Migration conflicts**: Regenerate migration
   ```bash
   # Delete conflicting migration file
   rm alembic/versions/conflicting_migration.py

   # Autogenerate fresh migration
   alembic revision --autogenerate -m "description"

   # Review generated migration for accuracy
   # Edit if needed

   # Apply migration
   alembic upgrade head
   ```

5. **Schema mismatch**: Add explicit upgrade/downgrade
   ```python
   def upgrade():
       # Add column with default for existing rows
       op.add_column('users',
           sa.Column('status', sa.String(20), nullable=False, server_default='active')
       )
       # Remove server default after backfill
       op.alter_column('users', 'status', server_default=None)

   def downgrade():
       op.drop_column('users', 'status')
   ```
            """,
            required_context=["file_path", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "alembic", "migrations", "database", "backend"],
        ),
        # 6. Fix CORS Configuration
        RemediationSkill(
            skill_id="fix_cors_configuration",
            name="Fix CORS Configuration",
            description="Resolve Cross-Origin Resource Sharing configuration issues",
            skill_type=SkillType.CONFIG_FIX,
            error_patterns=[
                r"CORS.*blocked",
                r"No 'Access-Control-Allow-Origin'",
                r"CORS policy.*blocked",
                r"preflight request.*failed",
            ],
            applicable_categories=["runtime_error", "network_error"],
            fix_template="""
Fix CORS configuration at line {line_number} in {file_path}:

FastAPI CORS setup:

1. **Basic CORS configuration**:
   ```python
   from fastapi.middleware.cors import CORSMiddleware

   app = FastAPI()

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000"],  # Frontend URL
       allow_credentials=True,
       allow_methods=["*"],  # Or ["GET", "POST", "PUT", "DELETE"]
       allow_headers=["*"],  # Or specific headers
   )
   ```

2. **Development vs Production**:
   ```python
   import os

   origins = []
   if os.getenv("ENVIRONMENT") == "development":
       origins = ["http://localhost:3000", "http://localhost:8080"]
   else:
       origins = ["https://yourdomain.com"]

   app.add_middleware(
       CORSMiddleware,
       allow_origins=origins,
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

3. **Allow all origins (development only)**:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # WARNING: Not for production
       allow_credentials=False,  # Must be False with wildcard origins
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

4. **Specific headers and methods**:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],
       allow_credentials=True,
       allow_methods=["GET", "POST", "PUT", "DELETE"],
       allow_headers=["Content-Type", "Authorization", "X-API-Key"],
       expose_headers=["X-Total-Count"],  # Headers accessible to client
       max_age=3600,  # Cache preflight for 1 hour
   )
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "fastapi", "cors", "config", "backend"],
        ),
        # 7. Add Request Validation
        RemediationSkill(
            skill_id="add_request_validation",
            name="Add Request Input Validation",
            description="Implement request body and parameter validation",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Invalid.*input",
                r"Missing required.*parameter",
                r"422 Unprocessable Entity",
                r"Validation.*failed",
            ],
            applicable_categories=["validation_error"],
            fix_template=r"""
Add request validation at line {line_number} in {file_path}:

FastAPI validation patterns:

1. **Request body validation with Pydantic**:
   ```python
   from pydantic import BaseModel, Field, validator
   from typing import Optional

   class UserCreate(BaseModel):
       email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
       username: str = Field(..., min_length=3, max_length=50)
       age: int = Field(..., ge=0, le=150)

       @validator('username')
       def validate_username(cls, v):
           if not v.isalnum():
               raise ValueError('Username must be alphanumeric')
           return v

   @app.post("/users")
   async def create_user(user: UserCreate):
       return {"email": user.email, "username": user.username}
   ```

2. **Query parameter validation**:
   ```python
   from fastapi import Query

   @app.get("/users")
   async def list_users(
       skip: int = Query(0, ge=0),
       limit: int = Query(10, ge=1, le=100),
       search: Optional[str] = Query(None, min_length=3)
   ):
       return {"skip": skip, "limit": limit}
   ```

3. **Path parameter validation**:
   ```python
   from fastapi import Path

   @app.get("/users/{user_id}")
   async def get_user(
       user_id: int = Path(..., gt=0, description="User ID must be positive")
   ):
       return {"user_id": user_id}
   ```

4. **Custom validators**:
   ```python
   from fastapi import HTTPException

   class UserUpdate(BaseModel):
       email: Optional[str] = None
       password: Optional[str] = None

       @validator('password')
       def validate_password(cls, v):
           if v is not None:
               if len(v) < 8:
                   raise ValueError('Password must be at least 8 characters')
               if not any(c.isupper() for c in v):
                   raise ValueError('Password must contain uppercase letter')
               if not any(c.isdigit() for c in v):
                   raise ValueError('Password must contain a digit')
           return v
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "fastapi", "validation", "backend"],
        ),
        # 8. Fix Authentication
        RemediationSkill(
            skill_id="fix_authentication",
            name="Fix Authentication Middleware",
            description="Resolve JWT token validation and auth middleware issues",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"401 Unauthorized",
                r"Token.*expired",
                r"Invalid token",
                r"Could not validate credentials",
                r"JWT.*decode.*error",
            ],
            applicable_categories=["runtime_error", "validation_error"],
            fix_template="""
Fix authentication error at line {line_number} in {file_path}:

FastAPI JWT authentication patterns:

1. **JWT token validation dependency**:
   ```python
   from fastapi import Depends, HTTPException, status
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
   from jose import JWTError, jwt
   from datetime import datetime, timedelta

   security = HTTPBearer()

   SECRET_KEY = "your-secret-key"
   ALGORITHM = "HS256"

   def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
       token = credentials.credentials
       try:
           payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
           user_id: str = payload.get("sub")
           if user_id is None:
               raise HTTPException(
                   status_code=status.HTTP_401_UNAUTHORIZED,
                   detail="Could not validate credentials"
               )
           return user_id
       except JWTError:
           raise HTTPException(
               status_code=status.HTTP_401_UNAUTHORIZED,
               detail="Invalid authentication credentials"
           )

   @app.get("/protected")
   async def protected_route(user_id: str = Depends(verify_token)):
       return {"user_id": user_id}
   ```

2. **Create JWT tokens**:
   ```python
   def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
       to_encode = data.copy()
       expire = datetime.utcnow() + expires_delta
       to_encode.update({"exp": expire})
       encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
       return encoded_jwt

   @app.post("/login")
   async def login(username: str, password: str):
       user = authenticate_user(username, password)
       if not user:
           raise HTTPException(status_code=401, detail="Invalid credentials")

       access_token = create_access_token(data={"sub": str(user.id)})
       return {"access_token": access_token, "token_type": "bearer"}
   ```

3. **Handle token expiration**:
   ```python
   from jose.exceptions import ExpiredSignatureError

   def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
       token = credentials.credentials
       try:
           payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
           return payload.get("sub")
       except ExpiredSignatureError:
           raise HTTPException(
               status_code=status.HTTP_401_UNAUTHORIZED,
               detail="Token has expired",
               headers={"WWW-Authenticate": "Bearer"}
           )
       except JWTError:
           raise HTTPException(
               status_code=status.HTTP_401_UNAUTHORIZED,
               detail="Could not validate credentials",
               headers={"WWW-Authenticate": "Bearer"}
           )
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "fastapi", "auth", "jwt", "backend"],
        ),
        # 9. Optimize Database Query
        RemediationSkill(
            skill_id="optimize_database_query",
            name="Optimize Database Query Performance",
            description="Fix N+1 queries and optimize database performance",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"Query.*slow",
                r"N\+1.*query",
                r"Too many queries",
                r"Performance.*degradation",
                r"Timeout.*database",
            ],
            applicable_categories=["runtime_error", "timeout"],
            fix_template="""
Optimize database query at line {line_number} in {file_path}:

SQLAlchemy optimization patterns:

1. **Fix N+1 queries with eager loading**:
   ```python
   from sqlalchemy.orm import joinedload, selectinload

   # Bad: N+1 queries
   users = session.query(User).all()
   for user in users:
       print(user.posts)  # Separate query for each user

   # Good: Single query with JOIN
   users = session.query(User).options(joinedload(User.posts)).all()

   # Or use selectinload for large collections
   users = session.query(User).options(selectinload(User.posts)).all()
   ```

2. **Limit columns with load_only**:
   ```python
   from sqlalchemy.orm import load_only

   # Only load specific columns
   users = session.query(User).options(
       load_only(User.id, User.email, User.username)
   ).all()
   ```

3. **Use pagination**:
   ```python
   from fastapi import Query

   @app.get("/users")
   async def list_users(
       skip: int = Query(0, ge=0),
       limit: int = Query(10, ge=1, le=100),
       db: Session = Depends(get_db)
   ):
       users = db.query(User).offset(skip).limit(limit).all()
       total = db.query(User).count()
       return {"users": users, "total": total}
   ```

4. **Add database indexes**:
   ```python
   # In your model
   class User(Base):
       __tablename__ = "users"

       id = Column(Integer, primary_key=True)
       email = Column(String, unique=True, index=True)  # Add index
       username = Column(String, index=True)  # Add index
       created_at = Column(DateTime, index=True)  # Add index for sorting

       # Composite index for common query combinations
       __table_args__ = (
           Index('idx_user_email_username', 'email', 'username'),
       )
   ```

5. **Use bulk operations**:
   ```python
   # Bulk insert
   users = [User(email=f"user{i}@example.com") for i in range(1000)]
   session.bulk_save_objects(users)
   session.commit()

   # Bulk update
   session.query(User).filter(User.active == False).update(
       {User.status: "inactive"}, synchronize_session=False
   )
   session.commit()
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "sqlalchemy", "performance", "database", "backend"],
        ),
        # 10. Fix Serialization
        RemediationSkill(
            skill_id="fix_serialization",
            name="Fix JSON Serialization Error",
            description="Resolve JSON encoding errors for non-serializable types",
            skill_type=SkillType.CODE_FIX,
            error_patterns=[
                r"not JSON serializable",
                r"TypeError.*JSON",
                r"Object of type.*not serializable",
                r"datetime.*not serializable",
            ],
            applicable_categories=["runtime_error", "type_error"],
            fix_template="""
Fix serialization error at line {line_number} in {file_path}:

JSON serialization solutions:

1. **Use Pydantic models for response**:
   ```python
   from pydantic import BaseModel
   from datetime import datetime
   from typing import Optional

   class UserResponse(BaseModel):
       id: int
       email: str
       created_at: datetime

       class Config:
           orm_mode = True  # Allow from_orm() for SQLAlchemy models

   @app.get("/users/{user_id}", response_model=UserResponse)
   async def get_user(user_id: int, db: Session = Depends(get_db)):
       user = db.query(User).filter(User.id == user_id).first()
       return user  # Automatically serialized via Pydantic
   ```

2. **Custom JSON encoder**:
   ```python
   from fastapi.encoders import jsonable_encoder
   from datetime import datetime
   import json

   class CustomJSONEncoder(json.JSONEncoder):
       def default(self, obj):
           if isinstance(obj, datetime):
               return obj.isoformat()
           if isinstance(obj, Decimal):
               return float(obj)
           if hasattr(obj, '__dict__'):
               return obj.__dict__
           return super().default(obj)

   # Use FastAPI's jsonable_encoder (recommended)
   @app.get("/users/{user_id}")
   async def get_user(user_id: int):
       user = get_user_from_db(user_id)
       return jsonable_encoder(user)
   ```

3. **Datetime serialization**:
   ```python
   from datetime import datetime

   class UserResponse(BaseModel):
       id: int
       created_at: datetime

       class Config:
           json_encoders = {
               datetime: lambda v: v.isoformat()
           }
   ```

4. **Handle SQLAlchemy models**:
   ```python
   from sqlalchemy.ext.declarative import declarative_base
   from sqlalchemy.inspection import inspect

   def to_dict(model):
       '''Convert SQLAlchemy model to dictionary.'''
       return {
           c.key: getattr(model, c.key)
           for c in inspect(model).mapper.column_attrs
       }

   @app.get("/users/{user_id}")
   async def get_user(user_id: int, db: Session = Depends(get_db)):
       user = db.query(User).filter(User.id == user_id).first()
       return to_dict(user)
   ```

5. **Exclude fields from serialization**:
   ```python
   from pydantic import BaseModel, Field

   class UserResponse(BaseModel):
       id: int
       email: str
       password: str = Field(exclude=True)  # Never serialized

       class Config:
           orm_mode = True
   ```
            """,
            required_context=["file_path", "line_number", "error_message"],
            metadata=SkillMetadata(version="1.0", created_at=time.time()),
            tags=["python", "fastapi", "json", "serialization", "backend"],
        ),
    ]

    return skills


def seed_backend_skills(library):
    """Seed backend-specific skills into the library."""
    skills = get_backend_skills()

    for skill in skills:
        library.add_skill(skill)

    library.save()
    print(f"✓ Seeded {len(skills)} backend-specific remediation skills")


if __name__ == "__main__":
    from .skill_library import SkillLibrary

    library = SkillLibrary()
    seed_backend_skills(library)

    print("\nBackend Skills Added:")
    for skill in get_backend_skills():
        print(f"  - {skill.name}")
