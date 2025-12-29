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
      payload: [{
        id: '1',
        exchange: 'binance',
        symbol: 'BTC/USD',
        timeframe: 60,
        side: 'long',
        status: 'active',
        pyramid_count: 1,
        max_pyramids: 3,
        replacement_count: 0,
        total_dca_legs: 3,
        filled_dca_legs: 1,
        base_entry_price: 50000,
        weighted_avg_entry: 50000,
        total_invested_usd: 1000,
        total_filled_quantity: 0.02,
        unrealized_pnl_usd: 50,
        unrealized_pnl_percent: 5,
        realized_pnl_usd: 0,
        tp_mode: 'standard',
        risk_timer_expires: null,
        risk_eligible: false,
        risk_blocked: false,
        created_at: '2024-01-01T00:00:00Z',
        closed_at: null,
        total_hedged_qty: 0,
        total_hedged_value_usd: 0,
        pyramids: [],
      }],
    };
    const queuedSignalMessage = {
      type: 'queued_signals_update',
      payload: [{ id: '1', symbol: 'ETH/USD' }],
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

  describe('Error handling', () => {
    it('should handle invalid JSON messages', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const messageEvent = new MessageEvent('message', {
        data: 'not valid json {{{',
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith('WebSocket: Invalid JSON received');
      expect(mockSetPositions).not.toHaveBeenCalled();
      expect(mockSetQueuedSignals).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should handle invalid message structure (missing type)', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify({ payload: [] }),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'WebSocket: Invalid message structure',
        expect.any(Array)
      );
      expect(mockSetPositions).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should handle invalid message type', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify({ type: 'unknown_type', payload: [] }),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'WebSocket: Invalid message structure',
        expect.any(Array)
      );
      expect(mockSetPositions).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should handle invalid position_groups_update payload', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      // Payload missing required fields
      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify({
          type: 'position_groups_update',
          payload: [{ id: '1' }], // Missing symbol, side, status, exchange
        }),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'WebSocket: Invalid position_groups_update payload',
        expect.any(Array)
      );
      expect(mockSetPositions).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should handle invalid queued_signals_update payload', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      // Payload missing required fields
      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify({
          type: 'queued_signals_update',
          payload: [{ wrongField: 'value' }], // Missing id and symbol
        }),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'WebSocket: Invalid queued_signals_update payload',
        expect.any(Array)
      );
      expect(mockSetQueuedSignals).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should warn when sending message while WebSocket is not open', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

      // Set readyState to CLOSED using Object.defineProperty for readonly property
      Object.defineProperty(mockWebSocket, 'readyState', { value: 3, writable: true }); // WebSocket.CLOSED

      service.send({ type: 'test' });

      expect(consoleWarnSpy).toHaveBeenCalledWith('WebSocket not open. Message not sent.');
      expect(mockWebSocket.send).not.toHaveBeenCalled();

      consoleWarnSpy.mockRestore();
    });

    it('should handle general errors during message processing', () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      // Make getState throw an error
      (usePositionsStore.getState as jest.Mock).mockImplementation(() => {
        throw new Error('Store error');
      });

      const positionGroupMessage = {
        type: 'position_groups_update',
        payload: [{
          id: '1',
          exchange: 'binance',
          symbol: 'BTC/USD',
          side: 'long',
          status: 'active',
        }],
      };

      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify(positionGroupMessage),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'WebSocket: Error processing message',
        expect.any(Error)
      );

      consoleErrorSpy.mockRestore();
    });

    it('should handle when WebSocket is null during send', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

      // Create a new service instance and manually set ws to null
      const newService = new WebSocketService('ws://localhost:8000/ws');
      (newService as any).ws = null;

      newService.send({ type: 'test' });

      expect(consoleWarnSpy).toHaveBeenCalledWith('WebSocket not open. Message not sent.');

      consoleWarnSpy.mockRestore();
    });

    it('should handle when WebSocket is null during close', () => {
      // Create a new service instance and manually set ws to null
      const newService = new WebSocketService('ws://localhost:8000/ws');
      (newService as any).ws = null;

      // Should not throw
      expect(() => newService.close()).not.toThrow();
    });
  });

  describe('Valid message handling', () => {
    it('should handle valid queued_signals_update with all required fields', () => {
      const queuedSignalMessage = {
        type: 'queued_signals_update',
        payload: [{
          id: '1',
          symbol: 'ETH/USD',
          status: 'pending',
          extra_field: 'should be preserved',
        }],
      };

      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify(queuedSignalMessage),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(mockSetQueuedSignals).toHaveBeenCalledWith(queuedSignalMessage.payload);
    });

    it('should handle empty payload arrays', () => {
      const positionGroupMessage = {
        type: 'position_groups_update',
        payload: [],
      };

      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify(positionGroupMessage),
      });

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent);
      }

      expect(mockSetPositions).toHaveBeenCalledWith([]);
    });
  });

  describe('WebSocket lifecycle', () => {
    it('should handle onopen event', () => {
      // The onopen handler is set but does nothing (commented console.log)
      // Just verify it doesn't throw
      if (mockWebSocket.onopen) {
        expect(() => mockWebSocket.onopen!(new Event('open'))).not.toThrow();
      }
    });
  });
});