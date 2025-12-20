import React from 'react';
import { Box, Paper, Skeleton, Tabs, Tab, Stack, Card, CardContent, useMediaQuery, useTheme } from '@mui/material';

// Card skeleton for mobile view (matches QueueSignalCard layout)
const QueueSignalCardSkeleton: React.FC = () => (
  <Card sx={{ mb: 2 }}>
    <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
      {/* Header: Symbol and chips */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Skeleton variant="text" width={90} height={24} />
          <Skeleton variant="rounded" width={50} height={20} />
        </Box>
        <Skeleton variant="rounded" width={60} height={24} />
      </Box>

      {/* Stats grid */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.5, mb: 1.5 }}>
        <Box>
          <Skeleton variant="text" width={50} height={14} />
          <Skeleton variant="text" width={70} height={20} />
        </Box>
        <Box>
          <Skeleton variant="text" width={60} height={14} />
          <Skeleton variant="text" width={80} height={20} />
        </Box>
        <Box>
          <Skeleton variant="text" width={70} height={14} />
          <Skeleton variant="text" width={90} height={20} />
        </Box>
        <Box>
          <Skeleton variant="text" width={55} height={14} />
          <Skeleton variant="text" width={75} height={20} />
        </Box>
      </Box>

      {/* Priority score */}
      <Box sx={{ mb: 1.5 }}>
        <Skeleton variant="text" width={100} height={14} />
        <Skeleton variant="text" width={120} height={20} />
      </Box>

      {/* Footer: Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, pt: 1, borderTop: '1px solid rgba(224, 224, 224, 0.2)' }}>
        <Skeleton variant="rounded" width={80} height={32} />
        <Skeleton variant="rounded" width={80} height={32} />
      </Box>
    </CardContent>
  </Card>
);

// Table skeleton for desktop view
const QueueTableSkeletonDesktop: React.FC = () => (
  <Box sx={{ height: '100%', p: 2 }}>
    {/* Toolbar */}
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
      <Skeleton variant="rectangular" width={200} height={40} sx={{ borderRadius: 1 }} />
      <Skeleton variant="rectangular" width={300} height={40} sx={{ borderRadius: 1 }} />
    </Box>

    {/* Table Header */}
    <Box sx={{ display: 'flex', gap: 2, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
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
      <Box key={i} sx={{ display: 'flex', gap: 2, mb: 2, pb: 2, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
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

// Card list skeleton for mobile view
const QueueTableSkeletonMobile: React.FC = () => (
  <Box sx={{ height: '100%', p: 1.5 }}>
    {/* Mobile toolbar */}
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
      <Skeleton variant="rectangular" width={120} height={36} sx={{ borderRadius: 1 }} />
      <Skeleton variant="circular" width={36} height={36} />
    </Box>

    {/* Queue signal cards */}
    {[1, 2, 3, 4].map((i) => (
      <QueueSignalCardSkeleton key={i} />
    ))}

    {/* Pagination */}
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mt: 2, gap: 1 }}>
      <Skeleton variant="circular" width={32} height={32} />
      <Skeleton variant="text" width={40} height={32} />
      <Skeleton variant="circular" width={32} height={32} />
    </Box>
  </Box>
);

export const QueueTableSkeleton: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return isMobile ? <QueueTableSkeletonMobile /> : <QueueTableSkeletonDesktop />;
};

export const QueuePageSkeleton: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 }, height: '85vh', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Skeleton variant="text" width={isMobile ? 120 : 200} height={48} />
        <Skeleton variant="circular" width={40} height={40} />
      </Box>

      {/* Active Rules Summary */}
      <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          alignItems={{ xs: 'flex-start', sm: 'center' }}
        >
          <Skeleton variant="text" width={isMobile ? 120 : 160} height={24} />
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Skeleton variant="rounded" width={100} height={28} />
            <Skeleton variant="rounded" width={isMobile ? 100 : 140} height={28} />
            {!isMobile && <Skeleton variant="rounded" width={100} height={28} />}
          </Box>
        </Stack>
      </Paper>

      <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={0}>
            <Tab label={<Skeleton variant="text" width={isMobile ? 100 : 150} />} />
            <Tab label={<Skeleton variant="text" width={isMobile ? 80 : 120} />} />
          </Tabs>
        </Box>

        <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
          <QueueTableSkeleton />
        </Box>
      </Paper>
    </Box>
  );
};
