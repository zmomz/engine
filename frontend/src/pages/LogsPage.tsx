import React, { useState } from 'react';
import { Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel } from '@mui/material';

const LogsPage: React.FC = () => {
  const [logLevel, setLogLevel] = useState('all');

  const handleLogLevelChange = (event: any) => {
    setLogLevel(event.target.value as string);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h4" gutterBottom>
        System Logs
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <FormControl sx={{ minWidth: 120 }}>
          <InputLabel id="log-level-filter-label">Filter by Level</InputLabel>
          <Select
            labelId="log-level-filter-label"
            id="log-level-filter"
            value={logLevel}
            label="Filter by Level"
            onChange={handleLogLevelChange}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="info">Info</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="error">Error</MenuItem>
          </Select>
        </FormControl>
        <TextField
          variant="outlined"
          placeholder="Search logs..."
          aria-label="Search logs"
        />
      </Box>
      <Box sx={{ height: 400, width: '100%', border: '1px solid #ccc', p: 1, overflowY: 'scroll' }}>
        {/* Placeholder for log entries */}
        <Typography>[INFO] 2025-11-18 10:00:00 - Application started.</Typography>
        <Typography>[WARN] 2025-11-18 10:05:23 - High memory usage detected.</Typography>
        <Typography>[ERROR] 2025-11-18 10:10:45 - Failed to connect to exchange.</Typography>
      </Box>
    </Box>
  );
};

export default LogsPage;