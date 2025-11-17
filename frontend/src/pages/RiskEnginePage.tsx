import React from 'react';

const RiskEnginePage: React.FC = () => {
  return (
    <div>
      <h1>Risk Engine Panel</h1>

      <section>
        <h2>Current Risk Status</h2>
        <div>
          <strong>Loss %:</strong> -5.2%
        </div>
        <div>
          <strong>Loss USD:</strong> $120
        </div>
        <div>
          <strong>Timer Remaining:</strong> 15m (if enabled)
        </div>
        <div>
          <strong>5 Pyramids Reached:</strong> Yes
        </div>
        <div>
          <strong>Age Filter Passed:</strong> Yes
        </div>
        <div>
          <strong>Available Winning Offsets:</strong> 2 (Total Profit: $100)
        </div>
        <div>
          <strong>Projected Plan:</strong> Close 1 winner ($80) to cover partial loss.
        </div>
      </section>

      <section>
        <h2>Actions</h2>
        <button>Run Now</button>
        <button>Skip Once</button>
        <button>Block Group</button>
      </section>
    </div>
  );
};

export default RiskEnginePage;
