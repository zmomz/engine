import React from 'react';
import { Box, Card, CardContent, Grid, Skeleton, Divider } from '@mui/material';

export const RiskPageSkeleton: React.FC = () => (
  <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
      <Skeleton variant="text" width={220} height={48} />
      <Skeleton variant="rounded" width={180} height={40} />
    </Box>

    <Grid container spacing={{ xs: 2, sm: 3 }}>
      {/* Statistics Dashboard */}
      <Grid size={{ xs: 12 }}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width={120} height={32} sx={{ mb: 2 }} />
            <Grid container spacing={2}>
              {[1, 2, 3].map((i) => (
                <Grid size={{ xs: 12, sm: 4 }} key={i}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Skeleton variant="text" width={80} height={56} sx={{ mx: 'auto' }} />
                    <Skeleton variant="text" width={120} height={20} sx={{ mx: 'auto' }} />
                  </Box>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      </Grid>

      {/* Current Evaluation */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width={180} height={32} sx={{ mb: 2 }} />
            <Skeleton variant="text" width="80%" height={28} sx={{ mb: 2 }} />

            <Box sx={{ mb: 2 }}>
              <Skeleton variant="text" width="60%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="50%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="55%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="70%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="65%" height={20} />
            </Box>

            <Divider sx={{ my: 2 }} />

            <Skeleton variant="text" width="70%" height={24} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="65%" height={24} sx={{ mb: 2 }} />

            <Box sx={{ mt: 2 }}>
              <Skeleton variant="text" width="60%" height={24} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="80%" height={20} sx={{ ml: 2, mb: 1 }} />
              <Skeleton variant="text" width="75%" height={20} sx={{ ml: 2 }} />
            </Box>

            <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
              <Skeleton variant="rounded" width={80} height={32} />
              <Skeleton variant="rounded" width={100} height={32} />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Engine Status */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width={140} height={32} sx={{ mb: 2 }} />
            <Skeleton variant="text" width="60%" height={28} sx={{ mb: 2 }} />

            <Skeleton variant="text" width="50%" height={24} sx={{ mb: 1 }} />
            <Box sx={{ ml: 2 }}>
              <Skeleton variant="text" width="70%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="80%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="75%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="65%" height={20} />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* At-Risk Positions */}
      <Grid size={{ xs: 12 }}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width={180} height={32} sx={{ mb: 2 }} />
            <Box>
              {/* Table header */}
              <Box sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
                <Skeleton variant="text" width={120} height={24} />
                <Skeleton variant="text" width={80} height={24} />
                <Skeleton variant="text" width={80} height={24} />
                <Skeleton variant="text" width={100} height={24} />
                <Skeleton variant="text" width={100} height={24} />
              </Box>
              {/* Table rows */}
              {[1, 2, 3].map((i) => (
                <Box key={i} sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 1, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
                  <Skeleton variant="text" width={120} height={20} />
                  <Skeleton variant="text" width={80} height={20} />
                  <Skeleton variant="text" width={80} height={20} />
                  <Skeleton variant="rounded" width={100} height={24} />
                  <Skeleton variant="rounded" width={100} height={24} />
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Recent Actions */}
      <Grid size={{ xs: 12 }}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width={160} height={32} sx={{ mb: 2 }} />
            <Box>
              {/* Table header */}
              <Box sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
                <Skeleton variant="text" width={150} height={24} />
                <Skeleton variant="text" width={100} height={24} />
                <Skeleton variant="text" width={80} height={24} />
                <Skeleton variant="text" width={100} height={24} />
                <Skeleton variant="text" width={80} height={24} />
              </Box>
              {/* Table rows */}
              {[1, 2].map((i) => (
                <Box key={i} sx={{ display: 'flex', gap: { xs: 1.5, sm: 2 }, mb: 1, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
                  <Skeleton variant="text" width={150} height={20} />
                  <Skeleton variant="text" width={100} height={20} />
                  <Skeleton variant="text" width={80} height={20} />
                  <Skeleton variant="text" width={100} height={20} />
                  <Skeleton variant="rounded" width={80} height={24} />
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  </Box>
);
