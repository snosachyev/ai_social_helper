"""Telegram Service for Telethon-based channel parsing"""

import asyncio
import logging
import random
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel
from telethon import TelegramClient, events, errors
from telethon.tl.types import Channel, Message
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
import aiokafka
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Remove shared imports for now to test basic functionality
# from shared.models.base import BaseResponse, HealthCheck
# from shared.config.settings import settings
# from shared.database.postgres import get_async_session
# from shared.database.redis import get_redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Settings fallback
class Settings:
    service_version = "1.0.0"
    kafka_bootstrap_servers = "kafka:9092"
    api_host = "0.0.0.0"
    debug = False
    log_level = "INFO"

settings = Settings()

# Simple response models
class BaseResponse(BaseModel):
    success: bool
    message: str
    data: dict = {}

class HealthCheck(BaseModel):
    service_name: str
    status: str
    details: dict = {}

class ParseRequest(BaseModel):
    channel_username: str
    limit: int = 5
    save_format: str = "json"

# Global Telegram client
telegram_client: Optional[TelegramClient] = None
kafka_producer: Optional[aiokafka.AIOKafkaProducer] = None


class ProxyManager:
    """Класс для управления прокси"""
    
    @staticmethod
    def parse_proxy(proxy_string, proxy_type='socks5'):
        """Парсит строку прокси в формат для Telethon"""
        if not proxy_string:
            return None
            
        try:
            if proxy_type.lower() == 'mtproxy':
                parts = proxy_string.split(':')
                if len(parts) == 3:
                    host, port, secret = parts
                    return (host, int(port), secret)
                else:
                    logger.error(f"Неверный формат MTProxy: {proxy_string}")
                    return None
                    
            elif proxy_type.lower() in ['socks5', 'http']:
                proxy_string = proxy_string.replace(f'{proxy_type}://', '').replace('https://', '').replace('http://', '')
                
                if '@' in proxy_string:
                    auth_part, host_port = proxy_string.split('@')
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                    else:
                        username, password = auth_part, ''
                    
                    host, port = host_port.split(':')
                    return (proxy_type, host, int(port), True, username, password)
                else:
                    host, port = proxy_string.split(':')
                    return (proxy_type, host, int(port), True, '', '')
            else:
                logger.error(f"Неподдерживаемый тип прокси: {proxy_type}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка парсинга прокси {proxy_string}: {e}")
            return None
    
    @staticmethod
    def get_proxy_connection(proxy_config, proxy_type):
        """Возвращает appropriate connection object для разных типов прокси"""
        if proxy_type.lower() == 'mtproxy' and proxy_config:
            return ConnectionTcpMTProxyRandomizedIntermediate(*proxy_config)
        return None


class TelegramChannelParser:
    """Advanced Telegram channel parser with rate limiting"""
    
    def __init__(self, client: TelegramClient, rate_limit=2.0):
        self.client = client
        self.rate_limit = rate_limit
        self.min_delay = 1.0 / rate_limit
        self.last_request_time = 0
        
    async def rate_limit_sleep(self):
        """Умная задержка для контроля скорости запросов"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last + random.uniform(0.1, 0.5)
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()

    async def safe_get_entity(self, peer):
        """Безопасное получение entity с контролем скорости"""
        await self.rate_limit_sleep()
        
        try:
            return await self.client.get_entity(peer)
        except ValueError:
            logger.warning(f"Entity not found: {peer}")
            return None
        except errors.ChannelPrivateError:
            logger.warning(f"Channel is private: {peer}")
            return None
        except errors.FloodWaitError as e:
            wait = int(e.seconds) + random.randint(5, 15)
            logger.warning(f"FloodWait {wait}s for get_entity")
            await asyncio.sleep(wait)
            return await self.safe_get_entity(peer)

    async def parse_channel_posts(self, channel_username, limit=100, offset_id=0):
        """Парсит посты из указанного канала/группы"""
        entity = await self.safe_get_entity(channel_username)
        if not entity:
            logger.error(f"Не удалось найти канал: {channel_username}")
            return []

        posts = []
        parsed_count = 0
        
        logger.info(f"Начинаем парсинг канала: {entity.title}")
        
        try:
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                offset_id=offset_id,
                wait_time=1
            ):
                post_data = {
                    'message_id': message.id,
                    'channel_id': entity.id,
                    'channel_title': entity.title,
                    'channel_username': entity.username,
                    'text': message.text or '',
                    'date': message.date.isoformat() if message.date else None,
                    'sender_id': getattr(message, 'sender_id', None),
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0),
                    'reply_to_msg_id': getattr(message, 'reply_to_msg_id', None),
                    'media_type': None,
                    'media_url': None,
                    'sync_type': 'realtime'
                }

                if message.media:
                    if hasattr(message.media, 'photo'):
                        post_data['media_type'] = 'photo'
                    elif hasattr(message.media, 'document'):
                        post_data['media_type'] = 'document'
                    elif hasattr(message.media, 'webpage'):
                        post_data['media_type'] = 'webpage'
                    else:
                        post_data['media_type'] = 'other'

                posts.append(post_data)
                parsed_count += 1
                
                if parsed_count % 10 == 0:
                    logger.info(f"Спарсено {parsed_count} постов")
                
                await self.rate_limit_sleep()

        except errors.FloodWaitError as e:
            wait = int(e.seconds) + random.randint(5, 15)
            logger.warning(f"FloodWait {wait}s при парсинге")
            await asyncio.sleep(wait)
        except errors.ChannelPrivateError:
            logger.error("Нет доступа к каналу (приватный)")
        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}")

        logger.info(f"Парсинг завершен. Всего собрано {len(posts)} постов")
        return posts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global telegram_client, kafka_producer
    
    logger.info("Starting Telegram Service...")
    
    # Get Telegram credentials from environment
    api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
    api_hash = os.getenv('TELEGRAM_API_HASH', '')
    session_string = os.getenv('SESSION', '')
    proxy_string = os.getenv('TELEGRAM_PROXY')
    proxy_type = os.getenv('TELEGRAM_PROXY_TYPE', 'socks5')
    rate_limit = float(os.getenv('TELEGRAM_RATE_LIMIT', '2.0'))
    
    if not api_id or not api_hash:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set")
        raise RuntimeError("Telegram credentials not configured")
    
    # Parse proxy if provided
    proxy_config = None
    connection = None
    if proxy_string:
        proxy_config = ProxyManager.parse_proxy(proxy_string, proxy_type)
        if proxy_config:
            connection = ProxyManager.get_proxy_connection(proxy_config, proxy_type)
            logger.info(f"Using proxy: {proxy_type} - {proxy_string}")
    
    # Initialize Telegram client - use string session if provided
    if session_string:
        # Use StringSession for string sessions
        from telethon.sessions import StringSession
        session_obj = StringSession(session_string)
        logger.info(f"Using string session")
    else:
        # Use file session
        session_obj = 'my_session.session'
        logger.info(f"Using file session: my_session.session")
    
    client_params = {
        'session': session_obj,
        'api_id': api_id,
        'api_hash': api_hash,
        'device_model': "PC",
        'system_version': "Windows 10",
        'app_version': "4.8.1",
        'lang_code': "en"
    }
    
    if proxy_config and proxy_type != 'mtproxy':
        client_params['proxy'] = proxy_config
    elif connection:
        client_params['connection'] = connection
    
    telegram_client = TelegramClient(**client_params)
    
    # Skip Kafka for now to test basic functionality
    kafka_producer = None
    # kafka_producer = aiokafka.AIOKafkaProducer(
    #     bootstrap_servers=settings.kafka_bootstrap_servers
    # )
    
    # Initialize parser
    app.state.parser = TelegramChannelParser(telegram_client, rate_limit)
    
    try:
        await telegram_client.start()
        # await kafka_producer.start()
        
        if not await telegram_client.is_user_authorized():
            logger.error("Session is not authorized")
            raise RuntimeError("Telegram session not authorized")
        
        logger.info("Telegram client started successfully")
        
        # Register event handlers
        # setup_message_handlers()
        
        yield
        
    finally:
        logger.info("Shutting down Telegram Service...")
        if telegram_client:
            await telegram_client.disconnect()
        # if kafka_producer:
        #     await kafka_producer.stop()


def setup_message_handlers():
    """Setup Telegram message event handlers."""
    
    @telegram_client.on(events.NewMessage(chats=True))
    async def handle_new_message(event: events.NewMessage.Event):
        """Handle new messages from channels."""
        try:
            if not event.message or not event.chat:
                return
                
            # Extract message data
            message_data = {
                'message_id': event.message.id,
                'channel_id': event.chat.id,
                'channel_title': getattr(event.chat, 'title', ''),
                'channel_username': getattr(event.chat, 'username', ''),
                'text': event.message.text or '',
                'date': event.message.date.isoformat(),
                'sender_id': event.message.sender_id,
                'views': getattr(event.message, 'views', 0),
                'forwards': getattr(event.message, 'forwards', 0),
                'reply_to_msg_id': getattr(event.message, 'reply_to_msg_id', None),
                'media_type': None,
                'media_url': None,
                'sync_type': 'realtime'
            }
            
            # Handle media
            if event.message.media:
                if hasattr(event.message.media, 'photo'):
                    message_data['media_type'] = 'photo'
                elif hasattr(event.message.media, 'document'):
                    message_data['media_type'] = 'document'
            
            # Send to Kafka for processing
            await kafka_producer.send(
                'telegram_messages',
                value=message_data
            )
            
            logger.info(f"Processed message from channel {event.chat.id}")
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")


app = FastAPI(
    title="Telegram Service",
    description="Telethon-based Telegram channel monitoring and parsing",
    version=settings.service_version,
    lifespan=lifespan
)


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    status = "healthy"
    details = {
        "telegram_connected": telegram_client is not None and telegram_client.is_connected(),
        "telegram_authorized": telegram_client is not None and await telegram_client.is_user_authorized(),
        "kafka_connected": kafka_producer is not None,
        "version": settings.service_version
    }
    
    if not details["telegram_connected"] or not details["telegram_authorized"]:
        status = "unhealthy"
    
    return HealthCheck(
        service_name="telegram-service",
        status=status,
        details=details
    )


@app.post("/channels/join")
async def join_channel(channel_username: str):
    """Join a Telegram channel for monitoring."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        # Get channel entity
        channel = await telegram_client.get_entity(channel_username)
        if not isinstance(channel, Channel):
            raise HTTPException(status_code=400, detail="Not a channel")
        
        # Join channel
        await telegram_client.join_channel(channel)
        
        logger.info(f"Joined channel: {channel_username}")
        
        return BaseResponse(
            success=True,
            message=f"Successfully joined channel: {channel_username}",
            data={
                "channel_id": channel.id,
                "channel_title": channel.title,
                "channel_username": channel.username
            }
        )
        
    except Exception as e:
        logger.error(f"Error joining channel {channel_username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/channels/leave")
async def leave_channel(channel_username: str):
    """Leave a Telegram channel."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        # Get channel entity
        channel = await telegram_client.get_entity(channel_username)
        if not isinstance(channel, Channel):
            raise HTTPException(status_code=400, detail="Not a channel")
        
        # Leave channel
        await telegram_client.leave_channel(channel)
        
        logger.info(f"Left channel: {channel_username}")
        
        return BaseResponse(
            success=True,
            message=f"Successfully left channel: {channel_username}"
        )
        
    except Exception as e:
        logger.error(f"Error leaving channel {channel_username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/channels/list")
async def list_channels():
    """List all joined channels."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        # Get all dialogs
        dialogs = await telegram_client.get_dialogs()
        
        channels = []
        for dialog in dialogs:
            if isinstance(dialog.entity, Channel):
                channels.append({
                    "id": dialog.entity.id,
                    "title": dialog.entity.title,
                    "username": dialog.entity.username,
                    "participants_count": getattr(dialog.entity, 'participants_count', 0),
                    "date": dialog.entity.date.isoformat() if dialog.entity.date else None
                })
        
        return BaseResponse(
            success=True,
            message=f"Found {len(channels)} channels",
            data={"channels": channels}
        )
        
    except Exception as e:
        logger.error(f"Error listing channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/channels/{channel_id}/messages")
async def get_channel_messages(
    channel_id: int,
    limit: int = 100,
    offset_id: Optional[int] = None
):
    """Get messages from a specific channel."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        # Get channel entity
        channel = await telegram_client.get_entity(channel_id)
        
        # Get messages
        messages = []
        async for message in telegram_client.iter_messages(
            channel,
            limit=limit,
            offset_id=offset_id
        ):
            message_data = {
                "id": message.id,
                "text": message.text,
                "date": message.date.isoformat(),
                "sender_id": message.sender_id,
                "views": getattr(message, 'views', 0),
                "forwards": getattr(message, 'forwards', 0),
                "reply_to_msg_id": getattr(message, 'reply_to_msg_id', None)
            }
            
            # Handle media
            if message.media:
                if hasattr(message.media, 'photo'):
                    message_data["media_type"] = "photo"
                elif hasattr(message.media, 'document'):
                    message_data["media_type"] = "document"
            
            messages.append(message_data)
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(messages)} messages",
            data={"messages": messages}
        )
        
    except Exception as e:
        logger.error(f"Error getting messages from channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/channels/{channel_id}/sync")
async def sync_channel_messages(
    channel_id: int,
    background_tasks: BackgroundTasks,
    limit: int = 1000
):
    """Sync historical messages from a channel."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        # Add background task for syncing
        background_tasks.add_task(
            sync_channel_messages_task,
            channel_id,
            limit
        )
        
        return BaseResponse(
            success=True,
            message="Channel sync started in background"
        )
        
    except Exception as e:
        logger.error(f"Error starting channel sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/channels/parse")
async def parse_channel_posts(request: ParseRequest):
    """Parse posts from a channel using advanced parser."""
    try:
        if not telegram_client:
            raise HTTPException(status_code=503, detail="Telegram client not initialized")
        
        parser = app.state.parser
        posts = await parser.parse_channel_posts(request.channel_username, request.limit)
        
        if not posts:
            return BaseResponse(
                success=False,
                message="No posts found or error accessing channel"
            )
        
        # Save to files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"telegram_posts_{request.channel_username}_{timestamp}.json"
        txt_filename = f"telegram_posts_{request.channel_username}_{timestamp}.txt"
        
        # Save JSON
        json_data = {
            'parsed_at': datetime.now().isoformat(),
            'channel': request.channel_username,
            'total_posts': len(posts),
            'posts': posts
        }
        
        with open(f'/app/{json_filename}', 'w', encoding='utf-8') as f:
            import json
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # Save TXT
        with open(f'/app/{txt_filename}', 'w', encoding='utf-8') as f:
            f.write(f"Парсинг выполнен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Канал: {request.channel_username}\n")
            f.write(f"Всего постов: {len(posts)}\n")
            f.write("=" * 50 + "\n\n")
            
            for post in posts:
                f.write(f"ID: {post['message_id']}\n")
                f.write(f"Дата: {post['date']}\n")
                f.write(f"Канал: {post['channel_title']}\n")
                if post['views']:
                    f.write(f"Просмотры: {post['views']}\n")
                if post['media_type']:
                    f.write(f"Медиа: {post['media_type']}\n")
                f.write(f"Текст:\n{post['text']}\n")
                f.write("-" * 30 + "\n\n")
        
        logger.info(f"Posts saved to {json_filename} and {txt_filename}")
        
        # Skip Kafka for now
        # for post in posts:
        #     await kafka_producer.send(
        #         'telegram_messages',
        #         value=post
        #     )
        
        return BaseResponse(
            success=True,
            message=f"Successfully parsed {len(posts)} posts from {request.channel_username}",
            data={
                "posts": posts,
                "channel": request.channel_username,
                "total_parsed": len(posts),
                "files": {
                    "json": json_filename,
                    "txt": txt_filename
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error parsing channel {request.channel_username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files")
async def list_files():
    """List all parsed files."""
    try:
        import os
        files = []
        for filename in os.listdir('/app'):
            if filename.startswith('telegram_posts_') and (filename.endswith('.json') or filename.endswith('.txt')):
                file_path = f'/app/{filename}'
                stat = os.stat(file_path)
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return BaseResponse(
            success=True,
            message=f"Found {len(files)} files",
            data={"files": files}
        )
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{filename}")
async def download_file(filename: str):
    """Download a parsed file."""
    try:
        import os
        file_path = f'/app/{filename}'
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if not filename.startswith('telegram_posts_'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def sync_channel_messages_task(channel_id: int, limit: int):
    """Background task to sync channel messages."""
    try:
        channel = await telegram_client.get_entity(channel_id)
        
        message_count = 0
        async for message in telegram_client.iter_messages(
            channel,
            limit=limit
        ):
            if not message.text:
                continue
                
            message_data = {
                'message_id': message.id,
                'channel_id': channel_id,
                'channel_title': channel.title,
                'channel_username': channel.username,
                'text': message.text,
                'date': message.date.isoformat(),
                'sender_id': message.sender_id,
                'views': getattr(message, 'views', 0),
                'forwards': getattr(message, 'forwards', 0),
                'reply_to_msg_id': getattr(message, 'reply_to_msg_id', None),
                'media_type': None,
                'media_url': None,
                'sync_type': 'historical'
            }
            
            # Send to Kafka
            await kafka_producer.send(
                'telegram_messages',
                value=message_data
            )
            
            message_count += 1
            
            # Rate limiting
            if message_count % 100 == 0:
                await asyncio.sleep(1)
        
        logger.info(f"Synced {message_count} messages from channel {channel_id}")
        
    except Exception as e:
        logger.error(f"Error in channel sync task: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=8008,  # Unique port for telegram service
        reload=settings.debug,
        workers=1  # Single worker due to TelegramClient
    )