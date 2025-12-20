import React from 'react';
import { Card, CardContent, Box, Typography, Divider } from '@mui/material';

interface SettingsSectionCardProps {
  title: string;
  icon: React.ReactNode;
  description?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  noDivider?: boolean;
}

const SettingsSectionCard: React.FC<SettingsSectionCardProps> = ({
  title,
  icon,
  description,
  children,
  action,
  noDivider = false,
}) => {
  return (
    <Card sx={{ height: '100%', maxWidth: '100%', overflow: 'hidden' }}>
      <CardContent sx={{ overflow: 'hidden', p: { xs: 1.5, sm: 2 }, '&:last-child': { pb: { xs: 1.5, sm: 2 } } }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: { xs: 1, sm: 2 }, flexWrap: 'wrap', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 1, sm: 1.5 } }}>
            <Box sx={{ color: 'primary.main', opacity: 0.7, display: 'flex', '& svg': { fontSize: { xs: 20, sm: 24 } } }}>
              {icon}
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600, fontSize: { xs: '0.95rem', sm: '1.25rem' } }}>
                {title}
              </Typography>
              {description && (
                <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' } }}>
                  {description}
                </Typography>
              )}
            </Box>
          </Box>
          {action && (
            <Box>
              {action}
            </Box>
          )}
        </Box>

        {!noDivider && <Divider sx={{ mb: { xs: 1, sm: 2 } }} />}

        {/* Content */}
        {children}
      </CardContent>
    </Card>
  );
};

export default SettingsSectionCard;
