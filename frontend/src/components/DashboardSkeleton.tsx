import React from 'react';
import { Box, Card, CardContent, Grid, Skeleton } from '@mui/material';

export const MetricCardSkeleton: React.FC = () => (
  <Card>
    <CardContent>
      <Skeleton variant="text" width="60%" height={20} sx={{ mb: 1 }} />
      <Skeleton variant="text" width="80%" height={40} sx={{ mb: 1 }} />
      <Skeleton variant="circular" width={24} height={24} />
    </CardContent>
  </Card>
);

export const ChartCardSkeleton: React.FC<{ height?: number }> = ({ height = 300 }) => (
  <Card>
    <CardContent>
      <Skeleton variant="text" width="40%" height={28} sx={{ mb: 2 }} />
      <Skeleton variant="rectangular" width="100%" height={height} sx={{ borderRadius: 1 }} />
    </CardContent>
  </Card>
);

export const StatusBannerSkeleton: React.FC = () => (
  <Card>
    <CardContent>
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        flexWrap: 'wrap',
        gap: 2
      }}>
        <Box sx={{ width: { xs: '100%', sm: 'auto' } }}>
          <Skeleton variant="text" width={120} height={28} sx={{ mb: 1 }} />
          <Skeleton variant="rounded" width={100} height={32} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width={140} height={16} />
        </Box>
        <Box sx={{ width: { xs: '100%', sm: 'auto' } }}>
          <Skeleton variant="text" width={140} height={20} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width={100} height={36} />
          <Skeleton variant="text" width={120} height={16} />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, width: { xs: '100%', sm: 'auto' }, flexDirection: { xs: 'column', sm: 'row' } }}>
          <Skeleton variant="rounded" width="100%" height={36} sx={{ minWidth: { sm: 120 } }} />
          <Skeleton variant="rounded" width="100%" height={36} sx={{ minWidth: { sm: 140 } }} />
        </Box>
      </Box>
    </CardContent>
  </Card>
);

export const LiveDashboardSkeleton: React.FC = () => (
  <Grid container spacing={3}>
    {/* Engine Controls Banner Skeleton */}
    <Grid size={{ xs: 12 }}>
      <StatusBannerSkeleton />
    </Grid>

    {/* System Status Banner Skeleton */}
    <Grid size={{ xs: 12 }}>
      <StatusBannerSkeleton />
    </Grid>

    {/* Key Metrics Skeleton */}
    {[1, 2, 3, 4].map((i) => (
      <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
        <MetricCardSkeleton />
      </Grid>
    ))}

    {/* Capital Allocation Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="60%" height={28} sx={{ mb: 3 }} />
          <Box sx={{
            display: 'flex',
            justifyContent: 'space-around',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: { xs: 2, sm: 0 }
          }}>
            <Box sx={{ textAlign: 'center' }}>
              <Skeleton variant="text" width={120} height={48} sx={{ mb: 1, mx: 'auto' }} />
              <Skeleton variant="text" width={80} height={20} sx={{ mx: 'auto' }} />
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Skeleton variant="text" width={120} height={48} sx={{ mb: 1, mx: 'auto' }} />
              <Skeleton variant="text" width={80} height={20} sx={{ mx: 'auto' }} />
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Grid>

    {/* Queue Status Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="60%" height={28} sx={{ mb: 3 }} />
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Skeleton variant="text" width="50%" height={24} />
              <Skeleton variant="text" width="30%" height={28} />
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Skeleton variant="text" width="50%" height={24} />
              <Skeleton variant="rounded" width={50} height={28} />
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Grid>
  </Grid>
);

export const PerformanceDashboardSkeleton: React.FC = () => (
  <Grid container spacing={3}>
    {/* PnL Summary Cards Skeleton */}
    {[1, 2, 3, 4].map((i) => (
      <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
        <MetricCardSkeleton />
      </Grid>
    ))}

    {/* Equity Curve Skeleton */}
    <Grid size={{ xs: 12 }}>
      <ChartCardSkeleton />
    </Grid>

    {/* Win/Loss Stats Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="50%" height={28} sx={{ mb: 2 }} />
          <Box sx={{ mt: 2 }}>
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Skeleton variant="text" width="40%" height={24} />
                <Skeleton variant="text" width="30%" height={24} />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Grid>

    {/* Risk Metrics Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="40%" height={28} sx={{ mb: 2 }} />
          <Box sx={{ mt: 2 }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Skeleton variant="text" width="40%" height={24} />
                <Skeleton variant="text" width="30%" height={24} />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Grid>

    {/* Charts Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <ChartCardSkeleton />
    </Grid>
    <Grid size={{ xs: 12, md: 6 }}>
      <ChartCardSkeleton />
    </Grid>

    {/* Best/Worst Trades Skeleton */}
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="40%" height={28} sx={{ mb: 2 }} />
          {[1, 2, 3, 4, 5].map((i) => (
            <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1, pt: 1 }}>
              <Skeleton variant="text" width="30%" height={20} />
              <Skeleton variant="text" width="30%" height={20} />
            </Box>
          ))}
        </CardContent>
      </Card>
    </Grid>
    <Grid size={{ xs: 12, md: 6 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width="40%" height={28} sx={{ mb: 2 }} />
          {[1, 2, 3, 4, 5].map((i) => (
            <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1, pt: 1 }}>
              <Skeleton variant="text" width="30%" height={20} />
              <Skeleton variant="text" width="30%" height={20} />
            </Box>
          ))}
        </CardContent>
      </Card>
    </Grid>
  </Grid>
);
