Execution Engine - Comprehensive Summary
System Overview
A fully automated trading system that receives TradingView webhook signals and executes sophisticated grid-based trading strategies with built-in risk management. The engine operates as a self-contained web application (FastAPI backend + React frontend) with local PostgreSQL database storage.

Core Architecture
Signal Flow

TradingView Role: Only triggers entry and exit signals
Engine Autonomy: Handles all DCA orders, pyramid scaling, take-profit logic, and risk management independently
Key Principle: Once TradingView starts a position, the engine continues working without additional external signals

Technology Stack

Backend: Python FastAPI
Frontend: React
Database: PostgreSQL
Deployment: Self-contained desktop app (Windows + macOS)


Position Management System
Position Group Concept

Definition: One active trade = unique pair + timeframe combination
Example: BTCUSDT 1h = 1 Position Group (regardless of pyramids)
Lifecycle: Created on first signal, persists until fully closed

Pyramid System

Maximum: 5 pyramids per Position Group
Pool Logic: Pyramids do NOT count toward max position limits
Purpose: Average entry price improvement through multiple entries

DCA (Dollar Cost Averaging) Layers
Each pyramid contains up to 7 DCA legs with:

Price Gap: Percentage below base entry (e.g., -0.5%, -1%, -1.5%)
Capital Weight: Allocation percentage per leg (typically 20%)
Individual TP Target: Each leg has its own take-profit percentage

Example DCA Structure:
DCA0: 0% gap, 20% weight, 1% TP
DCA1: -0.5% gap, 20% weight, 0.5% TP
DCA2: -1% gap, 20% weight, 2% TP
DCA3: -1.5% gap, 20% weight, 1.5% TP
DCA4: -2% gap, 20% weight, 1% TP

Take-Profit Modes
Three Operational Modes:

Per-Leg TP (leg)

Each DCA leg closes independently when its TP is hit
Calculated from actual fill price, not original entry


Aggregate TP (aggregate)

Entire position closes when weighted average entry reaches TP
Single exit for all legs


Hybrid TP (hybrid)

Both logics run simultaneously
Whichever triggers first executes
"First trigger wins" principle




Execution Pool & Queue System
Pool Rules

Max Open Groups: Configurable limit (e.g., 10 Position Groups)
What Counts: Only first entry of new pair/timeframe
What Doesn't Count: Pyramids, DCA orders, partial closes
Slot Release: Only on full Position Group closure

Waiting Queue Priority System
When pool is full, signals queue with priority ranking:
Priority Order:

Pyramid Continuation: Same pair + timeframe as existing group (auto-priority, bypasses pool limit)
Deepest Loss %: Signals with highest current loss percentage (better average entry opportunity)
Highest Replacement Count: Signals replaced multiple times (strategy re-confirmation)
FIFO: First in, first out (tiebreaker)

Queue Behaviors

Replacement: New signal for same group replaces queued one
Exit While Queued: Queued entry is deleted
Replacement Tracking: Count logged internally


Risk Engine
Objective
Use profits from winning trades to offset losing trades without closing losers at full loss.
Activation Requirements (ALL must be true)
✅ All 5 pyramids received for that group
✅ Post-full waiting timer expired
✅ Loss % below configured threshold
✅ (Optional) Trade age threshold met
Timer Start Conditions (Configurable)

after_5_pyramids: Timer begins when 5th pyramid received
after_all_dca_submitted: Timer begins when all DCA orders placed
after_all_dca_filled: Timer begins when all DCA orders filled

Selection Logic
Ranking losers (by %):

Highest loss percentage
If tied → highest unrealized dollar loss
If still tied → oldest trade

Execution (in USD):

Calculate required_usd = absolute loss of selected loser
Rank winners by profit in USD
Use up to 3 winning trades to cover loss
Close only the portion needed (partial close enabled)

Important Rules

Partial closes do NOT release pool slots
Full closure DOES release pool slot
Ranking uses % but execution uses USD
DCA and pyramid structures preserved during partial risk closes


Precision Validation System
Before Every Order
Fetch and apply:

Tick Size: Price decimal precision
Step Size: Quantity precision
Minimum Quantity: Smallest allowed order size
Minimum Notional: Minimum order value

Enforcement
✅ Prices rounded to valid tick size
✅ Quantities rounded to valid step size
✅ Orders below minimum notional blocked
✅ Missing metadata → signal held until refreshed
Result

Zero precision-based API rejections
Universal exchange compatibility (Binance, Bybit, OKX, KuCoin, MEXC, Gate.io)


Exit Logic
Priority Rules

First Trigger Wins: TP or exit signal, whichever comes first
Exit Signal: Closes entire Position Group instantly
Partial TP: Closes only that DCA leg
Unfilled DCA: Cancelled on any exit
Pool Slot: Released only on full closure


Webhook Input Structure
Key Webhook Fields

Authentication: secret, user_id
TradingView Data: Exchange, symbol, timeframe, action, position sizes, prices
Execution Intent: signal/exit/reduce/reverse, side, position size type
Risk Parameters: Stop loss, take profit, max slippage

Execution Intent Types

signal: New entry or pyramid
exit: Close full position
reduce: Partial position reduction
reverse: Close and open opposite direction


Web Application UI Requirements
Dashboard Components
1. Live Dashboard (Global Overview)

Total active Position Groups
Execution pool usage (X/Max with progress bar)
Queued signals count
Total PnL (realized + unrealized, USD + %)
Last webhook timestamp
Engine status (Running/Paused/Error)
Risk Engine status (Active/Idle/Blocked)
Error & warning alerts

2. Positions & Pyramids View

Pair/Timeframe
Pyramids progress (X/5)
DCA filled status (Filled/Total)
Average entry price
Unrealized PnL (% and $, color-coded)
TP mode (leg/aggregate/hybrid)
Status (Waiting/Live/Partially Filled/Closing/Closed)

Expandable Leg Details:

Leg ID, Fill Price, Capital Weight, TP Target
Progress toward TP, Filled Size, State

3. Risk Engine Panel

Current loss % and USD
Timer remaining
Activation conditions status (5 pyramids, age filter)
Available winning offsets (count + total profit USD)
Projected closure plan
Manual controls: Run Now, Skip Once, Block Group

4. Waiting Queue View

Pair/Timeframe, Replacement count
Expected profit, Time in queue
Priority rank
Actions: Promote, Remove, Force Add to Pool

5. Performance & Portfolio Dashboard

PnL Metrics: Day/week/month/all-time realized + unrealized
Equity Curve: Full curve with realized vs total, exportable CSV/PNG
Win/Loss Stats: Win rate %, avg win vs loss, long vs short breakdown
Trade Distribution: Histogram of returns, heatmap by pair/timeframe
Risk Metrics: Max drawdown, current drawdown, Sharpe, Sortino, profit factor
Capital Allocation: Per-pair exposure, pool usage %, DCA locked %
Daily Summary: Total trades, volume, net PnL, best/worst symbol
Real-time TVL: Deployed vs free capital

6. Logs & Alerts Console

Categories: Error, Warning, Info, Webhook, Order, Risk Engine, Precision, System
Search & filter toolbar (pair, timeframe, event type, date range)
Auto-scroll toggle
Color-coded severity (🔴 Error, 🟠 Warning, 🔵 Info, 🟣 Risk, 🟢 Success)
Export options (.txt, .csv, .json)
Pinned alert strip for critical events
Webhook replay button (debugging)
Log retention settings

7. Settings Panel (No Manual JSON Editing)

Exchange API: Keys, secrets, testnet toggle, rate limits
Precision Control: Auto-refresh interval, fallback mode, manual fetch
Execution Pool: Max groups, pyramid exceptions, queue limits
Risk Engine: Loss thresholds, timer modes, combine winners limit
TP Mode: leg/aggregate/hybrid selector, default %, overrides
Local Storage: Auto-save, reset to default, config backup/export
Theme & UI: Light/dark mode, font size, refresh rate

Features:

Live preview panel (shows config impact before saving)
"Apply & Restart Engine" button (hot reload)
Validation layer (prevents invalid configs)
Backup & restore (one-click)
Readonly mode (view-only for operators)


Configuration System
Single JSON File Structure
All settings stored locally, fully editable via UI:
Config Categories:

App Settings: Engine mode, auto-restart, timezone
Exchange Settings: API credentials, testnet mode, rate limits
Execution Pool: Max groups, pyramid/DCA counting rules, queue limits
Grid Strategy: DCA count, gap %, TP mode/%, weights
Waiting Queue Logic: Priority rules, replacement policy, drop on exit
Risk Engine Settings: Loss triggers, timers, offset limits
Precision Enforcement: Refresh intervals, strict mode, fallback rules
Logging: Verbosity, retention days, auto-export
Security: Encrypted key storage, webhook validation
UI Preferences: Theme, column visibility, refresh rate
Packaging: Local/Docker mode, auto-update

Key Config Values:
max_open_groups: 10
max_pyramids_per_group: 5
max_dca_per_pyramid: 7
tp_mode: leg
queue_replace_same_symbol: true
require_full_pyramids: true
post_full_wait_minutes: 60
loss_threshold_percent: -5
max_winners_to_combine: 3

Security & Storage
Security Requirements
✅ API keys stored encrypted (OS keychain)
✅ Keys masked in UI (*A4B19K)
✅ Local encryption key OS-bound
✅ Webhook signature validation (shared secret)
✅ No remote execution allowed
Local Storage

Logs: Text/JSON files with rotation
Config: Single JSON, UI-managed
Trade History: PostgreSQL database
Backup: One-click export (config + DB + logs)

PostgreSQL Usage

Stores only closed trade history and performance stats
Live data in memory, synced to DB on close or shutdown


Logging System
Log Categories

Engine Execution: Core loop, state changes
Signal Logs: Incoming webhooks, parsing, validation
Precision Validation: Tick/step size enforcement
Order Logs: Send, fill, partial fill, cancel, reject
Risk Engine: Triggered actions, pairings, coverage logic
Error & Stack Traces: API failures, exceptions

Features
✅ Full audit trail
✅ Auto-rotation (prevents infinite growth)
✅ Export to CSV/JSON
✅ UI viewer with filters
✅ Structured by severity and category

Edge Cases & Behaviors
Handled Scenarios
✅ Duplicate entry signal → ignored (unless replacement enabled)
✅ Opposite side signal → queued until current side closes
✅ Partial fill → TP recalculates from actual fill price
✅ Price beyond last DCA → last DCA remains pending or cancelled
✅ Precision fetch fails → order paused until metadata refreshed
✅ Exit while queued → queued entry cancelled
✅ Risk engine partial close → structure preserved
✅ Full closure → pool slot released immediately

Exchange Support
ExchangeSpotTestnetNotesBinance✅✅Primary validation targetBybit✅✅Fully supportedOKX✅❌Precision fetch supportedKuCoin✅❌Futures via v3 APIMEXC✅❌TP logic compatibleGate.io✅❌Optional support
Requirements:

All exchanges must support tick size and step size metadata
Precision validation enforced before every order
Futures support optional per user choice


Deployment & Packaging
Deliverables
✅ Self-contained desktop app (backend + frontend bundled)
✅ PostgreSQL with full persistence
✅ Config UI + JSON file sync
✅ Engine + UI logs
✅ Full unit tests for execution logic
✅ Installation packages (Windows + macOS)
✅ Complete documentation (install, run, troubleshoot)
Update Delivery

Installer, patch, or auto-update mechanism
Config hot-reload without full shutdown


Key Concepts Summary

Autonomous Operation: TradingView only starts/stops; engine handles all execution
Hierarchical Structure: Position Group → Pyramids → DCA Legs → TP Targets
Intelligent Queueing: Priority-based with pyramid continuation auto-promotion
Risk Balancing: Use winners to offset losers, ranked by % but executed in USD
Precision-First: Zero rejection through pre-validation of all order parameters
Self-Contained: Single packaged app with local database, no cloud dependencies
Full Transparency: Comprehensive UI for monitoring, logs, and configuration
First Trigger Wins: TP vs Exit, whichever happens first executes

This system provides institutional-grade automated trading execution with sophisticated risk management, all running locally on the user's machine.
