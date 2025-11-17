import React from 'react';

const DashboardPage: React.FC = () => {
  return (
    <div>
      <h1>Dashboard - Global Overview</h1>
      <p>Welcome to your dashboard!</p>

      <section>
        <h2>Key Metrics</h2>
        <div>
          <strong>Total Active Position Groups:</strong> [X]
        </div>
        <div>
          <strong>Execution Pool Usage:</strong> [X / Max active groups (visual progress bar)]
        </div>
        <div>
          <strong>Queued Signals Count:</strong> [Number of entries waiting]
        </div>
        <div>
          <strong>Total PnL:</strong> [Realized + Unrealized, in both USD and %]
        </div>
        <div>
          <strong>Last Webhook Timestamp:</strong> [Timestamp]
        </div>
      </section>

      <section>
        <h2>System Status</h2>
        <div>
          <strong>Engine Status Banner:</strong> [Running / Paused / Error (color-coded)]
        </div>
        <div>
          <strong>Risk Engine Status:</strong> [Active / Idle / Blocked (with last action time)]
        </div>
        <div>
          <strong>Error & Warning Alerts:</strong> [API rejects, precision sync failure, rate limit, rejected orders]
        </div>
      </section>
    </div>
  );
};

export default DashboardPage;