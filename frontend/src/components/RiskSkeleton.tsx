import React from 'react';
import { Box, Card, CardContent, Grid, Skeleton, Divider, useMediaQuery, useTheme } from '@mui/material';

export const RiskPageSkeleton: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Skeleton variant="text" width={isMobile ? 140 : 220} height={48} />
        <Skeleton variant="rounded" width={isMobile ? 120 : 180} height={40} />
      </Box>

      <Grid container spacing={{ xs: 2, sm: 3 }}>
        {/* Statistics Dashboard */}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width={isMobile ? 80 : 120} height={32} sx={{ mb: 2 }} />
              <Grid container spacing={2}>
                {[1, 2, 3].map((i) => (
                  <Grid size={{ xs: 4, sm: 4 }} key={i}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Skeleton variant="text" width={isMobile ? 50 : 80} height={isMobile ? 36 : 56} sx={{ mx: 'auto' }} />
                      <Skeleton variant="text" width={isMobile ? 60 : 120} height={20} sx={{ mx: 'auto' }} />
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
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width={isMobile ? 120 : 180} height={32} sx={{ mb: 2 }} />
              <Skeleton variant="text" width="80%" height={28} sx={{ mb: 2 }} />

              <Box sx={{ mb: 2 }}>
                <Skeleton variant="text" width={isMobile ? '80%' : '60%'} height={20} sx={{ mb: 1 }} />
                <Skeleton variant="text" width={isMobile ? '70%' : '50%'} height={20} sx={{ mb: 1 }} />
                <Skeleton variant="text" width={isMobile ? '75%' : '55%'} height={20} sx={{ mb: 1 }} />
                <Skeleton variant="text" width={isMobile ? '85%' : '70%'} height={20} sx={{ mb: 1 }} />
                <Skeleton variant="text" width={isMobile ? '78%' : '65%'} height={20} />
              </Box>

              <Divider sx={{ my: 2 }} />

              <Skeleton variant="text" width="70%" height={24} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="65%" height={24} sx={{ mb: 2 }} />

              <Box sx={{ mt: 2 }}>
                <Skeleton variant="text" width="60%" height={24} sx={{ mb: 1 }} />
                <Skeleton variant="text" width="80%" height={20} sx={{ ml: 2, mb: 1 }} />
                <Skeleton variant="text" width="75%" height={20} sx={{ ml: 2 }} />
              </Box>

              <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Skeleton variant="rounded" width={80} height={32} />
                <Skeleton variant="rounded" width={100} height={32} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Engine Status */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width={isMobile ? 100 : 140} height={32} sx={{ mb: 2 }} />
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

        {/* At-Risk Positions - Card layout on mobile, table on desktop */}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width={isMobile ? 120 : 180} height={32} sx={{ mb: 2 }} />

              {isMobile ? (
                // Mobile: Card-style list
                <Box>
                  {[1, 2, 3].map((i) => (
                    <Box
                      key={i}
                      sx={{
                        p: 1.5,
                        mb: 1.5,
                        border: '1px solid rgba(224, 224, 224, 0.2)',
                        borderRadius: 1,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Skeleton variant="text" width={80} height={20} />
                        <Skeleton variant="rounded" width={60} height={24} />
                      </Box>
                      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1 }}>
                        <Box>
                          <Skeleton variant="text" width={50} height={14} />
                          <Skeleton variant="text" width={70} height={18} />
                        </Box>
                        <Box>
                          <Skeleton variant="text" width={40} height={14} />
                          <Skeleton variant="text" width={60} height={18} />
                        </Box>
                      </Box>
                    </Box>
                  ))}
                </Box>
              ) : (
                // Desktop: Table layout
                <Box>
                  {/* Table header */}
                  <Box sx={{ display: 'flex', gap: 2, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
                    <Skeleton variant="text" width={120} height={24} />
                    <Skeleton variant="text" width={80} height={24} />
                    <Skeleton variant="text" width={80} height={24} />
                    <Skeleton variant="text" width={100} height={24} />
                    <Skeleton variant="text" width={100} height={24} />
                  </Box>
                  {/* Table rows */}
                  {[1, 2, 3].map((i) => (
                    <Box key={i} sx={{ display: 'flex', gap: 2, mb: 1, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
                      <Skeleton variant="text" width={120} height={20} />
                      <Skeleton variant="text" width={80} height={20} />
                      <Skeleton variant="text" width={80} height={20} />
                      <Skeleton variant="rounded" width={100} height={24} />
                      <Skeleton variant="rounded" width={100} height={24} />
                    </Box>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Actions - Card layout on mobile, table on desktop */}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent sx={{ p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
              <Skeleton variant="text" width={isMobile ? 100 : 160} height={32} sx={{ mb: 2 }} />

              {isMobile ? (
                // Mobile: Card-style list
                <Box>
                  {[1, 2].map((i) => (
                    <Box
                      key={i}
                      sx={{
                        p: 1.5,
                        mb: 1.5,
                        border: '1px solid rgba(224, 224, 224, 0.2)',
                        borderRadius: 1,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Skeleton variant="text" width={100} height={18} />
                        <Skeleton variant="rounded" width={50} height={24} />
                      </Box>
                      <Skeleton variant="text" width="60%" height={16} sx={{ mb: 0.5 }} />
                      <Skeleton variant="text" width="80%" height={16} />
                    </Box>
                  ))}
                </Box>
              ) : (
                // Desktop: Table layout
                <Box>
                  {/* Table header */}
                  <Box sx={{ display: 'flex', gap: 2, mb: 2, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.4)' }}>
                    <Skeleton variant="text" width={150} height={24} />
                    <Skeleton variant="text" width={100} height={24} />
                    <Skeleton variant="text" width={80} height={24} />
                    <Skeleton variant="text" width={100} height={24} />
                    <Skeleton variant="text" width={80} height={24} />
                  </Box>
                  {/* Table rows */}
                  {[1, 2].map((i) => (
                    <Box key={i} sx={{ display: 'flex', gap: 2, mb: 1, pb: 1, borderBottom: '1px solid rgba(224, 224, 224, 0.1)' }}>
                      <Skeleton variant="text" width={150} height={20} />
                      <Skeleton variant="text" width={100} height={20} />
                      <Skeleton variant="text" width={80} height={20} />
                      <Skeleton variant="text" width={100} height={20} />
                      <Skeleton variant="rounded" width={80} height={24} />
                    </Box>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
