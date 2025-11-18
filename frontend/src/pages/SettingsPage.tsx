import React from 'react';

const SettingsPage: React.FC = () => {
  return (
    <div>
      <h1>Settings Panel - Full Config UI</h1>

      <section>
        <h2>Exchange API</h2>
        <div>
          <label htmlFor="api-key">API Key:</label>
          <input type="password" id="api-key" value="********" readOnly />
        </div>
        <div>
          <label htmlFor="api-secret">API Secret:</label>
          <input type="password" id="api-secret" value="********" readOnly />
        </div>
        <div>
          <label htmlFor="testnet-toggle">Testnet Mode:</label>
          <input type="checkbox" id="testnet-toggle" />
        </div>
      </section>

      <section>
        <h2>Precision Control</h2>
        <div>
          <strong>Auto-refresh interval:</strong> 60 seconds
        </div>
        <div>
          <button>Manual Fetch Precision</button>
        </div>
      </section>

      <section>
        <h2>Execution Pool</h2>
        <div>
          <label htmlFor="max-open-groups">Max Open Groups:</label>
          <input type="number" id="max-open-groups" defaultValue={10} />
        </div>
      </section>

      <section>
        <h2>Risk Engine</h2>
        <div>
          <label htmlFor="loss-threshold">Loss % Threshold:</label>
          <input type="number" id="loss-threshold" defaultValue={-5} />
        </div>
      </section>

      <section>
        <h2>TP Mode</h2>
        <div>
          <label htmlFor="tp-mode">TP Mode:</label>
          <select id="tp-mode">
            <option value="per_leg">Per-Leg</option>
            <option value="aggregate">Aggregate</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>
      </section>

      <section>
        <h2>Local Storage</h2>
        <div>
          <button>Backup Config</button>
          <button>Restore Config</button>
        </div>
      </section>

      <section>
        <h2>Theme & UI</h2>
        <div>
          <label htmlFor="theme-select">Theme:</label>
          <select id="theme-select">
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
      </section>

      <section>
        <h2>Actions</h2>
        <button>Apply & Restart Engine</button>
        <button>Reset to Default</button>
      </section>
    </div>
  );
};

export default SettingsPage;
