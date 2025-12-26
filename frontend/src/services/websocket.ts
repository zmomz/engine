import { z } from 'zod';
import usePositionsStore, { PositionGroup } from '../store/positionsStore';
import useQueueStore, { QueuedSignal } from '../store/queueStore';

// Valid WebSocket message types
const VALID_MESSAGE_TYPES = ['position_groups_update', 'queued_signals_update'] as const;

// Schema for validating incoming WebSocket messages
const wsMessageSchema = z.object({
  type: z.enum(VALID_MESSAGE_TYPES),
  payload: z.unknown(),
});

// Schema for position group data - validates required fields exist
// Uses passthrough to allow all other fields from the full PositionGroup type
const positionGroupSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  side: z.string(),
  status: z.string(),
  exchange: z.string(),
}).passthrough();

const positionGroupsPayloadSchema = z.array(positionGroupSchema);

// Schema for queued signal data - validates required fields exist
const queuedSignalSchema = z.object({
  id: z.string(),
  symbol: z.string(),
}).passthrough();

const queuedSignalsPayloadSchema = z.array(queuedSignalSchema);

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
      try {
        // Parse JSON safely
        let rawMessage: unknown;
        try {
          rawMessage = JSON.parse(event.data);
        } catch {
          console.error('WebSocket: Invalid JSON received');
          return;
        }

        // Validate message structure
        const messageResult = wsMessageSchema.safeParse(rawMessage);
        if (!messageResult.success) {
          console.error('WebSocket: Invalid message structure', messageResult.error.errors);
          return;
        }

        const message = messageResult.data;

        // Validate and process based on message type
        switch (message.type) {
          case 'position_groups_update': {
            const payloadResult = positionGroupsPayloadSchema.safeParse(message.payload);
            if (payloadResult.success) {
              // Cast validated data through unknown - passthrough ensures all fields are preserved
              usePositionsStore.getState().setPositions(payloadResult.data as unknown as PositionGroup[]);
            } else {
              console.error('WebSocket: Invalid position_groups_update payload', payloadResult.error.errors);
            }
            break;
          }
          case 'queued_signals_update': {
            const payloadResult = queuedSignalsPayloadSchema.safeParse(message.payload);
            if (payloadResult.success) {
              // Cast validated data through unknown - passthrough ensures all fields are preserved
              useQueueStore.getState().setQueuedSignals(payloadResult.data as unknown as QueuedSignal[]);
            } else {
              console.error('WebSocket: Invalid queued_signals_update payload', payloadResult.error.errors);
            }
            break;
          }
        }
      } catch (err) {
        console.error('WebSocket: Error processing message', err);
      }
    };

    this.ws.onerror = (event) => {
      console.error('WebSocket Error:', event);
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket Closed:', event);
    };
  }

  public send(message: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not open. Message not sent.');
    }
  }

  public close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}