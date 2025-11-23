import { useDataStore } from '../store/dataStore';

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;

  constructor(url: string) {
    this.url = url;
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      // console.log('WebSocket Connected');
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const { updatePositionGroups, updateQueuedSignals } = useDataStore.getState();

      switch (message.type) {
        case 'position_groups_update':
          updatePositionGroups(message.payload);
          break;
        case 'queued_signals_update':
          updateQueuedSignals(message.payload);
          break;
        default:
          // console.log('Unknown message type:', message.type);
          break;
      }
    };

    this.ws.onerror = (event) => {
      console.error('WebSocket Error:', event);
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket Closed:', event);
    };
  }

  public send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not open. Message not sent.', message);
    }
  }

  public close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}