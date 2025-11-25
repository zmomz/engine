import React, { useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card, CardContent, Typography } from '@mui/material';
import useEquityCurveStore from '../store/equityCurveStore';

const EquityCurveChart: React.FC = () => {
  const { historicalPositions, loading, error, fetchHistoricalPositions } = useEquityCurveStore();

  useEffect(() => {
    fetchHistoricalPositions();
  }, [fetchHistoricalPositions]);

  // Process data for the chart: calculate cumulative PnL over time
  const chartData = useMemo(() => {
      return historicalPositions
        .slice() // Create a copy to avoid mutating state if sort does in-place (though sort() usually returns reference) - best practice
        .sort((a, b) => new Date(a.close_time).getTime() - new Date(b.close_time).getTime())
        .reduce((acc: { date: string; cumulativePnl: number }[], position) => {
          const lastCumulativePnl = acc.length > 0 ? acc[acc.length - 1].cumulativePnl : 0;
          const cumulativePnl = lastCumulativePnl + position.realized_pnl;
          const date = new Date(position.close_time).toLocaleDateString();
          acc.push({ date, cumulativePnl });
          return acc;
        }, []);
  }, [historicalPositions]);

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Equity Curve
        </Typography>
        {loading && <Typography>Loading historical data...</Typography>}
        {error && <Typography color="error">Error: {error}</Typography>}
        {!loading && !error && chartData.length === 0 && (
          <Typography>No historical positions to display.</Typography>
        )}
        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart
              data={chartData}
              margin={{
                top: 5, right: 30, left: 20, bottom: 5,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="cumulativePnl" stroke="#82ca9d" activeDot={{ r: 8 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
};

export default EquityCurveChart;
