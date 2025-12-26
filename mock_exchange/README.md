# Mock Exchange

A full-featured mock exchange for testing the trading engine without connecting to real exchanges.

## Features

- **Binance-compatible API**: Same endpoints and response formats as Binance Futures
- **SQLite persistence**: Orders, positions, and balances persist across restarts
- **Price manipulation**: Set prices via admin API or UI to trigger order fills
- **Order matching engine**: Limit orders fill when price reaches target
- **Admin UI**: Web interface for price control, order management, and webhook sending
- **Mock TradingView**: Send test webhooks to the engine from the UI

## Quick Start

```bash
# Start with docker-compose
docker compose up mock-exchange

# Access the UI
open http://localhost:9000
```

## API Endpoints

### Public Endpoints (Binance-compatible)

| Endpoint | Description |
|----------|-------------|
| `GET /fapi/v1/ping` | Test connectivity |
| `GET /fapi/v1/time` | Get server time |
| `GET /fapi/v1/exchangeInfo` | Get exchange trading rules |
| `GET /fapi/v1/ticker/price` | Get symbol prices |
| `GET /fapi/v1/premiumIndex` | Get mark price and funding rate |
| `GET /fapi/v1/depth` | Get order book |

### Authenticated Endpoints (require X-MBX-APIKEY header)

| Endpoint | Description |
|----------|-------------|
| `GET /fapi/v2/balance` | Get account balance |
| `GET /fapi/v2/account` | Get account info with positions |
| `POST /fapi/v1/order` | Create order |
| `GET /fapi/v1/order` | Get order status |
| `GET /fapi/v1/openOrders` | Get open orders |
| `DELETE /fapi/v1/order` | Cancel order |
| `GET /fapi/v2/positionRisk` | Get positions |

### Admin Endpoints (for testing)

| Endpoint | Description |
|----------|-------------|
| `GET /admin/symbols` | Get all symbols with prices |
| `PUT /admin/symbols/{symbol}/price` | Set price (triggers order matching) |
| `GET /admin/orders` | Get all orders |
| `POST /admin/orders/{id}/fill` | Manually fill an order |
| `GET /admin/positions` | Get all positions |
| `GET /admin/balances` | Get all balances |
| `PUT /admin/balances/{id}` | Update balance |
| `GET /admin/api-keys` | Get all API keys |
| `POST /admin/api-keys` | Create new API key |
| `DELETE /admin/reset` | Reset all data |
| `POST /admin/webhook/send` | Send webhook to engine |
| `GET /admin/webhook/logs` | Get webhook send logs |

## Default Credentials

- **API Key**: `mock_api_key_12345`
- **API Secret**: `mock_api_secret_67890`

## Testing Workflow

### 1. Start the services

```bash
docker compose up -d
```

### 2. Open the Mock Exchange UI

Navigate to http://localhost:9000

### 3. Send a test signal

Use the "TradingView Webhook" tab to send signals:

1. Select exchange: `mock`
2. Select symbol: `BTCUSDT`
3. Set entry price: (use current price)
4. Set order size: `0.01`
5. Click "Send Webhook"

### 4. View orders

Switch to the "Orders" tab to see pending orders.

### 5. Manipulate prices to trigger fills

In the "Prices" tab:
- Set BTC price to trigger limit order fills
- Use +1%, -1% buttons for quick adjustments

### 6. Monitor positions

Switch to "Positions" tab to see:
- Open positions
- Entry prices
- Unrealized PnL (updates as you change prices)

## Example: Testing Risk Engine

1. Create a position with a limit order
2. Manually fill it
3. Change price to make position go into loss
4. Wait for risk engine timer
5. Observe risk engine actions

## Example: Testing TP Fills

1. Create position with market order (instant fill)
2. TP order is placed automatically
3. Change price to TP level
4. Order matching engine fills TP
5. Position closes

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_EXCHANGE_DB` | `/data/mock_exchange.db` | SQLite database path |
| `MOCK_EXCHANGE_URL` | `http://mock-exchange:9000` | URL for engine to connect |

## Default Symbols

The mock exchange comes pre-configured with:

- BTCUSDT ($95,000)
- ETHUSDT ($3,400)
- SOLUSDT ($190)
- ADAUSDT ($0.90)
- XRPUSDT ($2.30)
- DOGEUSDT ($0.32)
- LINKUSDT ($14.50)
- TRXUSDT ($0.26)
- LTCUSDT ($105)
- AVAXUSDT ($38)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Mock Exchange                        │
├─────────────────────────────────────────────────────────┤
│  FastAPI Server (Port 9000)                             │
│  ├── Binance-compatible REST API                        │
│  ├── Admin API for testing                              │
│  └── Static UI files                                    │
├─────────────────────────────────────────────────────────┤
│  Order Matching Engine                                   │
│  ├── Process market orders (instant fill)               │
│  ├── Check limit orders on price change                 │
│  └── Update positions and balances                      │
├─────────────────────────────────────────────────────────┤
│  SQLite Database                                         │
│  ├── API Keys                                           │
│  ├── Symbols (with prices)                              │
│  ├── Orders                                             │
│  ├── Positions                                          │
│  ├── Balances                                           │
│  └── Trades                                             │
└─────────────────────────────────────────────────────────┘
```
