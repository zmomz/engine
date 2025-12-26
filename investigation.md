Webhook Endpoint Analysis
1. Secret Validation ✅
Yes, the secret field is validated against the user's configured webhook secret. Location: signature_validation.py:34-54
received_secret = payload.get("secret")
if not received_secret:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing secret in payload.",
    )

# ...user lookup...

# Validate the secret using timing-safe comparison
if not hmac.compare_digest(user.webhook_secret, received_secret):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid secret.",
    )
The validation uses hmac.compare_digest() to prevent timing attacks.
2. Required Fields Parsing ✅
Yes, all required fields are parsed via Pydantic models in webhook_payloads.py.
Field Path	Type	Required
user_id	uuid.UUID	✅
secret	str	✅
source	str	✅
timestamp	datetime	✅
tv.exchange	str	✅
tv.symbol	str	✅
tv.timeframe	int	✅
tv.action	str	✅
tv.market_position	str	✅
tv.market_position_size	float	✅
tv.prev_market_position	str	✅
tv.prev_market_position_size	float	✅
tv.entry_price	float	✅
tv.close_price	float	✅
tv.order_size	float	✅
strategy_info.trade_id	str	✅
strategy_info.alert_name	str	✅
strategy_info.alert_message	str	✅
execution_intent.type	Literal["signal", "exit", "reduce", "reverse"]	✅
execution_intent.side	Literal["buy", "sell", "long", "short"]	✅
execution_intent.position_size_type	Literal["contracts", "base", "quote"]	✅
execution_intent.precision_mode	Literal["auto"]	✅
risk.max_slippage_percent	float	✅
risk.stop_loss	float	Optional
risk.take_profit	float	Optional
Additionally, there's a placeholder validator on TradingViewData fields:
@field_validator('exchange', 'symbol', 'action', 'market_position', 'prev_market_position')
@classmethod
def no_placeholders(cls, v: str) -> str:
    if "{{" in v or "}}" in v:
         raise ValueError("Unreplaced placeholder detected")
    return v
3. Missing/Malformed Field Handling ✅
When a required field is missing or malformed, Pydantic raises a ValidationError, which is converted to a 422 Unprocessable Entity response. Location: webhooks.py:26-29
try:
    webhook_payload = WebhookPayload(**payload)
except ValidationError as e:
    raise RequestValidationError(e.errors())
Example error response for missing tv.symbol:
{
  "detail": [
    {
      "type": "missing",
      "loc": ["tv", "symbol"],
      "msg": "Field required",
      "input": {...}
    }
  ]
}
Example error response for unreplaced placeholder:
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["tv", "symbol"],
      "msg": "Value error, Unreplaced placeholder detected",
      "input": "{{ticker}}"
    }
  ]
}
4. Incoming Signal Logging ✅
Yes, incoming signals are logged at the start of routing. Location: signal_router.py:51
logger.info(f"Received signal for {signal.tv.symbol} ({signal.tv.action}) on {signal.tv.exchange} for user {self.user.id}")
However, this logging happens after validation succeeds, not before. Invalid payloads that fail validation are not logged (only the HTTP 422 response is returned).
5. Complete Validation Flow & Error Responses
┌─────────────────────────────────────────────────────────────────────────────┐
│  POST /{user_id}/tradingview                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SignatureValidator.__call__()                                              │
│  Location: signature_validation.py:20-57                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Parse JSON body                                                         │
│     └─ FAIL → 422 "Invalid JSON payload."                                   │
│                                                                             │
│  2. Extract payload.get("secret")                                           │
│     └─ MISSING → 401 "Missing secret in payload."                           │
│                                                                             │
│  3. Lookup user by user_id                                                  │
│     └─ NOT FOUND → 404 "User not found."                                    │
│                                                                             │
│  4. hmac.compare_digest(user.webhook_secret, received_secret)               │
│     └─ MISMATCH → 403 "Invalid secret."                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  tradingview_webhook()                                                      │
│  Location: webhooks.py:14-35                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  5. WebhookPayload(**payload) - Pydantic validation                         │
│     └─ Missing field → 422 with field path                                  │
│     └─ Wrong type → 422 with type error                                     │
│     └─ Placeholder detected → 422 "Unreplaced placeholder detected"        │
│                                                                             │
│  6. SignalRouterService.route()                                             │
│     └─ logger.info("Received signal for...")  ← LOGGING HAPPENS HERE       │
│     └─ Process signal...                                                    │
│                                                                             │
│  7. Return 202 {"status": "success", ...}                                   │
└─────────────────────────────────────────────────────────────────────────────┘
Summary
Question	Answer
1. Secret validation?	✅ Yes, with timing-safe hmac.compare_digest()
2. All required fields parsed?	✅ Yes, via nested Pydantic models
3. Missing/malformed handling?	✅ 422 with detailed field-level errors
4. Logged before processing?	⚠️ Logged after validation, not before
5. Error responses?	Shown above (401, 403, 404, 422 codes)

Webhook Authentication Analysis
1. Is there webhook signature validation implemented? ✅ Yes, but it's secret-based, not HMAC signature-based
The system uses a per-user secret token approach rather than HMAC signature validation of the request body. Location: signature_validation.py How it works:
Each user has a unique webhook_secret generated at registration
The secret is a 32-character hex string: secrets.token_hex(16)
Incoming webhooks must include this secret in the JSON payload
The secret is compared using timing-safe hmac.compare_digest()
# User model - secret generation (user.py:12-13)
def generate_webhook_secret():
    return secrets.token_hex(16)

# Validation (signature_validation.py:50)
if not hmac.compare_digest(user.webhook_secret, received_secret):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret.")
Note: This is NOT traditional HMAC signature validation (where you'd compute HMAC(secret, request_body) and compare). It's a simpler shared-secret approach where the secret is sent in the payload itself.
2. Where is security.webhook_signature_validation checked? ❌ It doesn't exist
There is no security.webhook_signature_validation setting or function in the codebase. The grep search returned no results for this pattern. The validation is always enabled - it's hardcoded in the SignatureValidator dependency that's applied to the webhook endpoint:
# webhooks.py:18
user: User = Depends(SignatureValidator()),
There's no toggle to disable this validation.
3. What response does an unauthenticated request receive?
Failure Scenario	HTTP Status	Response Body
Invalid JSON body	422	{"detail": "Invalid JSON payload."}
Missing secret field	401	{"detail": "Missing secret in payload."}
User ID not found	404	{"detail": "User not found."}
Wrong secret value	403	{"detail": "Invalid secret."}
Code Location: signature_validation.py:28-54
# Invalid JSON
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid JSON payload.")

# Missing secret
raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing secret in payload.")

# User not found
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.")

# Invalid secret
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid secret.")
4. Are failed authentication attempts logged with details? ❌ No
Failed authentication attempts are NOT logged. The SignatureValidator class has no logging statements - it only raises HTTPException on failure.
# signature_validation.py - NO logger import, NO logging calls
import hmac
import hashlib
from fastapi import Request, HTTPException, status, Depends
# ... no logging module imported

class SignatureValidator:
    async def __call__(self, ...):
        # All failures just raise HTTPException without logging
        if not received_secret:
            raise HTTPException(...)  # No log
        if not user:
            raise HTTPException(...)  # No log
        if not hmac.compare_digest(...):
            raise HTTPException(...)  # No log
The only relevant logging occurs after successful authentication in signal_router.py:51:
logger.info(f"Received signal for {signal.tv.symbol} ({signal.tv.action}) on {signal.tv.exchange} for user {self.user.id}")
Summary
Question	Answer
1. Signature validation implemented?	⚠️ Partial - Uses shared secret in payload, not HMAC body signature
2. security.webhook_signature_validation?	❌ Does not exist - validation is always enabled
3. Unauthenticated response?	401/403/404 with generic error messages
4. Failed attempts logged?	❌ No logging of failed authentication
Security Observations
Secret in payload - The secret is transmitted in the request body rather than in a header. This means the secret could be logged by intermediary proxies if they log request bodies.
No failed auth logging - Failed authentication attempts (potential attacks) are not logged, making it harder to detect brute-force attempts.
User enumeration - The 404 "User not found" vs 403 "Invalid secret" responses allow an attacker to enumerate valid user IDs.


Webhook to Signal Object Transformation
1. How is raw JSON transformed into an internal signal object?
The transformation happens in 3 stages:
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: Raw JSON → WebhookPayload (Pydantic)                              │
│  Location: webhooks.py:25-27                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  payload = await request.json()                                             │
│  webhook_payload = WebhookPayload(**payload)                                │
│                                                                             │
│  Nested Pydantic models:                                                    │
│  ├── tv: TradingViewData                                                    │
│  ├── strategy_info: StrategyInfo                                            │
│  ├── execution_intent: ExecutionIntent                                      │
│  └── risk: RiskInfo                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: WebhookPayload → QueuedSignal (SQLAlchemy Model)                  │
│  Location: signal_router.py:223-231 and :256-264                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  qs = QueuedSignal(                                                         │
│      user_id=self.user.id,                                                  │
│      exchange=signal.tv.exchange.lower(),      # "BINANCE" → "binance"      │
│      symbol=signal.tv.symbol,                  # "BTCUSDT" or "BTC/USDT"    │
│      timeframe=signal.tv.timeframe,            # 1, 5, 15, etc.             │
│      side=signal_side,                         # "buy"→"long", "sell"→"short"|
│      entry_price=Decimal(str(signal.tv.entry_price)),                       │
│      signal_payload=signal.model_dump(mode='json')  # Full payload stored   │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: QueuedSignal → PositionGroup + DCAOrders                          │
│  Location: position_manager.py:71-150                                       │
└─────────────────────────────────────────────────────────────────────────────┘
Key Code - signal_router.py:223-231:
qs = QueuedSignal(
    user_id=self.user.id,
    exchange=signal.tv.exchange.lower(),
    symbol=signal.tv.symbol,
    timeframe=signal.tv.timeframe,
    side=signal_side,  # Mapped from action
    entry_price=Decimal(str(signal.tv.entry_price)),
    signal_payload=signal.model_dump(mode='json')  # Stores full original payload
)
2. Are TradingView placeholders properly mapped?
Partial implementation. Here's the mapping status:
TradingView Placeholder	JSON Field	Pydantic Field	Mapped?
{{ticker}}	tv.symbol	TradingViewData.symbol	✅ Yes
{{interval}}	tv.timeframe	TradingViewData.timeframe	✅ Yes (as int)
{{exchange}}	tv.exchange	TradingViewData.exchange	✅ Yes
{{strategy.order.action}}	tv.action	TradingViewData.action	✅ Yes
{{strategy.market_position}}	tv.market_position	TradingViewData.market_position	✅ Yes
{{strategy.market_position_size}}	tv.market_position_size	TradingViewData.market_position_size	✅ Yes
{{strategy.prev_market_position}}	tv.prev_market_position	TradingViewData.prev_market_position	✅ Yes
{{strategy.prev_market_position_size}}	tv.prev_market_position_size	TradingViewData.prev_market_position_size	✅ Yes
{{strategy.order.price}}	tv.entry_price	TradingViewData.entry_price	✅ Yes
{{close}}	tv.close_price	TradingViewData.close_price	✅ Yes
{{strategy.order.contracts}}	tv.order_size	TradingViewData.order_size	✅ Yes
Placeholder validation - webhook_payloads.py:20-25:
@field_validator('exchange', 'symbol', 'action', 'market_position', 'prev_market_position')
@classmethod
def no_placeholders(cls, v: str) -> str:
    if "{{" in v or "}}" in v:
         raise ValueError("Unreplaced placeholder detected")
    return v
⚠️ Note: This validator only checks 5 string fields. Numeric fields (entry_price, close_price, etc.) would fail with a Pydantic type error if they contained unreplaced placeholders.
3. How is execution_intent.type handled differently?
Location: signal_router.py:169-319
Intent Type	Handling	Code Path
exit	Closes existing position	Lines 171-183
signal	Creates new position or pyramid	Lines 186-319
reduce	❌ NOT IMPLEMENTED	Falls through to else block
reverse	❌ NOT IMPLEMENTED	Falls through to else block
Detailed flow:
# Line 170
intent_type = signal.execution_intent.type.lower() if signal.execution_intent else "signal"

# EXIT HANDLING (lines 171-183)
if intent_type == "exit":
    # Determine target side: buy action → close long, sell action → close short
    target_side = "long" if signal.tv.action.lower() == "buy" else "short"
    
    group_to_close = next((g for g in active_groups 
        if g.symbol == signal.tv.symbol 
        and g.exchange == signal.tv.exchange 
        and g.side == target_side), None)
    
    if group_to_close:
        await pos_manager.handle_exit_signal(group_to_close.id)
        response_message = f"Exit signal executed for {signal.tv.symbol}"
    else:
        response_message = f"No active {target_side} position found for {signal.tv.symbol} to exit."

# ENTRY/PYRAMID HANDLING (lines 186-319) - covers signal, reduce, reverse
else:  # intent_type != "exit"
    # Map action to side
    raw_action = signal.tv.action.lower()
    if raw_action == "buy":
        signal_side = "long"
    elif raw_action == "sell":
        signal_side = "short"
    else:
        signal_side = raw_action  # Fallback
    
    # Check for existing position
    existing_group = next((g for g in active_groups 
        if g.symbol == signal.tv.symbol 
        and g.exchange == signal.tv.exchange 
        and g.timeframe == signal.tv.timeframe 
        and g.side == signal_side), None)
    
    if existing_group:
        # PYRAMID: Add to existing position
        if existing_group.pyramid_count < dca_config.max_pyramids - 1:
            response_message = await execute_pyramid(existing_group)
        else:
            response_message = "Max pyramids reached. Signal ignored."
    else:
        # NEW POSITION
        slot_available = await exec_pool.request_slot()
        if slot_available:
            response_message = await execute_new_position()
        else:
            response_message = await queue_signal("Pool full.")
4. Signal Parsing/Mapping Code Summary
Complete flow with key transformations:
┌─────────────────────────────────────────────────────────────────────────────┐
│  INCOMING JSON                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  {                                                                          │
│    "user_id": "uuid",                                                       │
│    "secret": "abc123",                                                      │
│    "source": "tradingview",                                                 │
│    "timestamp": "2024-01-01T00:00:00Z",                                     │
│    "tv": {                                                                  │
│      "exchange": "BINANCE",          ──┐                                    │
│      "symbol": "BTCUSDT",              │                                    │
│      "timeframe": 15,                  │  TradingView placeholders          │
│      "action": "buy",                  │                                    │
│      "market_position": "long",        │                                    │
│      "entry_price": 50000.0,           │                                    │
│      ...                             ──┘                                    │
│    },                                                                       │
│    "execution_intent": {                                                    │
│      "type": "signal",               ── Determines routing                  │
│      "side": "long",                                                        │
│      ...                                                                    │
│    },                                                                       │
│    ...                                                                      │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TRANSFORMATIONS                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. exchange: "BINANCE" → "binance"           (lowercased)                  │
│                                                                             │
│  2. action → side mapping:                                                  │
│     "buy"  → "long"                                                         │
│     "sell" → "short"                                                        │
│                                                                             │
│  3. symbol normalization (for DCA config lookup):                           │
│     "BTCUSDT" → "BTC/USDT"                                                  │
│     "ETHBTC"  → "ETH/BTC"                                                   │
│                                                                             │
│  4. entry_price: float → Decimal                                            │
│                                                                             │
│  5. Full payload preserved in signal_payload JSON column                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTERNAL SIGNAL OBJECT (QueuedSignal)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  QueuedSignal(                                                              │
│    id: UUID (auto),                                                         │
│    user_id: UUID,                                                           │
│    exchange: "binance",           # lowercased                              │
│    symbol: "BTCUSDT",             # original format kept                    │
│    timeframe: 15,                                                           │
│    side: "long",                  # mapped from action                      │
│    entry_price: Decimal("50000"), # converted to Decimal                    │
│    signal_payload: {...},         # full original JSON                      │
│    queued_at: datetime,                                                     │
│    status: QueueStatus.QUEUED,                                              │
│    priority_score: Decimal("0"),                                            │
│    is_pyramid_continuation: False,                                          │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
Summary
Question	Answer
1. JSON → Signal transformation?	3-stage: JSON → Pydantic → QueuedSignal → PositionGroup
2. TradingView placeholders mapped?	✅ All mapped, with validation on 5 string fields
3. execution_intent.type handling?	Only exit and signal implemented; reduce/reverse fall through as signal
4. Key transformations?	exchange lowercased, action→side mapping, price→Decimal, symbol normalization for config lookup
⚠️ Gap Identified
reduce and reverse intent types are accepted by the schema but not explicitly handled - they're treated identically to signal, which may not be the intended behavior.


New Position Group Creation Flow
1. Exact Steps to Create a New Position Group
Entry Point: signal_router.py:221-251 → position_manager.py:71-253
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Check Slot Availability (signal_router.py:315-317)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  slot_available = await exec_pool.request_slot()                            │
│  if slot_available:                                                         │
│      response_message = await execute_new_position()                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Create QueuedSignal Object (signal_router.py:223-231)              │
├─────────────────────────────────────────────────────────────────────────────┤
│  qs = QueuedSignal(                                                         │
│      user_id=self.user.id,                                                  │
│      exchange=signal.tv.exchange.lower(),                                   │
│      symbol=signal.tv.symbol,                                               │
│      timeframe=signal.tv.timeframe,                                         │
│      side=signal_side,                                                      │
│      entry_price=Decimal(str(signal.tv.entry_price)),                       │
│      signal_payload=signal.model_dump(mode='json')                          │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Call PositionManagerService (signal_router.py:233-240)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  new_position_group = await pos_manager.create_position_group_from_signal(  │
│      session=db_session,                                                    │
│      user_id=self.user.id,                                                  │
│      signal=qs,                                                             │
│      risk_config=risk_config,                                               │
│      dca_grid_config=dca_config,                                            │
│      total_capital_usd=total_capital                                        │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Validate User Exists (position_manager.py:82-86)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  user = await session.get(User, user_id)                                    │
│  if not user:                                                               │
│      raise UserNotFoundException(f"User {user_id} not found")               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: Initialize Exchange Connector (position_manager.py:88-106)         │
├─────────────────────────────────────────────────────────────────────────────┤
│  exchange_connector = get_exchange_connector(signal.exchange, exchange_config)│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: Fetch Precision Rules (position_manager.py:108-122)                │
├─────────────────────────────────────────────────────────────────────────────┤
│  precision_rules = await exchange_connector.get_precision_rules()           │
│  symbol_precision = precision_rules.get(signal.symbol, {})                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: Calculate DCA Grid (position_manager.py:125-139)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  dca_levels = grid_calculator.calculate_dca_levels(                         │
│      base_price=signal.entry_price,        ◄── BASE ENTRY PRICE SOURCE      │
│      dca_config=dca_grid_config,                                            │
│      side=signal.side,                                                      │
│      precision_rules=symbol_precision,                                      │
│      pyramid_index=0                                                        │
│  )                                                                          │
│  dca_levels = grid_calculator.calculate_order_quantities(...)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 8: Create PositionGroup Record (position_manager.py:145-164)          │
├─────────────────────────────────────────────────────────────────────────────┤
│  new_position_group = PositionGroup(...)                                    │
│  session.add(new_position_group)                                            │
│  await session.flush()                    ◄── FIRST DB PERSIST (gets ID)    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 9: Create Initial Pyramid (position_manager.py:166-175)               │
├─────────────────────────────────────────────────────────────────────────────┤
│  new_pyramid = Pyramid(                                                     │
│      group_id=new_position_group.id,                                        │
│      pyramid_index=0,                                                       │
│      entry_price=signal.entry_price,                                        │
│      status=PyramidStatus.PENDING,                                          │
│      dca_config=json.loads(dca_grid_config.json())                          │
│  )                                                                          │
│  session.add(new_pyramid)                                                   │
│  await session.flush()                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 10: Instantiate OrderService (position_manager.py:177-182)            │
├─────────────────────────────────────────────────────────────────────────────┤
│  order_service = OrderService(                                              │
│      session=session,                                                       │
│      user=user,                                                             │
│      exchange_connector=exchange_connector                                  │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 11: Create DCAOrder Records (position_manager.py:184-228)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  for i, level in enumerate(dca_levels):                                     │
│      dca_order = DCAOrder(                                                  │
│          group_id=new_position_group.id,                                    │
│          pyramid_id=new_pyramid.id,                                         │
│          leg_index=i,                                                       │
│          symbol=signal.symbol,                                              │
│          side=order_side,                                                   │
│          order_type="limit" or "market",                                    │
│          price=level['price'],                                              │
│          quantity=level['quantity'],                                        │
│          ...                                                                │
│      )                                                                      │
│      session.add(dca_order)                                                 │
│      if current_status == OrderStatus.PENDING:                              │
│          orders_to_submit.append(dca_order)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 12: Submit Orders to Exchange (position_manager.py:231-238)           │
├─────────────────────────────────────────────────────────────────────────────┤
│  for order in orders_to_submit:                                             │
│      await order_service.submit_order(order)                                │
│                                                                             │
│  # If submission fails:                                                     │
│  except Exception:                                                          │
│      new_position_group.status = PositionGroupStatus.FAILED                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 13: Update Pyramid Status (position_manager.py:240-243)               │
├─────────────────────────────────────────────────────────────────────────────┤
│  new_pyramid.status = PyramidStatus.SUBMITTED                               │
│  await session.flush()                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 14: Post-Creation Tasks (position_manager.py:247-251)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  await self.update_risk_timer(new_position_group.id, risk_config, session)  │
│  await self.update_position_stats(new_position_group.id, session)           │
│  await broadcast_entry_signal(new_position_group, new_pyramid, session)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 15: Final Commit (signal_router.py:241)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  await db_session.commit()                  ◄── FINAL PERSIST               │
└─────────────────────────────────────────────────────────────────────────────┘
2. Data Stored in Position Group Record
Location: position_manager.py:145-161
new_position_group = PositionGroup(
    # Identity Fields
    user_id=user_id,                              # UUID - Owner
    exchange=signal.exchange.lower(),             # "binance", "bybit"
    symbol=signal.symbol,                         # "BTCUSDT"
    timeframe=signal.timeframe,                   # 15, 60, 240 (minutes)
    side=signal.side,                             # "long" or "short"
    
    # Status
    status=PositionGroupStatus.LIVE,              # Initial status
    
    # DCA Tracking
    total_dca_legs=len(dca_levels),               # Number of DCA levels
    
    # Price Data
    base_entry_price=signal.entry_price,          # From signal
    weighted_avg_entry=signal.entry_price,        # Initially same as base
    
    # Take-Profit Config
    tp_mode=dca_grid_config.tp_mode,              # "per_leg", "aggregate", "hybrid"
    tp_aggregate_percent=dca_grid_config.tp_aggregate_percent,
    
    # Pyramid Tracking
    pyramid_count=0,                              # Starts at 0
    max_pyramids=dca_grid_config.max_pyramids,    # From config
    
    # Risk Timer (initially null)
    risk_timer_start=None,
    risk_timer_expires=None
)
Complete Field Reference from position_group.py:
Field	Type	Source	Description
id	UUID	Auto-generated	Primary key
user_id	UUID	Signal	Owner reference
exchange	String	Signal (lowercased)	"binance", "bybit"
symbol	String	Signal	"BTCUSDT"
timeframe	Integer	Signal	Minutes (15, 60, 240)
side	Enum	Signal (mapped)	"long" or "short"
status	Enum	Set to LIVE	Position lifecycle state
pyramid_count	Integer	0	Current pyramid count
max_pyramids	Integer	DCA Config	Maximum allowed pyramids
replacement_count	Integer	0	Signal replacement counter
total_dca_legs	Integer	Calculated	Total DCA levels
filled_dca_legs	Integer	0	Filled DCA count
base_entry_price	Decimal	Signal	Original entry price
weighted_avg_entry	Decimal	Signal (initially)	Weighted average entry
total_invested_usd	Decimal	0	Total capital deployed
total_filled_quantity	Decimal	0	Total position size
unrealized_pnl_usd	Decimal	0	Unrealized P&L
unrealized_pnl_percent	Decimal	0	Unrealized P&L %
realized_pnl_usd	Decimal	0	Realized P&L
tp_mode	Enum	DCA Config	TP strategy
tp_aggregate_percent	Decimal	DCA Config	Aggregate TP %
risk_timer_start	DateTime	null	Risk timer start
risk_timer_expires	DateTime	null	Risk timer expiry
risk_eligible	Boolean	false	Eligible for risk action
risk_blocked	Boolean	false	Blocked from risk
risk_skip_once	Boolean	false	Skip next risk check
created_at	DateTime	Auto	Creation timestamp
updated_at	DateTime	Auto	Last update timestamp
closed_at	DateTime	null	Close timestamp
3. How "Base Entry Price" is Determined and Stored
Source: The entry_price from the incoming TradingView signal (signal.tv.entry_price) Flow:
TradingView Webhook JSON
    │
    ▼
tv.entry_price: 50000.0              (float in JSON)
    │
    ▼
WebhookPayload.tv.entry_price        (Pydantic: float)
    │
    ▼
QueuedSignal.entry_price             (Decimal conversion)
    │  Decimal(str(signal.tv.entry_price))
    ▼
PositionGroup.base_entry_price       (Numeric(20,10) in DB)
Code - position_manager.py:153-154:
new_position_group = PositionGroup(
    ...
    base_entry_price=signal.entry_price,      # From QueuedSignal
    weighted_avg_entry=signal.entry_price,    # Initially same
    ...
)
Usage: The base_entry_price is used as the anchor for calculating DCA grid levels:
# position_manager.py:126-127
dca_levels = self.grid_calculator_service.calculate_dca_levels(
    base_price=signal.entry_price,   # ◄── Used here
    ...
)
4. Is Position Group Immediately Persisted?
Yes, but in stages:
Stage	Method	What Happens
1	session.add() + flush()	PositionGroup gets ID, written to transaction buffer
2	session.add() + flush()	Pyramid gets ID, linked to PositionGroup
3	session.add() (loop)	DCAOrders added to session
4	Order submission	Orders sent to exchange
5	session.flush()	Final pyramid status update
6	session.commit()	FINAL PERSIST - All changes written to DB
Key code:
# position_manager.py:162-163
session.add(new_position_group)
await session.flush()  # ◄── Gets ID, but NOT committed yet

# position_manager.py:174-175
session.add(new_pyramid)
await session.flush()  # ◄── Pyramid gets ID

# position_manager.py:219
session.add(dca_order)  # ◄── Just added, no flush

# position_manager.py:242
await session.flush()   # ◄── Final flush

# signal_router.py:241 (back in caller)
await db_session.commit()  # ◄── ACTUAL DATABASE COMMIT
Important: If order submission fails, the status is set to FAILED but the record is still committed:
# position_manager.py:235-238
except Exception as e:
    logger.error(f"Failed to submit orders...")
    new_position_group.status = PositionGroupStatus.FAILED
    pass  # Continues, commit still happens
5. Position Group Creation Code
Complete code - position_manager.py:145-161:
# 4. Create PositionGroup
new_position_group = PositionGroup(
    user_id=user_id,
    exchange=signal.exchange.lower(),
    symbol=signal.symbol,
    timeframe=signal.timeframe,
    side=signal.side,
    status=PositionGroupStatus.LIVE,
    total_dca_legs=len(dca_levels),
    base_entry_price=signal.entry_price,
    weighted_avg_entry=signal.entry_price,
    tp_mode=dca_grid_config.tp_mode,
    tp_aggregate_percent=dca_grid_config.tp_aggregate_percent,
    pyramid_count=0,
    max_pyramids=dca_grid_config.max_pyramids,
    risk_timer_start=None,
    risk_timer_expires=None
)
session.add(new_position_group)
await session.flush()
logger.debug(f"Created PG {new_position_group.id}")
Summary
Question	Answer
1. Steps to create?	15 steps from slot check → final commit
2. Data stored?	25+ fields covering identity, status, pricing, DCA, risk
3. Base entry price?	signal.tv.entry_price → converted to Decimal → stored
4. Immediately persisted?	Flushed for ID, but committed only after order submission
5. Creation code?	Lines 145-161 in position_manager.py

Position Group Identity & Lookup Analysis
1. Is a Position Group uniquely identified by pair + timeframe?
Logical identity: Yes, but with additional fields. Database constraint: No. The logical identity for matching is a 5-field composite:
user_id
symbol (pair)
exchange
timeframe
side
Code - signal_router.py:196:
existing_group = next((g for g in active_groups 
    if g.symbol == signal.tv.symbol 
    and g.exchange == signal.tv.exchange 
    and g.timeframe == signal.tv.timeframe 
    and g.side == signal_side), None)
However, there is NO database unique constraint on position_groups table:
# alembic migration (lines 59-91) - NO UniqueConstraint for position_groups
op.create_table('position_groups',
    sa.Column('id', GUID(), nullable=False),
    sa.Column('user_id', GUID(), nullable=False),
    sa.Column('exchange', sa.String(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timeframe', sa.Integer(), nullable=False),
    sa.Column('side', sa.Enum(...), nullable=False),
    ...
    sa.PrimaryKeyConstraint('id')  # ◄── Only PK, no unique constraint!
)
Contrast: dca_configurations DOES have a unique constraint:
sa.UniqueConstraint('user_id', 'pair', 'timeframe', 'exchange', 
                    name='uix_user_pair_timeframe_exchange')
2. What happens if two signals arrive simultaneously for BTCUSDT 15m?
⚠️ Race condition exists - both signals could create separate Position Groups. Timeline of potential race condition:
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIME        SIGNAL A                          SIGNAL B                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  T+0ms       Webhook received                  Webhook received             │
│              │                                 │                            │
│  T+5ms       SignatureValidator ✓              SignatureValidator ✓         │
│              │                                 │                            │
│  T+10ms      get_active_position_groups()      get_active_position_groups() │
│              Returns: []                       Returns: []                  │
│              │                                 │                            │
│  T+15ms      existing_group = None             existing_group = None        │
│              │                                 │                            │
│  T+20ms      request_slot() → True             request_slot() → True        │
│              │                                 │                            │
│  T+25ms      execute_new_position()            execute_new_position()       │
│              │                                 │                            │
│  T+30ms      PositionGroup A created           PositionGroup B created      │
│              │                                 │                            │
│  T+50ms      commit()                          commit()                     │
│              │                                 │                            │
│  RESULT      TWO Position Groups for BTCUSDT 15m long!                      │
└─────────────────────────────────────────────────────────────────────────────┘
Why this happens:
No database unique constraint on (user_id, symbol, exchange, timeframe, side)
No row-level locking when checking for existing groups
In-memory filtering using Python's next() on a list that was fetched without locks
3. How are race conditions prevented?
⚠️ They are NOT effectively prevented. The codebase has for_update support but it's not used for the critical lookup: Available but unused:
# position_group.py:49-62
async def get_active_position_groups_for_user(
    self, user_id: uuid.UUID, 
    for_update: bool = False  # ◄── Parameter exists
) -> list[PositionGroup]:
    query = select(self.model).where(...)
    if for_update:
        query = query.with_for_update()  # ◄── Would add SELECT ... FOR UPDATE
    ...
Actual usage - signal_router.py:166:
# Called WITHOUT for_update=True
active_groups = await pg_repo.get_active_position_groups_for_user(self.user.id)
#                                                                 ↑ No for_update
ExecutionPoolManager does try to use locking, but incorrectly:
# execution_pool_manager.py:51
current_size = await self.get_current_pool_size(for_update=True)
But get_current_pool_size explicitly ignores it:
# execution_pool_manager.py:36-37
# Always call with for_update=False for aggregate functions like count
count = await repo.count_by_status(active_statuses, for_update=False)
4. How the System Looks Up Existing Position Groups
Step 1: Fetch all active groups for user Location: signal_router.py:166
active_groups = await pg_repo.get_active_position_groups_for_user(self.user.id)
Step 2: Repository query Location: position_group.py:49-62
async def get_active_position_groups_for_user(
    self, user_id: uuid.UUID, 
    for_update: bool = False
) -> list[PositionGroup]:
    query = select(self.model).where(
        self.model.user_id == user_id,
        self.model.status.in_(["live", "partially_filled", "active", "closing"])
    ).options(
        selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)
    )
    if for_update:
        query = query.with_for_update()
    result = await self.session.execute(query)
    return result.scalars().all()
Step 3: In-memory filtering with Python For Entry/Pyramid signals - signal_router.py:196:
existing_group = next((g for g in active_groups 
    if g.symbol == signal.tv.symbol           # Match symbol
    and g.exchange == signal.tv.exchange       # Match exchange
    and g.timeframe == signal.tv.timeframe     # Match timeframe
    and g.side == signal_side), None)          # Match side (long/short)
For Exit signals - signal_router.py:176:
group_to_close = next((g for g in active_groups 
    if g.symbol == signal.tv.symbol 
    and g.exchange == signal.tv.exchange 
    and g.side == target_side), None)  # ◄── Note: No timeframe check for exits!
Step 4: Decision based on match
if existing_group:
    # PYRAMID: Add to existing position
    if existing_group.pyramid_count < dca_config.max_pyramids - 1:
        response_message = await execute_pyramid(existing_group)
    else:
        response_message = "Max pyramids reached. Signal ignored."
else:
    # NEW POSITION: Create new Position Group
    slot_available = await exec_pool.request_slot()
    if slot_available:
        response_message = await execute_new_position()
    else:
        response_message = await queue_signal("Pool full.")
Summary Table
Question	Answer
1. Unique by pair+timeframe?	Logical: Yes (5-field composite). DB: No constraint
2. Simultaneous signals?	Race condition - both could create separate groups
3. Race condition prevention?	Not implemented - for_update available but unused
4. Lookup mechanism?	Fetch all active → Python in-memory filter by 4/5 fields
Identified Issues
Issue	Severity	Description
Missing unique constraint	🔴 High	No DB constraint on (user, symbol, exchange, timeframe, side)
No row locking	🔴 High	get_active_position_groups_for_user() called without for_update=True
In-memory filtering	🟡 Medium	Filtering in Python instead of SQL WHERE clause
Exit ignores timeframe	🟡 Medium	Exit signals match without timeframe, could close wrong position
Recommended Fixes
Add unique constraint (active positions only - partial index):
CREATE UNIQUE INDEX uix_active_position 
ON position_groups (user_id, symbol, exchange, timeframe, side) 
WHERE status NOT IN ('closed', 'failed');
Use row-level locking:
active_groups = await pg_repo.get_active_position_groups_for_user(
    self.user.id, 
    for_update=True  # ◄── Add this
)
Move filtering to SQL:
async def get_matching_position(self, user_id, symbol, exchange, timeframe, side):
    query = select(self.model).where(
        self.model.user_id == user_id,
        self.model.symbol == symbol,
        self.model.exchange == exchange,
        self.model.timeframe == timeframe,
        self.model.side == side,
        self.model.status.in_(["live", "partially_filled", "active"])
    ).with_for_update()
    ...

Position Group State Machine Analysis
1. Are All States Implemented?
Yes, all 7 states are defined: Location: position_group.py:26-33
class PositionGroupStatus(str, Enum):
    WAITING = "waiting"           # ⚠️ Defined but NEVER USED
    LIVE = "live"                 # ✅ Used - Initial state on creation
    PARTIALLY_FILLED = "partially_filled"  # ✅ Used
    ACTIVE = "active"             # ✅ Used
    CLOSING = "closing"           # ✅ Used
    CLOSED = "closed"             # ✅ Used
    FAILED = "failed"             # ✅ Used
State	Defined	Used in Transitions	Notes
WAITING	✅	❌ Never used	Default in model, but creation sets LIVE
LIVE	✅	✅	Set on creation
PARTIALLY_FILLED	✅	✅	When some DCA orders filled
ACTIVE	✅	✅	When all DCA orders filled
CLOSING	✅	✅	During close operation
CLOSED	✅	✅	Position fully closed
FAILED	✅	✅	Order submission failed
2. State Transition Triggers
┌─────────────────────────────────────────────────────────────────────────────┐
│                     POSITION GROUP STATE MACHINE                            │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────┐
                              │ WAITING  │ (Defined but never used)
                              └──────────┘
                                    
     ┌─────────────────────────────────────────────────────────────┐
     │                                                             │
     │  Signal Received + Slot Available                          │
     │  create_position_group_from_signal()                        │
     │  position_manager.py:151                                    │
     │                                                             │
     ▼                                                             │
┌──────────┐                                                       │
│   LIVE   │◄──────────────────────────────────────────────────────┘
└──────────┘
     │
     │  Order submission fails
     │  position_manager.py:237
     │
     ├─────────────────────────────────────────┐
     │                                         │
     │                                         ▼
     │                                    ┌──────────┐
     │                                    │  FAILED  │ (Terminal)
     │                                    └──────────┘
     │
     │  First DCA order fills (filled_dca_legs > 0)
     │  update_position_stats() → position_manager.py:687
     │
     ▼
┌───────────────────┐
│ PARTIALLY_FILLED  │◄─────────────────────────────────────────────┐
└───────────────────┘                                              │
     │                                                             │
     │  All DCA orders filled                                      │
     │  (filled_entry_legs >= total_dca_legs)                      │
     │  position_manager.py:683-684                                │
     │                                                             │
     ▼                                                             │
┌──────────┐                                                       │
│  ACTIVE  │                                                       │
└──────────┘                                                       │
     │                                                             │
     ├──── Aggregate TP triggered ────────────────────────┐        │
     │     position_manager.py:737                        │        │
     │                                                    ▼        │
     │                                              ┌─────────┐    │
     │                                              │ CLOSING │    │
     │                                              └─────────┘    │
     │                                                    │        │
     │                                                    │        │
     ├──── Exit signal received ──────────────────────────┤        │
     │     handle_exit_signal()                           │        │
     │     position_manager.py:403                        │        │
     │                                                    │        │
     ├──── Force close API ───────────────────────────────┤        │
     │     mark_position_as_closing()                     │        │
     │     order_management.py:322                        │        │
     │                                                    │        │
     ├──── Auto-close (qty <= 0) ─────────────────────────┤        │
     │     position_manager.py:690-692                    │        │
     │                                                    │        │
     │                                                    ▼        │
     │                                              ┌──────────┐   │
     └──────────────────────────────────────────────│  CLOSED  │   │
                                                    └──────────┘   │
                                                         ▲         │
                                                         │         │
        All positions can be closed via exit signal ─────┴─────────┘
3. Can States Go Backwards?
⚠️ Yes, backwards transitions are possible but likely unintended. Key code - position_manager.py:682-687:
# Status Transition Logic
if position_group.status in [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED]:
    if filled_entry_legs >= position_group.total_dca_legs:
        position_group.status = PositionGroupStatus.ACTIVE
        logger.info(f"PositionGroup {group_id} transitioned to ACTIVE")
    elif filled_entry_legs > 0:
        position_group.status = PositionGroupStatus.PARTIALLY_FILLED
Scenario for backward transition:
Position is ACTIVE (all 5 DCA legs filled)
Pyramid added → total_dca_legs increases from 5 to 10
update_position_stats() is called
Check: status in [LIVE, PARTIALLY_FILLED] → False (status is ACTIVE)
No backward transition occurs due to the guard clause
However, there's no explicit guard preventing manual/accidental backward transitions via direct assignment. Problematic patterns that DON'T exist but could be dangerous:
# This pattern is NOT in the code, but would cause issues if added:
position_group.status = PositionGroupStatus.PARTIALLY_FILLED  # Backward!
Analysis of guard clauses:
Transition	Guard Present?
LIVE → PARTIALLY_FILLED	✅ if status in [LIVE, PARTIALLY_FILLED]
PARTIALLY_FILLED → ACTIVE	✅ Same guard
ACTIVE → CLOSING	✅ if status not in [CLOSING, CLOSED]
* → CLOSED	✅ if status not in [CLOSED, CLOSING]
CLOSED → anything	✅ if status == CLOSED: raise error
4. Where is State Tracked and How is it Persisted?
Storage Location:
# position_group.py:52-57
status = Column(
    SQLAlchemyEnum(
        PositionGroupStatus, 
        name="group_status_enum", 
        values_callable=lambda x: [e.value for e in x]
    ),
    nullable=False,
    default=PositionGroupStatus.WAITING.value,
)
Persistence Methods:
Method	Location	Description
session.add() + flush()	position_manager.py:162-163	Initial creation
position_group_repo.update()	position_manager.py:693	After stats update
session.commit()	signal_router.py:241	Final persistence
Update flow:
# 1. Modify status
position_group.status = PositionGroupStatus.ACTIVE

# 2. Update via repository
await position_group_repo.update(position_group)

# 3. Repository implementation (base.py:35-39)
async def update(self, instance: ModelType) -> ModelType:
    self.session.add(instance)
    await self.session.flush()
    await self.session.refresh(instance)
    return instance

# 4. Commit by caller
await session.commit()
5. State Transition Logic Code
Creation → LIVE - position_manager.py:145-163:
new_position_group = PositionGroup(
    ...
    status=PositionGroupStatus.LIVE,  # ◄── Explicitly set to LIVE, not WAITING
    ...
)
session.add(new_position_group)
await session.flush()
LIVE → FAILED - position_manager.py:235-238:
except Exception as e:
    logger.error(f"Failed to submit orders for PositionGroup {new_position_group.id}: {e}")
    new_position_group.status = PositionGroupStatus.FAILED
    pass  # Continues to commit
LIVE/PARTIALLY_FILLED → ACTIVE - position_manager.py:682-685:
if position_group.status in [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED]:
    if filled_entry_legs >= position_group.total_dca_legs:
        position_group.status = PositionGroupStatus.ACTIVE
        logger.info(f"PositionGroup {group_id} transitioned to ACTIVE")
LIVE → PARTIALLY_FILLED - position_manager.py:686-687:
    elif filled_entry_legs > 0:
        position_group.status = PositionGroupStatus.PARTIALLY_FILLED
Any → CLOSING - order_management.py:319-323:
if position_group.status == PositionGroupStatus.CLOSED.value:
    raise APIError(f"PositionGroup {group_id} is already closed.", status_code=400)

position_group.status = PositionGroupStatus.CLOSING.value
await self.position_group_repository.update(position_group)
ACTIVE → CLOSING (Aggregate TP) - position_manager.py:735-738:
if should_execute_tp:
    ...
    position_group.status = PositionGroupStatus.CLOSING
    await position_group_repo.update(position_group)
Any → CLOSED (Exit Signal) - position_manager.py:403-420:
# If successful, update position status and PnL
position_group.status = PositionGroupStatus.CLOSED

current_price = Decimal(str(await exchange_connector.get_current_price(position_group.symbol)))
...
position_group.realized_pnl_usd = realized_pnl
position_group.unrealized_pnl_usd = Decimal("0")
position_group.closed_at = datetime.utcnow()

await position_group_repo.update(position_group)
Auto-close (qty = 0) - position_manager.py:690-692:
if current_qty <= 0 and len(filled_orders) > 0 and position_group.status not in [PositionGroupStatus.CLOSED, PositionGroupStatus.CLOSING]:
    position_group.status = PositionGroupStatus.CLOSED
    position_group.closed_at = datetime.utcnow()
Summary
Question	Answer
1. All states implemented?	7 defined, 6 used (WAITING is dead code)
2. Transition triggers?	Order fills, exit signals, TP triggers, failures
3. Backward transitions?	Protected by guards, but not strictly enforced
4. State storage?	SQLAlchemy Enum column, persisted via repository
5. Transition logic?	Scattered across position_manager.py and order_management.py
Issues Identified
Issue	Severity	Description
WAITING unused	🟡 Low	Defined as default but never assigned
No state machine abstraction	🟡 Medium	Transitions scattered, no centralized validation
Missing CLOSING in some paths	🟡 Medium	Exit signal goes directly to CLOSED, skipping CLOSING
No transition logging	🟡 Medium	Only ACTIVE transition is logged
State Transition Matrix
From \ To	WAITING	LIVE	PARTIALLY_FILLED	ACTIVE	CLOSING	CLOSED	FAILED
(new)	-	✅	-	-	-	-	-
WAITING	-	❌	❌	❌	❌	❌	❌
LIVE	-	-	✅	✅	✅	✅	✅
PARTIALLY_FILLED	-	-	-	✅	✅	✅	-
ACTIVE	-	-	-	-	✅	✅	-
CLOSING	-	-	-	-	-	✅	-
CLOSED	-	-	-	-	-	-	-
FAILED	-	-	-	-	-	-	-

Pyramid Detection and Handling Analysis
1. How does the system detect this is a pyramid (not a new position)?
Detection occurs in signal_router.py:196 via in-memory filtering:
existing_group = next((g for g in active_groups 
    if g.symbol == signal.tv.symbol 
    and g.exchange == signal.tv.exchange 
    and g.timeframe == signal.tv.timeframe 
    and g.side == signal_side), None)
Detection criteria: Matches on symbol + exchange + timeframe + side If existing_group is found → treated as pyramid continuation
If existing_group is None → treated as new position
2. Is this pyramid added without consuming a pool slot?
It depends on the configuration. There's a configurable bypass rule. From signal_router.py:289-311:
if existing_group:
    # Pyramid Logic Check
    if existing_group.pyramid_count < dca_config.max_pyramids - 1:
        # Check Priority Rules for Bypass
        priority_rules = risk_config.priority_rules
        bypass_enabled = priority_rules.priority_rules_enabled.get("same_pair_timeframe", False)
        
        if bypass_enabled:
            logger.info(f"Pyramid bypass rule ENABLED. Granting implicit slot")
            slot_available = True
        else:
            # Rule DISABLED: Must compete for a standard slot
            logger.info(f"Pyramid bypass rule DISABLED. Requesting standard slot")
            slot_available = await exec_pool.request_slot()
Two modes:
same_pair_timeframe = True: Pyramids bypass the pool entirely (no slot consumed)
same_pair_timeframe = False: Pyramids compete for a slot like new positions
The ExecutionPoolManager.request_slot() has an is_pyramid_continuation parameter that grants automatic slots, but it's not used in signal_router.py:
# execution_pool_manager.py:41-49
async def request_slot(self, is_pyramid_continuation: bool = False, ...):
    if is_pyramid_continuation:
        logger.info("ExecutionPoolManager: Granting slot for pyramid continuation")
        return True  # Always grant
3. What is the maximum number of pyramids allowed?
Default: 5 pyramids (configurable per DCA configuration) From grid_config.py:31:
max_pyramids: int = Field(5, description="Maximum number of pyramids allowed")
Stored on each PositionGroup at creation from position_manager.py:158:
max_pyramids=dca_grid_config.max_pyramids
4. What happens if a 6th pyramid signal arrives?
⚠️ BUG FOUND: The check uses < max_pyramids - 1 instead of < max_pyramids From signal_router.py:291:
if existing_group.pyramid_count < dca_config.max_pyramids - 1:
    # Allow pyramid
else:
    response_message = "Max pyramids reached. Signal ignored."
With max_pyramids = 5:
pyramid_count = 0 → allows (index 0 is initial entry)
pyramid_count = 1 → allows
pyramid_count = 2 → allows
pyramid_count = 3 → allows
pyramid_count = 4 → BLOCKED (4 < 5-1 = 4 is FALSE)
Result: Only 4 additional pyramids allowed (5 total entries including initial), but the math is off by one. The signal is silently ignored with return message "Max pyramids reached. Signal ignored." - no error logged, no queue entry.
5. Pyramid Handling Code Flow
Step 1: Detection in signal_router.py:
existing_group = next((g for g in active_groups if ...), None)
Step 2: Check capacity & bypass rules:
if existing_group.pyramid_count < dca_config.max_pyramids - 1:
    if bypass_enabled:
        slot_available = True
    else:
        slot_available = await exec_pool.request_slot()
Step 3: Execute pyramid via execute_pyramid() helper:
async def execute_pyramid(group):
    qs = QueuedSignal(...)  # Create signal object
    await pos_manager.handle_pyramid_continuation(...)
    await db_session.commit()
Step 4: Core pyramid logic in position_manager.py:255-355:
async def handle_pyramid_continuation(...):
    # 1. Calculate next pyramid index
    next_pyramid_index = existing_position_group.pyramid_count + 1
    
    # 2. Calculate DCA levels for this pyramid
    dca_levels = self.grid_calculator_service.calculate_dca_levels(
        pyramid_index=next_pyramid_index
    )
    
    # 3. Update PositionGroup stats
    existing_position_group.pyramid_count += 1
    existing_position_group.replacement_count += 1
    existing_position_group.total_dca_legs += len(dca_levels)
    
    # 4. Create Pyramid record
    new_pyramid = Pyramid(
        group_id=existing_position_group.id,
        pyramid_index=existing_position_group.pyramid_count,
        entry_price=signal.entry_price,
        status=PyramidStatus.PENDING,
    )
    
    # 5. Create DCAOrder objects linked to pyramid
    for level in dca_levels:
        dca_order = DCAOrder(
            group_id=existing_position_group.id,
            pyramid_id=new_pyramid.id,
            ...
        )
        await order_service.submit_order(dca_order)
Summary Table
Aspect	Behavior
Detection	In-memory match on symbol+exchange+timeframe+side
Pool slot	Bypasses if same_pair_timeframe=True, else competes
Max pyramids	Default 5 (configurable)
6th signal	Silently ignored with message
Tracking	Separate Pyramid model with index 0-4
Pyramid states	PENDING → SUBMITTED → FILLED
Issues Identified
Off-by-one bug: Check uses < max_pyramids - 1 which blocks the 5th pyramid when max_pyramids=5
Silent rejection: Max pyramid exceeded signals are not logged at warning/error level
No queue option: Over-limit pyramids are ignored, not queued for later
Inconsistent bypass: is_pyramid_continuation parameter exists in ExecutionPoolManager but isn't used from signal_router.py

Pyramid Count Tracking Analysis
1. Where is the pyramid counter stored?
Stored in the position_groups table as an integer column. From position_group.py:59-62:
# Pyramid tracking
pyramid_count = Column(Integer, default=0)
max_pyramids = Column(Integer, default=5)
replacement_count = Column(Integer, default=0)
Column	Purpose
pyramid_count	Current number of pyramids added (starts at 0)
max_pyramids	Maximum allowed (from DCA config, default 5)
replacement_count	Total pyramids ever added (includes replacements)
Note: Initial entry is pyramid index 0, so pyramid_count=0 means only the initial entry exists.
2. Is pyramid count incremented atomically?
No, it is NOT atomic. The increment uses standard Python in-memory operation. From position_manager.py:294:
# 4. Update PositionGroup Stats
existing_position_group.pyramid_count += 1
existing_position_group.replacement_count += 1
existing_position_group.total_dca_legs += len(dca_levels)
Race condition vulnerability:
No SELECT ... FOR UPDATE when fetching the group
No SQL-level UPDATE ... SET pyramid_count = pyramid_count + 1
Two concurrent signals could both read pyramid_count=3, both increment to 4, resulting in lost update
Safe atomic pattern would be:
# NOT IMPLEMENTED - just showing what atomic would look like
await session.execute(
    update(PositionGroup)
    .where(PositionGroup.id == group_id)
    .values(pyramid_count=PositionGroup.pyramid_count + 1)
)
3. How to query "how many pyramids does BTCUSDT 1h have"?
No direct repository method exists. You must query manually. SQL Query:
SELECT pyramid_count, max_pyramids 
FROM position_groups 
WHERE symbol = 'BTCUSDT' 
  AND timeframe = 60  -- 1h = 60 minutes
  AND status IN ('live', 'partially_filled', 'active', 'closing');
Python via existing repository (requires session):
from app.repositories.position_group import PositionGroupRepository

repo = PositionGroupRepository(session)
active_groups = await repo.get_active_position_groups_for_user(user_id)

# Filter in-memory (no dedicated method)
btcusdt_1h = next(
    (g for g in active_groups 
     if g.symbol == 'BTCUSDT' and g.timeframe == 60),
    None
)

if btcusdt_1h:
    print(f"Pyramids: {btcusdt_1h.pyramid_count} / {btcusdt_1h.max_pyramids}")
Alternative - count actual Pyramid records:
from sqlalchemy import select, func
from app.models.pyramid import Pyramid

result = await session.execute(
    select(func.count(Pyramid.id))
    .where(Pyramid.group_id == position_group.id)
)
actual_pyramid_count = result.scalar()
4. Does pyramid count affect Risk Engine activation?
Yes, via two mechanisms:
Mechanism A: Timer Start Condition
From position_manager.py:512:
if risk_config.timer_start_condition == "after_5_pyramids" and position_group.pyramid_count >= 5:
    timer_started = True
If timer_start_condition = "after_5_pyramids", the risk timer only starts when pyramid_count >= 5.
Mechanism B: Eligibility Check (require_full_pyramids)
From risk_engine.py:44-46:
if not all([
    pg.status == PositionGroupStatus.ACTIVE.value,
    pg.pyramid_count >= pg.max_pyramids if config.require_full_pyramids else True,
    pg.risk_timer_expires and pg.risk_timer_expires <= datetime.utcnow(),
    pg.unrealized_pnl_percent <= config.loss_threshold_percent,
]):
    # Position not eligible for risk action
Risk Engine eligibility criteria:
Condition	Default	Effect
require_full_pyramids	True	Position must have pyramid_count >= max_pyramids
timer_start_condition	"after_all_dca_filled"	Options: after_5_pyramids, after_all_dca_submitted, after_all_dca_filled
Default behavior: require_full_pyramids=True means a position with only 3 of 5 pyramids is excluded from risk engine actions (won't be closed as loser, won't be combined).
5. Pyramid Counting Logic
Initial Entry (pyramid_count = 0)
From position_manager.py:157:
new_position_group = PositionGroup(
    ...
    pyramid_count=0,  # Starts at 0
    max_pyramids=dca_grid_config.max_pyramids,
)
Initial Pyramid record created with index 0:
new_pyramid = Pyramid(
    group_id=new_position_group.id,
    pyramid_index=0,  # First entry
    ...
)
Pyramid Continuation (incrementing)
From position_manager.py:279-306:
# Calculate next index BEFORE incrementing
next_pyramid_index = existing_position_group.pyramid_count + 1

# Calculate DCA levels for this pyramid index
dca_levels = self.grid_calculator_service.calculate_dca_levels(
    pyramid_index=next_pyramid_index
)

# INCREMENT the counter
existing_position_group.pyramid_count += 1
existing_position_group.replacement_count += 1
existing_position_group.total_dca_legs += len(dca_levels)

# Create Pyramid record with the NEW count
new_pyramid = Pyramid(
    group_id=existing_position_group.id,
    pyramid_index=existing_position_group.pyramid_count,  # Now equals next_pyramid_index
    entry_price=signal.entry_price,
    status=PyramidStatus.PENDING,
)
Limit Check (before allowing pyramid)
From signal_router.py:291:
if existing_group.pyramid_count < dca_config.max_pyramids - 1:
    # Allow pyramid
else:
    response_message = "Max pyramids reached. Signal ignored."
Summary: Pyramid Count Flow
Signal arrives for BTCUSDT 1h (existing position)
         │
         ▼
┌─────────────────────────────────────┐
│ Lookup existing_group               │
│ (in-memory filter, no row lock)     │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Check: pyramid_count < max - 1 ?    │
│ (BUG: should be < max)              │
└─────────────────────────────────────┘
         │
    ┌────┴────┐
    │ Yes     │ No
    ▼         ▼
┌───────┐  "Max pyramids reached"
│Execute│   (signal ignored)
└───────┘
    │
    ▼
┌─────────────────────────────────────┐
│ handle_pyramid_continuation()       │
│                                     │
│ 1. next_index = pyramid_count + 1   │
│ 2. pyramid_count += 1  (NOT ATOMIC) │
│ 3. Create Pyramid(index=next_index) │
│ 4. Create DCA orders                │
│ 5. Commit                           │
└─────────────────────────────────────┘
Issues Identified
Issue	Location	Impact
Non-atomic increment	position_manager.py:294	Race condition can skip/duplicate pyramids
Off-by-one in limit check	signal_router.py:291	Only allows max_pyramids - 1 additions
No query method	position_group.py	Must filter in-memory to find specific pair/timeframe
Dual counting systems	pyramid_count vs actual Pyramid records	Can diverge if errors occur

Pyramid DCA Order Generation Analysis
1. Does each pyramid generate its own set of DCA orders?
Yes. Each pyramid creates a completely independent set of DCA orders. From position_manager.py:321-342:
# 7. Create DCAOrder objects
orders_to_submit = []
order_side = "buy" if signal.side == "long" else "sell"

for i, level in enumerate(dca_levels):
    dca_order = DCAOrder(
        group_id=existing_position_group.id,   # Links to PositionGroup
        pyramid_id=new_pyramid.id,              # Links to THIS Pyramid
        leg_index=i,
        symbol=signal.symbol,
        side=order_side,
        order_type="limit",
        price=level['price'],
        quantity=level['quantity'],
        ...
    )
    session.add(dca_order)
    orders_to_submit.append(dca_order)
Data model relationships:
PositionGroup (1)
    │
    ├── Pyramid 0 (initial)
    │       └── DCAOrder 0, 1, 2, 3 (leg_index)
    │
    ├── Pyramid 1
    │       └── DCAOrder 0, 1, 2, 3
    │
    └── Pyramid 2
            └── DCAOrder 0, 1, 2, 3
From dca_order.py:46-47:
group_id = Column(GUID, ForeignKey("position_groups.id"), nullable=False)
pyramid_id = Column(GUID, ForeignKey("pyramids.id"), nullable=False)
2. Are DCA gaps calculated from the pyramid's entry price?
Yes. Each pyramid uses its own signal entry price as the base, NOT the original position's base_entry_price. From position_manager.py:280-286:
dca_levels = self.grid_calculator_service.calculate_dca_levels(
    base_price=signal.entry_price,  # <-- NEW signal's entry price
    dca_config=dca_grid_config,
    side=signal.side,
    precision_rules=symbol_precision,
    pyramid_index=next_pyramid_index
)
And in grid_calculator.py:64-69:
# Calculate DCA entry price from BASE_PRICE (the pyramid's entry)
if side == "long":
    dca_price = base_price * (Decimal("1") + gap_percent / Decimal("100"))
else:
    dca_price = base_price * (Decimal("1") - gap_percent / Decimal("100"))
Example:
Position Group for BTCUSDT Long:

Pyramid 0 (initial):
  - Signal entry: $100,000
  - DCA Leg 0: $100,000 × (1 + 0%) = $100,000
  - DCA Leg 1: $100,000 × (1 - 2%) = $98,000
  - DCA Leg 2: $100,000 × (1 - 4%) = $96,000

Pyramid 1 (added later):
  - Signal entry: $95,000  ← NEW base price
  - DCA Leg 0: $95,000 × (1 + 0%) = $95,000
  - DCA Leg 1: $95,000 × (1 - 2%) = $93,100
  - DCA Leg 2: $95,000 × (1 - 4%) = $91,200
3. How are multiple DCA sets managed together?
Via group_id foreign key - all orders share the same PositionGroup, queried together.
Query all orders for a position group:
From dca_order.py:61-67:
async def get_all_orders_by_group_id(self, group_id: str) -> List[DCAOrder]:
    result = await self.session.execute(
        select(self.model).where(
            self.model.group_id == group_id  # Gets ALL pyramids' orders
        )
    )
    return result.scalars().all()
Eager loading with pyramids:
From position_group.py:29-35:
query = (
    select(self.model)
    .where(self.model.id == group_id)
    .options(
        selectinload(self.model.dca_orders),  # All DCA orders
        selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)  # Pyramids with their orders
    )
)
Stats calculation aggregates across all pyramids:
From position_manager.py:553-559:
all_orders = list(position_group.dca_orders)  # ALL orders from ALL pyramids

# Group by pyramid for status updates
pyramid_orders = {}
for order in all_orders:
    if order.pyramid_id:
        pyramid_orders.setdefault(order.pyramid_id, []).append(order)
Aggregation example:
# Total filled quantity across ALL pyramids
total_filled_quantity = sum(
    order.filled_quantity for order in all_orders 
    if order.status == OrderStatus.FILLED
)

# Weighted average entry across ALL filled orders
weighted_avg_entry = sum(qty * price) / sum(qty)
4. DCA Generation Code for Pyramids
Step 1: Get pyramid-specific DCA levels config
From grid_config.py:57-75:
def get_levels_for_pyramid(self, pyramid_index: int) -> List[DCALevelConfig]:
    """
    Returns specific levels for a pyramid index,
    or falls back to default 'levels' if no specific config.
    
    - pyramid_count = 0 → Initial Entry (uses default levels)
    - pyramid_count = 1 → First Pyramid (look for key "1")
    """
    key = str(pyramid_index)
    if key in self.pyramid_specific_levels and self.pyramid_specific_levels[key]:
        return self.pyramid_specific_levels[key]
    return self.levels  # Fallback to default
Step 2: Calculate DCA price levels
From grid_calculator.py:29-88:
@staticmethod
def calculate_dca_levels(
    base_price: Decimal,          # Pyramid's signal entry price
    dca_config: DCAGridConfig,
    side: Literal["long", "short"],
    precision_rules: Dict,
    pyramid_index: int = 0        # Which pyramid (0 = initial)
) -> List[Dict]:
    
    tick_size = Decimal(str(precision_rules["tick_size"]))
    dca_levels = []
    
    # Get levels config for THIS pyramid
    levels_config = dca_config.get_levels_for_pyramid(pyramid_index)
    
    for idx, layer in enumerate(levels_config):
        gap_percent = layer.gap_percent
        weight_percent = layer.weight_percent
        tp_percent = layer.tp_percent
        
        # Calculate DCA entry price from THIS pyramid's base
        if side == "long":
            dca_price = base_price * (Decimal("1") + gap_percent / Decimal("100"))
        else:
            dca_price = base_price * (Decimal("1") - gap_percent / Decimal("100"))
        
        dca_price = round_to_tick_size(dca_price, tick_size)
        
        # Calculate TP price
        if side == "long":
            tp_price = dca_price * (Decimal("1") + tp_percent / Decimal("100"))
        else:
            tp_price = dca_price * (Decimal("1") - tp_percent / Decimal("100"))
        
        dca_levels.append({
            "leg_index": idx,
            "price": dca_price,
            "gap_percent": gap_percent,
            "weight_percent": weight_percent,
            "tp_percent": tp_percent,
            "tp_price": tp_price
        })
    
    return dca_levels
Step 3: Calculate quantities
From grid_calculator.py:113-173:
@staticmethod
def calculate_order_quantities(
    dca_levels: List[Dict],
    total_capital_usd: Decimal,
    precision_rules: Dict
) -> List[Dict]:
    
    step_size = Decimal(str(precision_rules.get("step_size", "0.000001")))
    min_qty = Decimal(str(precision_rules.get("min_qty", "0.000001")))
    min_notional = Decimal(str(precision_rules.get("min_notional", "1")))
    
    for level in dca_levels:
        # Capital allocated to this leg
        leg_capital = total_capital_usd * (level["weight_percent"] / Decimal("100"))
        
        # Quantity = capital / price
        quantity = leg_capital / level["price"]
        quantity = round_to_step_size(quantity, step_size)
        
        # Validate minimums
        if quantity < min_qty:
            raise ValidationError(f"Quantity {quantity} below minimum {min_qty}")
        
        notional = quantity * level["price"]
        if notional < min_notional:
            raise ValidationError(f"Notional {notional} below minimum {min_notional}")
        
        level["quantity"] = quantity
    
    return dca_levels
Step 4: Create DCAOrder records
From position_manager.py:321-342:
orders_to_submit = []
order_side = "buy" if signal.side == "long" else "sell"

for i, level in enumerate(dca_levels):
    dca_order = DCAOrder(
        group_id=existing_position_group.id,
        pyramid_id=new_pyramid.id,
        leg_index=i,
        symbol=signal.symbol,
        side=order_side,
        order_type="limit",
        price=level['price'],
        quantity=level['quantity'],
        status=OrderStatus.PENDING,
        gap_percent=level.get('gap_percent', Decimal("0")),
        weight_percent=level.get('weight_percent', Decimal("0")),
        tp_percent=level.get('tp_percent', Decimal("0")),
        tp_price=level.get('tp_price', Decimal("0")),
    )
    session.add(dca_order)
    orders_to_submit.append(dca_order)

# Submit to exchange
for order in orders_to_submit:
    await order_service.submit_order(order)
Summary Diagram
Signal arrives: BTCUSDT @ $95,000
         │
         ▼
┌─────────────────────────────────────────┐
│ get_levels_for_pyramid(pyramid_index=1) │
│ → Returns pyramid-specific OR default   │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ calculate_dca_levels(                   │
│   base_price=$95,000,  ← Pyramid's own  │
│   pyramid_index=1                       │
│ )                                       │
│ → [{price: $95,000, gap: 0%},           │
│    {price: $93,100, gap: -2%},          │
│    {price: $91,200, gap: -4%}]          │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ calculate_order_quantities(             │
│   total_capital=$1000                   │
│ )                                       │
│ → Adds 'quantity' to each level         │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Create DCAOrder records:                │
│   - group_id = PositionGroup.id         │
│   - pyramid_id = new_pyramid.id         │
│   - leg_index = 0, 1, 2...              │
│   - Submit to exchange                  │
└─────────────────────────────────────────┘
Key Design Decisions
Aspect	Behavior
Base price	Each pyramid uses its own signal entry price
DCA config	Can be pyramid-specific via pyramid_specific_levels
Order ownership	Each DCAOrder has both group_id and pyramid_id
Querying	get_all_orders_by_group_id() returns all pyramids' orders
Statistics	Aggregated across all pyramids for weighted avg, total qty
Capital	Each pyramid gets fresh capital allocation (same total_capital_usd)

DCA Layer Configuration Analysis
1. How are DCA layers configured (price gap, capital weight, take profit)?
Each DCA layer is configured via the DCALevelConfig schema with three parameters: From grid_config.py:5-9:
class DCALevelConfig(BaseModel):
    gap_percent: Decimal      # Price offset from base (e.g., -2% below entry)
    weight_percent: Decimal   # Capital allocation (must sum to 100%)
    tp_percent: Decimal       # Take-profit target for this leg
Example configuration:
{
  "dca_levels": [
    {"gap_percent": 0,    "weight_percent": 25, "tp_percent": 2.0},
    {"gap_percent": -2,   "weight_percent": 25, "tp_percent": 2.5},
    {"gap_percent": -4,   "weight_percent": 25, "tp_percent": 3.0},
    {"gap_percent": -6,   "weight_percent": 25, "tp_percent": 3.5}
  ]
}
Calculation logic from grid_calculator.py:64-77:
# For LONG positions:
dca_price = base_price * (1 + gap_percent / 100)  # Negative gap = below entry
tp_price = dca_price * (1 + tp_percent / 100)     # TP above DCA price

# For SHORT positions:
dca_price = base_price * (1 - gap_percent / 100)  # Negative gap = above entry  
tp_price = dca_price * (1 - tp_percent / 100)     # TP below DCA price
Capital allocation from grid_calculator.py:135:
leg_capital = total_capital_usd * (level["weight_percent"] / Decimal("100"))
quantity = leg_capital / level["price"]
2. Is grid_strategy.max_dca_per_pyramid respected?
This setting does NOT exist in the codebase. I searched for max_dca_per_pyramid and grid_strategy - neither exists:
Grep pattern: max_dca|grid_strategy
Result: No matches found
The number of DCA layers is implicitly controlled by the dca_levels array length. From grid_calculator.py:47:
for idx, layer in enumerate(levels_config):  # Iterates ALL configured levels
    # No max limit check here
What actually exists:
Setting	Location	Purpose
max_pyramids	DCAConfiguration	Max pyramid entries (default 5)
len(dca_levels)	DCAConfiguration	Implicit DCA count per pyramid
To limit DCA layers, you would configure fewer items in the dca_levels array.
3. Can DCA configuration be different per symbol or is it global?
Per-symbol configuration is supported via the dca_configurations table. From dca_configuration.py:31-78:
class DCAConfiguration(Base):
    __tablename__ = "dca_configurations"
    
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    pair = Column(String, nullable=False)       # e.g., "BTC/USDT"
    timeframe = Column(Integer, nullable=False) # e.g., 15, 60
    exchange = Column(String, nullable=False)   # e.g., "binance"
    
    dca_levels = Column(JSON, nullable=False)
    pyramid_specific_levels = Column(JSON, nullable=False, default=dict)
    tp_mode = Column(SQLAlchemyEnum(TakeProfitMode))
    max_pyramids = Column(Integer, default=5)
    
    # Unique constraint enforces one config per combo
    __table_args__ = (
        UniqueConstraint('user_id', 'pair', 'timeframe', 'exchange', 
                        name='uix_user_pair_timeframe_exchange'),
    )
Lookup hierarchy from signal_router.py:68-101:
# 1. Normalize pair format: BTCUSDT -> BTC/USDT
normalized_pair = signal.tv.symbol
if '/' not in normalized_pair:
    if normalized_pair.endswith('USDT'):
        normalized_pair = normalized_pair[:-4] + '/' + normalized_pair[-4:]

# 2. Look up SPECIFIC config for this pair+timeframe+exchange
specific_config = await dca_config_repo.get_specific_config(
    user_id=self.user.id,
    pair=normalized_pair,
    timeframe=signal.tv.timeframe,
    exchange=signal.tv.exchange.lower()
)

# 3. If found, use it; otherwise ERROR (no fallback to global)
if specific_config:
    dca_config = DCAGridConfig(
        levels=specific_config.dca_levels,
        tp_mode=specific_config.tp_mode,
        max_pyramids=specific_config.max_pyramids,
        pyramid_specific_levels=specific_config.pyramid_specific_levels
    )
else:
    logger.error(f"No DCA configuration found for {signal.tv.symbol}")
    return f"Configuration Error: No active DCA configuration..."
Configuration granularity:
Level	Supported	Example
Per User	✅ Yes	User A has different config than User B
Per Symbol	✅ Yes	BTC/USDT different from ETH/USDT
Per Timeframe	✅ Yes	15m different from 1h
Per Exchange	✅ Yes	Binance different from Bybit
Per Pyramid	✅ Yes	Pyramid 1 different from Pyramid 2
Global fallback	❌ No	Must have specific config or signal fails
4. Where DCA layer parameters are defined and loaded
Definition: Schema Layer
grid_config.py:5-9 - Individual level config:
class DCALevelConfig(BaseModel):
    gap_percent: Decimal    # Price offset from base
    weight_percent: Decimal # Capital allocation %
    tp_percent: Decimal     # Take-profit %
grid_config.py:19-35 - Grid config container:
class DCAGridConfig(BaseModel):
    levels: List[DCALevelConfig]           # Default DCA levels
    pyramid_specific_levels: Dict[str, List[DCALevelConfig]]  # Per-pyramid overrides
    tp_mode: Literal["per_leg", "aggregate", "hybrid"]
    tp_aggregate_percent: Decimal
    max_pyramids: int = 5
    entry_order_type: Literal["limit", "market"] = "limit"
Storage: Database Model
dca_configuration.py:31-68:
class DCAConfiguration(Base):
    __tablename__ = "dca_configurations"
    
    dca_levels = Column(JSON, nullable=False, default=list)
    pyramid_specific_levels = Column(JSON, nullable=False, default=dict)
    tp_mode = Column(SQLAlchemyEnum(TakeProfitMode))
    tp_settings = Column(JSON, nullable=False, default=dict)
    max_pyramids = Column(Integer, default=5)
Loading: Signal Router
signal_router.py:80-98:
# Fetch from database
specific_config = await dca_config_repo.get_specific_config(
    user_id=self.user.id,
    pair=normalized_pair,
    timeframe=signal.tv.timeframe,
    exchange=signal.tv.exchange.lower()
)

# Convert DB model to Pydantic schema
dca_config = DCAGridConfig(
    levels=specific_config.dca_levels,                    # JSON array from DB
    tp_mode=specific_config.tp_mode.value,
    tp_aggregate_percent=Decimal(str(specific_config.tp_settings.get("tp_aggregate_percent", 0))),
    max_pyramids=specific_config.max_pyramids,
    entry_order_type=specific_config.entry_order_type.value,
    pyramid_specific_levels=specific_config.pyramid_specific_levels or {}
)
Usage: Grid Calculator
grid_calculator.py:44-45:
# Resolve levels for this pyramid (specific or default)
levels_config = dca_config.get_levels_for_pyramid(pyramid_index)
grid_config.py:57-75 - Pyramid-specific lookup:
def get_levels_for_pyramid(self, pyramid_index: int) -> List[DCALevelConfig]:
    """
    pyramid_count = 0 → Initial Entry (uses default levels)
    pyramid_count = 1 → First Pyramid (look for key "1")
    """
    key = str(pyramid_index)
    if key in self.pyramid_specific_levels and self.pyramid_specific_levels[key]:
        return self.pyramid_specific_levels[key]
    return self.levels  # Fallback to default
Configuration Flow Diagram
┌─────────────────────────────────────────────────────────────┐
│  dca_configurations table (per user/pair/timeframe/exchange)│
├─────────────────────────────────────────────────────────────┤
│  dca_levels (JSON):                                         │
│  [                                                          │
│    {"gap_percent": 0, "weight_percent": 25, "tp_percent": 2}│
│    {"gap_percent": -2, "weight_percent": 25, "tp_percent": 3}│
│    ...                                                      │
│  ]                                                          │
│                                                             │
│  pyramid_specific_levels (JSON):                            │
│  {                                                          │
│    "1": [{"gap_percent": 0, ...}, ...],  // Pyramid 1       │
│    "2": [{"gap_percent": 0, ...}, ...]   // Pyramid 2       │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  signal_router.py: Load specific config                     │
│  dca_config_repo.get_specific_config(user, pair, tf, exch)  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  DCAGridConfig (Pydantic schema)                            │
│  .get_levels_for_pyramid(pyramid_index)                     │
│    → Returns specific levels OR default                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  GridCalculatorService.calculate_dca_levels()               │
│  - Iterates ALL levels in config                            │
│  - Calculates price: base × (1 + gap%)                      │
│  - Calculates TP: dca_price × (1 + tp%)                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  GridCalculatorService.calculate_order_quantities()         │
│  - leg_capital = total × (weight% / 100)                    │
│  - quantity = leg_capital / price                           │
│  - Validates min_qty, min_notional                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  DCAOrder records created and submitted to exchange         │
└─────────────────────────────────────────────────────────────┘
Summary
Question	Answer
How configured?	gap_percent, weight_percent, tp_percent per level
max_dca_per_pyramid?	Does not exist - implicit via array length
Per-symbol config?	Yes - unique per user+pair+timeframe+exchange
Global fallback?	No - signal fails without specific config
Per-pyramid config?	Yes - via pyramid_specific_levels dict
Validation?	Weights should sum to 100% (warning only, not enforced)
For a long entry at price $100 with DCA gaps of [0%, -0.5%, -1%, -1.5%, -2%]:
1. Show me the code that calculates DCA order prices.
2. Are prices calculated as: DCA1 = $99.50, DCA2 = $99.00, etc.?
3. How is capital weight applied to determine order size?
4. Is precision validation applied BEFORE order submission?
5. Walk through the exact calculation for one DCA layer.
I'll trace through the exact DCA calculation code with your example.
Read c:\Users\zmzer\Documents\freelancing\engine\backend\app\services\grid_calculator.py
Grep "precision|tick_size|step_size|min_qty|min_notional" (in c:\Users\zmzer\Documents\freelancing\engine\backend\app\services)
469 lines of output
Now I have all the information to provide a comprehensive walkthrough with your exact example.
DCA Price Calculation Walkthrough
Your Example Setup
Entry price: $100
Side: Long
DCA gaps: [0%, -0.5%, -1%, -1.5%, -2%]
Weights: Let's assume [20%, 20%, 20%, 20%, 20%] (equal distribution)
Total capital: $1,000
Precision: tick_size=0.01, step_size=0.001, min_qty=0.001, min_notional=10
1. Code that calculates DCA order prices
From grid_calculator.py:63-69:
# Calculate DCA entry price
if side == "long":
    dca_price = base_price * (Decimal("1") + gap_percent / Decimal("100"))
else:
    dca_price = base_price * (Decimal("1") - gap_percent / Decimal("100"))

dca_price = round_to_tick_size(dca_price, tick_size)
The rounding function from grid_calculator.py:12-16:
def round_to_tick_size(value: Decimal, tick_size: Decimal) -> Decimal:
    return (value / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick_size
2. Are prices calculated as DCA1 = $99.50, DCA2 = $99.00?
⚠️ NO - The formula is ADDITIVE, not what you might expect for a long position. For LONG positions, the code does:
dca_price = base_price * (1 + gap_percent / 100)
With negative gap_percent values:
Leg	gap_percent	Formula	Result
0	0%	$100 × (1 + 0/100)	$100.00
1	-0.5%	$100 × (1 + (-0.5)/100) = $100 × 0.995	$99.50
2	-1%	$100 × (1 + (-1)/100) = $100 × 0.99	$99.00
3	-1.5%	$100 × (1 + (-1.5)/100) = $100 × 0.985	$98.50
4	-2%	$100 × (1 + (-2)/100) = $100 × 0.98	$98.00
Yes, your understanding is correct! Negative gaps produce lower prices for longs (buying the dip). For SHORT positions, the formula would be:
dca_price = base_price * (1 - gap_percent / 100)
So negative gaps would produce higher prices (shorting the rally).
3. How is capital weight applied to determine order size?
From grid_calculator.py:131-169:
for i, level in enumerate(dca_levels):
    # Step 1: Calculate capital for this leg
    leg_capital = total_capital_usd * (level["weight_percent"] / Decimal("100"))
    
    # Step 2: Calculate quantity = capital / price
    quantity = leg_capital / level["price"]
    
    # Step 3: Round to step size (ROUND_DOWN)
    quantity = round_to_step_size(quantity, step_size)
    
    # Step 4: Validate minimums
    if quantity < min_qty:
        raise ValidationError(f"Quantity {quantity} below minimum {min_qty}")
    
    notional = quantity * level["price"]
    if notional < min_notional:
        raise ValidationError(f"Notional {notional} below minimum {min_notional}")
    
    level["quantity"] = quantity
4. Is precision validation applied BEFORE order submission?
Yes, precision validation happens in TWO places BEFORE submission:
A. Symbol metadata check (signal_router.py)
From signal_router.py:141-147:
# Precision Validation (Block if metadata missing)
precision_rules = await exchange.get_precision_rules()
validator = PrecisionValidator(precision_rules)
if not validator.validate_symbol(signal.tv.symbol):
    response_message = f"Validation Error: Metadata missing or incomplete"
    return response_message  # BLOCKS signal processing
The validator checks from precision_validator.py:15-27:
def validate_symbol(self, symbol: str) -> bool:
    if symbol not in self.rules:
        return False
    
    rule = self.rules[symbol]
    required_fields = ['tick_size', 'step_size', 'min_qty', 'min_notional']
    
    for field in required_fields:
        if field not in rule:
            return False
    return True
B. Quantity calculation validation (grid_calculator.py)
From grid_calculator.py:152-167:
# Validate minimum quantity
if quantity < min_qty:
    raise ValidationError(f"Quantity {quantity} below minimum {min_qty}")

# Validate minimum notional
notional = quantity * level["price"]
if notional < min_notional:
    raise ValidationError(f"Notional {notional} below minimum {min_notional}")
Validation order:
✅ Symbol exists in precision rules
✅ All required fields present (tick_size, step_size, min_qty, min_notional)
✅ Price rounded to tick_size
✅ Quantity rounded to step_size
✅ Quantity >= min_qty
✅ Notional (qty × price) >= min_notional
➡️ Only then: DCAOrder created and submitted
5. Complete Walkthrough for One DCA Layer
Layer 2: gap_percent = -1%, weight_percent = 20%, tp_percent = 2%
Step 1: Calculate DCA Price
# Input
base_price = Decimal("100")
gap_percent = Decimal("-1")
side = "long"
tick_size = Decimal("0.01")

# Calculation
dca_price = 100 * (1 + (-1) / 100)
dca_price = 100 * 0.99
dca_price = Decimal("99.00")

# Round to tick_size (already aligned)
dca_price = round_to_tick_size(99.00, 0.01)
dca_price = (99.00 / 0.01).quantize(1, ROUND_DOWN) * 0.01
dca_price = 9900 * 0.01 = Decimal("99.00")
Step 2: Calculate TP Price
# Input
tp_percent = Decimal("2")

# Calculation (long = TP above entry)
tp_price = dca_price * (1 + tp_percent / 100)
tp_price = 99.00 * 1.02
tp_price = Decimal("100.98")

# Round to tick_size
tp_price = round_to_tick_size(100.98, 0.01)
tp_price = Decimal("100.98")
Step 3: Calculate Quantity
# Input
total_capital_usd = Decimal("1000")
weight_percent = Decimal("20")
step_size = Decimal("0.001")
min_qty = Decimal("0.001")
min_notional = Decimal("10")

# Calculation
leg_capital = 1000 * (20 / 100)
leg_capital = Decimal("200")  # $200 for this leg

raw_quantity = leg_capital / dca_price
raw_quantity = 200 / 99.00
raw_quantity = Decimal("2.0202020202...")

# Round to step_size (ROUND_DOWN)
quantity = round_to_step_size(2.0202..., 0.001)
quantity = (2.0202 / 0.001).quantize(1, ROUND_DOWN) * 0.001
quantity = 2020 * 0.001 = Decimal("2.020")
Step 4: Validate
# Check min_qty
quantity >= min_qty?
2.020 >= 0.001 ✅ PASS

# Check min_notional
notional = quantity * dca_price
notional = 2.020 * 99.00 = Decimal("199.98")
notional >= min_notional?
199.98 >= 10 ✅ PASS
Step 5: Final Level Object
{
    "leg_index": 2,
    "price": Decimal("99.00"),
    "gap_percent": Decimal("-1"),
    "weight_percent": Decimal("20"),
    "tp_percent": Decimal("2"),
    "tp_price": Decimal("100.98"),
    "quantity": Decimal("2.020")
}
Complete Grid for Your Example
Leg	Gap%	Price	Weight	Capital	Raw Qty	Final Qty	Notional	TP Price
0	0%	$100.00	20%	$200	2.0000	2.000	$200.00	$102.00
1	-0.5%	$99.50	20%	$200	2.0100	2.010	$199.99	$101.49
2	-1%	$99.00	20%	$200	2.0202	2.020	$199.98	$100.98
3	-1.5%	$98.50	20%	$200	2.0304	2.030	$199.95	$100.47
4	-2%	$98.00	20%	$200	2.0408	2.040	$199.92	$99.96
Total: 5 limit buy orders placed at decreasing prices, all validated against exchange minimums.

DCA Order Placement Analysis
1. Are all DCA orders placed immediately when a signal arrives?
Yes, with one exception for market entry orders. From position_manager.py:184-234:
# 7. Create DCAOrder objects
orders_to_submit = []
entry_type = dca_grid_config.entry_order_type  # "limit" or "market"

for i, level in enumerate(dca_levels):
    # Default to limit
    current_order_type = "limit"
    current_status = OrderStatus.PENDING
    
    # Only first leg (Leg 0) can be market
    if i == 0:
        if entry_type == "market":
            current_order_type = "market"
            current_status = OrderStatus.TRIGGER_PENDING  # WAIT, don't submit yet
    
    dca_order = DCAOrder(...)
    session.add(dca_order)
    
    # Only submit PENDING (limit) orders immediately
    if current_status == OrderStatus.PENDING:
        orders_to_submit.append(dca_order)
    else:
        logger.info(f"Order leg {i} set to TRIGGER_PENDING. Not submitting yet.")

# Submit all limit orders immediately
for order in orders_to_submit:
    await order_service.submit_order(order)
Behavior:
Entry Type	Leg 0	Legs 1-4
limit	Submitted immediately	Submitted immediately
market	Waits for price trigger	Submitted immediately
2. Or are they placed one at a time as price moves?
No - all LIMIT orders are placed at once. The exchange holds them until price hits each level. The only exception is TRIGGER_PENDING (market entry) which waits for price: From order_fill_monitor.py:141-177:
if order.status == OrderStatus.TRIGGER_PENDING.value:
    # Watch price
    current_price = Decimal(str(await connector.get_current_price(order.symbol)))
    should_trigger = False
    
    if order.side == "buy":
        if current_price <= order.price:  # Price dropped to entry level
            should_trigger = True
    else:  # sell
        if current_price >= order.price:  # Price rose to entry level
            should_trigger = True
    
    if should_trigger:
        logger.info(f"Trigger condition met. Submitting Market Order.")
        await order_service.submit_order(order)  # Now place as market
        
        if order.status == OrderStatus.FILLED.value:
            await position_manager.update_position_stats(order.group_id)
            await order_service.place_tp_order(order)
Order placement summary:
Signal arrives
     │
     ▼
┌─────────────────────────────────────────┐
│ Create ALL DCAOrder records in DB       │
│ - Leg 0: PENDING or TRIGGER_PENDING     │
│ - Legs 1-4: PENDING                     │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Submit ALL PENDING orders to exchange   │
│ (Limit orders sit on order book)        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Monitor polls every 5 seconds:          │
│ - TRIGGER_PENDING: Check price trigger  │
│ - OPEN: Check if filled                 │
│ - FILLED: Place TP order                │
└─────────────────────────────────────────┘
3. What order type is used (limit, market, stop-limit)?
Three order types are used:
Context	Order Type	Code Location
DCA Entry (default)	LIMIT	position_manager.py:196
DCA Entry (Leg 0 with market config)	MARKET	position_manager.py:200-201
Take-Profit	LIMIT	order_management.py:137
Force Close / Risk Engine	MARKET	order_management.py:352
From order_management.py:36-56 - Submit order:
async def submit_order(self, dca_order: DCAOrder) -> DCAOrder:
    order_type_value = dca_order.order_type.value.upper()  # "LIMIT" or "MARKET"
    side_value = dca_order.side.value.upper()              # "BUY" or "SELL"

    exchange_order_data = await self.exchange_connector.place_order(
        symbol=dca_order.symbol,
        order_type=order_type_value,
        side=side_value,
        quantity=dca_order.quantity,
        price=dca_order.price  # Ignored for MARKET orders
    )
Note: Stop-limit orders are NOT used. The system uses:
Limit orders that sit on the order book at DCA prices
Market orders for immediate fills when triggered
4. How are partially filled DCA orders handled?
From order_management.py:197-230:
async def check_order_status(self, dca_order: DCAOrder) -> DCAOrder:
    exchange_order_data = await self.exchange_connector.get_order_status(...)
    
    # Map exchange status
    mapped_status = exchange_status.lower()
    if mapped_status == "closed":
        mapped_status = "filled"
    
    # Special handling for partial fills
    filled_quantity_from_exchange = Decimal(str(exchange_order_data.get("filled", 0)))
    if new_status == OrderStatus.OPEN and \
       filled_quantity_from_exchange > 0 and \
       filled_quantity_from_exchange < dca_order.quantity:
        new_status = OrderStatus.PARTIALLY_FILLED
    
    # Update filled quantity
    if new_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
        dca_order.filled_quantity = filled_quantity_from_exchange
        dca_order.avg_fill_price = Decimal(str(exchange_order_data.get("average", 0)))
        
        if new_status == OrderStatus.FILLED and dca_order.filled_at is None:
            dca_order.filled_at = datetime.utcnow()
Partial fill handling:
Detection: Monitor checks filled quantity from exchange
Status update: OPEN → PARTIALLY_FILLED if 0 < filled < quantity
Tracking: filled_quantity and avg_fill_price updated incrementally
TP placement: Only when status == FILLED (fully filled)
From order_fill_monitor.py:195-203:
# Handle filled orders (not partial!)
if updated_order.status == OrderStatus.FILLED.value:
    await session.flush()
    await position_manager.update_position_stats(updated_order.group_id)
    await order_service.place_tp_order(updated_order)  # Only for FULLY filled
Order status flow:
PENDING → OPEN → PARTIALLY_FILLED → FILLED
    │                                  │
    │                                  ▼
    │                          Place TP Order
    │                                  │
    │                                  ▼
    │                          Monitor TP → FILLED
    │                                  │
    └──────────────────────────────────┘
                                       ▼
                              Update Position Stats
5. DCA Order Placement Code
Step 1: Create DCAOrder Objects
From position_manager.py:184-228:
# Initialize OrderService
order_service = self.order_service_class(
    session=session,
    user=user,
    exchange_connector=exchange_connector
)

# Create order objects
orders_to_submit = []
order_side = "buy" if signal.side == "long" else "sell"
entry_type = dca_grid_config.entry_order_type  # "limit" or "market"

for i, level in enumerate(dca_levels):
    current_order_type = "limit"
    current_status = OrderStatus.PENDING
    
    # Leg 0 market handling
    if i == 0 and entry_type == "market":
        current_order_type = "market"
        current_status = OrderStatus.TRIGGER_PENDING
    
    dca_order = DCAOrder(
        group_id=new_position_group.id,
        pyramid_id=new_pyramid.id,
        leg_index=i,
        symbol=signal.symbol,
        side=order_side,
        order_type=current_order_type,
        price=level['price'],
        quantity=level['quantity'],
        status=current_status,
        gap_percent=level.get('gap_percent'),
        weight_percent=level.get('weight_percent'),
        tp_percent=level.get('tp_percent'),
        tp_price=level.get('tp_price'),
    )
    session.add(dca_order)
    
    if current_status == OrderStatus.PENDING:
        orders_to_submit.append(dca_order)
Step 2: Submit to Exchange
From position_manager.py:229-238:
# Submit all pending (limit) orders
try:
    for order in orders_to_submit:
        await order_service.submit_order(order)
except Exception as e:
    logger.error(f"Failed to submit orders: {e}")
    new_position_group.status = PositionGroupStatus.FAILED
Step 3: Exchange API Call
From order_management.py:36-63:
async def submit_order(self, dca_order: DCAOrder) -> DCAOrder:
    max_retries = 3
    base_delay = 1

    for attempt in range(max_retries):
        try:
            exchange_order_data = await self.exchange_connector.place_order(
                symbol=dca_order.symbol,
                order_type=dca_order.order_type.value.upper(),
                side=dca_order.side.value.upper(),
                quantity=dca_order.quantity,
                price=dca_order.price
            )

            # Update order with exchange response
            dca_order.exchange_order_id = exchange_order_data["id"]
            dca_order.status = OrderStatus.OPEN.value
            dca_order.submitted_at = datetime.utcnow()
            
            await self.dca_order_repository.update(dca_order)
            return dca_order
            
        except ExchangeConnectionError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                await asyncio.sleep(delay)
            else:
                dca_order.status = OrderStatus.FAILED.value
                raise APIError(f"Failed after {max_retries} attempts")
Step 4: TP Order Placement (on fill)
From order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
        
    if dca_order.tp_order_id:
        return dca_order  # Already has TP

    # Determine TP side (opposite of entry)
    tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
    
    # Place limit TP order
    exchange_order_data = await self.exchange_connector.place_order(
        symbol=dca_order.symbol,
        order_type="LIMIT",
        side=tp_side,
        quantity=dca_order.filled_quantity,
        price=dca_order.tp_price
    )
    
    dca_order.tp_order_id = exchange_order_data["id"]
    await self.dca_order_repository.update(dca_order)
    return dca_order
Complete Order Lifecycle
┌──────────────────────────────────────────────────────────────┐
│                     SIGNAL ARRIVES                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ CREATE DCAOrders in DB (5 legs)                              │
│                                                              │
│ Leg 0: PENDING (limit) or TRIGGER_PENDING (market)           │
│ Leg 1: PENDING                                               │
│ Leg 2: PENDING                                               │
│ Leg 3: PENDING                                               │
│ Leg 4: PENDING                                               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ SUBMIT to exchange (all PENDING orders)                      │
│                                                              │
│ exchange.place_order(symbol, "LIMIT", "BUY", qty, price)     │
│ → Status: PENDING → OPEN                                     │
│ → exchange_order_id assigned                                 │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ MONITOR LOOP (every 5 seconds)                               │
│                                                              │
│ For TRIGGER_PENDING:                                         │
│   - Check current price                                      │
│   - If price <= target → Submit as MARKET                    │
│                                                              │
│ For OPEN:                                                    │
│   - Check exchange status                                    │
│   - Update filled_quantity, avg_fill_price                   │
│                                                              │
│ For PARTIALLY_FILLED:                                        │
│   - Continue monitoring until FILLED                         │
│                                                              │
│ For FILLED:                                                  │
│   - Place TP limit order                                     │
│   - Update position stats                                    │
│                                                              │
│ For FILLED + TP exists:                                      │
│   - Monitor TP order                                         │
│   - If TP filled → Update stats, mark tp_hit=True            │
└──────────────────────────────────────────────────────────────┘
Summary Table
Question	Answer
All placed immediately?	Yes - all LIMIT orders placed at once
One at a time?	No - exchange holds limit orders until price hits
Order type?	LIMIT (DCA entry/TP), MARKET (triggered entry, force close)
Partial fills?	Tracked via filled_quantity, TP only on full fill
Retry logic?	3 attempts with exponential backoff (1s, 2s, 4s)
Monitor interval?	5 seconds default

DCA Fill Tracking Mechanism
1. Is there a webhook/websocket listening for fill events?
No. The system uses polling, not webhooks or websockets. From order_fill_monitor.py:236-250:
async def _monitoring_loop(self):
    """The main loop for the Order Fill Monitoring task."""
    while self._running:
        try:
            await self._check_orders()
            await asyncio.sleep(self.polling_interval_seconds)  # Default: 5 seconds
        except asyncio.CancelledError:
            break
Architecture:
┌─────────────────────────────────────────────────────────────┐
│               OrderFillMonitorService                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  _monitoring_loop()                                  │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │  while True:                                   │  │   │
│  │  │    _check_orders()  ──► Exchange REST API     │  │   │
│  │  │    sleep(5 seconds)                           │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
Started at application startup from main.py:72-79:
app.state.order_fill_monitor = OrderFillMonitorService(
    session_factory=AsyncSessionLocal,
    dca_order_repository_class=DCAOrderRepository,
    position_group_repository_class=PositionGroupRepository,
    order_service_class=OrderService,
    position_manager_service_class=PositionManagerService
)
await app.state.order_fill_monitor.start_monitoring_task()
Trade-offs:
Approach	Latency	Complexity	Used?
Polling (REST)	~5 seconds	Low	✅ Yes
Webhooks	~instant	Medium	❌ No
WebSockets	~instant	High	❌ No
2. How is "Filled Legs / Total Legs" count updated?
From position_manager.py:676-679:
# Update Legs Count
# Count only ENTRY legs that are filled, excluding special TP fill records (leg_index=999)
filled_entry_legs = sum(
    1 for o in filled_orders 
    if o.leg_index != 999 and not o.tp_hit
)
position_group.filled_dca_legs = filled_entry_legs
Counting logic:
total_dca_legs: Set at creation = number of DCA levels in config
filled_dca_legs: Count of orders with status=FILLED AND leg_index != 999 (excludes TP records)
Status transitions based on fill count from position_manager.py:682-687:
if position_group.status in [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED]:
    if filled_entry_legs >= position_group.total_dca_legs:
        position_group.status = PositionGroupStatus.ACTIVE
    elif filled_entry_legs > 0:
        position_group.status = PositionGroupStatus.PARTIALLY_FILLED
filled_dca_legs	total_dca_legs	Status
0	5	LIVE
1-4	5	PARTIALLY_FILLED
5	5	ACTIVE
3. When a DCA fills, is the TP order placed immediately?
Yes, immediately after detecting the fill (within the same polling cycle). From order_fill_monitor.py:195-203:
# Handle filled orders
if updated_order.status == OrderStatus.FILLED.value:
    # CRITICAL: Flush order status update before recalculating stats
    await session.flush()
    
    logger.info(f"Order {order.id} FILLED - updating position stats and placing TP order")
    await position_manager.update_position_stats(updated_order.group_id, session=session)
    await order_service.place_tp_order(updated_order)  # TP placed HERE
    logger.info(f"✓ Successfully placed TP order for {updated_order.id}")
TP order placement from order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
        
    if dca_order.tp_order_id:
        return dca_order  # Already has TP, skip
    
    # TP side is opposite of entry
    tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
    
    # Place LIMIT order at pre-calculated tp_price
    exchange_order_data = await self.exchange_connector.place_order(
        symbol=dca_order.symbol,
        order_type="LIMIT",
        side=tp_side,
        quantity=dca_order.filled_quantity,
        price=dca_order.tp_price
    )
    
    dca_order.tp_order_id = exchange_order_data["id"]
    await self.dca_order_repository.update(dca_order)
    return dca_order
Flow:
Order FILLED detected
        │
        ▼
┌───────────────────────┐
│ session.flush()       │  (persist fill status)
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ update_position_stats │  (recalc qty, avg price, PnL)
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ place_tp_order()      │  (LIMIT sell @ tp_price)
└───────────────────────┘
        │
        ▼
    Continue loop
4. What happens if a DCA order is partially filled?
Partial fills are tracked separately and TP is NOT placed until fully filled. From order_management.py:197-230:
async def check_order_status(self, dca_order: DCAOrder) -> DCAOrder:
    exchange_order_data = await self.exchange_connector.get_order_status(...)
    
    # Get filled quantity from exchange
    filled_quantity_from_exchange = Decimal(str(exchange_order_data.get("filled", 0)))
    
    # Detect partial fill: some filled but not all
    if new_status == OrderStatus.OPEN and \
       filled_quantity_from_exchange > 0 and \
       filled_quantity_from_exchange < dca_order.quantity:
        new_status = OrderStatus.PARTIALLY_FILLED
    
    # Update tracking fields
    if new_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
        dca_order.filled_quantity = filled_quantity_from_exchange
        dca_order.avg_fill_price = Decimal(str(exchange_order_data.get("average", 0)))
        
        if new_status == OrderStatus.FILLED and dca_order.filled_at is None:
            dca_order.filled_at = datetime.utcnow()
Partial fill handling in monitor from order_fill_monitor.py:73:
# Fetch orders with these statuses for monitoring
all_orders = await dca_order_repo.get_open_and_partially_filled_orders(user_id=user.id)
Partial fill behavior:
Scenario	filled_quantity	status	TP Placed?	Stats Updated?
No fill	0	OPEN	No	No
Partial (50%)	0.5	PARTIALLY_FILLED	No	No
Full fill	1.0	FILLED	Yes	Yes
⚠️ Important: Position stats (weighted_avg_entry, total_filled_quantity) are only recalculated when an order reaches FILLED status. Partial fills are tracked but don't affect position-level calculations until complete.
5. Fill Tracking Mechanism (Complete Flow)
The Monitor Loop
From order_fill_monitor.py:51-225:
async def _check_orders(self):
    async with self.session_factory() as session:
        # 1. Get all active users
        user_repo = UserRepository(session)
        active_users = await user_repo.get_all_active_users()
        
        for user in active_users:
            # 2. Fetch open/partial orders for this user
            dca_order_repo = self.dca_order_repository_class(session)
            all_orders = await dca_order_repo.get_open_and_partially_filled_orders(user_id=user.id)
            
            # 3. Group by exchange
            orders_by_exchange = {}
            for order in all_orders:
                ex = order.group.exchange
                orders_by_exchange.setdefault(ex, []).append(order)
            
            # 4. Process each exchange
            for exchange_name, orders_to_check in orders_by_exchange.items():
                # Setup exchange connector
                connector = get_exchange_connector(exchange_name, exchange_keys_data)
                order_service = self.order_service_class(session, user, connector)
                
                for order in orders_to_check:
                    # --- CASE A: Already FILLED, check TP ---
                    if order.status == OrderStatus.FILLED.value:
                        updated_order = await order_service.check_tp_status(order)
                        if updated_order.tp_hit:
                            await position_manager.update_position_stats(order.group_id)
                        continue
                    
                    # --- CASE B: TRIGGER_PENDING (market watch) ---
                    if order.status == OrderStatus.TRIGGER_PENDING.value:
                        current_price = await connector.get_current_price(order.symbol)
                        if should_trigger(order, current_price):
                            await order_service.submit_order(order)  # Submit as MARKET
                            if order.status == OrderStatus.FILLED.value:
                                await position_manager.update_position_stats(order.group_id)
                                await order_service.place_tp_order(order)
                        continue
                    
                    # --- CASE C: OPEN/PARTIALLY_FILLED (check exchange) ---
                    updated_order = await order_service.check_order_status(order)
                    
                    if updated_order.status == OrderStatus.FILLED.value:
                        await session.flush()
                        await position_manager.update_position_stats(order.group_id)
                        await order_service.place_tp_order(updated_order)
                
                await connector.close()
            
            await session.commit()
Stats Recalculation
From position_manager.py:582-646:
async def _execute_update_position_stats(self, session, group_id):
    position_group = await position_group_repo.get_with_orders(group_id, refresh=True)
    all_orders = list(position_group.dca_orders)
    
    # Get filled orders sorted chronologically
    filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
    filled_orders.sort(key=lambda x: x.filled_at or x.created_at)
    
    # Replay trades to calculate current state
    current_qty = Decimal("0")
    current_invested_usd = Decimal("0")
    total_realized_pnl = Decimal("0")
    current_avg_price = Decimal("0")
    
    for o in filled_orders:
        qty = o.filled_quantity
        price = o.avg_fill_price or o.price
        
        # Determine if ENTRY or EXIT
        is_entry = (group_side == "long" and order_side == "buy") or \
                   (group_side == "short" and order_side == "sell")
        
        if is_entry:
            # Update weighted average
            new_invested = current_invested_usd + (qty * price)
            new_qty = current_qty + qty
            current_avg_price = new_invested / new_qty
            current_qty = new_qty
            current_invested_usd = new_invested
        else:
            # EXIT: Calculate realized PnL
            if group_side == "long":
                trade_pnl = (price - current_avg_price) * qty
            else:
                trade_pnl = (current_avg_price - price) * qty
            
            total_realized_pnl += trade_pnl
            current_qty -= qty
            current_invested_usd = current_qty * current_avg_price
    
    # Update position group
    position_group.weighted_avg_entry = current_avg_price
    position_group.total_invested_usd = current_invested_usd
    position_group.total_filled_quantity = current_qty
    position_group.realized_pnl_usd = total_realized_pnl
Complete Fill Tracking Diagram
┌─────────────────────────────────────────────────────────────────────┐
│                    APPLICATION STARTUP                               │
│  OrderFillMonitorService.start_monitoring_task()                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITORING LOOP (every 5s)                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  For each active user:                                               │
│    For each open/partial order:                                      │
│      ┌─────────────────────────────────────────────────────────┐    │
│      │ exchange.get_order_status(order_id, symbol)             │    │
│      │                         │                                │    │
│      │                         ▼                                │    │
│      │ ┌─────────────────────────────────────────────────────┐ │    │
│      │ │ Exchange REST API Response:                         │ │    │
│      │ │ {                                                   │ │    │
│      │ │   "id": "123456",                                   │ │    │
│      │ │   "status": "closed",   // or "open", "canceled"   │ │    │
│      │ │   "filled": 0.5,        // filled quantity         │ │    │
│      │ │   "average": 99.50      // avg fill price          │ │    │
│      │ │ }                                                   │ │    │
│      │ └─────────────────────────────────────────────────────┘ │    │
│      └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌─────────┐    ┌───────────┐    ┌─────────┐
        │  OPEN   │    │ PARTIAL   │    │ FILLED  │
        │ (no-op) │    │  FILLED   │    │         │
        └─────────┘    └───────────┘    └────┬────┘
                              │              │
                              │              ▼
                              │    ┌─────────────────────┐
                              │    │ 1. session.flush()  │
                              │    │ 2. update_stats()   │
                              │    │ 3. place_tp_order() │
                              │    └─────────────────────┘
                              │              │
                              ▼              ▼
                    ┌─────────────────────────────────┐
                    │ Update in DB:                   │
                    │ - order.status                  │
                    │ - order.filled_quantity         │
                    │ - order.avg_fill_price          │
                    │ - order.filled_at               │
                    │ - position_group.filled_dca_legs│
                    │ - position_group.total_filled_qty│
                    │ - position_group.weighted_avg   │
                    └─────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────────────────┐
                    │ session.commit()                │
                    └─────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────────────────┐
                    │ sleep(5 seconds)                │
                    │ Loop again...                   │
                    └─────────────────────────────────┘
Summary Table
Question	Answer
Webhook/WebSocket?	No - uses REST API polling every 5 seconds
Filled legs count	sum(1 for o if status=FILLED and leg_index!=999)
TP placement timing	Immediately after fill detected (same poll cycle)
Partial fill handling	Status=PARTIALLY_FILLED, tracked but no TP until full
Stats recalc trigger	Only on FILLED status, not partial
Latency	Up to 5 seconds (polling interval)
Potential Issues:
5-second latency - Fast-moving markets could see price drift before TP placed
No partial TP - If 90% filled, no TP until 100%
No websocket - Higher API usage, slower reaction time
Stats replay - Recalculates from all filled orders each time (O(n) per fill)


DCA Order Cancellation Logic
1. On exit signal - are ALL unfilled DCA orders cancelled?
Yes, ALL unfilled orders AND all TP orders are cancelled. From position_manager.py:357-388:
async def handle_exit_signal(self, position_group_id: uuid.UUID, session: Optional[AsyncSession] = None):
    """
    Handles an exit signal for a position group.
    1. Cancels all open DCA orders.
    2. Places a market order to close the total filled quantity.
    """
    # ... setup code ...
    
    order_service = self.order_service_class(session=session, user=self.user, exchange_connector=exchange_connector)

    # 1. Cancel open orders (ALL unfilled + ALL TPs)
    await order_service.cancel_open_orders_for_group(position_group.id)
    logger.info(f"Cancelled open orders for PositionGroup {position_group.id}")

    # 2. Close remaining position with market order
    total_filled_quantity = position_group.total_filled_quantity
    if total_filled_quantity > 0:
        await order_service.close_position_market(
            position_group=position_group,
            quantity_to_close=total_filled_quantity
        )
The cancel_open_orders_for_group() method from order_management.py:431-447:
async def cancel_open_orders_for_group(self, group_id: uuid.UUID):
    """
    Cancels all open orders for a group:
    1. Open/Partially Filled DCA orders (Entry orders).
    2. TP orders associated with Filled DCA orders.
    """
    orders = await self.dca_order_repository.get_all_orders_by_group_id(group_id)
    
    for order in orders:
        # Cancel Entry Orders (unfilled DCA legs)
        if order.status in [OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value]:
            await self.cancel_order(order)
        
        # Cancel TP Orders for Filled entries
        elif order.status == OrderStatus.FILLED.value and order.tp_order_id:
            await self.cancel_tp_order(order)
Exit signal flow:
Exit Signal Received
        │
        ▼
┌─────────────────────────────────────────────┐
│ cancel_open_orders_for_group()              │
│                                             │
│ For each order in group:                    │
│   ├─ OPEN/PARTIALLY_FILLED → cancel_order() │
│   └─ FILLED + has TP → cancel_tp_order()    │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│ close_position_market()                     │
│ (Sell/Buy remaining filled quantity)        │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│ Status = CLOSED                             │
│ Calculate realized PnL                      │
└─────────────────────────────────────────────┘
2. On TP hit (per-leg mode) - is only that leg's order cancelled?
No cancellation needed - the TP order simply fills and is marked complete. In per-leg TP mode, each DCA leg has its own independent TP order. When a TP fills: From order_management.py:252-304:
async def check_tp_status(self, dca_order: DCAOrder) -> DCAOrder:
    if not dca_order.tp_order_id:
        return dca_order

    exchange_order_data = await self.exchange_connector.get_order_status(
        order_id=dca_order.tp_order_id,
        symbol=dca_order.symbol
    )
    
    status = exchange_order_data["status"].lower()
    
    if status == "closed" or status == "filled":
        # Mark TP as hit (NOT cancelled)
        dca_order.tp_hit = True
        dca_order.tp_executed_at = datetime.utcnow()
        await self.dca_order_repository.update(dca_order)
        
        # Create a TP fill record to track the exit
        tp_fill_order = DCAOrder(
            group_id=dca_order.group_id,
            pyramid_id=dca_order.pyramid_id,
            leg_index=999,  # Special index for TP fills
            side=tp_side,   # Opposite of entry
            status=OrderStatus.FILLED.value,
            ...
        )
        await self.dca_order_repository.create(tp_fill_order)
Per-leg TP behavior:
Event	Action	Other Legs Affected?
Leg 1 TP fills	Mark tp_hit=True, create exit record	No
Leg 2 TP fills	Mark tp_hit=True, create exit record	No
Leg 3 still OPEN	Remains on exchange	N/A
Only cancelled when: Exit signal, Aggregate TP, or Force Close is triggered.
3. If price moves beyond the last DCA level, what happens?
Nothing special - the orders remain on the exchange order book. There is NO automatic cancellation if price moves beyond the last DCA level. Scenario Analysis:
Scenario	What Happens
Price above all DCA levels (long)	Orders sit unfilled on order book
Price below all DCA levels (long)	All orders filled, position ACTIVE
Price reverses back	Orders may fill on the way back
Signal arrives for same pair	Pyramid added (if under limit)
Exit signal	All unfilled orders cancelled
Example for LONG @ $100 with DCAs at $100, $99, $98, $97, $96:
Price drops to $94 (below all DCAs)
        │
        ├── All 5 DCA orders FILLED
        ├── Position status = ACTIVE
        ├── 5 TP orders placed
        └── No more DCA orders to fill

Price rises to $105 (above all DCAs)
        │
        ├── No DCA orders filled (all above entry)
        ├── Position status = LIVE
        ├── Orders remain on order book
        └── Wait for price to drop OR exit signal
⚠️ Gap: The system does NOT:
Cancel stale orders after a timeout
Alert when price is far from unfilled DCAs
Automatically adjust DCA levels based on price movement
4. DCA Cancellation Logic
Method 1: Cancel Single Order
From order_management.py:82-114:
async def cancel_order(self, dca_order: DCAOrder) -> DCAOrder:
    """
    Cancels a DCA order on the exchange and updates its status in the database.
    Handles OrderNotFound gracefully.
    """
    if not dca_order.exchange_order_id:
        # No exchange order to cancel, just mark as cancelled
        dca_order.status = OrderStatus.CANCELLED.value
        await self.dca_order_repository.update(dca_order)
        return dca_order

    try:
        await self.exchange_connector.cancel_order(
            order_id=dca_order.exchange_order_id,
            symbol=dca_order.symbol
        )
    except ccxt.OrderNotFound:
        # Order already gone - treat as success
        logger.warning(f"Order {dca_order.exchange_order_id} not found. Assuming already closed/cancelled.")
    except APIError as e:
        dca_order.status = OrderStatus.FAILED.value
        await self.dca_order_repository.update(dca_order)
        raise e

    # Mark as cancelled in DB
    dca_order.status = OrderStatus.CANCELLED.value
    dca_order.cancelled_at = datetime.utcnow()
    await self.dca_order_repository.update(dca_order)
    return dca_order
Method 2: Cancel TP Order
From order_management.py:402-429:
async def cancel_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    """
    Cancels the TP order associated with a filled DCA order.
    """
    if not dca_order.tp_order_id:
        return dca_order

    try:
        await self.exchange_connector.cancel_order(
            order_id=dca_order.tp_order_id,
            symbol=dca_order.symbol
        )
    except ccxt.OrderNotFound:
        logger.warning(f"TP order not found. Assuming already closed/cancelled.")
    except APIError as e:
        logger.error(f"Failed to cancel TP order: {e}")
        # Do NOT re-raise - goal is to close position

    # Clear TP order ID regardless of outcome
    dca_order.tp_order_id = None
    dca_order.tp_hit = False
    await self.dca_order_repository.update(dca_order)
    return dca_order
Method 3: Cancel All Orders for Group
From order_management.py:431-447:
async def cancel_open_orders_for_group(self, group_id: uuid.UUID):
    """
    Cancels all open orders for a group:
    1. Open/Partially Filled DCA orders (Entry orders).
    2. TP orders associated with Filled DCA orders.
    """
    orders = await self.dca_order_repository.get_all_orders_by_group_id(group_id)
    
    for order in orders:
        # Cancel Entry Orders
        if order.status in [OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value]:
            await self.cancel_order(order)
        
        # Cancel TP Orders for Filled entries
        elif order.status == OrderStatus.FILLED.value and order.tp_order_id:
            await self.cancel_tp_order(order)
Cancellation Triggers Summary
Trigger	What Gets Cancelled	Method Called
Exit Signal	ALL unfilled DCAs + ALL TPs	cancel_open_orders_for_group()
Force Close	ALL unfilled DCAs + ALL TPs	cancel_open_orders_for_group()
Aggregate TP Hit	ALL unfilled DCAs + ALL TPs	cancel_open_orders_for_group()
Risk Engine Close	ALL unfilled DCAs + ALL TPs	cancel_open_orders_for_group()
Per-Leg TP Fill	Nothing (TP naturally fills)	N/A
Price Beyond DCAs	Nothing (no auto-cancel)	N/A
Cancellation Flow Diagram
┌─────────────────────────────────────────────────────────────────────┐
│                     CANCELLATION TRIGGERS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Exit Signal (TradingView)                                       │
│  2. Force Close (API/Dashboard)                                     │
│  3. Aggregate TP Hit (price >= avg_entry * (1 + aggregate_tp%))     │
│  4. Risk Engine Action (loser closure/combination)                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  cancel_open_orders_for_group(group_id)                             │
│                                                                     │
│  1. Fetch ALL orders for group                                      │
│                                                                     │
│  2. For each order:                                                 │
│     ┌─────────────────────────────────────────────────────────────┐│
│     │ IF status = OPEN or PARTIALLY_FILLED:                       ││
│     │   └─► exchange.cancel_order(exchange_order_id, symbol)      ││
│     │   └─► order.status = CANCELLED                              ││
│     │   └─► order.cancelled_at = now()                            ││
│     └─────────────────────────────────────────────────────────────┘│
│     ┌─────────────────────────────────────────────────────────────┐│
│     │ ELIF status = FILLED AND tp_order_id exists:                ││
│     │   └─► exchange.cancel_order(tp_order_id, symbol)            ││
│     │   └─► order.tp_order_id = None                              ││
│     │   └─► order.tp_hit = False                                  ││
│     └─────────────────────────────────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  close_position_market(position_group, total_filled_quantity)       │
│  (Only if there's quantity to close)                                │
└─────────────────────────────────────────────────────────────────────┘
Summary Table
Question	Answer
Exit signal cancels all?	Yes - all unfilled DCAs + all TPs
Per-leg TP cancels leg?	No - TP fills naturally, no cancellation
Price beyond DCAs?	Nothing - orders remain on order book
Partial fill handling	Order status = PARTIALLY_FILLED, cancelled on exit
OrderNotFound handling	Gracefully ignored (assumed already filled/cancelled)
Cancel failures	Logged but don't block position closure

Take-Profit Mode Implementation Analysis
Overview
All three TP modes are defined but implementation varies:
Mode	Defined	Implemented	How
Per-Leg	✅	✅ Fully	Limit orders placed on exchange
Aggregate	✅	✅ Fully	Background monitoring + market close
Hybrid	✅	⚠️ Partial	Per-leg orders + aggregate monitoring
1. Per-Leg TP Mode
Configuration Location
From dca_configuration.py:58-62:
tp_mode = Column(
    SQLAlchemyEnum(TakeProfitMode, name="take_profit_mode_enum"),
    default=TakeProfitMode.PER_LEG,  # Default mode
    nullable=False
)
From grid_config.py:5-9:
class DCALevelConfig(BaseModel):
    gap_percent: Decimal      # Price offset from base
    weight_percent: Decimal   # Capital allocation
    tp_percent: Decimal       # TP percentage FOR THIS LEG
TP Price Calculation
From grid_calculator.py:71-77:
# Calculate TP price for each leg
if side == "long":
    tp_price = dca_price * (Decimal("1") + tp_percent / Decimal("100"))
else:  # short
    tp_price = dca_price * (Decimal("1") - tp_percent / Decimal("100"))

tp_price = round_to_tick_size(tp_price, tick_size)
Example (Long @ $100, tp_percent=2%):
DCA Leg 0: Entry $100.00 → TP $102.00
DCA Leg 1: Entry $99.00  → TP $100.98
DCA Leg 2: Entry $98.00  → TP $99.96
Execution Mechanism
From order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    """Places a Take-Profit order for a filled DCA order."""
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
    
    if dca_order.tp_order_id:
        return dca_order  # Already has TP
    
    # TP side is opposite of entry
    tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
    
    # Place LIMIT order at pre-calculated tp_price
    exchange_order_data = await self.exchange_connector.place_order(
        symbol=dca_order.symbol,
        order_type="LIMIT",
        side=tp_side,
        quantity=dca_order.filled_quantity,
        price=dca_order.tp_price  # Stored from DCALevelConfig
    )
    
    dca_order.tp_order_id = exchange_order_data["id"]
    await self.dca_order_repository.update(dca_order)
Flow:
DCA Leg Fills
     │
     ▼
┌─────────────────────────────────────┐
│ order_fill_monitor detects FILLED   │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ place_tp_order()                    │
│ - LIMIT SELL @ tp_price             │
│ - quantity = filled_quantity        │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ Monitor TP order until filled       │
│ - Mark tp_hit = True                │
│ - Create exit record (leg_index=999)│
└─────────────────────────────────────┘
2. Aggregate TP Mode
Configuration Location
From dca_configuration.py:64-66:
# Flexible storage for mode-specific TP settings
# Example: {"tp_aggregate_percent": 10.0}
tp_settings = Column(JSON, nullable=False, default=dict)
From position_group.py:78-82:
tp_mode = Column(
    SQLAlchemyEnum("per_leg", "aggregate", "hybrid", name="tp_mode_enum"),
    nullable=False,
)
tp_aggregate_percent = Column(Numeric(10, 4))  # e.g., 5.0 for 5%
TP Price Calculation
From position_manager.py:700-709:
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    aggregate_tp_price = Decimal("0")
    
    if position_group.side.lower() == "long":
        # TP = weighted_avg_entry * (1 + tp_aggregate_percent%)
        aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
        if current_price >= aggregate_tp_price:
            should_execute_tp = True
    else:  # Short
        aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
        if current_price <= aggregate_tp_price:
            should_execute_tp = True
Example (Long, avg_entry=$99.00, tp_aggregate_percent=5%):
Aggregate TP Price = $99.00 × 1.05 = $103.95

When current_price >= $103.95 → Trigger close
Execution Mechanism
From position_manager.py:711-740:
if should_execute_tp:
    logger.info(f"Aggregate TP Triggered for Group {group_id} at {current_price}")
    
    # Instantiate OrderService
    order_service = self.order_service_class(
        session=session,
        user=user,
        exchange_connector=exchange_connector
    )
    
    # 1. Cancel all open orders (unfilled DCAs + per-leg TPs)
    await order_service.cancel_open_orders_for_group(group_id)
    
    # 2. Execute Market Close for ENTIRE remaining quantity
    close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
    
    await order_service.place_market_order(
        user_id=user.id,
        exchange=position_group.exchange,
        symbol=position_group.symbol,
        side=close_side,
        quantity=current_qty,  # ENTIRE position
        position_group_id=group_id,
        record_in_db=True
    )
    
    position_group.status = PositionGroupStatus.CLOSING
    await position_group_repo.update(position_group)
Flow:
update_position_stats() called (on any fill)
     │
     ▼
┌─────────────────────────────────────────────────┐
│ Check: tp_mode == "aggregate" or "hybrid"?      │
│ Check: current_price >= aggregate_tp_price?     │
└─────────────────────────────────────────────────┘
     │ YES
     ▼
┌─────────────────────────────────────────────────┐
│ 1. cancel_open_orders_for_group()               │
│    - Cancel unfilled DCA orders                 │
│    - Cancel any per-leg TP orders               │
└─────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────┐
│ 2. place_market_order()                         │
│    - MARKET order to close ENTIRE position      │
│    - Side = opposite of position side           │
└─────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────┐
│ 3. Status = CLOSING                             │
└─────────────────────────────────────────────────┘
3. Hybrid TP Mode
Configuration Location
Same as Aggregate - uses both tp_percent per leg AND tp_aggregate_percent. From grid_config.py:55-61:
if dca_config.tp_mode == "hybrid":
    # In Hybrid, "First Trigger Wins". We place the Limit Order at the closest target.
    # For simplicity and typical use, Hybrid uses Per Leg for the Limit Order,
    # and Aggregate monitors run in background.
    # If both act as Limit Orders, we'd need OCO. We assume Per Leg takes precedence.
    tp_percent = layer.tp_percent  # Uses per-leg TP for limit orders
TP Price Calculation
Per-leg component: Same as Per-Leg mode (limit orders placed) Aggregate component: Same as Aggregate mode (background monitoring)
Execution Mechanism
Hybrid combines both mechanisms:
Per-leg TP orders ARE placed as limit orders (like Per-Leg mode)
Aggregate check runs in update_position_stats() (like Aggregate mode)
First trigger wins:
If per-leg TP fills first → that leg closes, others continue
If aggregate TP triggers first → cancel all, market close entire position
From position_manager.py:700:
# Same check covers BOTH aggregate and hybrid
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    # ... aggregate TP logic runs for BOTH modes
Flow:
┌─────────────────────────────────────────────────────────────────────┐
│                         HYBRID MODE                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐     ┌─────────────────────────┐       │
│  │    Per-Leg TP Orders    │     │   Aggregate Monitoring   │       │
│  │    (Limit on Exchange)  │     │   (Background Check)     │       │
│  └───────────┬─────────────┘     └───────────┬─────────────┘       │
│              │                               │                      │
│              ▼                               ▼                      │
│  ┌─────────────────────────┐     ┌─────────────────────────┐       │
│  │ Leg 1 TP fills at $102  │     │ Price hits $103.95      │       │
│  │ → That leg closes       │     │ (aggregate target)      │       │
│  │ → Others continue       │     │ → Cancel ALL orders     │       │
│  │                         │     │ → Market close ALL      │       │
│  └─────────────────────────┘     └─────────────────────────┘       │
│                                                                     │
│                    WHICHEVER TRIGGERS FIRST WINS                    │
└─────────────────────────────────────────────────────────────────────┘
Comparison Table
Aspect	Per-Leg	Aggregate	Hybrid
Config	tp_percent per level	tp_aggregate_percent	Both
Order Type	LIMIT (on exchange)	MARKET (on trigger)	LIMIT + MARKET
Trigger	Each leg independently	avg_entry + X%	First wins
Closes	One leg at a time	Entire position	Depends
Exchange Orders	Multiple TP limits	None until trigger	Multiple + monitor
Latency	Instant (exchange)	~5s polling	Per-leg instant, aggregate ~5s
Configuration Example
{
  "dca_levels": [
    {"gap_percent": 0, "weight_percent": 25, "tp_percent": 2.0},
    {"gap_percent": -2, "weight_percent": 25, "tp_percent": 2.5},
    {"gap_percent": -4, "weight_percent": 25, "tp_percent": 3.0},
    {"gap_percent": -6, "weight_percent": 25, "tp_percent": 3.5}
  ],
  "tp_mode": "hybrid",
  "tp_settings": {
    "tp_aggregate_percent": 5.0
  }
}
Result for Hybrid:
Leg 0: Entry $100, TP limit @ $102 (2%)
Leg 1: Entry $98, TP limit @ $100.45 (2.5%)
Leg 2: Entry $96, TP limit @ $98.88 (3%)
Leg 3: Entry $94, TP limit @ $97.29 (3.5%)
AND aggregate monitoring: if weighted_avg × 1.05 is reached → market close all
Implementation Gaps
Gap	Description	Impact
Per-Leg in Aggregate	When tp_mode="aggregate", per-leg tp_percent is calculated but not used	TP orders still created with prices, but monitored differently
Hybrid race condition	If aggregate triggers while per-leg TP is partially filled	Could have leftover position
No OCO orders	Exchange doesn't get both TP types simultaneously	Relies on polling for aggregate
Aggregate latency	5-second polling delay	Price could move significantly
Code Location Summary
Component	File	Line
TP mode enum	dca_configuration.py	26-29
TP mode on position	position_group.py	78-82
Per-leg TP calc	grid_calculator.py	71-77
Per-leg TP placement	order_management.py	116-149
Aggregate TP check	position_manager.py	695-740
Hybrid handling	grid_calculator.py	55-61
For Per-Leg TP mode:
1. Is each TP calculated from the ACTUAL FILL PRICE (not original entry)?
2. Example: DCA2 fills at $99.00 with TP of +1.5%. Is TP target $100.485?
3. How is the TP order placed (limit order at target price)?
4. What happens when only one leg hits TP - does only that leg close?
5. Show me the per-leg TP calculation code.
I'll trace through the per-leg TP calculation to answer these questions precisely.
Read c:\Users\zmzer\Documents\freelancing\engine\backend\app\services\order_management.py (lines 116-215)
Read c:\Users\zmzer\Documents\freelancing\engine\backend\app\services\order_management.py (lines 251-330)
Now let me check exactly where the tp_price is calculated and stored on the DCAOrder:
Read c:\Users\zmzer\Documents\freelancing\engine\backend\app\services\grid_calculator.py (lines 61-100)
Read c:\Users\zmzer\Documents\freelancing\engine\backend\app\services\position_manager.py (lines 201-250)
Now I have complete information to answer the questions precisely.
Per-Leg TP Analysis
1. Is each TP calculated from the ACTUAL FILL PRICE?
⚠️ NO - TP is calculated from the ORIGINAL PLANNED ENTRY PRICE, not actual fill price. The TP price is pre-calculated at signal processing time (before any fills) and stored on the DCAOrder record. From grid_calculator.py:71-77:
# Calculate TP price from PLANNED dca_price (not actual fill)
if side == "long":
    tp_price = dca_price * (Decimal("1") + tp_percent / Decimal("100"))
else:
    tp_price = dca_price * (Decimal("1") - tp_percent / Decimal("100"))

tp_price = round_to_tick_size(tp_price, tick_size)
Then stored on DCAOrder from position_manager.py:217:
dca_order = DCAOrder(
    ...
    price=level['price'],              # Planned entry price
    tp_price=level.get('tp_price'),    # Pre-calculated TP (based on planned price)
)
When TP order is placed from order_management.py:131-140:
# Use the PRE-CALCULATED tp_price from the order record
tp_price = dca_order.tp_price  # NOT recalculated from avg_fill_price!

exchange_order_data = await self.exchange_connector.place_order(
    symbol=dca_order.symbol,
    order_type="LIMIT",
    side=tp_side,
    quantity=dca_order.filled_quantity,
    price=tp_price  # Uses stored value, not actual fill
)
2. Example: DCA2 fills at $99.00 with TP of +1.5%. Is TP target $100.485?
It depends on the PLANNED price vs ACTUAL fill price. Scenario A: Planned = $99.00, Fills at $99.00 (exact fill)
TP Price = $99.00 × 1.015 = $100.485 ✅
Scenario B: Planned = $99.00, Fills at $98.50 (slippage/better fill)
TP Price = $99.00 × 1.015 = $100.485 (still uses planned price!)
Actual profit = ($100.485 - $98.50) / $98.50 = 2.01% (better than expected)
Scenario C: Planned = $99.00, Fills at $99.50 (worse fill)
TP Price = $99.00 × 1.015 = $100.485 (still uses planned price!)
Actual profit = ($100.485 - $99.50) / $99.50 = 0.99% (worse than expected)
⚠️ This is a potential issue - TP is not adjusted for actual fill price slippage.
3. How is the TP order placed?
As a LIMIT order at the pre-calculated target price. From order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    """Places a Take-Profit order for a filled DCA order."""
    
    # 1. Validate order is filled
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
    
    # 2. Skip if TP already exists
    if dca_order.tp_order_id:
        return dca_order
    
    # 3. Determine TP side (opposite of entry)
    tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
    
    # 4. Get pre-calculated TP price
    tp_price = dca_order.tp_price
    
    # 5. Place LIMIT order on exchange
    exchange_order_data = await self.exchange_connector.place_order(
        symbol=dca_order.symbol,
        order_type="LIMIT",      # Always LIMIT
        side=tp_side,            # Opposite of entry
        quantity=dca_order.filled_quantity,  # Uses ACTUAL filled qty
        price=tp_price           # Pre-calculated price
    )
    
    # 6. Store exchange order ID
    dca_order.tp_order_id = exchange_order_data["id"]
    await self.dca_order_repository.update(dca_order)
Key points:
Order type: LIMIT (sits on order book until price hits)
Quantity: Uses filled_quantity (actual fill, not planned)
Price: Uses tp_price (pre-calculated, not adjusted for fill)
4. What happens when only one leg hits TP - does only that leg close?
Yes, only that specific leg closes. Other legs continue independently. From order_management.py:252-304:
async def check_tp_status(self, dca_order: DCAOrder) -> DCAOrder:
    """Checks the status of the TP order associated with this DCA order."""
    
    if not dca_order.tp_order_id:
        return dca_order

    exchange_order_data = await self.exchange_connector.get_order_status(
        order_id=dca_order.tp_order_id,
        symbol=dca_order.symbol
    )
    
    status = exchange_order_data["status"].lower()
    
    if status == "closed" or status == "filled":
        # Mark THIS LEG's TP as hit
        dca_order.tp_hit = True
        dca_order.tp_executed_at = datetime.utcnow()
        await self.dca_order_repository.update(dca_order)
        
        # Create EXIT record for this leg only
        tp_side = "sell" if dca_order.side.lower() == "buy" else "buy"
        filled_qty = Decimal(str(exchange_order_data.get("filled", dca_order.filled_quantity)))
        avg_price = Decimal(str(exchange_order_data.get("average", dca_order.tp_price)))
        
        tp_fill_order = DCAOrder(
            group_id=dca_order.group_id,
            pyramid_id=dca_order.pyramid_id,
            leg_index=999,  # Special index for TP exits
            side=tp_side,
            status=OrderStatus.FILLED.value,
            filled_quantity=filled_qty,
            avg_fill_price=avg_price,
            ...
        )
        await self.dca_order_repository.create(tp_fill_order)
Each leg is independent:
Position Group (BTCUSDT Long)
├── Leg 0: Entry $100 → TP $102 → FILLED, TP HIT ✅ (closed)
├── Leg 1: Entry $99 → TP $100.49 → FILLED, TP pending... (still open)
├── Leg 2: Entry $98 → TP $99.47 → OPEN (not filled yet)
└── Leg 3: Entry $97 → TP $98.46 → OPEN (not filled yet)
When Leg 0 TP hits:
dca_order.tp_hit = True for Leg 0 only
Exit record created with leg_index=999
update_position_stats() recalculates:
Reduces total_filled_quantity by Leg 0's quantity
Adds realized PnL for Leg 0
Other legs continue monitoring independently
5. Per-Leg TP Calculation Code
Step 1: Calculate TP Price at Signal Time
From grid_calculator.py:29-88:
@staticmethod
def calculate_dca_levels(
    base_price: Decimal,          # Signal entry price
    dca_config: DCAGridConfig,
    side: Literal["long", "short"],
    precision_rules: Dict,
    pyramid_index: int = 0
) -> List[Dict]:
    
    tick_size = Decimal(str(precision_rules["tick_size"]))
    dca_levels = []
    
    levels_config = dca_config.get_levels_for_pyramid(pyramid_index)
    
    for idx, layer in enumerate(levels_config):
        gap_percent = layer.gap_percent
        tp_percent = layer.tp_percent  # Per-leg TP %
        
        # Calculate PLANNED entry price
        if side == "long":
            dca_price = base_price * (Decimal("1") + gap_percent / Decimal("100"))
        else:
            dca_price = base_price * (Decimal("1") - gap_percent / Decimal("100"))
        
        dca_price = round_to_tick_size(dca_price, tick_size)
        
        # Calculate TP price FROM PLANNED ENTRY (not actual fill!)
        if side == "long":
            tp_price = dca_price * (Decimal("1") + tp_percent / Decimal("100"))
        else:
            tp_price = dca_price * (Decimal("1") - tp_percent / Decimal("100"))
        
        tp_price = round_to_tick_size(tp_price, tick_size)
        
        dca_levels.append({
            "leg_index": idx,
            "price": dca_price,      # Planned entry
            "tp_percent": tp_percent,
            "tp_price": tp_price     # Pre-calculated TP
        })
    
    return dca_levels
Step 2: Store TP Price on DCAOrder
From position_manager.py:204-218:
dca_order = DCAOrder(
    group_id=new_position_group.id,
    pyramid_id=new_pyramid.id,
    leg_index=i,
    symbol=signal.symbol,
    side=order_side,
    order_type=current_order_type,
    price=level['price'],                              # Planned entry
    quantity=level['quantity'],
    tp_percent=level.get('tp_percent', Decimal("0")),  # TP %
    tp_price=level.get('tp_price', Decimal("0")),      # Pre-calculated TP price
)
Step 3: Place TP Order When Entry Fills
From order_fill_monitor.py:195-203:
if updated_order.status == OrderStatus.FILLED.value:
    await session.flush()
    await position_manager.update_position_stats(updated_order.group_id)
    await order_service.place_tp_order(updated_order)  # Places TP using stored tp_price
From order_management.py:131-140:
# Use the stored tp_price (NOT recalculated from actual fill)
tp_price = dca_order.tp_price

exchange_order_data = await self.exchange_connector.place_order(
    symbol=dca_order.symbol,
    order_type="LIMIT",
    side=tp_side,
    quantity=dca_order.filled_quantity,  # Actual filled qty
    price=tp_price                        # Pre-calculated price
)
Step 4: Monitor TP and Record Exit
From order_management.py:267-297:
if status == "closed" or status == "filled":
    dca_order.tp_hit = True
    dca_order.tp_executed_at = datetime.utcnow()
    
    # Create exit record
    tp_fill_order = DCAOrder(
        group_id=dca_order.group_id,
        pyramid_id=dca_order.pyramid_id,
        leg_index=999,  # Special marker for TP exit
        side=tp_side,
        status=OrderStatus.FILLED.value,
        filled_quantity=filled_qty,
        avg_fill_price=avg_price,
    )
    await self.dca_order_repository.create(tp_fill_order)
Complete Per-Leg TP Flow
┌─────────────────────────────────────────────────────────────────────┐
│                    SIGNAL ARRIVES                                    │
│                                                                     │
│  Base price: $100, Side: Long                                       │
│  Config: gap=-1%, tp_percent=1.5%                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  grid_calculator.calculate_dca_levels()                             │
│                                                                     │
│  Planned Entry: $100 × (1 + (-1%)) = $99.00                         │
│  TP Price: $99.00 × (1 + 1.5%) = $100.485                          │
│                                                                     │
│  Returns: {price: $99.00, tp_price: $100.485}                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DCAOrder created and stored:                                       │
│                                                                     │
│  price = $99.00 (planned entry)                                     │
│  tp_price = $100.485 (pre-calculated, FIXED)                        │
│  tp_percent = 1.5%                                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Entry LIMIT order submitted @ $99.00                               │
│  Actual fill @ $98.50 (better price due to slippage)                │
│                                                                     │
│  filled_quantity = 1.0                                              │
│  avg_fill_price = $98.50                                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  place_tp_order() called:                                           │
│                                                                     │
│  TP LIMIT SELL @ $100.485 (uses stored tp_price, NOT recalculated!) │
│  Quantity: 1.0 (actual filled qty)                                  │
│                                                                     │
│  ⚠️ Actual profit if TP hits: ($100.485 - $98.50) / $98.50 = 2.01%  │
│  (Better than expected 1.5% because of favorable entry fill)        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Monitor polls TP order status...                                   │
│  TP fills @ $100.485                                                │
│                                                                     │
│  - Mark tp_hit = True                                               │
│  - Create exit record (leg_index=999)                               │
│  - Recalculate position stats                                       │
│  - THIS LEG ONLY closes, others continue                            │
└─────────────────────────────────────────────────────────────────────┘
Summary Table
Question	Answer
TP from actual fill?	NO - uses pre-calculated price from planned entry
Example $99 + 1.5%	TP = $100.485 (from planned, regardless of actual fill)
Order type	LIMIT at pre-calculated tp_price
Single leg TP hit	Only that leg closes, others continue
TP quantity	Uses filled_quantity (actual fill)
TP price	Uses tp_price (pre-calculated, fixed)
Potential Issue
The TP is not adjusted for actual fill price slippage. If you want TP based on actual fill:
# CURRENT (not adjusting for fill):
tp_price = dca_order.tp_price  # Pre-calculated

# BETTER APPROACH (adjust for actual fill):
actual_fill = dca_order.avg_fill_price
tp_percent = dca_order.tp_percent
if side == "long":
    tp_price = actual_fill * (1 + tp_percent / 100)
else:
    tp_price = actual_fill * (1 - tp_percent / 100)
This would ensure the actual profit percentage matches the configured tp_percent.

Aggregate TP Mode Analysis
1. How is the weighted average entry price calculated?
Using a chronological replay of all filled orders, tracking running totals. From position_manager.py:582-640:
# --- 2. Calculate Stats from Filled Orders (Chronological Replay) ---
filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]

# Sort by filled_at to ensure correct sequence of Entry -> Exit
filled_orders.sort(key=lambda x: x.filled_at or x.created_at or datetime.min)

current_qty = Decimal("0")
current_invested_usd = Decimal("0")
current_avg_price = Decimal("0")

for o in filled_orders:
    order_side = o.side.lower()
    group_side = position_group.side.lower()
    
    qty = o.filled_quantity
    price = o.avg_fill_price or o.price  # Uses ACTUAL fill price
    
    # Determine if this is an ENTRY or EXIT
    is_entry = (group_side == "long" and order_side == "buy") or \
               (group_side == "short" and order_side == "sell")

    if is_entry:
        # --- ENTRY: Add to position ---
        new_invested = current_invested_usd + (qty * price)
        new_qty = current_qty + qty
        
        # Recalculate weighted average
        if new_qty > 0:
            current_avg_price = new_invested / new_qty
        
        current_qty = new_qty
        current_invested_usd = new_invested
        
    else:
        # --- EXIT: Reduce position ---
        # (PnL calculation omitted for brevity)
        current_qty -= qty
        current_invested_usd = current_qty * current_avg_price
Formula:
weighted_avg_entry = total_invested_usd / total_filled_quantity

Where:
  total_invested_usd = Σ (fill_qty × fill_price) for all entries
  total_filled_quantity = Σ fill_qty for all entries - Σ fill_qty for all exits
Example:
Leg 0: Fill 1.0 @ $100.00  →  invested = $100,  qty = 1.0,  avg = $100.00
Leg 1: Fill 1.0 @ $98.00   →  invested = $198,  qty = 2.0,  avg = $99.00
Leg 2: Fill 1.0 @ $96.00   →  invested = $294,  qty = 3.0,  avg = $98.00

weighted_avg_entry = $294 / 3.0 = $98.00
2. When a new DCA fills, is the average recalculated?
Yes, the average is recalculated every time update_position_stats() is called. This happens:
After every fill detection in the order monitor
After TP hits
After any position-affecting action
From order_fill_monitor.py:195-203:
if updated_order.status == OrderStatus.FILLED.value:
    await session.flush()
    
    # Recalculates weighted_avg_entry from ALL filled orders
    await position_manager.update_position_stats(updated_order.group_id, session=session)
    
    await order_service.place_tp_order(updated_order)
Recalculation flow:
New DCA Fill Detected
        │
        ▼
┌─────────────────────────────────────────────┐
│ update_position_stats()                     │
│                                             │
│ 1. Fetch ALL filled orders for group        │
│ 2. Sort chronologically                     │
│ 3. Replay entries/exits                     │
│ 4. Calculate new weighted_avg_entry         │
│ 5. Store on position_group                  │
│ 6. Check aggregate TP trigger               │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│ position_group.weighted_avg_entry = $98.00  │
│ (Updated with new fill included)            │
└─────────────────────────────────────────────┘
Key point: The weighted average uses actual fill prices (avg_fill_price), not planned prices. From position_manager.py:601-602:
qty = o.filled_quantity
price = o.avg_fill_price or o.price  # Prefers actual fill price
3. Is the TP target based on this weighted average?
Yes, the aggregate TP target is dynamically calculated from the current weighted average. From position_manager.py:700-709:
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    aggregate_tp_price = Decimal("0")
    
    if position_group.side.lower() == "long":
        # TP = weighted_avg × (1 + tp_aggregate_percent%)
        aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
        if current_price >= aggregate_tp_price:
            should_execute_tp = True
    else:  # Short
        aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
        if current_price <= aggregate_tp_price:
            should_execute_tp = True
Formula:
LONG:  aggregate_tp_price = weighted_avg_entry × (1 + tp_aggregate_percent / 100)
SHORT: aggregate_tp_price = weighted_avg_entry × (1 - tp_aggregate_percent / 100)
Example (Long, tp_aggregate_percent = 3%):
After Leg 0 fills @ $100:  avg = $100.00  →  TP target = $103.00
After Leg 1 fills @ $98:   avg = $99.00   →  TP target = $101.97
After Leg 2 fills @ $96:   avg = $98.00   →  TP target = $100.94

TP target MOVES DOWN as average improves from DCA
Key insight: The TP target is recalculated on every stats update, so it tracks the improving average as more DCAs fill.
4. When aggregate TP hits, are ALL open legs closed together?
Yes, the ENTIRE remaining position is closed with a single market order. From position_manager.py:711-740:
if should_execute_tp:
    logger.info(f"Aggregate TP Triggered for Group {group_id} at {current_price} (Target: {aggregate_tp_price})")
    
    order_service = self.order_service_class(
        session=session,
        user=user,
        exchange_connector=exchange_connector
    )
    
    # 1. Cancel ALL open orders (unfilled DCAs + per-leg TPs)
    await order_service.cancel_open_orders_for_group(group_id)
    
    # 2. Execute Market Close for ENTIRE remaining quantity
    close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
    await order_service.place_market_order(
        user_id=user.id,
        exchange=position_group.exchange,
        symbol=position_group.symbol,
        side=close_side,
        quantity=current_qty,  # ENTIRE position quantity
        position_group_id=group_id,
        record_in_db=True
    )
    
    # 3. Mark group as CLOSING
    position_group.status = PositionGroupStatus.CLOSING
    await position_group_repo.update(position_group)
What gets cancelled/closed:
Item	Action
Unfilled DCA orders (OPEN)	Cancelled
Partially filled DCAs	Cancelled (filled portion stays)
Per-leg TP orders	Cancelled
Filled position quantity	Market sold/bought
Example scenario:
Position: BTCUSDT Long, tp_aggregate_percent = 3%

Before Aggregate TP:
├── Leg 0: FILLED @ $100 (qty: 1.0), TP order @ $102 pending
├── Leg 1: FILLED @ $98 (qty: 1.0), TP order @ $99.47 pending
├── Leg 2: OPEN @ $96 (qty: 1.0), waiting to fill
├── Leg 3: OPEN @ $94 (qty: 1.0), waiting to fill
│
│ weighted_avg = $99.00
│ aggregate_tp_price = $99.00 × 1.03 = $101.97
│ current_price = $102.00 (>= $101.97) → TRIGGERED!

After Aggregate TP:
├── Leg 0 TP order: CANCELLED
├── Leg 1 TP order: CANCELLED
├── Leg 2 entry order: CANCELLED
├── Leg 3 entry order: CANCELLED
├── Market SELL 2.0 BTC @ ~$102 (closes entire position)
│
│ Status: CLOSING → CLOSED
│ Realized PnL: (2.0 × $102) - (2.0 × $99) = $6.00 profit
5. Aggregate TP Calculation Code
Complete Flow
# === STEP 1: Trigger - Called after any fill ===
# order_fill_monitor.py:201
await position_manager.update_position_stats(updated_order.group_id, session=session)


# === STEP 2: Fetch all orders for the group ===
# position_manager.py:548
position_group = await position_group_repo.get_with_orders(group_id, refresh=True)
all_orders = list(position_group.dca_orders)


# === STEP 3: Calculate weighted average from ACTUAL fills ===
# position_manager.py:582-619
filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
filled_orders.sort(key=lambda x: x.filled_at or x.created_at or datetime.min)

current_qty = Decimal("0")
current_invested_usd = Decimal("0")
current_avg_price = Decimal("0")

for o in filled_orders:
    qty = o.filled_quantity
    price = o.avg_fill_price or o.price  # ACTUAL fill price
    
    is_entry = (group_side == "long" and o.side == "buy") or \
               (group_side == "short" and o.side == "sell")

    if is_entry:
        new_invested = current_invested_usd + (qty * price)
        new_qty = current_qty + qty
        
        if new_qty > 0:
            current_avg_price = new_invested / new_qty  # Weighted average
        
        current_qty = new_qty
        current_invested_usd = new_invested
    else:
        # Handle exits (per-leg TPs that already hit)
        current_qty -= qty
        current_invested_usd = current_qty * current_avg_price


# === STEP 4: Store updated stats ===
# position_manager.py:642-646
position_group.weighted_avg_entry = current_avg_price
position_group.total_invested_usd = current_invested_usd
position_group.total_filled_quantity = current_qty


# === STEP 5: Get current market price ===
# position_manager.py:657-659
current_price = await exchange_connector.get_current_price(position_group.symbol)
current_price = Decimal(str(current_price))


# === STEP 6: Calculate aggregate TP target ===
# position_manager.py:700-709
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    
    if position_group.side.lower() == "long":
        aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
        should_execute_tp = current_price >= aggregate_tp_price
    else:
        aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
        should_execute_tp = current_price <= aggregate_tp_price


# === STEP 7: Execute if triggered ===
# position_manager.py:711-740
if should_execute_tp:
    # Cancel all open orders
    await order_service.cancel_open_orders_for_group(group_id)
    
    # Market close entire position
    close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
    await order_service.place_market_order(
        user_id=user.id,
        exchange=position_group.exchange,
        symbol=position_group.symbol,
        side=close_side,
        quantity=current_qty,
        position_group_id=group_id,
        record_in_db=True
    )
    
    position_group.status = PositionGroupStatus.CLOSING
Visual Flow Diagram
┌─────────────────────────────────────────────────────────────────────┐
│                     DCA FILL DETECTED                                │
│                                                                     │
│  Leg 1 fills @ $98.00 (actual fill price)                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  update_position_stats()                                            │
│                                                                     │
│  Replay all fills:                                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Leg 0: qty=1.0, price=$100.00                               │   │
│  │   invested = $100, qty = 1.0, avg = $100.00                 │   │
│  │                                                              │   │
│  │ Leg 1: qty=1.0, price=$98.00                                │   │
│  │   invested = $198, qty = 2.0, avg = $99.00                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  position_group.weighted_avg_entry = $99.00                         │
│  position_group.total_filled_quantity = 2.0                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Fetch current market price: $102.00                                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Calculate Aggregate TP Target                                      │
│                                                                     │
│  tp_mode = "aggregate"                                              │
│  tp_aggregate_percent = 3%                                          │
│  side = "long"                                                      │
│                                                                     │
│  aggregate_tp_price = $99.00 × (1 + 3/100)                          │
│  aggregate_tp_price = $99.00 × 1.03 = $101.97                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Check Trigger: current_price >= aggregate_tp_price?                │
│                                                                     │
│  $102.00 >= $101.97?  →  YES! TRIGGERED                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Execute Aggregate TP                                               │
│                                                                     │
│  1. cancel_open_orders_for_group()                                  │
│     - Cancel Leg 2 entry order (OPEN)                               │
│     - Cancel Leg 3 entry order (OPEN)                               │
│     - Cancel Leg 0 TP order (if exists)                             │
│     - Cancel Leg 1 TP order (if exists)                             │
│                                                                     │
│  2. place_market_order()                                            │
│     - MARKET SELL 2.0 BTC                                           │
│     - Records exit in database                                      │
│                                                                     │
│  3. position_group.status = CLOSING                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Position Closed                                                    │
│                                                                     │
│  Realized PnL = (2.0 × $102) - (2.0 × $99) = $6.00                  │
│  Status: CLOSED                                                     │
└─────────────────────────────────────────────────────────────────────┘
Comparison: Per-Leg vs Aggregate TP
Aspect	Per-Leg TP	Aggregate TP
TP Price Basis	Pre-calculated from planned entry	Dynamic from weighted avg of actual fills
Recalculated?	No (fixed at order creation)	Yes (every stats update)
Order Type	LIMIT (on exchange)	MARKET (on trigger)
Closes	One leg at a time	Entire position at once
Unfilled DCAs	Continue waiting	Cancelled
Latency	Instant (exchange executes)	~5 seconds (polling)
Slippage	None (limit price)	Possible (market order)
Summary Table
Question	Answer
How is weighted avg calculated?	Σ(qty × fill_price) / Σ qty from actual fills
Recalculated on new fill?	Yes, every update_position_stats() call
TP based on weighted avg?	Yes, avg × (1 + tp_aggregate_percent%)
All legs close together?	Yes, single market order for entire quantity
Open orders?	Cancelled before market close
Uses actual fill prices?	Yes (unlike per-leg which uses planned prices)

Hybrid TP Mode Analysis
1. Do both per-leg and aggregate TP systems run simultaneously?
Yes, both systems run in parallel:
System	Mechanism	Location
Per-Leg TP	LIMIT orders on exchange	Placed when each DCA fills
Aggregate TP	Background price monitoring	Checked in update_position_stats()
Per-Leg orders ARE placed in Hybrid mode: From grid_calculator.py:55-61:
if dca_config.tp_mode == "hybrid":
    # In Hybrid, "First Trigger Wins". We place the Limit Order at the closest target.
    # For simplicity and typical use, Hybrid uses Per Leg for the Limit Order,
    # and Aggregate monitors run in background.
    # If both act as Limit Orders, we'd need OCO. We assume Per Leg takes precedence.
    tp_percent = layer.tp_percent  # Per-leg TP prices ARE calculated
Aggregate monitoring ALSO runs in Hybrid mode: From position_manager.py:700:
# Same check covers BOTH aggregate and hybrid
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    # Aggregate TP logic runs for BOTH modes
Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                      HYBRID MODE                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │    PER-LEG TP SYSTEM        │  │   AGGREGATE TP SYSTEM       │  │
│  │                             │  │                             │  │
│  │  • LIMIT orders on exchange │  │  • Background monitoring    │  │
│  │  • One per filled DCA leg   │  │  • Polls every ~5 seconds   │  │
│  │  • Exchange executes        │  │  • Checks price vs target   │  │
│  │  • Instant when hit         │  │  • Market order if hit      │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
│               │                               │                     │
│               └───────────┬───────────────────┘                     │
│                           │                                         │
│                           ▼                                         │
│              ┌─────────────────────────┐                           │
│              │   FIRST TRIGGER WINS    │                           │
│              └─────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
2. What determines "first trigger wins"?
There is NO explicit coordination logic - it's implicit based on execution order. The "first trigger wins" is determined by:
Trigger	How It Wins
Per-Leg TP	Exchange fills the limit order → monitor detects → marks tp_hit=True → reduces position
Aggregate TP	Monitor detects price >= target → cancels ALL orders (including per-leg TPs) → market close
Key insight: If aggregate TP triggers first, it cancels all per-leg TP orders. If per-leg triggers first, aggregate check sees reduced quantity and adjusts. From position_manager.py:721-722:
if should_execute_tp:  # Aggregate triggered
    # 1. Cancel all open orders (INCLUDING per-leg TPs!)
    await order_service.cancel_open_orders_for_group(group_id)
Race condition scenario:
Timeline:
─────────────────────────────────────────────────────────────────────►
     │                    │                    │
     │                    │                    │
     ▼                    ▼                    ▼
  Leg 0 TP         Monitor polls          Aggregate
  hits on          (5s interval)          would trigger
  exchange                                 
     │                    │                    
     │              Sees Leg 0 TP hit         
     │              Recalculates avg          
     │              Aggregate check           
     │              with reduced qty          
No mutex or lock - relies on:
Per-leg TPs being on exchange (instant execution)
Aggregate being software-monitored (5s polling delay)
3. If per-leg TP hits first, does it only close that leg or everything?
Only that specific leg closes. The position continues with remaining legs. From order_management.py:267-297:
if status == "closed" or status == "filled":
    # Mark only THIS order's TP as hit
    dca_order.tp_hit = True
    dca_order.tp_executed_at = datetime.utcnow()
    
    # Create exit record for THIS leg only
    tp_fill_order = DCAOrder(
        group_id=dca_order.group_id,
        leg_index=999,  # Exit marker
        filled_quantity=filled_qty,  # Only this leg's quantity
        ...
    )
Example flow:
Initial state (Hybrid mode, tp_aggregate_percent=5%):
├── Leg 0: Entry $100, TP limit @ $102 (2%), qty=1.0
├── Leg 1: Entry $98, TP limit @ $100.45 (2.5%), qty=1.0
├── Leg 2: Entry $96, TP limit @ $98.88 (3%), qty=1.0
│
│ weighted_avg = $98.00
│ aggregate_tp = $98 × 1.05 = $102.90
│ total_qty = 3.0

Price rises to $102:
├── Leg 0 TP @ $102 FILLS (exchange executes limit)
│
│ Monitor detects Leg 0 TP hit:
│   - dca_order.tp_hit = True (Leg 0 only)
│   - Create exit record for 1.0 qty
│   - Call update_position_stats()

After Leg 0 TP:
├── Leg 0: CLOSED (TP hit)
├── Leg 1: Entry $98, TP limit @ $100.45, qty=1.0 (still active)
├── Leg 2: Entry $96, TP limit @ $98.88, qty=1.0 (still active)
│
│ Recalculated:
│ weighted_avg = ($98 + $96) / 2 = $97.00 (Leg 0 removed from avg)
│ aggregate_tp = $97 × 1.05 = $101.85 (target moved down!)
│ total_qty = 2.0
4. How are the remaining legs handled after a partial close?
Remaining legs continue with their per-leg TPs, AND aggregate monitoring continues with recalculated values. From position_manager.py:596-640:
for o in filled_orders:
    qty = o.filled_quantity
    price = o.avg_fill_price or o.price
    
    is_entry = (group_side == "long" and order_side == "buy") or \
               (group_side == "short" and order_side == "sell")

    if is_entry:
        # Add to position
        new_invested = current_invested_usd + (qty * price)
        new_qty = current_qty + qty
        current_avg_price = new_invested / new_qty
        current_qty = new_qty
        current_invested_usd = new_invested
    else:
        # EXIT (per-leg TP hit) - REDUCES position
        current_qty -= qty
        current_invested_usd = current_qty * current_avg_price
After per-leg TP hit, recalculation happens:
Weighted average recalculated excluding closed leg's contribution
Aggregate TP target moves (usually down for longs, as profitable legs exit)
Remaining per-leg TPs stay active on exchange
Aggregate monitoring continues with new values
Detailed example:
Before any TP (3 legs filled):
  Leg 0: qty=1.0 @ $100 (invested $100)
  Leg 1: qty=1.0 @ $98 (invested $98)
  Leg 2: qty=1.0 @ $96 (invested $96)
  
  total_invested = $294
  total_qty = 3.0
  weighted_avg = $294 / 3.0 = $98.00
  aggregate_tp = $98 × 1.05 = $102.90

After Leg 0 TP hits @ $102:
  Exit: qty=1.0 sold @ $102 (realized PnL = $2)
  
  Replay remaining:
  Leg 1: qty=1.0 @ $98 (invested $98)
  Leg 2: qty=1.0 @ $96 (invested $96)
  
  total_invested = $194
  total_qty = 2.0
  weighted_avg = $194 / 2.0 = $97.00  ← Improved!
  aggregate_tp = $97 × 1.05 = $101.85  ← Target moved down!

Remaining active:
  Leg 1 TP limit @ $100.45 (still on exchange)
  Leg 2 TP limit @ $98.88 (still on exchange)
  Aggregate monitoring @ $101.85 (recalculated target)
5. Hybrid TP Coordination Logic
There is NO explicit coordination code. The "hybrid" behavior emerges from:
Per-leg TP orders being placed normally
Aggregate check running with tp_mode in ["aggregate", "hybrid"]
Per-Leg Component (same as per_leg mode)
From order_fill_monitor.py:130-138:
# Check if entry order filled
if order.status == OrderStatus.FILLED.value:
    updated_order = await order_service.check_tp_status(order)
    if updated_order.tp_hit:
        logger.info(f"TP hit for order {order.id}. Updating position stats.")
        await session.flush()
        await position_manager.update_position_stats(updated_order.group_id, session=session)
    continue
Aggregate Component (same as aggregate mode)
From position_manager.py:695-740:
# --- 4. Aggregate/Hybrid TP Execution Logic ---
# Only if we are holding a position and not already closing
if current_qty > 0 and position_group.status not in [PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED]:
    should_execute_tp = False
    
    # SAME CHECK FOR BOTH aggregate AND hybrid
    if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
        aggregate_tp_price = Decimal("0")
        if position_group.side.lower() == "long":
            aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
            if current_price >= aggregate_tp_price:
                should_execute_tp = True
        else:
            aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
            if current_price <= aggregate_tp_price:
                should_execute_tp = True
        
        if should_execute_tp:
            # Cancel ALL open orders (including remaining per-leg TPs)
            await order_service.cancel_open_orders_for_group(group_id)
            
            # Market close entire remaining position
            await order_service.place_market_order(
                quantity=current_qty,  # Whatever is left
                ...
            )
Complete Hybrid Flow Diagram
┌─────────────────────────────────────────────────────────────────────┐
│                    HYBRID MODE SETUP                                 │
│                                                                     │
│  Config: tp_mode="hybrid", tp_aggregate_percent=5%                  │
│  Per-leg: tp_percent=[2%, 2.5%, 3%, 3.5%]                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DCA Orders Created with TP Prices (same as per_leg mode)           │
│                                                                     │
│  Leg 0: Entry $100, TP $102.00                                      │
│  Leg 1: Entry $98, TP $100.45                                       │
│  Leg 2: Entry $96, TP $98.88                                        │
│  Leg 3: Entry $94, TP $97.29                                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  As DCAs Fill → Per-Leg TP Orders Placed on Exchange                │
│                                                                     │
│  Leg 0 fills → LIMIT SELL @ $102.00 placed                          │
│  Leg 1 fills → LIMIT SELL @ $100.45 placed                          │
│  ...                                                                │
└─────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌───────────────────────────┐     ┌───────────────────────────┐
│   PER-LEG TP SYSTEM       │     │   AGGREGATE TP SYSTEM     │
│                           │     │                           │
│   Exchange monitors       │     │   update_position_stats() │
│   limit orders            │     │   runs after every fill   │
│                           │     │                           │
│   If price hits $102:     │     │   Calculates:             │
│   → Leg 0 TP executes     │     │   avg = $97.00            │
│   → Instant fill          │     │   target = $97 × 1.05     │
│                           │     │          = $101.85        │
│                           │     │                           │
│                           │     │   If price >= $101.85:    │
│                           │     │   → Aggregate triggers    │
└───────────────────────────┘     └───────────────────────────┘
            │                                   │
            │                                   │
            ▼                                   ▼
┌───────────────────────────────────────────────────────────────────┐
│                     SCENARIO A: Per-Leg Wins                       │
│                                                                   │
│  Price hits $102 (Leg 0 TP target)                                │
│                                                                   │
│  1. Exchange fills Leg 0 TP limit order                           │
│  2. Monitor detects tp_hit=True                                   │
│  3. update_position_stats() called                                │
│  4. Recalculates: qty=2.0, avg=$97, aggregate_target=$101.85      │
│  5. Remaining legs continue with their TPs                        │
│  6. Aggregate monitoring continues with new values                │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│                     SCENARIO B: Aggregate Wins                     │
│                                                                   │
│  Price jumps to $103 (above aggregate target $101.85)             │
│                                                                   │
│  1. update_position_stats() runs (5s polling)                     │
│  2. Detects: current_price >= aggregate_tp_price                  │
│  3. cancel_open_orders_for_group()                                │
│     - Cancels Leg 0 TP @ $102                                     │
│     - Cancels Leg 1 TP @ $100.45                                  │
│     - Cancels Leg 2 TP @ $98.88                                   │
│     - Cancels Leg 3 TP @ $97.29                                   │
│  4. place_market_order() - SELL entire 4.0 qty @ ~$103            │
│  5. Status = CLOSING → CLOSED                                     │
└───────────────────────────────────────────────────────────────────┘
Potential Issues with Hybrid Mode
Issue	Description	Impact
No true OCO	Can't link per-leg + aggregate on exchange	Relies on software polling
Race condition	Per-leg could fill during aggregate market close	Possible over-sell
5s latency	Aggregate trigger delayed by polling	Price could move
No coordination flag	Both systems unaware of each other	Implicit behavior only
Partial fill edge case	What if aggregate triggers with partial per-leg fill?	Undefined behavior
Summary Table
Question	Answer
Both systems run?	Yes - per-leg limits + aggregate monitoring
"First trigger wins"?	Implicit - no explicit coordination
Per-leg hits first?	Only that leg closes, others continue
Remaining legs?	Continue with recalculated aggregate target
Aggregate hits first?	Cancels all per-leg TPs, market closes everything
Coordination logic?	None explicit - same code as aggregate/per_leg
Effective Hybrid Behavior
Per-Leg TP Targets:    $102.00  $100.45  $98.88  $97.29
                          │        │        │       │
                          ▼        ▼        ▼       ▼
Price ──────────────────────────────────────────────────────►
                                        │
Aggregate TP Target: ───────────────────┼─── $101.85
                                        │
                                        │
If price rises gradually:               │
  → Per-leg TPs hit one by one          │
  → Position reduces incrementally      │
  → Aggregate target recalculates       │
                                        │
If price spikes above aggregate:        │
  → Aggregate triggers                  │
  → ALL per-leg TPs cancelled           │
  → Entire position market closed       │


TP Order Exchange Management Analysis
1. Are TP orders placed as limit orders or monitored internally?
Per-Leg TP: LIMIT orders placed directly on exchange. From order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    """Places a Take-Profit order for a filled DCA order."""
    
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
    
    if dca_order.tp_order_id:
        return dca_order  # Already exists
    
    try:
        tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
        tp_price = dca_order.tp_price
        
        # Place LIMIT order on exchange
        exchange_order_data = await self.exchange_connector.place_order(
            symbol=dca_order.symbol,
            order_type="LIMIT",      # ← LIMIT order on exchange
            side=tp_side,
            quantity=dca_order.filled_quantity,
            price=tp_price
        )
        
        dca_order.tp_order_id = exchange_order_data["id"]
        await self.dca_order_repository.update(dca_order)
Aggregate TP: Monitored internally via polling. From position_manager.py:700-709:
# Background check in update_position_stats()
if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
    if position_group.side.lower() == "long":
        aggregate_tp_price = current_avg_price * (1 + tp_aggregate_percent / 100)
        if current_price >= aggregate_tp_price:  # ← Internal price check
            should_execute_tp = True
Summary:
TP Type	Mechanism	Where Monitored
Per-Leg	LIMIT order	Exchange order book
Aggregate	Price polling	Internal (5s interval)
Hybrid	Both	Exchange + Internal
2. If price hits TP but order doesn't fill, what happens?
The TP order remains OPEN on exchange - no automatic fallback. From order_management.py:252-304:
async def check_tp_status(self, dca_order: DCAOrder) -> DCAOrder:
    """Checks the status of the TP order associated with this DCA order."""
    
    if not dca_order.tp_order_id:
        return dca_order

    try:
        exchange_order_data = await self.exchange_connector.get_order_status(
            order_id=dca_order.tp_order_id,
            symbol=dca_order.symbol
        )
        
        status = exchange_order_data["status"].lower()
        
        # Only acts on "closed" or "filled"
        if status == "closed" or status == "filled":
            dca_order.tp_hit = True
            dca_order.tp_executed_at = datetime.utcnow()
            # ... create exit record
        
        # NO HANDLING FOR:
        # - status == "open" (TP not filled yet)
        # - status == "partially_filled"
        # - status == "expired"
        
        return dca_order
Scenarios where TP might not fill:
Scenario	What Happens	System Response
Price touches TP briefly	Order may not execute	TP stays OPEN, keeps waiting
Low liquidity	Partial fill or no fill	No special handling
Price gaps past TP	Order sits unfilled	Keeps monitoring
Order expires (if time-limited)	Exchange cancels	Not detected
⚠️ Gap identified: No handling for:
TP orders that remain unfilled for extended periods
Partial TP fills
Price that gaps past TP level
3. How is slippage handled (risk.max_slippage_percent)?
⚠️ max_slippage_percent is DEFINED but NOT IMPLEMENTED. From webhook_payloads.py:38-41:
class RiskInfo(BaseModel):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_percent: float  # ← Defined in schema
Search results: max_slippage is NOT used anywhere in the services:
Grep pattern: max_slippage|slippage|risk\.max|risk_info
Path: backend/app/services/
Result: No matches found
Current behavior:
Order Type	Slippage Handling
Per-Leg TP (LIMIT)	None - fills at exact price or not at all
Aggregate TP (MARKET)	None - accepts any fill price
DCA Entry (LIMIT)	None - fills at exact price or not at all
DCA Entry (MARKET)	None - accepts any fill price
Force Close (MARKET)	None - accepts any fill price
What should happen with slippage protection:
# NOT IMPLEMENTED - hypothetical code
async def place_market_order_with_slippage_protection(...):
    current_price = await connector.get_current_price(symbol)
    
    max_slippage = risk_config.max_slippage_percent  # e.g., 0.5%
    
    if side == "SELL":
        min_acceptable_price = current_price * (1 - max_slippage / 100)
    else:
        max_acceptable_price = current_price * (1 + max_slippage / 100)
    
    # Option 1: Use limit order instead of market
    # Option 2: Check fill price after execution and alert
    # Option 3: Use exchange's built-in slippage protection
4. TP Order Placement and Monitoring Code
Step 1: TP Order Placement (when DCA fills)
From order_fill_monitor.py:195-203:
# Handle filled orders
if updated_order.status == OrderStatus.FILLED.value:
    # Flush order status update
    await session.flush()
    
    # Update position stats
    await position_manager.update_position_stats(updated_order.group_id, session=session)
    
    # Place TP order on exchange
    await order_service.place_tp_order(updated_order)
    logger.info(f"✓ Successfully placed TP order for {updated_order.id}")
Step 2: TP Order Creation
From order_management.py:116-149:
async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
    """Places a Take-Profit order for a filled DCA order."""
    
    # 1. Validate preconditions
    if dca_order.status != OrderStatus.FILLED:
        raise APIError("Cannot place TP order for unfilled order.")
    
    if dca_order.tp_order_id:
        return dca_order  # Already has TP
    
    try:
        # 2. Determine TP parameters
        tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
        tp_price = dca_order.tp_price  # Pre-calculated
        
        # 3. Place LIMIT order on exchange
        exchange_order_data = await self.exchange_connector.place_order(
            symbol=dca_order.symbol,
            order_type="LIMIT",
            side=tp_side,
            quantity=dca_order.filled_quantity,
            price=tp_price
        )
        
        # 4. Store exchange order ID
        dca_order.tp_order_id = exchange_order_data["id"]
        await self.dca_order_repository.update(dca_order)
        return dca_order
        
    except Exception as e:
        logger.error(f"Failed to place TP order for {dca_order.id}: {e}")
        # Don't raise - avoid crashing monitor loop
        return dca_order
Step 3: TP Order Monitoring
From order_fill_monitor.py:130-138:
for order in orders_to_check:
    try:
        # If already filled (entry), check the TP order
        if order.status == OrderStatus.FILLED.value:
            updated_order = await order_service.check_tp_status(order)
            if updated_order.tp_hit:
                logger.info(f"TP hit for order {order.id}. Updating position stats.")
                await session.flush()
                await position_manager.update_position_stats(updated_order.group_id, session=session)
            continue
Step 4: TP Status Check
From order_management.py:252-304:
async def check_tp_status(self, dca_order: DCAOrder) -> DCAOrder:
    """Checks the status of the TP order associated with this DCA order."""
    
    if not dca_order.tp_order_id:
        return dca_order

    try:
        # 1. Query exchange for TP order status
        exchange_order_data = await self.exchange_connector.get_order_status(
            order_id=dca_order.tp_order_id,
            symbol=dca_order.symbol
        )
        
        status = exchange_order_data["status"].lower()
        
        # 2. Handle filled TP
        if status == "closed" or status == "filled":
            dca_order.tp_hit = True
            dca_order.tp_executed_at = datetime.utcnow()
            await self.dca_order_repository.update(dca_order)
            
            # 3. Create exit record for stats tracking
            tp_side = "sell" if dca_order.side.lower() == "buy" else "buy"
            filled_qty = Decimal(str(exchange_order_data.get("filled", dca_order.filled_quantity)))
            avg_price = Decimal(str(exchange_order_data.get("average", dca_order.tp_price)))
            
            tp_fill_order = DCAOrder(
                group_id=dca_order.group_id,
                pyramid_id=dca_order.pyramid_id,
                leg_index=999,  # Special marker for TP exits
                symbol=dca_order.symbol,
                side=tp_side,
                order_type=OrderType.LIMIT,
                price=avg_price,
                quantity=filled_qty,
                status=OrderStatus.FILLED.value,
                exchange_order_id=str(exchange_order_data.get("id")),
                filled_quantity=filled_qty,
                avg_fill_price=avg_price,
                filled_at=datetime.utcnow(),
                submitted_at=datetime.utcnow(),
                gap_percent=Decimal("0"),
                weight_percent=Decimal("0"),
                tp_percent=Decimal("0"),
                tp_price=Decimal("0")
            )
            await self.dca_order_repository.create(tp_fill_order)
            
            logger.info(f"TP order {dca_order.tp_order_id} hit! Created TP fill record.")
        
        return dca_order
        
    except Exception as e:
        logger.error(f"Failed to check TP status for order {dca_order.id}: {e}")
        return dca_order
Complete TP Order Lifecycle
┌─────────────────────────────────────────────────────────────────────┐
│                    DCA ENTRY FILLS                                   │
│                                                                     │
│  order_fill_monitor detects: status = FILLED                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  place_tp_order()                                                   │
│                                                                     │
│  1. Validate: order.status == FILLED                                │
│  2. Check: tp_order_id is None (not already placed)                 │
│  3. Calculate: tp_side = opposite of entry                          │
│  4. Get: tp_price from dca_order (pre-calculated)                   │
│  5. Place: LIMIT order on exchange                                  │
│  6. Store: exchange_order_id as tp_order_id                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Exchange Order Book                                                │
│                                                                     │
│  LIMIT SELL 1.0 BTC @ $102.00                                       │
│  Status: OPEN                                                       │
│  Waiting for price to hit...                                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ (Monitor polls every 5 seconds)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  check_tp_status() - Each poll cycle                                │
│                                                                     │
│  1. Query exchange: get_order_status(tp_order_id)                   │
│  2. Check status:                                                   │
│     - "open" → Continue waiting (no action)                         │
│     - "closed"/"filled" → TP HIT!                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  Status: OPEN           │     │  Status: FILLED         │
│                         │     │                         │
│  • Continue monitoring  │     │  • tp_hit = True        │
│  • Check again in 5s    │     │  • Create exit record   │
│                         │     │  • Update position stats│
└─────────────────────────┘     └─────────────────────────┘
TP Order Data Flow
┌─────────────────────────────────────────────────────────────────────┐
│                    DCAOrder Record                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Entry Order Fields:                                                │
│  ├── exchange_order_id: "binance_123456"  (entry order)             │
│  ├── status: "filled"                                               │
│  ├── filled_quantity: 1.0                                           │
│  ├── avg_fill_price: $99.50                                         │
│  │                                                                  │
│  TP Order Fields:                                                   │
│  ├── tp_price: $102.00  (pre-calculated)                            │
│  ├── tp_order_id: "binance_789012"  (TP order on exchange)          │
│  ├── tp_hit: False → True (when TP fills)                           │
│  └── tp_executed_at: None → timestamp                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ When TP fills
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              New DCAOrder Record (Exit)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  leg_index: 999  (special marker for TP exit)                       │
│  side: "sell"  (opposite of entry)                                  │
│  status: "filled"                                                   │
│  filled_quantity: 1.0                                               │
│  avg_fill_price: $102.00                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
Summary Table
Question	Answer
TP order type	Per-Leg: LIMIT on exchange, Aggregate: Internal monitoring
TP doesn't fill	Stays OPEN, no timeout or fallback
Partial TP fill	Not handled - only checks for "closed"/"filled"
Slippage protection	NOT IMPLEMENTED - max_slippage_percent defined but unused
Monitoring interval	5 seconds polling
Exit record	Created with leg_index=999 when TP hits
Gaps and Issues Identified
Issue	Description	Impact
No slippage protection	max_slippage_percent unused	Market orders may execute at unfavorable prices
No TP timeout	Unfilled TPs wait forever	Capital tied up indefinitely
No partial TP handling	Only "filled" status checked	Partial TP fills ignored
No TP adjustment	TP price fixed at creation	Can't adapt to market conditions
No stale order detection	Orders can sit for days	No alerts or auto-cleanup
5s latency	Polling-based monitoring	Price could move significantly


Pyramid Aggregate TP Mode (NEW)
==============================

A fourth TP mode has been added: `pyramid_aggregate`. This mode allows each pyramid within a position group to have its own independent aggregate TP evaluation.

1. What is Pyramid Aggregate TP Mode?

Unlike regular `aggregate` mode which closes the entire position when a single TP target is hit, `pyramid_aggregate` mode evaluates each pyramid independently and closes them separately when their individual TP targets are reached.

Location: position_manager.py:416-571

```python
elif position_group.tp_mode == "pyramid_aggregate" and position_group.tp_aggregate_percent > 0:
    await self._check_pyramid_aggregate_tp(...)
```

2. How Does It Work?

For each pyramid in the position group:

Step 1: Calculate Pyramid-Specific Weighted Average Entry
```python
for order in pyramid_filled_orders:
    qty = order.filled_quantity or order.quantity
    price = order.avg_fill_price or order.price
    total_qty += qty
    total_value += qty * price

pyramid_avg_entry = total_value / total_qty
```

Step 2: Get Pyramid-Specific TP Percentage
```python
pyramid_tp_percents = pyramid_config.get("pyramid_tp_percents", {})
pyramid_index_key = str(pyramid.pyramid_index)

if pyramid_index_key in pyramid_tp_percents:
    tp_percent = Decimal(str(pyramid_tp_percents[pyramid_index_key]))
else:
    tp_percent = position_group.tp_aggregate_percent  # Fallback
```

Step 3: Calculate and Check TP Target
```python
if position_group.side.lower() == "long":
    pyramid_tp_price = pyramid_avg_entry * (1 + tp_percent / 100)
    tp_triggered = current_price >= pyramid_tp_price
else:
    pyramid_tp_price = pyramid_avg_entry * (1 - tp_percent / 100)
    tp_triggered = current_price <= pyramid_tp_price
```

3. Per-Pyramid TP Percentages

Configuration supports per-pyramid TP percentages via `tp_settings.pyramid_tp_percents`:

```json
{
  "tp_settings": {
    "tp_aggregate_percent": 3.0,  // Default fallback
    "pyramid_tp_percents": {
      "0": 2.0,    // Pyramid 0: 2% TP
      "1": 2.5,    // Pyramid 1: 2.5% TP
      "2": 3.0,    // Pyramid 2: 3% TP
      "3": 4.0     // Pyramid 3: 4% TP
    }
  }
}
```

Location: grid_config.py:31-35

```python
class TPSettings(BaseModel):
    tp_aggregate_percent: Decimal = Field(default=Decimal("0"))
    pyramid_tp_percents: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Per-pyramid TP percentages. Key is pyramid index, value is TP %."
    )
```

4. Key Differences from Other TP Modes

Aspect	Per-Leg	Aggregate	Hybrid	Pyramid Aggregate
Evaluation Level	Each DCA order	Entire position	Both	Each pyramid
TP Price Basis	Pre-calculated per order	Position weighted avg	Both	Pyramid weighted avg
Closes	One order at a time	Entire position	First wins	One pyramid at a time
Independent Targets	No	No	No	Yes - per pyramid
Configurable Per-Entry	Yes (tp_percent per level)	No	Yes	Yes (pyramid_tp_percents)

5. Execution Flow

```
Position with 3 Pyramids (pyramid_aggregate mode):

┌─────────────────────────────────────────────────────────────────────┐
│  Pyramid 0: Entry $100 avg, TP target 2% = $102                     │
│  Pyramid 1: Entry $95 avg, TP target 2.5% = $97.375                 │
│  Pyramid 2: Entry $90 avg, TP target 3% = $92.70                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Price rises to $93:                                                 │
│  - Pyramid 0: $93 < $102 → NOT triggered                            │
│  - Pyramid 1: $93 < $97.375 → NOT triggered                         │
│  - Pyramid 2: $93 >= $92.70 → TRIGGERED! → Close Pyramid 2          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Price continues to $98:                                             │
│  - Pyramid 0: $98 < $102 → NOT triggered                            │
│  - Pyramid 1: $98 >= $97.375 → TRIGGERED! → Close Pyramid 1         │
│  - Pyramid 2: Already closed                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Price hits $102:                                                    │
│  - Pyramid 0: $102 >= $102 → TRIGGERED! → Close Pyramid 0           │
│  - Entire position now closed                                        │
└─────────────────────────────────────────────────────────────────────┘
```

6. Summary

Question	Answer
Mode name	pyramid_aggregate
Scope	Each pyramid evaluated independently
TP calculation	Pyramid's weighted avg × (1 + pyramid_tp_percent%)
Per-pyramid config	tp_settings.pyramid_tp_percents dict
Fallback	tp_aggregate_percent if no specific config
Order type	Market order on trigger (per pyramid)


Risk Engine Implementation
==========================

The Risk Engine is a multi-component system that manages position risk through timer management, loser/winner selection, and simultaneous offset execution.

1. Risk Engine Architecture

Location: backend/app/services/risk/

Module	File	Purpose
risk_engine.py	Main orchestrator	Coordinates all components, monitoring loop
risk_timer.py	Timer management	Start, reset, expire timer lifecycle
risk_selector.py	Selection algorithms	Identify worst loser and best winners
risk_executor.py	Execution calculations	Partial close quantity calculations

2. Risk Action Types

Location: models/risk_action.py:22-28

```python
class RiskActionType(str, Enum):
    OFFSET_LOSS = "offset_loss"      # Loser + winners partially closed
    MANUAL_BLOCK = "manual_block"    # User blocked position from risk
    MANUAL_SKIP = "manual_skip"      # User skipped next evaluation
    MANUAL_CLOSE = "manual_close"    # User manually closed position
    ENGINE_CLOSE = "engine_close"    # Engine closed due to conditions
    TP_HIT = "tp_hit"               # Take-profit triggered
```

3. Timer Management

Location: risk_timer.py

Timer States:
```
NULL ──► TIMER_STARTED ──► TIMER_EXPIRED ──► ELIGIBLE
  ▲              │                              │
  └──────────────┴──── RESET (conditions change)
```

Database Fields on PositionGroup (position_group.py:101-105):
```python
risk_timer_start = Column(DateTime)       # When timer started
risk_timer_expires = Column(DateTime)     # When timer expires
risk_eligible = Column(Boolean)           # True if ready for offset
risk_blocked = Column(Boolean)            # User can block from evaluation
risk_skip_once = Column(Boolean)          # Skip next evaluation only
```

Timer Start Conditions:
1. Required pyramids complete (all DCAs filled)
2. Loss threshold exceeded (e.g., -1.5% or worse)
3. Timer set to expire after `post_pyramids_wait_minutes`

Timer Reset Triggers:
- New pyramid received (pyramid_count increases)
- Price improved beyond loss threshold
- Pyramids no longer complete

4. Offset Execution Flow

Location: risk_engine.py:150-354

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Get active positions for user                                   │
│  2. Update timers for all positions                                 │
│  3. Select loser and winners                                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LOSER SELECTION (risk_selector.py)                                 │
│                                                                     │
│  Eligibility:                                                       │
│  - ACTIVE status                                                    │
│  - Not blocked (risk_blocked = False)                               │
│  - Not skipped (risk_skip_once = False)                             │
│  - Required pyramids complete                                       │
│  - Loss threshold exceeded                                          │
│  - Timer expired (risk_timer_expires <= now)                        │
│                                                                     │
│  Ranking: (highest_loss_percent, highest_loss_usd, oldest_trade)    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  WINNER SELECTION                                                   │
│                                                                     │
│  Required USD = abs(loser.unrealized_pnl_usd)                       │
│  Select top N winners (max_winners_to_combine, default 3)           │
│  Ranked by unrealized profit USD (descending)                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PARTIAL CLOSE CALCULATIONS (risk_executor.py)                      │
│                                                                     │
│  For each winner:                                                   │
│    profit_per_unit = current_price - weighted_avg_entry             │
│    quantity_to_close = profit_to_take / profit_per_unit             │
│    (Rounded to exchange precision, validated against minimums)      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SIMULTANEOUS EXECUTION                                             │
│                                                                     │
│  results = await asyncio.gather(*close_tasks, return_exceptions=True)│
│                                                                     │
│  All market orders hit exchange at the same time!                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Record RiskAction with details + Broadcast Telegram notification   │
└─────────────────────────────────────────────────────────────────────┘
```

5. Risk Engine Configuration

Location: schemas/grid_config.py:212-323

Parameter	Type	Default	Description
max_open_positions_global	int	10	Maximum positions across all symbols
max_open_positions_per_symbol	int	1	Max positions per trading pair
max_total_exposure_usd	Decimal	10000	Total capital exposed limit
max_realized_loss_usd	Decimal	500	Circuit breaker (auto-pauses queue)
loss_threshold_percent	Decimal	-1.5	Loss % that triggers timer start
required_pyramids_for_timer	int	3	Pyramids needed before timer starts
post_pyramids_wait_minutes	int	15	Minutes to wait after conditions met
max_winners_to_combine	int	3	Max winners to close for offsetting
evaluate_on_fill	bool	False	Trigger evaluation on position fill
evaluate_interval_seconds	int	60	Polling interval for evaluation
engine_paused_by_loss_limit	bool	False	Engine auto-paused due to max loss
engine_force_stopped	bool	False	Engine manually stopped by user

6. Risk API Endpoints

Location: api/risk.py

Endpoint	Method	Purpose
/risk/status	GET	Get current status, loser/winners, timer states
/risk/run-evaluation	POST	Manually trigger single evaluation
/risk/{group_id}/block	POST	Block position from risk evaluation
/risk/{group_id}/unblock	POST	Unblock position
/risk/{group_id}/skip	POST	Skip next evaluation for position
/risk/force-stop	POST	Stop queue (risk engine continues)
/risk/force-start	POST	Resume queue after stop
/risk/sync-exchange	POST	Sync local PnL with exchange

7. RiskAction Model

Location: models/risk_action.py:31-71

Field	Type	Purpose
id	UUID	Primary key
group_id	UUID FK	Position group involved
action_type	RiskActionType	Type of action (OFFSET_LOSS, etc.)
timestamp	DateTime	When action occurred
loser_group_id	UUID FK	The losing position
loser_pnl_usd	Decimal	Loss amount
winner_details	JSON	Array of {group_id, pnl_usd, symbol, quantity_closed}
exit_price	Decimal	Exit price for close actions
entry_price	Decimal	Entry price
pnl_percent	Decimal	PnL percentage
realized_pnl_usd	Decimal	Realized profit/loss
quantity_closed	Decimal	Amount closed
duration_seconds	Decimal	How long position was held
notes	String	Additional details

8. Risk Engine Example Scenario

```
BEFORE OFFSET:
┌─────────────────────────────────────────────────────────────────────┐
│  LOSER: BTCUSDT Long                                                 │
│  - Entry: $100, Current: $95                                        │
│  - Qty: 1.0 BTC                                                     │
│  - Unrealized PnL: -$5.00 (-5%)                                     │
│  - Timer EXPIRED, ELIGIBLE                                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  WINNER 1: ETHUSDT Long                                              │
│  - Entry: $2,000, Current: $2,100                                   │
│  - Qty: 2.0 ETH                                                     │
│  - Unrealized PnL: +$200 (+5%)                                      │
│  - Available profit: $200                                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  WINNER 2: SOLUSDT Long                                              │
│  - Entry: $50, Current: $55                                         │
│  - Qty: 10.0 SOL                                                    │
│  - Unrealized PnL: +$50 (+10%)                                      │
│  - Available profit: $50                                            │
└─────────────────────────────────────────────────────────────────────┘

EXECUTION:
- Required to offset: $5.00 (loser's loss)
- From WINNER 1: Close 0.025 ETH ($5.25 profit covers $5.00)
- LOSER: Market close entire 1.0 BTC

AFTER OFFSET:
- BTC position CLOSED with -$5.00 realized loss
- ETH position REDUCED by 0.025 ETH with +$5.25 realized profit
- NET: +$0.25 realized profit (loss offset + small gain)
- SOL position unchanged (wasn't needed)
```

9. Summary

Question	Answer
What triggers risk evaluation?	Timer expiration + eligibility criteria
How is loser selected?	Highest loss %, then USD, then oldest
How are winners selected?	Top N by unrealized profit USD
Are orders simultaneous?	Yes - asyncio.gather() executes all at once
What gets recorded?	RiskAction with loser, winners, quantities
Can users control it?	Yes - block, skip, force-stop options

---

# Recent Architecture Refactoring (December 2025)

This section documents the major architectural improvements made to the codebase.

## 1. Exchange Configuration Service

**Location:** `backend/app/services/exchange_config_service.py`

A centralized service for extracting and validating exchange configurations from user credentials. This eliminates duplicated code across signal_router, positions, risk_engine, and dashboard.

### Key Features

| Feature | Description |
|---------|-------------|
| Multi-exchange support | Handles both legacy single-key format and new multi-exchange format |
| Legacy fallback | Automatically detects and converts old `encrypted_data` format |
| Connector initialization | Provides ready-to-use exchange connectors |
| Validation | Validates configuration before returning |

### API Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `get_exchange_config(user, target_exchange)` | Extract exchange config for specific exchange | `Tuple[str, Dict]` |
| `get_connector(user, target_exchange)` | Get initialized ExchangeInterface | `ExchangeInterface` |
| `get_all_configured_exchanges(user)` | Get all exchange configs for user | `Dict[str, Dict]` |
| `has_valid_config(user, exchange)` | Check if valid config exists | `bool` |

### Configuration Format Handling

```
Legacy Format (single exchange):
{
  "encrypted_data": "base64_encrypted_string"
}

Multi-Exchange Format:
{
  "binance": {"encrypted_data": "..."},
  "bybit": {"encrypted_data": "..."}
}
```

### Usage Example

```python
from app.services.exchange_config_service import ExchangeConfigService, ExchangeConfigError

try:
    connector = ExchangeConfigService.get_connector(user, "binance")
    # Use connector...
except ExchangeConfigError as e:
    logger.error(f"Exchange config error: {e}")
```

---

## 2. Risk Engine Refactoring

The Risk Engine has been refactored into a modular architecture with separate concerns.

### Module Structure

```
backend/app/services/risk/
├── __init__.py              # Exports
├── risk_engine.py           # Main orchestrator (RiskEngineService)
├── risk_selector.py         # Loser/winner selection algorithms
├── risk_timer.py            # Timer management logic
└── risk_executor.py         # Offset execution calculations
```

### 2.1 Risk Selector Module

**Location:** `backend/app/services/risk/risk_selector.py`

Pure selection logic for filtering eligible losers and selecting top winners.

#### Key Functions

| Function | Purpose |
|----------|---------|
| `_check_pyramids_complete(pg, required_pyramids)` | Check if required pyramids have ALL DCAs filled |
| `_filter_eligible_losers(positions, config)` | Filter positions eligible for loss offset |
| `_select_top_winners(positions, count, exclude_id)` | Select top profitable positions |
| `select_loser_and_winners(positions, config)` | Main selection logic returning loser, winners, required_usd |

#### Eligibility Criteria

A position is eligible for loss offset when ALL conditions are met:

1. Status is ACTIVE
2. Required number of pyramids are filled (all DCAs complete)
3. Loss threshold is exceeded (`unrealized_pnl_percent <= loss_threshold_percent`)
4. Timer has expired (`risk_timer_expires <= now`)
5. Not blocked (`risk_blocked = False`)
6. Not skip_once flagged (`risk_skip_once = False`)

#### Selection Priority

**Loser Selection (by % loss):**
1. Highest loss percentage (primary)
2. Highest unrealized loss USD (secondary)
3. Oldest trade (tertiary)

**Winner Selection (by $ profit):**
- Rank all winning positions by unrealized profit USD
- Select up to `max_winners_to_combine` (default: 3)
- Exclude the loser from winner selection

### 2.2 Risk Timer Module

**Location:** `backend/app/services/risk/risk_timer.py`

Handles starting, resetting, and expiring risk timers for positions.

#### Timer State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│  Timer STARTS when BOTH conditions are met:                    │
│  1. Required pyramids are complete (all DCAs filled)           │
│  2. Loss threshold is exceeded                                 │
│                                                                 │
│  Timer RESETS (stops and clears) when:                         │
│  - A new pyramid is received (pyramid_count increases)         │
│  - Loss threshold is no longer exceeded (price improved)       │
│  - Pyramids are no longer complete (should not happen)         │
│                                                                 │
│  Timer EXPIRES when:                                           │
│  - risk_timer_expires <= now                                   │
│  - Position becomes eligible for offset                        │
└─────────────────────────────────────────────────────────────────┘
```

#### Telegram Notifications

The timer module broadcasts Telegram events:
- `timer_started` - When timer begins countdown
- `timer_expired` - When timer expires and position is eligible
- `timer_reset` - When timer is reset due to conditions changing

### 2.3 Risk Executor Module

**Location:** `backend/app/services/risk/risk_executor.py`

Handles calculating partial close quantities and precision handling.

#### Partial Close Calculation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  For each winner:                                               │
│  1. Get exchange connector and precision rules                  │
│  2. Calculate available profit = unrealized_pnl_usd             │
│  3. profit_to_take = min(available_profit, remaining_needed)    │
│  4. Get current price from exchange                             │
│  5. profit_per_unit = current_price - weighted_avg_entry        │
│     (For shorts: weighted_avg_entry - current_price)            │
│  6. quantity_to_close = profit_to_take / profit_per_unit        │
│  7. Round to step_size                                          │
│  8. Validate against min_notional                               │
│  9. Cap at total_filled_quantity if needed                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Position Manager Refactoring

The Position Manager has been split into focused modules.

### Module Structure

```
backend/app/services/position/
├── __init__.py              # Exports and re-exports exceptions
├── position_manager.py      # Main orchestrator (PositionManagerService)
├── position_creator.py      # Position and pyramid creation
└── position_closer.py       # Position exit and closing logic
```

### 3.1 Position Creator Module

**Location:** `backend/app/services/position/position_creator.py`

Handles creating new positions from signals and adding pyramids.

#### Key Functions

| Function | Purpose |
|----------|---------|
| `create_position_group_from_signal()` | Create new position group from signal |
| `handle_pyramid_continuation()` | Add pyramid to existing position |
| `_get_exchange_connector_for_user()` | Get exchange connector for user |

#### Custom Exceptions

| Exception | When Raised |
|-----------|-------------|
| `UserNotFoundException` | User not found in database |
| `DuplicatePositionException` | Attempting to create duplicate active position |

#### Position Creation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Get user from database                                      │
│  2. Get exchange connector                                      │
│  3. Fetch precision rules                                       │
│  4. Calculate DCA levels and quantities                         │
│  5. Create PositionGroup model                                  │
│  6. Create Pyramid model (pyramid_index=0)                      │
│  7. Create DCAOrder objects                                     │
│  8. Submit limit orders to exchange                             │
│  9. Broadcast entry signal via Telegram                         │
│  10. Update risk timer                                          │
│  11. Return PositionGroup                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Position Closer Module

**Location:** `backend/app/services/position/position_closer.py`

Handles closing positions, TP execution, and recording close actions.

#### Key Functions

| Function | Purpose |
|----------|---------|
| `execute_handle_exit_signal()` | Handle exit signal within provided session |
| `save_close_action()` | Save close action to risk_actions history |
| `_get_exchange_connector_for_user()` | Get exchange connector for user |

#### Close Action Recording

When a position is closed, a RiskAction record is created:

| Field | Source |
|-------|--------|
| `action_type` | Mapped from exit_reason (manual, engine, tp_hit, risk_offset) |
| `exit_price` | Current market price at close |
| `entry_price` | weighted_avg_entry from position |
| `pnl_percent` | Calculated from entry/exit prices |
| `realized_pnl_usd` | Actual realized PnL |
| `quantity_closed` | Amount that was closed |
| `duration_seconds` | Time from position open to close |

#### Exit Reason to Action Type Mapping

| exit_reason | RiskActionType |
|-------------|----------------|
| "manual" | MANUAL_CLOSE |
| "engine" | ENGINE_CLOSE |
| "tp_hit" | TP_HIT |
| "risk_offset" | OFFSET_LOSS |

---

## 4. Architecture Benefits

### Before Refactoring

```
services/
├── position_manager.py      # ~1200 lines, monolithic
├── risk_engine.py           # ~1300 lines, monolithic
└── exchange connector logic duplicated everywhere
```

### After Refactoring

```
services/
├── exchange_config_service.py   # Centralized, reusable
├── position/
│   ├── position_manager.py      # ~500 lines, orchestration only
│   ├── position_creator.py      # ~400 lines, creation logic
│   └── position_closer.py       # ~280 lines, exit logic
└── risk/
    ├── risk_engine.py           # ~880 lines, orchestration only
    ├── risk_selector.py         # ~130 lines, selection logic
    ├── risk_timer.py            # ~115 lines, timer logic
    └── risk_executor.py         # ~130 lines, execution logic
```

### Key Improvements

| Aspect | Improvement |
|--------|-------------|
| Separation of Concerns | Each module has a single responsibility |
| Testability | Pure functions can be unit tested independently |
| Maintainability | Smaller files are easier to understand and modify |
| Reusability | ExchangeConfigService eliminates code duplication |
| Debugging | Easier to trace issues to specific modules |

---

## 5. Updated Service Dependencies

### PositionManagerService

```python
PositionManagerService(
    session_factory: Callable[..., AsyncSession],
    user: User,
    position_group_repository_class: type[PositionGroupRepository],
    grid_calculator_service: GridCalculatorService,
    order_service_class: type[OrderService],
)
```

### RiskEngineService

```python
RiskEngineService(
    session_factory: callable,
    position_group_repository_class: type[PositionGroupRepository],
    risk_action_repository_class: type[RiskActionRepository],
    dca_order_repository_class: type[DCAOrderRepository],
    order_service_class: type[OrderService],
    risk_engine_config: RiskEngineConfig,
    polling_interval_seconds: int = None,
    user: Optional[User] = None
)
```

---

## 6. Migration Notes

### Using ExchangeConfigService

Old pattern (duplicated everywhere):
```python
encrypted_data = user.encrypted_api_keys
exchange_key = exchange_name.lower()
if isinstance(encrypted_data, dict):
    if exchange_key in encrypted_data:
        exchange_config = encrypted_data[exchange_key]
    # ... more conditional logic
connector = get_exchange_connector(exchange_name, exchange_config)
```

New pattern:
```python
from app.services.exchange_config_service import ExchangeConfigService

connector = ExchangeConfigService.get_connector(user, exchange_name)
```

### Importing from Split Modules

The main orchestrator classes re-export exceptions for backward compatibility:

```python
# Both work:
from app.services.position.position_manager import PositionManagerService, UserNotFoundException
from app.services.position.position_creator import UserNotFoundException
```

---

## 7. Telegram Broadcasting System

A comprehensive notification system for broadcasting trading events to Telegram channels.

### Architecture Overview

```
backend/app/
├── schemas/
│   └── telegram_config.py           # TelegramConfig schema
└── services/
    ├── telegram_broadcaster.py      # Core broadcaster class
    └── telegram_signal_helper.py    # Integration helpers
```

### 7.1 TelegramConfig Schema

**Location:** `backend/app/schemas/telegram_config.py`

#### Connection Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | False | Enable/disable broadcasting |
| `bot_token` | str | None | Telegram bot token |
| `channel_id` | str | None | Channel ID (e.g., @channelname or -100123456789) |
| `channel_name` | str | "AlgoMakers.Ai Signals" | Display name |
| `engine_signature` | str | (multiline) | Signature shown in messages |

#### Message Type Toggles

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `send_entry_signals` | bool | True | Entry signal messages |
| `send_exit_signals` | bool | True | Exit signal messages |
| `send_status_updates` | bool | True | Status transitions (PARTIALLY_FILLED, ACTIVE, etc.) |
| `send_dca_fill_updates` | bool | True | Individual DCA leg fill notifications |
| `send_pyramid_updates` | bool | True | New pyramid notifications |
| `send_tp_hit_updates` | bool | True | Take profit hit notifications |
| `send_failure_alerts` | bool | True | Order/position failure alerts |
| `send_risk_alerts` | bool | True | Risk timer event alerts |

#### Advanced Controls

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `update_existing_message` | bool | True | Edit existing message instead of new one (reduces spam) |
| `update_on_pyramid` | bool | True | Update message when pyramid fills |
| `show_unrealized_pnl` | bool | True | Show live unrealized P&L |
| `show_invested_amount` | bool | True | Show invested amount |
| `show_duration` | bool | True | Show position duration |
| `alert_loss_threshold_percent` | float | None | Alert if loss exceeds threshold |
| `alert_profit_threshold_percent` | float | None | Alert if profit exceeds threshold |

#### Quiet Hours

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `quiet_hours_enabled` | bool | False | Enable quiet hours |
| `quiet_hours_start` | str | None | Start time (e.g., "22:00") |
| `quiet_hours_end` | str | None | End time (e.g., "08:00") |
| `quiet_hours_urgent_only` | bool | True | Only send urgent alerts during quiet hours |

### 7.2 TelegramBroadcaster Class

**Location:** `backend/app/services/telegram_broadcaster.py`

The core class responsible for formatting and sending messages to Telegram.

#### Key Methods

| Method | Purpose |
|--------|---------|
| `send_entry_signal()` | Send entry signal with DCA levels, weights, TP targets |
| `send_exit_signal()` | Send exit signal with PnL and duration |
| `send_dca_fill()` | Send DCA leg fill notification |
| `send_status_change()` | Send status transition notification |
| `send_tp_hit()` | Send take profit hit notification |
| `send_risk_event()` | Send risk engine event notification |
| `send_failure()` | Send failure/error alert |
| `send_pyramid_added()` | Send new pyramid notification |

#### Helper Methods

| Method | Purpose |
|--------|---------|
| `_format_duration(hours)` | Format duration as "15m", "2.5h", "1.2d" |
| `_format_price(price, decimals)` | Format price with comma separators |
| `_format_pnl(percent, usd)` | Format P&L with sign and optional USD |
| `_is_quiet_hours()` | Check if current time is within quiet hours |
| `_should_send(is_urgent)` | Determine if message should be sent |

#### Message Format Example (Entry Signal)

```
📈 LONG Entry
BINANCE · BTCUSDT · 15m
🆔 a1b2c3d4

┌─ DCA Levels ─────────────────
│ ✅ 40%  50,000.00  → TP 52,500.00
│ ⏳ 30%  49,500.00  → TP 51,975.00
│ ⏳ 30%  49,000.00  → TP 51,450.00
└──────────────────────────────
🎯 Aggregate TP: 52,000.00 (+4.0%)

📊 PARTIALLY_FILLED (1/3 legs)
💰 Invested: $500.00
📈 Unrealized: +1.25% (+$6.25)
📈 Avg Entry: 50,000.00

🔷 Pyramid 1/5 · per_leg TP
⏱️ Open: 15m
```

### 7.3 Signal Helper Functions

**Location:** `backend/app/services/telegram_signal_helper.py`

High-level functions that integrate with the position lifecycle.

#### Broadcast Functions

| Function | Triggered By | Config Check |
|----------|--------------|--------------|
| `broadcast_entry_signal()` | New pyramid fills | `send_entry_signals` |
| `broadcast_exit_signal()` | Position closes | `send_exit_signals` |
| `broadcast_dca_fill()` | Individual DCA leg fills | `send_dca_fill_updates` |
| `broadcast_status_change()` | Position status changes | `send_status_updates` |
| `broadcast_tp_hit()` | Take profit triggered | `send_tp_hit_updates` |
| `broadcast_risk_event()` | Risk timer events | `send_risk_alerts` |
| `broadcast_failure()` | Order/position failures | `send_failure_alerts` |
| `broadcast_pyramid_added()` | New pyramid added | `send_pyramid_updates` |

#### Event Types

**Risk Events:**
- `timer_started` - Risk timer began countdown
- `timer_expired` - Timer expired, position eligible for offset
- `timer_reset` - Timer reset due to conditions changing
- `offset_executed` - Loss offset operation completed

**Exit Reasons:**
- `manual` - User-initiated close
- `engine` - System-initiated close
- `tp_hit` - Take profit triggered
- `risk_offset` - Closed by risk engine offset

### 7.4 Message Update Strategy

The system supports updating existing messages instead of sending new ones:

```
┌─────────────────────────────────────────────────────────────────┐
│  Message Update Flow                                            │
│                                                                 │
│  1. Initial message sent → telegram_message_id stored           │
│  2. On DCA fill → Edit existing message with updated progress   │
│  3. On pyramid fill → Update or send new based on config        │
│  4. On close → Send final exit message                          │
│                                                                 │
│  Benefits:                                                      │
│  - Reduces channel spam                                         │
│  - All position updates in one message thread                   │
│  - Better user experience                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 7.5 Quiet Hours Implementation

```
┌─────────────────────────────────────────────────────────────────┐
│  Quiet Hours Logic                                              │
│                                                                 │
│  Normal Hours: Send all enabled message types                   │
│                                                                 │
│  Quiet Hours (e.g., 22:00 - 08:00):                             │
│  ├─ If urgent_only=True:                                        │
│  │   ├─ Send: failure_alerts, risk_alerts                       │
│  │   └─ Skip: entry, exit, dca_fill, status, tp_hit, pyramid    │
│  └─ If urgent_only=False:                                       │
│      └─ Skip all notifications                                  │
│                                                                 │
│  Supports overnight ranges (start > end)                        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.6 Integration Points

The Telegram system is called from:

| Component | Event | Function Called |
|-----------|-------|-----------------|
| `position_creator.py` | Position created | `broadcast_entry_signal()` |
| `position_closer.py` | Position closed | `broadcast_exit_signal()` |
| `order_fill_monitor.py` | DCA leg fills | `broadcast_dca_fill()` |
| `order_fill_monitor.py` | Status changes | `broadcast_status_change()` |
| `position_manager.py` | TP hit | `broadcast_tp_hit()` |
| `risk_timer.py` | Timer events | `broadcast_risk_event()` |
| `position_creator.py` | Failures | `broadcast_failure()` |
| `position_creator.py` | Pyramid added | `broadcast_pyramid_added()` |

### 7.7 Configuration Storage

Telegram config is stored in the User model as JSON:

```python
# User model
telegram_config: Dict = Column(JSON, nullable=True)

# Example stored value
{
    "enabled": true,
    "bot_token": "123456789:ABC...",
    "channel_id": "@my_signals",
    "send_entry_signals": true,
    "send_exit_signals": true,
    "quiet_hours_enabled": true,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}
```

### 7.8 API Endpoints

**Location:** `backend/app/api/telegram.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/telegram/config` | GET | Get current Telegram config |
| `/telegram/config` | PUT | Update Telegram config |
| `/telegram/test` | POST | Send test message |

### 7.9 Frontend Component

**Location:** `frontend/src/components/TelegramSettings.tsx`

Features:
- Connection setup (bot token, channel ID)
- Message type toggle switches
- Quiet hours configuration
- Advanced display options
- Test message button

---

# Issue Status Review (December 2025)

This section tracks the current status of previously identified issues.

## Fixed Issues

### 1. Off-by-One Pyramid Bug ✅ FIXED

**Previous Issue:** The pyramid check used `pyramid_count < max_pyramids - 1` which blocked the last pyramid.

**Current Status:** Fixed in `signal_router.py:333`
```python
if existing_group.pyramid_count < dca_config.max_pyramids:
```

### 2. Race Condition Prevention ✅ IMPROVED

**Previous Issue:** No database constraint and `for_update` not used for critical lookups.

**Current Status:**
- Partial unique index added to `position_groups` table (lines 48-54 in `position_group.py`)
- `for_update=True` now used in signal_router.py for both exit (line 195) and entry (line 232) signals

```python
# position_group.py:48-54
__table_args__ = (
    Index(
        'uix_active_position_group',
        'user_id', 'symbol', 'exchange', 'timeframe', 'side',
        unique=True,
        postgresql_where="status NOT IN ('closed', 'failed')"
    ),
    ...
)
```

### 3. Failed Authentication Logging ✅ FIXED

**Previous Issue:** Failed webhook authentication attempts were not logged.

**Current Status:** All authentication failures now logged with IP address in `signature_validation.py`:
- Line 35: Invalid JSON payload
- Line 43: Missing secret
- Line 51: User not found
- Line 60: Invalid secret

### 4. Slippage Protection ✅ IMPLEMENTED

**Previous Issue:** `max_slippage_percent` was defined in webhook payload but not implemented.

**Current Status:** Fully implemented in `order_management.py:492-521`:
- Calculates actual slippage after order execution
- Supports "warn" (log only) and "reject" (raise SlippageExceededError) actions
- Integrated into exit signal flow via `position_closer.py`
- Configuration in `RiskEngineConfig` (grid_config.py:257-263)

### 5. TP Calculation from Actual Fill Price ✅ FIXED

**Previous Issue:** TP was calculated from planned entry price, not actual fill price.

**Current Status:** Fixed in `order_management.py:124-165`:
- `adjust_for_fill_price` parameter added (default: `True`)
- When enabled, recalculates TP based on `avg_fill_price` instead of planned price
- Logs when adjustment is made

```python
# order_management.py:148-162
if adjust_for_fill_price and dca_order.avg_fill_price and ...:
    # Recalculate TP based on actual fill price
    adjusted_tp_price = dca_order.avg_fill_price * (1 + tp_percent/100)
```

---

## Remaining Issues

### 1. reduce/reverse Intent Types ❌ NOT IMPLEMENTED

**Status:** Still falls through to entry/pyramid handling

**Location:** `signal_router.py:170-215`

The `execution_intent.type` only handles "exit" explicitly. Values like "reduce" and "reverse" fall through to the `else` block and are treated as regular entry signals.

```python
intent_type = signal.execution_intent.type.lower() if signal.execution_intent else "signal"
if intent_type == "exit":
    # Exit handling
else:  # "signal", "reduce", "reverse" all handled the same
    # Entry/pyramid handling
```

### 2. WAITING Status Never Used

**Status:** Still defined but never set in normal flow

**Location:** `position_group.py:29`

The `WAITING` status is defined in the enum but positions are created with `LIVE` status. This may be intentional design.

### 3. Hybrid TP Mode Partial Implementation

**Status:** Per-leg TP orders work, but aggregate fallback monitoring may need verification

The hybrid mode creates per-leg TP orders but also needs to monitor for aggregate TP if individual legs don't hit. This interaction should be tested.

---

## Summary Table

| Issue | Status | Location |
|-------|--------|----------|
| Off-by-one pyramid bug | ✅ Fixed | signal_router.py:333 |
| Race condition prevention | ✅ Improved | position_group.py:48-54, signal_router.py:195,232 |
| Failed auth logging | ✅ Fixed | signature_validation.py:35,43,51,60 |
| Slippage protection | ✅ Implemented | order_management.py:492-521 |
| TP from actual fill price | ✅ Fixed | order_management.py:124-165 |
| reduce/reverse intents | ❌ Not implemented | signal_router.py:170-215 |
| WAITING status unused | ⚠️ By design? | position_group.py:29 |
| Hybrid TP mode | ⚠️ Needs testing | position_manager.py |
