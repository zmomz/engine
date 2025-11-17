import React from 'react';

const LogsPage: React.FC = () => {
  return (
    <div>
      <h1>Logs & Alerts - Full System Event Console</h1>

      <section>
        <h2>Log Filters</h2>
        <div>
          <label htmlFor="log-category">Category:</label>
          <select id="log-category">
            <option value="all">All</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
            <option value="webhook">Webhook</option>
            <option value="order">Order</option>
            <option value="risk">Risk Engine</option>
            <option value="precision">Precision</option>
            <option value="system">System</option>
          </select>
          <input type="text" placeholder="Search..." />
          <button>Search</button>
        </div>
        <div>
          <label htmlFor="auto-scroll">Auto-Scroll:</label>
          <input type="checkbox" id="auto-scroll" defaultChecked />
          <button>Export</button>
        </div>
      </section>

      <section>
        <h2>Pinned Alerts</h2>
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '10px' }}>
          🔴 API Down: Binance connection lost!
        </div>
      </section>

      <section>
        <h2>Log Entries</h2>
        <div style={{ height: '300px', overflowY: 'scroll', border: '1px solid #ccc', padding: '10px' }}>
          <p style={{ color: 'blue' }}>[INFO] 2025-11-17 10:00:00 - System started.</p>
          <p style={{ color: 'green' }}>[ORDER] 2025-11-17 10:01:05 - BTCUSDT BUY order filled.</p>
          <p style={{ color: 'orange' }}>[WARNING] 2025-11-17 10:02:10 - Rate limit almost reached for Bybit.</p>
          <p style={{ color: 'red' }}>[ERROR] 2025-11-17 10:03:15 - API Reject: Invalid quantity for ETHUSDT.</p>
          <p style={{ color: 'purple' }}>[RISK] 2025-11-17 10:04:20 - Offset loss for PositionGroup XYZ.</p>
          {/* More log entries */}
        </div>
      </section>

      <section>
        <h2>Log Settings</h2>
        <div>
          <strong>Log Retention:</strong> Last X days, Max file size, or Infinite with prune.
        </div>
        <div>
          <button>Webhook Replay</button>
        </div>
      </section>
    </div>
  );
};

export default LogsPage;
