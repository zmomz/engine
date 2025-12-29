import React, { useState, useEffect } from 'react';
import { Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel, Button, CircularProgress, Alert } from '@mui/material';
import useLogStore from '../store/logStore';

const LogLine = React.memo(({ log }: { log: string }) => (
    <div style={{ marginBottom: '4px', whiteSpace: 'pre-wrap', borderBottom: '1px solid #eee' }}>
        {log}
    </div>
));

const LogsPage: React.FC = () => {
  const { logs, loading, error, fetchLogs } = useLogStore();
  const [logLevel, setLogLevel] = useState('all');
  const [lineCount, setLineCount] = useState(100);
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

        <FormControl sx={{ minWidth: 100 }} size="small">
             <InputLabel id="line-count-label">Lines</InputLabel>
             <Select
                labelId="line-count-label"
                value={lineCount}
                label="Lines"
                onChange={(e) => setLineCount(Number(e.target.value))}
             >
                 <MenuItem value={100}>100</MenuItem>
                 <MenuItem value={500}>500</MenuItem>
                 <MenuItem value={1000}>1000</MenuItem>
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
         <Button 
            variant="contained" 
            onClick={() => {
                const blob = new Blob([filteredLogs.join('\n')], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `engine-logs-${new Date().toISOString()}.txt`;
                a.click();
                URL.revokeObjectURL(url);
            }}
         >
            Export Logs
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
                <LogLine key={index} log={log} />
            ))
        ) : (
            <Typography color="text.secondary" align="center" sx={{ mt: 2 }}>No logs found.</Typography>
        )}
      </Box>
    </Box>
  );
};

export default LogsPage;