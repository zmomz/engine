import { useEffect, useRef } from 'react';
import useAuthStore from '../store/authStore';

const WS_BASE_URL = process.env.REACT_APP_WS_BASE_URL || 'ws://localhost:8000/ws';

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectInterval: number = 1000; // 1 second
  private isConnected: boolean = false;
  private userId: string | null = null;

  public connect(userId: string, token: string) {
    if (this.isConnected && this.userId === userId) {
      console.log('WebSocket already connected for this user.');
      return;
    }

    this.userId = userId;
    const url = `${WS_BASE_URL}/${userId}?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('WebSocket connected.');
      this.isConnected = true;
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('WebSocket message received:', message);
      // Dispatch to Zustand store based on message type
      // Example: if (message.type === 'POSITION_UPDATE') { useAuthStore.getState().updatePosition(message.payload); }
    };

    this.ws.onclose = (event) => {
      this.isConnected = false;
      console.log('WebSocket disconnected:', event.code, event.reason);
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) { // 1000 is normal closure
        this.reconnectAttempts++;
        const delay = this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1);
        console.log(`Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(userId, token), delay);
      } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('Max reconnect attempts reached. Giving up.');
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.ws?.close();
    };
  }

  public disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client initiated disconnect');
      this.ws = null;
      this.isConnected = false;
      this.userId = null;
      console.log('WebSocket explicitly disconnected.');
    }
  }

  public send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not open. Message not sent:', message);
    }
  }
}

const webSocketService = new WebSocketService();

export const useWebSocket = () => {
  const { token, user, isAuthenticated, logout } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated && user?.id && token) {
      webSocketService.connect(user.id, token);
    } else if (!isAuthenticated) {
      webSocketService.disconnect();
    }

    return () => {
      // Disconnect when component unmounts or dependencies change
      webSocketService.disconnect();
    };
  }, [isAuthenticated, user?.id, token, logout]);

  return webSocketService;
};

export default webSocketService;
