# Investigation Questions

## 1. Webhook Endpoint & Authentication
1. Is there webhook signature validation implemented?
2. Where is security.webhook_signature_validation checked?
3. What response does an unauthenticated request receive?
4. Are failed authentication attempts logged with details?
5. What rate limiting is applied to webhook endpoints?
6. How is the webhook secret generated and stored per user?

## 2. Signal Transformation
1. How is raw JSON transformed into an internal signal object?
2. Are TradingView placeholders properly mapped?
3. How is execution_intent.type handled differently?
4. What are the key transformations (exchange lowercasing, action→side mapping)?
5. How are malformed/missing fields handled (validation errors)?
6. Is the raw payload logged before or after validation?

## 3. User Authentication & Session Management
1. How is user registration handled?
2. What password hashing algorithm is used?
3. How are JWT tokens generated and validated?
4. What is the token expiration policy?
5. How are HTTP cookies secured (HttpOnly, Secure, SameSite)?
6. How is user logout handled (token invalidation)?
7. What rate limiting is applied to login/registration endpoints?

## 4. Exchange Integration & API Keys
1. Which exchanges are supported (Binance, Bybit, etc.)?
2. How are exchange API keys encrypted and stored?
3. What encryption algorithm is used for API key storage?
4. How is testnet mode configured per exchange?
5. How does the exchange connector factory work?
6. What error mapping exists for exchange-specific errors?
7. How are exchange precision rules (tick size, step size) fetched and cached?
8. How is account type handled for Bybit (UNIFIED/CONTRACT)?

## 5. Position Group Creation
1. What are the steps to create a position group?
2. What data is stored in a position group?
3. How is base entry price determined?
4. Is Position Group immediately persisted or flushed for ID?
5. Where is the creation code located?
6. What validations occur before position creation?

## 6. Position Identity & Lookup
1. Is a Position Group uniquely identified by pair + timeframe?
2. What happens if two signals arrive simultaneously for BTCUSDT 15m?
3. How are race conditions prevented (or not)?
4. What is the lookup mechanism (database vs in-memory filter)?
5. Is there a unique constraint on the database level?

## 7. Position State Machine
1. What states are defined (WAITING, LIVE, PARTIALLY_FILLED, ACTIVE, CLOSING, CLOSED, FAILED)?
2. Are all states implemented and used?
3. What triggers state transitions?
4. Can states go backwards?
5. Where is state tracked and how is it persisted?
6. Where is the transition logic located?

## 8. Pyramid Detection & Handling
1. How does the system detect this is a pyramid (not a new position)?
2. Is this pyramid added without consuming a pool slot?
3. What is the maximum number of pyramids allowed?
4. What happens if a 6th pyramid signal arrives (when max is 5)?
5. How does pyramid continuation bypass work?

## 9. Pyramid Counter & Storage
1. Where is the pyramid counter stored?
2. Is pyramid count incremented atomically?
3. How to query "how many pyramids does BTCUSDT 1h have"?
4. Does pyramid count affect Risk Engine activation?
5. How is pyramid index tracked per DCA order?

## 10. DCA Order Generation
1. Does each pyramid generate its own set of DCA orders?
2. Are DCA gaps calculated from the pyramid's entry price?
3. How are multiple DCA sets managed together?
4. How is DCA order quantity calculated from capital weight?

## 11. DCA Configuration Management
1. How are DCA layers configured (price gap, capital weight, take profit)?
2. Is grid_strategy.max_dca_per_pyramid respected?
3. Can DCA configuration be different per symbol/timeframe/exchange?
4. How are DCA configurations stored (JSON structure)?
5. What CRUD operations exist for DCA configs?
6. How are pyramid-specific DCA levels configured?

## 12. DCA Price & Size Calculation
1. How is the DCA price calculated from entry price?
2. Are prices calculated as: DCA1 = entry - gap1%, DCA2 = entry - gap2%?
3. How is capital weight applied to determine order size?
4. Is precision validation applied BEFORE order submission?
5. How are tick size and step size enforced?

## 13. DCA Order Placement
1. Are all DCA orders placed immediately when a signal arrives?
2. Or are they placed one at a time as price moves?
3. What order type is used (LIMIT, MARKET, stop-limit)?
4. How are partially filled DCA orders handled?
5. What retry logic exists for failed order submissions?
6. How many retry attempts with what backoff strategy?

## 14. Order Fill Monitoring
1. Is there a webhook/websocket listening for fill events?
2. Or is polling used? What is the polling interval?
3. How is "Filled Legs / Total Legs" count updated?
4. When a DCA fills, is the TP order placed immediately?
5. What happens if a DCA order is partially filled?
6. How is the OrderFillMonitorService started and managed?

## 15. DCA Cancellation
1. On exit signal - are ALL unfilled DCA orders cancelled?
2. On TP hit (per-leg mode) - is only that leg's order cancelled?
3. If price moves beyond the last DCA level, what happens?
4. How is order-not-found handled during cancellation?

## 16. Take-Profit Modes Overview
1. What TP modes are supported (PER_LEG, AGGREGATE, HYBRID, PYRAMID_AGGREGATE)?
2. Where is the TP mode configured?
3. How is TP mode stored in DCA configuration?

## 17. Per-Leg TP Mode
1. Is each TP calculated from the ACTUAL FILL PRICE (not original entry)?
2. Example: DCA2 fills at $99.00 with TP of +1.5%. Is TP target $100.485?
3. How is the TP order placed (limit order at target price)?
4. What happens when only one leg hits TP - does only that leg close?

## 18. Aggregate TP Mode
1. How is the weighted average entry price calculated?
2. When a new DCA fills, is the average recalculated?
3. Is the TP target based on this weighted average?
4. When aggregate TP hits, are ALL open legs closed together?

## 19. Hybrid TP Mode
1. Do both per-leg and aggregate TP systems run simultaneously?
2. What determines "first trigger wins"?
3. If per-leg TP hits first, does it only close that leg or everything?
4. How are the remaining legs handled after a partial close?

## 20. Pyramid Aggregate TP Mode
1. What is Pyramid Aggregate TP Mode?
2. How does it differ from regular Aggregate mode?
3. How are multiple pyramids' entries weighted together?

## 21. TP Order Execution
1. Are TP orders placed as limit orders or monitored internally?
2. If price hits TP but order doesn't fill, what happens?
3. How is slippage handled (risk.max_slippage_percent)?

## 22. Queue Management System
1. How does the signal queue work?
2. What triggers a signal to be queued vs immediately executed?
3. How is execution pool size limit enforced?
4. What is the QueueManagerService polling interval?

## 23. Queue Priority Calculation
1. How is dynamic priority score calculated?
2. What factors contribute to priority (time waiting, symbol, etc.)?
3. How is FIFO tiebreak handled when scores are equal?
4. How does pyramid continuation affect priority?

## 24. Queue Operations
1. How is signal promotion from queue to active pool handled?
2. What happens when a queued signal is manually promoted?
3. How does force-add work (overriding pool limits)?
4. How is signal replacement handled (same symbol/timeframe)?
5. Can queued signals be cancelled/removed?

## 25. Risk Engine Overview
1. What is the Risk Engine's purpose?
2. What is the polling/evaluation interval?
3. What triggers risk evaluation (time-based, on-fill, manual)?
4. How is RiskEngineService started and managed?

## 26. Offset Loss Strategy
1. What is the offset loss strategy?
2. How is a "losing" position identified for closure?
3. What selection strategies exist (largest loss, best risk/reward)?
4. How are "winning" positions selected for partial close?
5. What percentage of winners is closed to offset losses?

## 27. Risk Timers & Eligibility
1. How do risk timers work per position?
2. What is the default timer duration?
3. When does a position become eligible for risk evaluation?
4. Does pyramid continuation reset the risk timer?
5. How is timer state persisted?

## 28. Risk Manual Controls
1. How does blocking a position work?
2. How does unblocking work?
3. What does "skip next evaluation" do?
4. How does force-stop affect the queue?
5. How does force-start resume operations?
6. What is max realized loss threshold and how does it work?

## 29. Risk Actions Logging
1. How are risk actions recorded (RiskAction model)?
2. What action types exist (OFFSET_LOSS, MANUAL_BLOCK, etc.)?
3. What details are stored per action (loser, winner, PnL)?
4. How is risk action history queried?

## 30. Telegram Notification System
1. How is Telegram integration configured (bot token, channel ID)?
2. What notification types are supported?
3. How are messages formatted for different events?

## 31. Telegram Quiet Hours
1. How do quiet hours work?
2. What is the urgent-only override?
3. How are quiet hours configured (start/end times)?

## 32. Telegram Message Types
1. What message is sent on signal reception?
2. What message is sent on order fill?
3. What message is sent on TP hit?
4. What message is sent on risk engine action?
5. Can message types be toggled on/off?

## 33. Dashboard & Analytics
1. How is TVL (Total Value Locked) calculated?
2. How is free USDT balance fetched?
3. How is unrealized PnL calculated across positions?
4. How is realized PnL aggregated?
5. How is win rate calculated?
6. What caching is applied to dashboard data?

## 34. Position History & Metrics
1. How is position history stored and queried?
2. What pagination is applied to history queries?
3. How is position duration calculated?
4. What metrics are tracked per closed position?

## 35. Settings Management
1. How are user settings structured?
2. What settings categories exist (risk, DCA, telegram, exchange)?
3. How are settings updated via API?
4. Are settings changes validated before saving?

## 36. API Security & Rate Limiting
1. What CORS configuration is applied?
2. What rate limits exist per endpoint?
3. How is rate limiting implemented (SlowAPI)?
4. Are sensitive endpoints more restricted?

## 37. Background Services Architecture
1. What background services run on startup?
2. How are services started and stopped?
3. What happens if a background service crashes?
4. How is service health monitored?

## 38. Database & Persistence
1. What ORM is used (SQLAlchemy)?
2. Is async database access supported?
3. How are database migrations handled (Alembic)?
4. What indexes exist for performance?
5. How is connection pooling configured?

## 39. Error Handling & Logging
1. How are errors logged throughout the system?
2. What log levels are used (DEBUG, INFO, WARNING, ERROR)?
3. How is log rotation configured?
4. Are logs structured (JSON format)?
5. How can logs be viewed via API?

## 40. Frontend Architecture
1. What frontend framework is used (React)?
2. What state management is used?
3. What pages exist in the frontend?
4. How is authentication handled on frontend?

## 41. Frontend Features
1. Is mobile responsive design implemented?
2. Is dark mode supported?
3. Are keyboard shortcuts implemented?
4. Is pull-to-refresh supported on mobile?
5. How are loading states displayed (skeletons)?
6. How are errors handled (error boundaries)?

## 42. Position Close Scenarios
1. How is manual close from UI handled?
2. How is TP-triggered close handled?
3. How is risk engine forced close handled?
4. How is exit signal close handled?
5. What cleanup occurs on position close (cancel orders, update state)?

## 43. Exchange Synchronization
1. What does "sync with exchange" do?
2. How are local and exchange states reconciled?
3. What happens if orders exist on exchange but not locally?
4. What happens if local orders don't exist on exchange?

## 44. Precision & Validation
1. How are exchange precision rules fetched?
2. How is tick size enforced on prices?
3. How is step size enforced on quantities?
4. What happens if an order violates precision rules?
5. Is precision validation cached?

## 45. Multi-User Support
1. How are users isolated from each other?
2. Can multiple users trade the same symbol?
3. How are user-specific configurations stored?
4. Is there admin/superuser functionality?

## 46. Testing & Mock Exchange
1. Is there a mock exchange connector for testing?
2. How does testnet mode work?
3. What test coverage exists?
4. How are integration tests structured?
