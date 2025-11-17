import React from 'react';

const QueuePage: React.FC = () => {
  return (
    <div>
      <h1>Waiting Queue View</h1>

      <table>
        <thead>
          <tr>
            <th>Pair / Timeframe</th>
            <th>Replacement Count</th>
            <th>Expected Profit</th>
            <th>Time in Queue</th>
            <th>Priority Rank</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {/* Placeholder for queued signals data */}
          <tr>
            <td>BTCUSDT 1h</td>
            <td>2</td>
            <td>+1.2%</td>
            <td>15m</td>
            <td>2</td>
            <td>
              <button>Promote</button>
              <button>Remove</button>
              <button>Force Add to Pool</button>
            </td>
          </tr>
          <tr>
            <td>ETHUSDT 4h</td>
            <td>0</td>
            <td>+0.8%</td>
            <td>30m</td>
            <td>4</td>
            <td>
              <button>Promote</button>
              <button>Remove</button>
              <button>Force Add to Pool</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default QueuePage;
