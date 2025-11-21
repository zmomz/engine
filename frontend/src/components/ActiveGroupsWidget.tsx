import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface ActiveGroupsWidgetProps {
  count: number | null;
}

const ActiveGroupsWidget: React.FC<ActiveGroupsWidgetProps> = ({ count }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div">
          Active Position Groups
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h4" color="info.main">
            {count !== null ? count : 'Loading...'}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ActiveGroupsWidget;
