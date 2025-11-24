import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.db.database import get_db_session

@pytest.mark.asyncio
async def test_get_db_session_success():
    # Mock the session that AsyncSessionLocal returns
    mock_session = AsyncMock()
    
    # Mock AsyncSessionLocal to return the mock_session context manager
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None
    
    mock_session_maker = MagicMock(return_value=mock_session_cm)
    
    with patch("app.db.database.AsyncSessionLocal", mock_session_maker):
        async for session in get_db_session():
            assert session == mock_session
        
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_db_session_error():
    # Mock the session that AsyncSessionLocal returns
    mock_session = AsyncMock()
    
    # Mock AsyncSessionLocal to return the mock_session context manager
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None
    
    mock_session_maker = MagicMock(return_value=mock_session_cm)
    
    with patch("app.db.database.AsyncSessionLocal", mock_session_maker):
        gen = get_db_session()
        session = await anext(gen)
        
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("Test error"))
        
        # Verify rollback is called
        mock_session.rollback.assert_awaited_once()
        # Verify close is called
        mock_session.close.assert_awaited_once()