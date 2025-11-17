import React from 'react';

const PositionsPage: React.FC = () => {
  return (
    <div>
      <h1>Positions & Pyramids View</h1>
      <p>Main Trading Table</p>

      <table>
        <thead>
          <tr>
            <th>Pair / Timeframe</th>
            <th>Pyramids</th>
            <th>DCA Filled</th>
            <th>Avg Entry</th>
            <th>Unrealized PnL</th>
            <th>TP Mode</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {/* Placeholder for position data */}
          <tr>
            <td>BTCUSDT 1h</td>
            <td>3 / 5</td>
            <td>2 / 4</td>
            <td>$30,000</td>
            <td style={{ color: 'green' }}>+5% ($150)</td>
            <td>leg</td>
            <td>Live</td>
          </tr>
          <tr>
            <td>ETHUSDT 4h</td>
            <td>1 / 5</td>
            <td>0 / 3</td>
            <td>$2,000</td>
            <td style={{ color: 'red' }}>-2% ($40)</td>
            <td>aggregate</td>
            <td>Partially Filled</td>
          </tr>
        </tbody>
      </table>

      <section>
        <h2>Position Group Details (Click to expand)</h2>
        {/* Placeholder for expanded details when a row is clicked */}
        <div>
          <strong>Leg ID:</strong> DCA2
        </div>
        <div>
          <strong>Fill Price:</strong> 0.01153
        </div>
        <div>
          <strong>Capital Weight:</strong> 20%
        </div>
        <div>
          <strong>TP Target:</strong> +1.5% or global avg TP
        </div>
        <div>
          <strong>Progress:</strong> 73% toward TP
        </div>
        <div>
          <strong>Filled Size:</strong> 187 USDT
        </div>
        <div>
          <strong>State:</strong> Open
        </div>
      </section>
    </div>
  );
};

export default PositionsPage;
