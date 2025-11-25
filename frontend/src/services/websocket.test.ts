import { WebSocketService } from '../services/websocket';
import usePositionsStore from '../store/positionsStore';
import useQueueStore from '../store/queueStore';

jest.mock('../store/positionsStore', () => ({
  __esModule: true,
  default: {
    getState: jest.fn(),
  },
}));

jest.mock('../store/queueStore', () => ({
  __esModule: true,
  default: {
    getState: jest.fn(),
  },
}));

describe('WebSocketService', () => {
  let mockWebSocket: jest.Mocked<WebSocket>;
  let service: WebSocketService;
  let mockSetPositions: jest.Mock;
  let mockSetQueuedSignals: jest.Mock;

  beforeEach(() => {
    mockWebSocket = { 
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      readyState: 1, // WebSocket.OPEN
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
    } as any;

    const mockWebSocketConstructor = jest.fn(() => mockWebSocket) as any;
    mockWebSocketConstructor.CONNECTING = 0;
    mockWebSocketConstructor.OPEN = 1;
    mockWebSocketConstructor.CLOSING = 2;
    mockWebSocketConstructor.CLOSED = 3;

    global.WebSocket = mockWebSocketConstructor;

    mockSetPositions = jest.fn();
    mockSetQueuedSignals = jest.fn();

    (usePositionsStore.getState as jest.Mock).mockReturnValue({
      setPositions: mockSetPositions,
    });
    
    (useQueueStore.getState as jest.Mock).mockReturnValue({
      setQueuedSignals: mockSetQueuedSignals,
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
    expect(mockSetPositions).toHaveBeenCalledWith(positionGroupMessage.payload);

    // Simulate receiving a queued signal update message
    const messageEvent2 = new MessageEvent('message', {
      data: JSON.stringify(queuedSignalMessage),
    });
    if (mockWebSocket.onmessage) {
      mockWebSocket.onmessage(messageEvent2);
    }
    expect(mockSetQueuedSignals).toHaveBeenCalledWith(queuedSignalMessage.payload);
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