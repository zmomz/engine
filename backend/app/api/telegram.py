"""
Telegram Configuration API Endpoints
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.db.database import get_db_session
from app.models.user import User
from app.schemas.telegram_config import TelegramConfig, TelegramConfigUpdate
from app.services.telegram_broadcaster import TelegramBroadcaster
from app.api.dependencies.users import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config", response_model=TelegramConfig)
async def get_telegram_config(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Get current user's Telegram configuration"""

    if current_user.telegram_config:
        return TelegramConfig(**current_user.telegram_config)
    else:
        # Return default config
        return TelegramConfig()


@router.put("/config", response_model=TelegramConfig)
async def update_telegram_config(
    config_update: TelegramConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Update Telegram configuration"""

    # Get current config or create new one
    if current_user.telegram_config:
        current_config = TelegramConfig(**current_user.telegram_config)
    else:
        current_config = TelegramConfig()

    # Update fields
    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_config, field, value)

    # Save to database
    db_user = await session.get(User, current_user.id)  # load the user attached to this session
    db_user.telegram_config = current_config.model_dump(mode='json')
    attributes.flag_modified(db_user, 'telegram_config')
    await session.commit()
    await session.refresh(db_user)

    logger.info(f"Updated Telegram config for user {current_user.username}")

    return current_config


@router.post("/test-connection")
async def test_telegram_connection(
    config_update: TelegramConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Test Telegram bot connection with provided credentials"""

    # Start with the stored config, or a default if none exists
    if current_user.telegram_config:
        config_data = current_user.telegram_config
    else:
        config_data = {}

    # Merge with the provided update
    update_data = config_update.model_dump(exclude_unset=True)
    config_data.update(update_data)
    
    config = TelegramConfig(**config_data)

    if not config.bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot token not provided"
        )

    broadcaster = TelegramBroadcaster(config)
    success, error = await broadcaster.test_connection()

    if success:
        return {"status": "success", "message": "Telegram connection OK"}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Telegram error: {error}"
        )



@router.post("/test-message")
async def send_test_message(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Send a test message to the Telegram channel"""

    if not current_user.telegram_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram configuration not set"
        )

    config = TelegramConfig(**current_user.telegram_config)

    if not config.bot_token or not config.channel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot token and channel ID required"
        )

    # Create test message
    test_message = (
        "📈 Test Signal from AlgoMakers Engine\n\n"
        "This is a test message to verify your Telegram configuration.\n\n"
        f"Channel: {config.channel_name}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "✅ If you see this message, your configuration is working correctly!"
    )

    broadcaster = TelegramBroadcaster(config)
    try:
        message_id = await broadcaster._send_message(test_message)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    if message_id:
        return {"status": "success", "message": "Test message sent successfully", "message_id": message_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send test message. Check your channel ID and bot permissions."
        )
