import React from 'react';
import { Box, Skeleton, Card, CardContent, Grid, useMediaQuery, useTheme } from '@mui/material';

// DCA Config Card skeleton for mobile (matches DCAConfigCard layout)
const DCAConfigCardSkeleton: React.FC = () => (
  <Card sx={{ mb: 2 }}>
    <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
      {/* Header: Name and chips */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Skeleton variant="text" width={100} height={24} />
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Skeleton variant="rounded" width={60} height={20} />
          <Skeleton variant="rounded" width={50} height={20} />
        </Box>
      </Box>

      {/* Quick stats */}
      <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
        <Box>
          <Skeleton variant="text" width={70} height={14} />
          <Skeleton variant="text" width={40} height={18} />
        </Box>
        <Box>
          <Skeleton variant="text" width={60} height={14} />
          <Skeleton variant="text" width={30} height={18} />
        </Box>
        <Box>
          <Skeleton variant="text" width={55} height={14} />
          <Skeleton variant="text" width={50} height={18} />
        </Box>
      </Box>

      {/* Footer: Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, pt: 1, borderTop: '1px solid rgba(224, 224, 224, 0.2)' }}>
        <Skeleton variant="rounded" width={32} height={32} />
        <Skeleton variant="rounded" width={32} height={32} />
      </Box>
    </CardContent>
  </Card>
);

const SettingsPageSkeleton: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box sx={{ p: { xs: 2, sm: 3 } }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Skeleton variant="text" width={isMobile ? 100 : 150} height={40} />
      </Box>

      {/* Tabs skeleton */}
      <Box sx={{ mb: 3, display: 'flex', gap: { xs: 1, sm: 2 }, flexWrap: 'wrap' }}>
        <Skeleton variant="rounded" width={isMobile ? 60 : 80} height={36} />
        <Skeleton variant="rounded" width={isMobile ? 70 : 100} height={36} />
        <Skeleton variant="rounded" width={isMobile ? 80 : 110} height={36} />
        <Skeleton variant="rounded" width={isMobile ? 90 : 130} height={36} />
      </Box>

      {/* Metric cards row */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width="60%" height={16} />
              <Skeleton variant="text" width="80%" height={28} />
              <Skeleton variant="text" width="40%" height={14} />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width="60%" height={16} />
              <Skeleton variant="text" width="80%" height={28} />
              <Skeleton variant="text" width="40%" height={14} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Settings cards */}
      <Grid container spacing={{ xs: 2, sm: 3 }}>
        {isMobile ? (
          // Mobile: DCA Config cards layout
          <Grid size={{ xs: 12 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Skeleton variant="text" width={120} height={28} />
              <Skeleton variant="rounded" width={100} height={36} />
            </Box>
            {[1, 2, 3].map((i) => (
              <DCAConfigCardSkeleton key={i} />
            ))}
          </Grid>
        ) : (
          // Desktop: Two-column card layout
          <>
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
          </>
        )}
      </Grid>
    </Box>
  );
};

export default SettingsPageSkeleton;
