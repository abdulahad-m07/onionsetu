# backend/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.main import app
from backend.app.config.database import Base, get_db
from backend.app.models.user import User, UserRoleEnum
from backend.app.services.auth_service import AuthService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        # Seed test users
        admin = User(
            id="admin_001",
            phone="+919999900001",
            name="Super Admin",
            role=UserRoleEnum.ADMIN,
            procurement_center_id="APMC-HQ-01",
        )
        grader = User(
            id="grader_001",
            phone="+919999900002",
            name="Chief Grader Ramesh",
            role=UserRoleEnum.GRADER,
            procurement_center_id="APMC-LASALGAON-01",
        )
        farmer = User(
            id="farmer_001",
            phone="+919999900003",
            name="Suresh Shinde",
            role=UserRoleEnum.FARMER,
            procurement_center_id="APMC-LASALGAON-01",
        )
        session.add_all([admin, grader, farmer])
        await session.commit()

        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def grader_token():
    return AuthService.create_access_token(user_id="grader_001", role=UserRoleEnum.GRADER)

@pytest.fixture
def farmer_token():
    return AuthService.create_access_token(user_id="farmer_001", role=UserRoleEnum.FARMER)

@pytest.fixture
def admin_token():
    return AuthService.create_access_token(user_id="admin_001", role=UserRoleEnum.ADMIN)
