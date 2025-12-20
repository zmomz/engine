import React from 'react';
import { Box, Skeleton, Card, CardContent, Grid } from '@mui/material';

const SettingsPageSkeleton: React.FC = () => {
  return (
    <Box sx={{ p: { xs: 2, sm: 3 } }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Skeleton variant="text" width={150} height={40} />
      </Box>

      {/* Tabs skeleton */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
        <Skeleton variant="rounded" width={80} height={36} />
        <Skeleton variant="rounded" width={100} height={36} />
        <Skeleton variant="rounded" width={110} height={36} />
        <Skeleton variant="rounded" width={130} height={36} />
      </Box>

      {/* Metric cards row */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Skeleton variant="text" width="60%" height={20} />
              <Skeleton variant="text" width="80%" height={32} />
              <Skeleton variant="text" width="40%" height={16} />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Skeleton variant="text" width="60%" height={20} />
              <Skeleton variant="text" width="80%" height={32} />
              <Skeleton variant="text" width="40%" height={16} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Settings cards */}
      <Grid container spacing={{ xs: 2, sm: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Skeleton variant="circular" width={24} height={24} />
                <Skeleton variant="text" width={150} height={28} />
              </Box>
              <Skeleton variant="rectangular" width="100%" height={1} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <Skeleton variant="circular" width={24} height={24} />
                <Skeleton variant="text" width={180} height={28} />
              </Box>
              <Skeleton variant="rectangular" width="100%" height={1} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} sx={{ mb: 2 }} />
              <Skeleton variant="rounded" width="100%" height={56} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SettingsPageSkeleton;
