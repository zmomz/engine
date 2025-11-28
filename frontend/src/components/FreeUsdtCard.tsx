import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface FreeUsdtCardProps {
  freeUsdt: number | null;
}

const FreeUsdtCard: React.FC<FreeUsdtCardProps> = ({ freeUsdt }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div">
          Free USDT
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h4" sx={{ color: 'text.primary' }}>
            {typeof freeUsdt === 'number' ? `$${freeUsdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Loading...'}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default FreeUsdtCard;
