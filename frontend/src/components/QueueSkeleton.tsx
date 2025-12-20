import React from 'react';
import { Box, Paper, Skeleton, Tabs, Tab, Stack } from '@mui/material';

export const QueueTableSkeleton: React.FC = () => (
  <Box sx={{ height: '100%', p: { xs: 1.5, sm: 2 } }}>
    {/* Toolbar */}
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
      <Skeleton variant="rectangular" width={200} height={40} sx={{ borderRadius: 1 }} />
      <Skeleton variant="rectangular" width={300} height={40} sx={{ borderRadius: 1 }} />
    </Box>

    {/* Table Header */}
    <Box sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
      <Skeleton variant="text" width={120} height={30} />
      <Skeleton variant="text" width={80} height={30} />
      <Skeleton variant="text" width={70} height={30} />
      <Skeleton variant="text" width={100} height={30} />
      <Skeleton variant="text" width={130} height={30} />
      <Skeleton variant="text" width={250} height={30} />
      <Skeleton variant="text" width={120} height={30} />
    </Box>

    {/* Table Rows */}
    {[1, 2, 3, 4, 5].map((i) => (
      <Box key={i} sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 2, pb: 2, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
        <Skeleton variant="text" width={120} height={24} />
        <Skeleton variant="rounded" width={80} height={24} />
        <Skeleton variant="text" width={70} height={24} />
        <Skeleton variant="text" width={100} height={24} />
        <Skeleton variant="text" width={130} height={24} />
        <Skeleton variant="text" width={250} height={24} />
        <Skeleton variant="text" width={120} height={24} />
        <Skeleton variant="text" width={110} height={24} />
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Skeleton variant="rounded" width={80} height={28} />
          <Skeleton variant="rounded" width={80} height={28} />
        </Box>
      </Box>
    ))}

    {/* Pagination */}
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
      <Skeleton variant="text" width={150} height={30} />
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Skeleton variant="circular" width={32} height={32} />
        <Skeleton variant="text" width={60} height={32} />
        <Skeleton variant="circular" width={32} height={32} />
      </Box>
    </Box>
  </Box>
);

export const QueuePageSkeleton: React.FC = () => (
  <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 }, height: '85vh', display: 'flex', flexDirection: 'column' }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
      <Skeleton variant="text" width={200} height={48} />
      <Skeleton variant="circular" width={40} height={40} />
    </Box>

    {/* Active Rules Summary */}
    <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Skeleton variant="text" width={160} height={24} />
        <Skeleton variant="rounded" width={120} height={28} />
        <Skeleton variant="rounded" width={140} height={28} />
        <Skeleton variant="rounded" width={100} height={28} />
      </Stack>
    </Paper>

    <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={0}>
          <Tab label={<Skeleton variant="text" width={150} />} />
          <Tab label={<Skeleton variant="text" width={120} />} />
        </Tabs>
      </Box>

      <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
        <QueueTableSkeleton />
      </Box>
    </Paper>
  </Box>
);
