**Execution Engine Scope of Work**


# <a id="_Toc1"></a>

**The Execution Engine is a fully automated trading system that:**

<!--[if !supportLists]-->·       <!--[endif]-->Receives TradingView webhook signals

<!--[if !supportLists]-->·       <!--[endif]-->Executes grid-based entries using pyramids received by tradingview and DCA inside the engine

<!--[if !supportLists]-->·       <!--[endif]-->Applies precision validation before every order

<!--[if !supportLists]-->·       <!--[endif]-->Automatically handles exits

<!--[if !supportLists]-->·       <!--[endif]-->Runs a Risk Engine to offset losing trades

<!--[if !supportLists]-->·       <!--[endif]-->Enforces max position limits using a pool + queue

<!--[if !supportLists]-->·       <!--[endif]-->Stores all data in database

<!--[if !supportLists]-->·       <!--[endif]-->Includes an integrated web app for real-time monitoring

 

**Key characteristics:**

<!--[if !supportLists]-->·       <!--[endif]-->Supports multiple exchanges and symbols

<!--[if !supportLists]-->·       <!--[endif]-->All logic lives inside a single packaged webapp application / server

<!--[if !supportLists]-->·       <!--[endif]-->TradingView **only triggers the entry** (and optionally the exit)

<!--[if !supportLists]-->·       <!--[endif]-->The engine itself calculates and executes all **DCA orders**

<!--[if !supportLists]-->·       <!--[endif]-->The engine itself handles all **pyramid scaling**

<!--[if !supportLists]-->·       <!--[endif]-->The engine itself runs the **Risk Engine**, without needing TradingView

<!--[if !supportLists]-->·       <!--[endif]-->**_TradingView is only used to start or end a position. All DCA, pyramid scaling, take-profit, and risk logic are handled locally by the engine and do not require additional TradingView alerts._**

<!--[if !supportLists]-->·       <!--[endif]-->Example to clarify

<!--[if !supportLists]-->·       <!--[endif]-->If TradingView fires this webhook:

|                                            |                                   |                                           |                                      |
| ------------------------------------------ | --------------------------------- | ----------------------------------------- | ------------------------------------ |
| Key / JSON Path                            | Example Value                     | Source / Placeholder                      | Description                          |
| **secret**                                 | YOUR\_WEBHOOK\_SECRET             | Manual                                    | Security key to verify request       |
| **source**                                 | tradingview                       | Static                                    | Identifies webhook origin            |
| **timestamp**                              | {{timenow}}                       | TradingView                               | Alert execution timestamp            |
| **tv.exchange**                            | BINANCE                           | {{exchange}}                              | Exchange name from TradingView       |
| **tv.symbol**                              | BTCUSDT                           | {{ticker}}                                | Trading pair                         |
| **tv.timeframe**                           | 15                                | {{interval}}                              | Chart timeframe in minutes           |
| **tv.action**                              | buy                               | {{strategy.order.action}}                 | Buy, Sell, Long, Short               |
| **tv.market\_position**                    | long                              | {{strategy.market\_position}}             | Current strategy position            |
| **tv.market\_position\_size**              | 2.5                               | {{strategy.market\_position\_size}}       | Current position size                |
| **tv.prev\_market\_position**              | flat                              | {{strategy.prev\_market\_position}}       | Previous position                    |
| **tv.prev\_market\_position\_size**        | 0                                 | {{strategy.prev\_market\_position\_size}} | Previous size                        |
| **tv.entry\_price**                        | {{strategy.order.price}}          | TradingView                               | Order execution price                |
| **tv.close\_price**                        | {{close}}                         | TradingView                               | Last candle close                    |
| **tv.order\_size**                         | {{strategy.order.contracts}}      | TradingView                               | Order size (contracts/units)         |
| **strategy\_info.trade\_id**               | 12345                             | {{strategy.order.id}}                     | Unique order ID                      |
| **strategy\_info.alert\_name**             | BTC Long Entry                    | {{alert\_name}}                           | Name of the alert                    |
| **strategy\_info.alert\_message**          | DCA Entry 1                       | {{strategy.order.comment}}                | Custom alert message/comment         |
| **execution\_intent.type**                 | signal                            | Manual                                    | signal, exit, reduce, reverse        |
| **execution\_intent.side**                 | buy                               | Mirrors tv.action                         | Direction of trade                   |
| **execution\_intent.position\_size\_type** | contracts                         | Manual                                    | contracts, base, quote               |
| **execution\_intent.precision\_mode**      | auto                              | Manual                                    | Auto-detect precision or force rules |
| **risk.stop\_loss**                        | {{strategy.position\_avg\_price}} | Optional                                  | Stop loss reference                  |
| **risk.take\_profit**                      | null                              | Optional                                  | Take profit reference                |
| **risk.max\_slippage\_percent**            | 0.2                               | Manual                                    | Allowed slippage percent             |

<!--[if !supportLists]-->·       <!--[endif]-->The engine will:

<!--[if !supportLists]-->a.     <!--[endif]-->Open Position Group

<!--[if !supportLists]-->b.     <!--[endif]-->Submit pyramid + DCA orders by itself

<!--[if !supportLists]-->c.      <!--[endif]-->Calculate TP levels automatically

<!--[if !supportLists]-->d.     <!--[endif]-->Handle partial TP close when triggered

<!--[if !supportLists]-->e.     <!--[endif]-->Run Risk Engine if losses exceed threshold

<!--[if !supportLists]-->f.       <!--[endif]-->Close full position if exit webhook arrives

<!--[if !supportLists]-->g.     <!--[endif]-->**Continue working even if no more TradingView signals arrive**

<!--[if !supportLists]-->·       <!--[endif]-->Designed for stable, repeatable, hands-off execution

 


# <a id="_Toc2"></a>

**2.1 Purpose**

<!--[if !supportLists]-->·       <!--[endif]-->Execute entries that received from TradingView in different price level and execute take profit based on the grid configuration

<!--[if !supportLists]-->·       <!--[endif]-->Improve price efficiency by using multiple DCA which will reduce drawdown using DCA layering

<!--[if !supportLists]-->·       <!--[endif]-->Allow different take-profit modes depending on grid configuration

 

**2.2 Core Logic**

<!--[if !supportLists]-->·       <!--[endif]-->First signal creates a new Position Group  (refer to Appendix table on 15 for full definition)

<!--[if !supportLists]-->·       <!--[endif]-->Additional long signals (same pair + timeframe) create pyramids, not new positions

<!--[if !supportLists]-->·       <!--[endif]-->Each pyramid contains multiple DCA layers below the base price

<!--[if !supportLists]-->·       <!--[endif]-->Each layer has 3 elements:

<!--[if !supportLists]-->a.     <!--[endif]-->Price gap

<!--[if !supportLists]-->b.     <!--[endif]-->Weight allocation

<!--[if !supportLists]-->c.      <!--[endif]-->Take-profit target

Execution rules:

✅ First TP or exit signal always wins✅ Unfilled DCA orders are cancelled on exit✅ Different take-profit modes available

 

**2.3 DCA Example Table (Long Entry)**

|           |              |                |             |
| --------- | ------------ | -------------- | ----------- |
| DCA Layer | Price Gap    | Capital Weight | Take Profit |
| DCA0      | 0 percent    | 20 percent     | 1 percent   |
| DCA1      | -0.5 percent | 20 percent     | 0.5 percent |
| DCA2      | -1.0 percent | 20 percent     | 2 percent   |
| DCA3      | -1.5 percent | 20 percent     | 1.5 percent |
| DCA4      | -2.0 percent | 20 percent     | 1 percent   |

📌 Each TP is calculated from **actual fill price**, not original entry price.

 

**2.4 Take-Profit Modes**

|              |                                                   |
| ------------ | ------------------------------------------------- |
| Mode         | Description                                       |
| Per-Leg TP   | Each DCA closes independently based on its own TP |
| Aggregate TP | Entire position closes when avg entry reaches TP  |
| Hybrid TP    | Both logics run, whichever closes first applies   |

 

**2.5 Exit Logic**

✅ If any TP is hit → only that segment closes✅ If TradingView exit arrives → full group closes instantly✅ Unfilled DCA is cancelled on exit✅ First trigger always wins

 


# <a id="_Toc3"></a>

Before any order is submitted, the engine fetches:

<!--[if !supportLists]-->·       <!--[endif]-->Tick size (price decimal rule)

<!--[if !supportLists]-->·       <!--[endif]-->Step size (quantity rule)

<!--[if !supportLists]-->·       <!--[endif]-->Minimum quantity

<!--[if !supportLists]-->·       <!--[endif]-->Minimum notional value

Precision rules:

✅ Prices are rounded to valid tick size✅ Quantity rounded to valid step size✅ Orders below minimum notional are blocked✅ If precision metadata is missing → signal is held until refreshed

Result:

<!--[if !supportLists]-->·       <!--[endif]-->Zero precision-based API rejection

<!--[if !supportLists]-->·       <!--[endif]-->Universal exchange compatibility

<!--[if !supportLists]-->·       <!--[endif]-->Works on Binance, Bybit, OKX, KuCoin, etc.

 

 


# <a id="_Toc4"></a>

The Risk Engine is responsible for closing losing positions using profits from winning positions.It activates only after full structure conditions are met and follows strict priority rules.

 

**4.1 Objective**

<!--[if !supportLists]-->·       <!--[endif]-->Reduce floating losses without closing positions at full loss

<!--[if !supportLists]-->·       <!--[endif]-->Use winning trades to offset losing trades

<!--[if !supportLists]-->·       <!--[endif]-->Maintain controlled portfolio drawdown

<!--[if !supportLists]-->·       <!--[endif]-->Execute offsets in **dollar value**, not percent

 

**4.2 Activation Conditions**

The Risk Engine will only start operating on a Position Group when **all** of the following are true:

✅ All 5 pyramids for that pair and timeframe have been received✅ Post-full waiting time has passed✅ Loss percent is below configured threshold✅ (Optional) Trade age threshold is met if enabled

 

**4.3 Timer Behavior**

The timer does **not** start at first entry.It starts only based on one of the following selectable modes:

|                            |                                                        |
| -------------------------- | ------------------------------------------------------ |
| Timer Start Mode           | Description                                            |
| after\_5\_pyramids         | Timer begins when 5th pyramid signal is received       |
| after\_all\_dca\_submitted | Timer begins only when all DCA orders are submitted    |
| after\_all\_dca\_filled    | Timer begins only when all DCA orders are fully filled |

Additional option:

<!--[if !supportLists]-->·       <!--[endif]-->Timer may reset if a **replacement pyramid** is received (configurable)

 

**4.4 Selection Priorities**

When the Risk Engine runs, it follows this ranking process:

<!--[if !supportLists]-->1.     <!--[endif]-->Select the losing trade with the **highest loss percent**

<!--[if !supportLists]-->2.     <!--[endif]-->If tied → select the one with highest unrealized dollar loss

<!--[if !supportLists]-->3.     <!--[endif]-->If still tied → select the oldest trade

📌 Loss ranking = percent📌 Offset execution = USD

 

**4.5 Offset Execution Logic**

<!--[if !supportLists]-->·       <!--[endif]-->required\_usd = absolute unrealized loss of selected losing trade

<!--[if !supportLists]-->·       <!--[endif]-->Select winning trades ranked by profit in USD

<!--[if !supportLists]-->·       <!--[endif]-->Use up to 3 winning trades to cover required\_usd

<!--[if !supportLists]-->·       <!--[endif]-->Only close the portion needed to cover the loss

<!--[if !supportLists]-->·       <!--[endif]-->Partial closes do **not** release pool slot

<!--[if !supportLists]-->·       <!--[endif]-->Full Position Group closure **does** release pool slot

 

**4.6 Risk Configuration Parameters**

risk.loss\_threshold\_percentrisk.use\_trade\_age\_filterrisk.age\_threshold\_minutesrisk.require\_full\_pyramidsrisk.post\_full\_wait\_minutesrisk.timer\_start\_conditionrisk.reset\_timer\_on\_replacementrisk.max\_winners\_to\_combinerisk.partial\_close\_enabledrisk.min\_close\_notional

 


# <a id="_Toc5"></a>

The Execution Pool limits how many Position Groups can be live at the same time.

📌 A Position Group = a unique pair + timeframe📌 Pyramids and DCA **do not** count as separate positions

 

**5.1 Pool Rules**

|                                   |                          |
| --------------------------------- | ------------------------ |
| Item                              | Counts Toward Max Limit? |
| First entry of new pair/timeframe | ✅ Yes                    |
| Pyramid entries                   | ❌ No                     |
| DCA orders                        | ❌ No                     |
| Risk-engine partial close         | ❌ No                     |
| Full Position Group closed        | ✅ Slot released          |

 

**5.2 Waiting Queue Rules**

If the pool is full:

<!--[if !supportLists]-->·       <!--[endif]-->New signals go into waiting queue

<!--[if !supportLists]-->·       <!--[endif]-->If exit signal arrives while queued → it is deleted

<!--[if !supportLists]-->·       <!--[endif]-->If a new pyramid signal arrives for same group → it **replaces** the queued one and replaced the entry price

<!--[if !supportLists]-->·       <!--[endif]-->Replacement count is tracked internally

<!--[if !supportLists]-->·       <!--[endif]-->Queue always ranked by selection priority

 

**5.3 Queue Selection Priority**

When a pool slot becomes free:

|          |                                                                   |                                                                                                                                                                                         |
| -------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Priority | Updated Rule                                                      | Explanation                                                                                                                                                                             |
| **1**    | **Same pair + same timeframe = auto-priority**                    | If the queued signal is a continuation (pyramid) of an already active Position Group, it is selected first. It does not count as a new position, so it bypasses the max position limit. |
| **2**    | **Pick the signal with the deepest current loss percentage**      | A larger loss percent means the market has moved further in discount zone, offering a better average entry. This follows a "buy deeper retrace first" logic.                            |
| **3**    | **If tied, choose the signal with the highest replacement count** | A signal that was replaced multiple times by new alerts is considered repeatedly confirmed by the strategy, therefore higher priority.                                                  |
| 4        | **If still tied, fall back to FIFO (first in, first out)**        | Oldest queued signal is selected last as a fair tiebreak rule.                                                                                                                          |

 


# <a id="_Toc6"></a>

<!--[if !supportLists]-->1.     <!--[endif]-->Receive TradingView signal

<!--[if !supportLists]-->2.     <!--[endif]-->Validate and precision-check

<!--[if !supportLists]-->3.     <!--[endif]-->If pool slot available → execute

<!--[if !supportLists]-->4.     <!--[endif]-->If not → queue with ranking

<!--[if !supportLists]-->5.     <!--[endif]-->Track fills and take-profit logic

<!--[if !supportLists]-->6.     <!--[endif]-->Apply exit rules or TP rules (first trigger wins)

<!--[if !supportLists]-->7.     <!--[endif]-->If risk engine active → evaluate offset

<!--[if !supportLists]-->8.     <!--[endif]-->Log state, update database, update UI

 


# <a id="_Toc7"></a>

<!--[if !supportLists]-->·       <!--[endif]-->The system includes a built-in webapp application UI or browser, no external frontend.

<!--[if !supportLists]-->·       <!--[endif]-->Backend and UI run inside the same packaged app.

 

**7.1 UI Requirements**

|                               |                                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| Category                      | Requirement                                                                                    |
| ✅ **Live Monitoring**         | Real-time view of all active Position Groups, pyramids, and DCA legs                           |
| ✅ **Queue & Pool Visibility** | Shows open pool slots, queued signals, replacement counts, and priority order                  |
| ✅ **Risk Engine Panel**       | Displays active risk checks, selected losing trade, offsetting winners, and closing decisions  |
| ✅ **System Status Console**   | Exchange connection status, precision sync, webhook activity, API rate limit, and error alerts |
| ✅ **Advanced Log Viewer**     | Search, filter, export, and event tagging (entry, exit, DCA, risk close, API reject, etc.)     |
| ✅ **Local Config Panel**      | All engine settings editable in UI, no JSON or code editing required                           |
| ✅ **Theme Support**           | Light and dark mode switch                                                                     |

 

 


### <a id="_Toc8"></a>**Performance & Portfolio Dashboard**

|                             |                                                                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Metric Group                | Required Display                                                                                                                          |
| **PnL Metrics**             | - Realized PnL (day, week, month, all-time)- Unrealized PnL (open positions)- PnL per pair, per timeframe, per strategy                   |
| **Equity Curve**            | - Full equity curve for closed trades- Separate curve for realized vs total equity (realized + unrealized)- Downloadable CSV / PNG export |
| **Win/Loss Stats**          | - Win rate percent- Average win vs average loss (RR ratio)- Long vs short performance breakdown                                           |
| **Trade Distribution**      | - Histogram of trade returns- Heatmap by pair / timeframe- Best and worst 10 trades                                                       |
| **Risk Metrics**            | - Max drawdown- Current drawdown- Sharpe ratio- Sortino ratio- Profit factor                                                              |
| **Capital Allocation View** | - Per-pair capital exposure- % of pool used- % locked in DCA legs                                                                         |
| **Daily Summary Snapshot**  | - Total trades executed- Total volume traded- Net PnL for the day- Best and worst symbol of the day                                       |
| **Real-time TVL Gauge**     | Shows how much capital is deployed vs free                                                                                                |

 


## <a id="_Toc9"></a>

 


### <a id="_Toc10"></a>**A) Live Dashboard (Global Overview)**

Main real-time control screen showing engine status and portfolio summary.

|                                  |                                                                              |
| -------------------------------- | ---------------------------------------------------------------------------- |
| Metric / Widget                  | Description                                                                  |
| **Total Active Position Groups** | Number of currently open Position Groups (not counting pyramids or DCA legs) |
| **Execution Pool Usage**         | X / Max active groups (visual progress bar)                                  |
| **Queued Signals Count**         | Number of entries waiting due to pool limit or missing precision             |
| **Total PnL**                    | Realized + Unrealized, in both USD and %                                     |
| **Last Webhook Timestamp**       | Shows when the last TradingView signal arrived                               |
| **Engine Status Banner**         | Running / Paused / Error (color-coded)                                       |
| **Risk Engine Status**           | Active / Idle / Blocked (with last action time)                              |
| **Error & Warning Alerts**       | API rejects, precision sync failure, rate limit, rejected orders             |

 


### <a id="_Toc11"></a>**B) Positions & Pyramids View (Main Trading Table)**

#### <a id="_Toc12"></a>

|                      |                                                      |
| -------------------- | ---------------------------------------------------- |
| Column               | Description                                          |
| **Pair / Timeframe** | Example: BTCUSDT 1h (group identity)                 |
| **Pyramids**         | X / 5 received so far                                |
| **DCA Filled**       | Filled Legs / Total Legs                             |
| **Avg Entry**        | Weighted average entry price of all filled DCA legs  |
| **Unrealized PnL**   | % and $ (auto color green/red)                       |
| **TP Mode**          | leg / aggregate / hybrid                             |
| **Status**           | Waiting / Live / Partially Filled / Closing / Closed |


#### <a id="_Toc13"></a>

When user clicks a Position Group:

|                    |                                     |
| ------------------ | ----------------------------------- |
| Field              | Example                             |
| **Leg ID**         | DCA2                                |
| **Fill Price**     | 0.01153                             |
| **Capital Weight** | 20 percent                          |
| **TP Target**      | +1.5 percent or global avg TP       |
| **Progress**       | 73 percent toward TP                |
| **Filled Size**    | 187 USDT                            |
| **State**          | Open / Hit TP / Cancelled / Pending |


### <a id="_Toc14"></a>**C) Risk Engine Panel**

|                               |                                                             |
| ----------------------------- | ----------------------------------------------------------- |
| Field                         | Description                                                 |
| **Loss %**                    | Current % loss of the group                                 |
| **Loss USD**                  | Floating-dollar loss based on fill prices                   |
| **Timer Remaining**           | Time left before Risk Engine is allowed to act (if enabled) |
| **5 Pyramids Reached**        | Yes / No                                                    |
| **Age Filter Passed**         | Yes / No (based on minutes active)                          |
| **Available Winning Offsets** | Count + total profit in USD                                 |
| **Projected Plan**            | Shows which winners will be closed and how much             |


#### <a id="_Toc15"></a>

|                 |                                               |
| --------------- | --------------------------------------------- |
| Action          | Description                                   |
| **Run Now**     | Force risk engine action immediately          |
| **Skip Once**   | Ignore this group for the next cycle          |
| **Block Group** | Exempt this group from risk engine completely |


### <a id="_Toc16"></a>**D) Waiting Queue View**

|                       |                                                       |
| --------------------- | ----------------------------------------------------- |
| Column                | Description                                           |
| **Pair / Timeframe**  | Group identity                                        |
| **Replacement Count** | How many times refreshed by newer signal              |
| **Expected Profit**   | Estimated TP gain based on entry + weight             |
| **Time in Queue**     | Minutes since added                                   |
| **Priority Rank**     | Based on rule set (loss %, replacement, profit, FIFO) |


#### <a id="_Toc17"></a>

|                       |                                               |
| --------------------- | --------------------------------------------- |
| Action                | Result                                        |
| **Promote**           | Force move to live pool if slot free          |
| **Remove**            | Delete queued signal                          |
| **Force Add to Pool** | Override position limit and open trade anyway |


### <a id="_Toc18"></a>**E) Logs & Alerts (Full System Event Console)**

|                                 |                                                                                     |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| Feature                         | Description                                                                         |
| **Log Categories / Filters**    | Error, Warning, Info, Webhook, Order, Risk Engine, Precision, System                |
| **Search & Filter Toolbar**     | Filter by pair, timeframe, event type, date range                                   |
| **Auto-Scroll Toggle**          | On for live stream, Off for manual review                                           |
| **Color-Coded Severity**        | 🔴 Error, 🟠 Warning, 🔵 Info, 🟣 Risk Event, 🟢 Order Success                      |
| **Highlight Critical Failures** | Rejected order, invalid precision, API error, rate-limit hit                        |
| **Export Options**              | Export to .txt, .csv, or .json                                                      |
| **Pinned Alert Strip**          | Always-visible bar for latest high-severity events (API down, order rejected, etc.) |
| **Webhook Replay Button**       | Re-send the same webhook payload for debugging (optional, toggle in config)         |
| **Log Retention Setting**       | Configurable: last X days, max file size, or infinite with prune                    |


### <a id="_Toc19"></a>**F) Settings Panel (Full Config UI – No Manual JSON Editing Needed)**

|                       |                                                                                |
| --------------------- | ------------------------------------------------------------------------------ |
| Group                 | Editable Parameters                                                            |
| **Exchange API**      | API key, secret, passphrase, testnet toggle, rate-limit mode                   |
| **Precision Control** | Auto-refresh interval, fallback mode, last sync timestamp, manual fetch button |
| **Execution Pool**    | Max open groups, pyramid exception toggle, queue size limit                    |
| **Risk Engine**       | Loss % threshold, age timer mode, timer reset mode, combine winners limit      |
| **TP Mode**           | leg / aggregate / hybrid selector, default TP %, override rules                |
| **Local Storage**     | Auto-save config toggle, reset to default button, config backup/export         |
| **Theme & UI**        | Light / dark mode, font size, performance refresh rate                         |


#### <a id="_Toc20"></a>

|                                     |                                                                 |
| ----------------------------------- | --------------------------------------------------------------- |
| Feature                             | Description                                                     |
| **Live Preview Panel**              | Shows how config changes affect engine logic (before saving)    |
| **“Apply & Restart Engine” Button** | Hot-reloads config without shutting down UI                     |
| **Validation Layer**                | Prevents invalid config (ex: negative %, missing API key, etc.) |
| **Backup & Restore**                | One-click save/restore of full configuration JSON               |
| **Readonly Mode**                   | View-only mode for operators (no config changes allowed)        |

 


# <a id="_Toc21"></a>

|                  |                                          |
| ---------------- | ---------------------------------------- |
| State            | Description                              |
| Waiting          | In queue, pool full or missing precision |
| Live (Unfilled)  | Orders placed but not executed           |
| Partially Filled | One or more DCA legs filled              |
| Active           | Running with TP tracking                 |
| Closing          | Exit or risk close in progress           |
| Closed           | All positions closed, slot released      |

 


# <a id="_Toc22"></a>

✅ If duplicate entry signal arrives → ignored unless replacement enabled✅ If signal arrives for opposite side → queued until current side closes✅ If partial fill happens → TP recalculates from actual fill price✅ If price moves beyond last DCA level → last DCA remains pending or cancelled per config✅ If precision fetch fails → order is paused until metadata refreshed✅ If exit signal comes while queued → queued entry is cancelled✅ If risk engine closes partial legs → DCA & pyramid structure preserved✅ If full Position Group closes → execution pool slot released immediately

 


# <a id="_Toc23"></a>

All engine settings are stored in one local JSON file.The UI allows full editing, so no manual file editing is required.

|                           |                                               |                                                                    |
| ------------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| Config Category           | What It Controls                              | Examples of Parameters                                             |
| **App Settings**          | Global engine behavior                        | engine\_mode, auto\_restart, timezone                              |
| **Exchange Settings**     | API credentials & exchange-specific rules     | api\_key, api\_secret, testnet\_mode, rate\_limit                  |
| **Execution Pool**        | Max active positions & pyramid logic          | max\_open\_groups, count\_pyramids\_in\_pool, queue\_limit         |
| **Grid Strategy**         | DCA layers, weights, TP mode                  | dca\_count, dca\_gap\_percent, tp\_mode, tp\_percent               |
| **Waiting Queue Logic**   | Queue prioritization & replacement policy     | queue\_priority\_rules, allow\_replacement, drop\_on\_exit         |
| **Risk Engine Settings**  | Loss thresholds & closure logic               | loss\_percent\_trigger, age\_timer\_minutes, combine\_winners\_max |
| **Precision Enforcement** | Tick size, step size, min notional validation | precision\_refresh\_interval, strict\_mode, fallback\_rules        |
| **Logging**               | Log verbosity, retention, export options      | log\_level, max\_log\_days, auto\_export                           |
| **Security & Secrets**    | Encrypted storage of keys & tokens            | encryption\_enabled, key\_vault\_path                              |
| **UI Preferences**        | UI customizations & layout memory             | theme, column\_visibility, refresh\_rate                           |
| **Packaging Settings**    | Build type for deployment                     | local\_mode, docker\_mode, auto\_update                            |


### <a id="_Toc24"></a>

<!--[if !supportLists]-->·       <!--[endif]-->JSON config is **auto-synced** between UI and engine in real time.

<!--[if !supportLists]-->·       <!--[endif]-->Backup & restore buttons will export/import the full config.

<!--[if !supportLists]-->·       <!--[endif]-->Each category can be **collapsed** in the UI for clean navigation.

<!--[if !supportLists]-->·       <!--[endif]-->Config changes only take effect after **Apply & Restart Engine** (soft reload, no full shutdown).

 

Below is the **final config structure** (no code formatting, just Notion style):

|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| app.mode                         webapp \_self\_containedapp.data\_dir                     ./engine\_dataapp.log\_level                    info exchange.name                    binanceexchange.api\_key                 REDACTEDexchange.api\_secret              REDACTEDexchange.testnet                 trueexchange.precision\_refresh\_sec   60 execution\_pool.max\_open\_groups           10execution\_pool.count\_pyramids\_toward\_pool falseexecution\_pool.count\_dca\_toward\_pool      false grid\_strategy.max\_pyramids\_per\_group      5grid\_strategy.max\_dca\_per\_pyramid         7grid\_strategy.tp\_mode                     leg waiting\_rule.queue\_replace\_same\_symbol    truewaiting\_rule.selection\_priority           \[ pyramid\_continuation, highest\_loss\_percent, highest\_replacement\_count, highest\_expected\_profit, fifo ] risk\_engine.require\_full\_pyramids         truerisk\_engine.enable\_post\_full\_wait         truerisk\_engine.post\_full\_wait\_minutes        60risk\_engine.timer\_start\_condition         after\_5\_pyramidsrisk\_engine.reset\_timer\_on\_replacement    false risk\_engine.loss\_threshold\_percent        -5risk\_engine.use\_trade\_age\_filter          falserisk\_engine.age\_threshold\_minutes         200 risk\_engine.offset\_mode                   usdrisk\_engine.max\_winners\_to\_combine        3risk\_engine.partial\_close\_enabled         truerisk\_engine.min\_close\_notional            20 risk\_engine.evaluate\_on\_fill              truerisk\_engine.evaluate\_interval\_sec         10 precision.enforce\_tick\_size               trueprecision.enforce\_step\_size               trueprecision.enforce\_min\_notional            true logging.audit\_log\_enabled                 truelogging.rotate\_daily                      truelogging.keep\_days                         30 security.store\_secrets\_encrypted          truesecurity.webhook\_signature\_validation     true UI.framework                             proposer\_choiceUI.theme                                 darkUI.realtime\_update\_ms                    500 packaging.target\_platforms                \[ win, mac ]packaging.auto\_update                     false  |

 


# <a id="_Toc25"></a>

 


### <a id="_Toc26"></a>**11.1 Logging System**

|                        |                                                                  |
| ---------------------- | ---------------------------------------------------------------- |
| Feature                | Description                                                      |
| ✅ Local Logging        | All logs stored on device, no external/cloud dependency          |
| ✅ Full Audit Trail     | Every order, risk action, exit event, and API response recorded  |
| ✅ Log Rotation         | Auto-prunes old logs to prevent infinite file growth             |
| ✅ Export Options       | Logs can be exported to CSV / JSON for analysis                  |
| ✅ Structured Log Types | Each log entry tagged by category and severity                   |
| ✅ UI Log Viewer        | Filter by: Error, Warning, Info, Webhook, Order, Risk, Precision |


#### <a id="_Toc27"></a>

|                           |                                                               |
| ------------------------- | ------------------------------------------------------------- |
| Log Type                  | Purpose                                                       |
| Engine Execution Logs     | Tracks core loop, state changes, system events                |
| Signal Logs               | Incoming webhooks, parsed data, validation outcome            |
| Precision Validation Logs | Tick size, step size, min notional enforcement results        |
| Order Logs                | Order send, fill, partial fill, cancellation, rejection       |
| Risk Engine Logs          | Triggered actions, pairing closed trades, loss coverage logic |
| Error & Stack Traces      | API failures, exceptions, fallback behavior                   |


### <a id="_Toc28"></a>**11.2 Security Requirements**

|                                            |                                                   |
| ------------------------------------------ | ------------------------------------------------- |
| Requirement                                | Enforcement                                       |
| API keys must never be stored in plaintext | Stored encrypted using OS keychain                |
| No API keys visible in UI                  | Masked: \*\*\*\*A4B19K\*\*\*                      |
| Local encryption key is OS-bound           | Cannot be copied or used on another machine       |
| Webhook authentication required            | Shared-secret signature validation                |
| No remote execution allowed                | Engine does not expose remote commands or sockets |


### <a id="_Toc29"></a>**11.3 Local Storage**

|                  |                                        |
| ---------------- | -------------------------------------- |
| Component        | Implementation                         |
| Log Storage      | Local text or JSON files with rotation |
| Config Store     | Single JSON config file, UI-managed    |
| Trade History DB | postgresql                             |
| Backup Option    | One-click export (config + DB + logs)  |


### <a id="_Toc30"></a>

<!--[if !supportLists]-->·       <!--[endif]-->Postgresql is used only to store **closed trade history and performance stats**.

<!--[if !supportLists]-->·       <!--[endif]-->Live data stays in memory and is synced to DB once trades close or engine shuts down.

 

 


# <a id="_Toc31"></a>

|          |      |         |                           |
| -------- | ---- | ------- | ------------------------- |
| Exchange | Spot | Testnet | Notes                     |
| Binance  | ✅    | ✅       | Primary validation target |
| Bybit    | ✅    | ✅       | Fully supported           |
| OKX      | ✅    | ❌       | Precision fetch supported |
| KuCoin   | ✅    | ❌       | Futures via v3 API        |
| MEXC     | ✅    | ❌       | TP logic compatible       |
| Gate.io  | ✅    | ❌       | Optional support          |

Notes:

<!--[if !supportLists]-->·       <!--[endif]-->All exchanges must support tick size and step size metadata

<!--[if !supportLists]-->·       <!--[endif]-->Precision validation must be enforced before every order

<!--[if !supportLists]-->·       <!--[endif]-->Futures support is optional per user choice

 

 


# <a id="_Toc32"></a>

This section is for freelancers, vendors, or engineering teams responding to the scope.

They must provide:

<!--[if !supportLists]-->1.     <!--[endif]-->Short review of the scope, noting any missing items

<!--[if !supportLists]-->2.     <!--[endif]-->Proposed architecture and language choice

<!--[if !supportLists]-->3.     <!--[endif]-->webapp app framework they will use

<!--[if !supportLists]-->4.     <!--[endif]-->Timeline + milestone breakdown

<!--[if !supportLists]-->5.     <!--[endif]-->Full cost proposal (fixed or milestone-based)

<!--[if !supportLists]-->6.     <!--[endif]-->Security plan for encrypted local secrets

<!--[if !supportLists]-->7.     <!--[endif]-->Local database approach

<!--[if !supportLists]-->8.     <!--[endif]-->Test plan, including simulated signals and exchange mocks

<!--[if !supportLists]-->9.     <!--[endif]-->Error handling and auto-recovery approach

<!--[if !supportLists]-->10.  <!--[endif]-->Deployment packaging plan for Windows and macOS

<!--[if !supportLists]-->11.  <!--[endif]-->How updates will be delivered (installer, patch, etc.)

 

**13.1 Required Deliverables**

✅ Self-contained web app (backend + frontend)✅ database with full persistence✅ Config UI + JSON file sync✅ Engine + UI logs✅ Full unit tests for execution logic✅ Precision-safe order placement✅ Risk Engine logic fully implemented✅ Installation package for Windows and macOS✅ Full documentation (install, run, troubleshoot)

 


# <a id="_Toc33"></a>

These diagrams represent the engine logic, not UI layout.

(You can paste these directly into Notion — Notion supports Mermaid syntax)

 

**14.1 Execution Flow (Signal → DCA → Exit)**

|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| flowchart TD  A\[TradingView webhook] --> B\[Validate and parse]  B -->\|valid\| C\[Determine Position Group]  B -->\|invalid\| Z\[Reject and log]   C --> D{Existing group?}  D -->\|No\| E{Pool slot available?}  E -->\|Yes\| F\[Create new group, place entry and DCA]  E -->\|No\| G\[Queue signal]   D -->\|Yes\| H\[Add as pyramid, place new DCA set]   F --> I\[Monitor fills and TP]  H --> I  I --> J{Exit signal received?}  J -->\|Yes\| K\[Cancel unfilled DCA, close all legs, release slot]  J -->\|No\| L\[Continue monitoring]  |

 

**14.2 Risk Engine Flow (Selection in %, Execution in USD)**

|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| flowchart TD  A\[Risk cycle] --> B\[Get losing groups]  B --> C{5 pyramids reached?}  C -->\|No\| Z\[Skip]  C -->\|Yes\| D{Timer expired?}  D -->\|No\| Z  D -->\|Yes\| E{Loss percent below threshold?}  E -->\|No\| Z   E --> F\[Rank losers by percent]  F --> G\[Pick worst loser, compute required USD]  G --> H\[Sort winners by profit USD]  H --> I\[Select up to 3 winners]  I --> J\[Partial close winners, cover required USD]  J --> K\[Re-evaluate PnL and repeat if needed]  |

 

**14.3 Queue and Pool Logic**

|                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| flowchart TD  A\[New signal] --> B{Same group exists?}  B -->\|Yes\| C\[Add as pyramid, bypass pool]  B -->\|No\| D{Pool has free slot?}  D -->\|Yes\| E\[Open as new group, consume slot]  D -->\|No\| F\[Queue signal]   F --> G{Replacement signal for same group?}  G -->\|Yes\| H\[Replace queued signal]  G -->\|No\| I\[Stay queued]   J\[Group closed] --> K\[Release slot]  K --> L\[Promote highest priority queued entry]  |

 


# <a id="_Toc34"></a>

|                        |                                                         |                                                     |                                                    |
| ---------------------- | ------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------- |
| # <a id="_Toc35"></a>  | # <a id="_Toc36"></a>                                   | # <a id="_Toc37"></a>                               | # <a id="_Toc38"></a>                              |
| **Position Group**     | One active trade defined by pair + timeframe            | Group stays until fully closed                      | BTCUSDT 1h = 1 group, even if 5 pyramids exist     |
| **Pyramid**            | Additional entry for the same Position Group            | Max 5, does not count toward max open positions     | 5 separate long entries on BTCUSDT 1h              |
| **DCA Leg**            | Individual partial order at predefined price gap        | Each leg has its own weight + TP                    | DCA2 at -1% with 20 percent allocation             |
| **TP Leg**             | Exit target tied to a specific DCA leg or total average | Depends on TP mode (leg, aggregate, hybrid)         | DCA3 hits +1.5 percent and closes only that leg    |
| **Base Entry Price**   | First executed entry price for the Position Group       | All DCA gaps use this as reference                  | Entry = 0.01171 → DCA1 at -0.5 percent             |
| **Execution Pool**     | Max number of allowed live Position Groups              | Only first entry counts, not pyramids or DCA        | Max open positions = 10 → 10 Position Groups max   |
| **Waiting Queue**      | Holds pending entries when pool is full                 | Promotes based on configured priority rules         | 3 queued signals waiting for free slot             |
| **Replacement Signal** | New signal replaces older queued one (same pair + TF)   | Increases replacement counter                       | ETHUSDT 15m signal replaced 4 times                |
| **Exit Signal**        | TradingView command to close full Position Group        | Closes all filled legs and cancels remaining DCA    | "exit" webhook → closes BTCUSDT 1h group instantly |
| **Risk Engine**        | Auto-balances by closing winners to cover losing trades | Uses percent to rank losers, uses dollar to execute | Lose -120 USD covered by 2 winners +80 and +50     |
| **Unrealized PnL**     | Floating profit/loss of open Position Group             | Used for risk engine dollar balancing               | Position showing +37.5 USD unrealized profit       |
| **Full Close**         | Closes entire Position Group                            | Releases 1 execution pool slot                      | Whole EURUSDT 5m group fully exited                |
| **Partial Close**      | Closes one DCA leg or partial risk action               | Does NOT release pool slot                          | Only DCA2 closed by TP, group still active         |
| **Precision Rules**    | Tick size, step size, minimum qty, minimum notional     | All prices and qty auto-adjusted before order send  | Binance BTC tick size = 0.10, step size = 0.0001   |


# <a id="_Toc39"></a>

 

Backend: python fastAPI

Frontend: React
