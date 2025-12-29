# Future Improvements Plan

This document outlines planned improvements identified during the SoW vs Implementation review.

## 1. Additional Exchange Support

### Current State
- Implementation supports: Binance (spot), Mock Exchange (testing)
- SoW specifies: Binance, Bybit, OKX, KuCoin, MEXC, Gate.io

### Implementation Plan

#### Phase 1: Bybit Integration
- [ ] Add Bybit connector extending `BaseExchangeConnector`
- [ ] Implement precision fetching via Bybit API
- [ ] Add Bybit-specific order types if needed
- [ ] Test with Bybit testnet
- [ ] Update frontend exchange selector

#### Phase 2: OKX Integration
- [ ] Add OKX connector
- [ ] Handle OKX-specific API quirks (different rate limits, response formats)
- [ ] Test precision validation

#### Phase 3: Additional Exchanges
- [ ] KuCoin support
- [ ] MEXC support
- [ ] Gate.io support (optional)

### Technical Considerations
- All connectors should inherit from `BaseExchangeConnector`
- Each exchange needs its own precision cache
- Rate limiting should be configurable per exchange
- Testnet support where available

---

## 2. Risk Engine Improvements

### 2.1 Configurable Evaluate Interval

**Current State:** Risk engine runs on a fixed 60-second interval

**SoW Specifies:** `risk_engine.evaluate_interval_sec = 10`

**Implementation Plan:**
- [ ] Add `evaluate_interval_sec` to `RiskEngineConfig` schema
- [ ] Update `risk_engine_loop` to use configurable interval
- [ ] Add UI control in Settings > Risk Engine section
- [ ] Default to 60s (current behavior) for backward compatibility

**Code Location:** [backend/app/services/risk/risk_engine.py](backend/app/services/risk/risk_engine.py)

```python
# Current (hardcoded):
await asyncio.sleep(60)

# Target (configurable):
await asyncio.sleep(self.config.evaluate_interval_sec)
```

### 2.2 Loss Ranking Priority

**Current State:** Losers are ranked by absolute USD loss (`unrealized_pnl_usd`)

**SoW Specifies:**
1. Select loser with highest loss **percent** first
2. If tied, use highest dollar loss
3. If still tied, use oldest trade

**Implementation Plan:**
- [ ] Update `_filter_eligible_losers` to sort by percent first
- [ ] Add secondary sort by USD loss
- [ ] Add tertiary sort by `created_at` (oldest first)
- [ ] Update unit tests to verify ranking order

**Code Location:** [backend/app/services/risk/risk_engine.py:_filter_eligible_losers](backend/app/services/risk/risk_engine.py)

```python
# Current:
eligible.sort(key=lambda pg: pg.unrealized_pnl_usd)

# Target:
eligible.sort(key=lambda pg: (
    pg.unrealized_pnl_percent,  # Primary: lowest percent (most negative)
    pg.unrealized_pnl_usd,      # Secondary: lowest USD
    pg.created_at               # Tertiary: oldest first
))
```

---

## 3. Priority Matrix

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| Risk Engine Evaluate Interval | High | Low | Medium |
| Loss Ranking Priority Fix | High | Low | High |
| Bybit Integration | Medium | Medium | High |
| OKX Integration | Medium | Medium | Medium |
| Additional Exchanges | Low | High | Low |

---

## 4. Notes

- All changes should include unit tests
- Integration tests should be run against testnets where possible
- Documentation should be updated in SoW.md after implementation
- Consider feature flags for new exchange connectors during rollout
