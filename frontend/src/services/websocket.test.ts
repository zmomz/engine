import { WebSocketService } from '../services/websocket';
import { useDataStore } from '../store/dataStore';

jest.mock('../store/dataStore', () => ({
  useDataStore: {
    getState: jest.fn(),
  },
}));

describe('WebSocketService', () => {
  let mockWebSocket: jest.Mocked<WebSocket>;
  let service: WebSocketService;
  let mockUpdatePositionGroups: jest.Mock;
  let mockUpdateQueuedSignals: jest.Mock;

  beforeEach(() => {
    mockWebSocket = { 
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      readyState: WebSocket.OPEN,
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
    } as any;

    global.WebSocket = jest.fn(() => mockWebSocket) as jest.Mock;

    mockUpdatePositionGroups = jest.fn();
    mockUpdateQueuedSignals = jest.fn();

    (useDataStore.getState as jest.Mock).mockReturnValue({
      updatePositionGroups: mockUpdatePositionGroups,
      updateQueuedSignals: mockUpdateQueuedSignals,
    });

    service = new WebSocketService('ws://localhost:8000/ws');
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should connect to the WebSocket server', () => {
    expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws');
  });

  it('should send messages through the WebSocket', () => {
    const message = { type: 'test', payload: 'hello' };
    service.send(message);
    expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(message));
  });

  it('should handle incoming messages and update the store', () => {
    const positionGroupMessage = {
      type: 'position_groups_update',
      payload: [{ id: 1, symbol: 'BTC/USD' }],
    };
    const queuedSignalMessage = {
      type: 'queued_signals_update',
      payload: [{ id: 1, symbol: 'ETH/USD' }],
    };

    // Simulate receiving a position group update message
    const messageEvent1 = new MessageEvent('message', {
      data: JSON.stringify(positionGroupMessage),
    });
    if (mockWebSocket.onmessage) {
      mockWebSocket.onmessage(messageEvent1);
    }
    expect(mockUpdatePositionGroups).toHaveBeenCalledWith(positionGroupMessage.payload);

    // Simulate receiving a queued signal update message
    const messageEvent2 = new MessageEvent('message', {
      data: JSON.stringify(queuedSignalMessage),
    });
    if (mockWebSocket.onmessage) {
      mockWebSocket.onmessage(messageEvent2);
    }
    expect(mockUpdateQueuedSignals).toHaveBeenCalledWith(queuedSignalMessage.payload);
  });

  it('should handle WebSocket errors', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const errorEvent = new Event('error');
    if (mockWebSocket.onerror) {
      mockWebSocket.onerror(errorEvent);
    }
    expect(consoleErrorSpy).toHaveBeenCalledWith('WebSocket Error:', errorEvent);
    consoleErrorSpy.mockRestore();
  });

  it('should handle WebSocket close events', () => {
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    const closeEvent = new CloseEvent('close', { code: 1000, reason: 'Normal closure' });
    if (mockWebSocket.onclose) {
      mockWebSocket.onclose(closeEvent);
    }
    expect(consoleLogSpy).toHaveBeenCalledWith('WebSocket Closed:', closeEvent);
    consoleLogSpy.mockRestore();
  });

  it('should close the WebSocket connection', () => {
    service.close();
    expect(mockWebSocket.close).toHaveBeenCalled();
  });
});