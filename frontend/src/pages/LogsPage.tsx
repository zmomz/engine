import React, { useState, useEffect } from 'react';
import { Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel, Button, CircularProgress, Alert } from '@mui/material';
import useLogStore from '../store/logStore';

const LogsPage: React.FC = () => {
  const { logs, loading, error, fetchLogs } = useLogStore();
  const [logLevel, setLogLevel] = useState('all');
  const [lineCount] = useState(100);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchLogs(lineCount, logLevel);
    // Auto-refresh every 5 seconds
    const interval = setInterval(() => {
        fetchLogs(lineCount, logLevel);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchLogs, lineCount, logLevel]);

  const handleLogLevelChange = (event: any) => {
    setLogLevel(event.target.value as string);
  };

  const filteredLogs = logs.filter(log => 
    log.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <Box sx={{ width: '100%', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        System Logs
      </Typography>
      
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FormControl sx={{ minWidth: 120 }} size="small">
          <InputLabel id="log-level-filter-label">Level</InputLabel>
          <Select
            labelId="log-level-filter-label"
            id="log-level-filter"
            value={logLevel}
            label="Level"
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
          size="small"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        
         <Button variant="outlined" onClick={() => fetchLogs(lineCount, logLevel)}>
            Refresh
         </Button>
      </Box>

      <Box 
        sx={{ 
            height: '60vh', 
            width: '100%', 
            border: '1px solid #ccc', 
            p: 2, 
            overflowY: 'scroll',
            bgcolor: '#f5f5f5',
            fontFamily: 'monospace',
            fontSize: '0.875rem',
            borderRadius: 1
        }}
      >
        {loading && logs.length === 0 ? (
             <Box display="flex" justifyContent="center" p={2}>
                 <CircularProgress size={24} />
             </Box>
        ) : filteredLogs.length > 0 ? (
            filteredLogs.map((log, index) => (
                <div key={index} style={{ marginBottom: '4px', whiteSpace: 'pre-wrap' }}>
                    {log}
                </div>
            ))
        ) : (
            <Typography color="text.secondary" align="center" sx={{ mt: 2 }}>No logs found.</Typography>
        )}
      </Box>
    </Box>
  );
};

export default LogsPage;