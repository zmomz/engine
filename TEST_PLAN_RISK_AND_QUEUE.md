# Risk Engine & Queue Logic Test Plan

This plan is designed to practically verify the **Execution Pool Queueing System** and the **Risk Engine Activation** logic by forcing the system into constrained states.

## User Configuration
Target User: `zmomz`
ID: `e7d6ae10-2a7d-4383-90d3-461c986e1e71`

## Phase 1: Setup & Constraints
To trigger limits and timers immediately, we will temporarily modify `users.json` for `zmomz`:
- `max_open_positions_global`: **2** (Forces queue after 2 distinct trades)
- `post_full_wait_minutes`: **0** (Allows Risk Engine to check immediately after max pyramids)
- `loss_threshold_percent`: **0.0** (Or a small number to ensure eligibility if PnL is even slightly negative)

## Phase 2: Queue & Priority Verification
**Objective:** Confirm that new signals queue when full, but pyramids bypass the queue.

1.  **Fill Slot 1**: Send `Buy BTCUSDT` (Binance).
    *   *Expectation*: Position created. Pool 1/2.
2.  **Fill Slot 2**: Send `Buy ETHUSDT` (Bybit).
    *   *Expectation*: Position created. Pool 2/2 (FULL).
3.  **Trigger Queue**: Send `Buy SOLUSDT` (Binance).
    *   *Expectation*: **QUEUED**. Log: "Pool full. Signal queued."
4.  **Verify Priority Bypass**: Send `Buy BTCUSDT` (Binance) - Pyramid.
    *   *Expectation*: **EXECUTED**. Existing positions bypass queue.
5.  **Verify Queue Addition**: Send `Buy ADAUSDT` (Bybit).
    *   *Expectation*: **QUEUED**.

## Phase 3: Risk Engine Activation
**Objective:** Confirm Risk Engine starts monitoring after 5 pyramids.

1.  **Max Out Pyramids**: Send 4 more `Buy BTCUSDT` signals.
    *   Total Pyramids: 5 (Max).
2.  **Observation**: Watch logs for `RiskEngine`.
    *   *Expectation*: "RiskEngine: Checking candidates..." and identifying BTCUSDT as a candidate (eligible due to 0 wait time).

## Phase 4: Cleanup
1.  Send `exit` signals for all symbols (BTC, ETH, SOL, ADA).
2.  Restore `users.json` to original configuration (`max: 10`, `wait: 15`).
