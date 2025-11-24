import pytest
from httpx import AsyncClient
from unittest.mock import mock_open, patch, MagicMock
from app.main import app
from app.models.user import User
from app.api.dependencies.users import get_current_active_user

# Mock User
@pytest.fixture
def mock_superuser():
    return User(id="123", username="admin", is_superuser=True)

@pytest.fixture
def mock_regular_user():
    return User(id="456", username="user", is_superuser=False)

@pytest.mark.asyncio
async def test_get_logs_superuser_success(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    mock_log_content = "INFO:test log 1\nERROR:test log 2\nINFO:test log 3"
    
    with patch("app.api.logs.LOG_FILE_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("builtins.open", mock_open(read_data=mock_log_content)):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/logs")
                
    assert response.status_code == 200
    assert len(response.json()["logs"]) == 3
    assert response.json()["logs"][0] == "INFO:test log 1"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_filter_level(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    mock_log_content = "INFO:test log 1\nERROR:test log 2\nINFO:test log 3"
    
    with patch("app.api.logs.LOG_FILE_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("builtins.open", mock_open(read_data=mock_log_content)):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/logs?level=ERROR")
                
    assert response.status_code == 200
    assert len(response.json()["logs"]) == 1
    assert response.json()["logs"][0] == "ERROR:test log 2"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_file_not_found(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    with patch("app.api.logs.LOG_FILE_PATH") as mock_path:
        mock_path.exists.return_value = False
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/logs")
            
    assert response.status_code == 200
    assert response.json()["logs"] == []
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_permission_denied(mock_regular_user):
    app.dependency_overrides[get_current_active_user] = lambda: mock_regular_user
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/logs")
        
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient privileges"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_read_error(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    with patch("app.api.logs.LOG_FILE_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("builtins.open", side_effect=Exception("Read error")):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/logs")
                
    assert response.status_code == 500
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_validation_error(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Test invalid lines (too small)
        response = await ac.get("/api/v1/logs?lines=0")
        assert response.status_code == 422
        
        # Test invalid lines (too large)
        response = await ac.get("/api/v1/logs?lines=1001")
        assert response.status_code == 422
        
        # Test invalid level
        response = await ac.get("/api/v1/logs?level=INVALID")
        assert response.status_code == 422

    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_logs_defaults(mock_superuser):
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    
    mock_log_content = "\n".join([f"Log {i}" for i in range(150)])
    
    with patch("app.api.logs.LOG_FILE_PATH") as mock_path:
        mock_path.exists.return_value = True
        with patch("builtins.open", mock_open(read_data=mock_log_content)):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/logs")
                
    assert response.status_code == 200
    # Default is 100 lines
    assert len(response.json()["logs"]) == 100
    assert response.json()["logs"][-1] == "Log 149"
    
    app.dependency_overrides = {}

