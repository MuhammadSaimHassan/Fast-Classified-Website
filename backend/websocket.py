from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
from datetime import datetime


class ConnectionManager:
    def __init__(self):
        # Map of user_id to their WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Map of user_id to their online status
        self.online_users: Set[str] = set()
        # Map of conversation_id to list of user_ids currently viewing it
        self.typing_users: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.online_users.add(user_id)
        # Broadcast online status to all connected users
        await self.broadcast_online_status(user_id, True)

    def disconnect(self, user_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        self.online_users.discard(user_id)
        # Remove from all typing indicators
        for conversation_id in self.typing_users:
            self.typing_users[conversation_id].discard(user_id)

    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                return True
            except Exception:
                self.disconnect(user_id)
                return False
        return False

    async def broadcast(self, message: dict, exclude_user: str = None):
        """Broadcast message to all connected users"""
        disconnected = []
        for user_id, connection in self.active_connections.items():
            if user_id != exclude_user:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected:
            self.disconnect(user_id)

    async def broadcast_online_status(self, user_id: str, is_online: bool):
        """Broadcast user's online status to all connected users"""
        message = {
            "type": "online_status",
            "user_id": user_id,
            "is_online": is_online,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message, exclude_user=user_id)

    async def send_typing_indicator(self, conversation_id: str, user_id: str, is_typing: bool, receiver_id: str):
        """Send typing indicator to conversation participants"""
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id] = set()
        
        if is_typing:
            self.typing_users[conversation_id].add(user_id)
        else:
            self.typing_users[conversation_id].discard(user_id)
        
        message = {
            "type": "typing",
            "conversation_id": conversation_id,
            "user_id": user_id,
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_personal_message(message, receiver_id)

    async def send_new_message(self, message_data: dict, receiver_id: str):
        """Send new message notification"""
        message = {
            "type": "new_message",
            "data": message_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self.send_personal_message(message, receiver_id)

    async def send_notification(self, notification_data: dict, user_id: str):
        """Send notification to a specific user"""
        message = {
            "type": "notification",
            "data": notification_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self.send_personal_message(message, user_id)

    async def send_session_update(self, session_data: dict, user_ids: List[str]):
        """Send session update to relevant users"""
        message = {
            "type": "session_update",
            "data": session_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is online"""
        return user_id in self.online_users

    def get_online_users(self) -> List[str]:
        """Get list of online user IDs"""
        return list(self.online_users)


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint handler"""
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "typing":
                # Handle typing indicator
                await manager.send_typing_indicator(
                    conversation_id=data.get("conversation_id"),
                    user_id=user_id,
                    is_typing=data.get("is_typing", False),
                    receiver_id=data.get("receiver_id")
                )
            
            elif message_type == "message_read":
                # Handle message read acknowledgment
                await manager.send_personal_message(
                    {
                        "type": "message_read",
                        "message_id": data.get("message_id"),
                        "reader_id": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    data.get("sender_id")
                )
            
            elif message_type == "ping":
                # Handle ping to keep connection alive
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast_online_status(user_id, False)
    except Exception as e:
        manager.disconnect(user_id)
        await manager.broadcast_online_status(user_id, False)

