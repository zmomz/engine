import React from 'react';
import { Alert, AlertTitle, Box, IconButton, Collapse } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import InfoIcon from '@mui/icons-material/Info';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

export interface AlertBannerProps {
  severity: 'info' | 'warning' | 'error' | 'success';
  title?: string;
  message: string;
  action?: React.ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  variant?: 'standard' | 'filled' | 'outlined';
  show?: boolean;
}

const severityIcons = {
  info: <InfoIcon />,
  warning: <WarningIcon />,
  error: <ErrorIcon />,
  success: <CheckCircleIcon />,
};

export const AlertBanner: React.FC<AlertBannerProps> = ({
  severity,
  title,
  message,
  action,
  dismissible = true,
  onDismiss,
  variant = 'filled',
  show = true,
}) => {
  const [open, setOpen] = React.useState(show);

  React.useEffect(() => {
    setOpen(show);
  }, [show]);

  const handleDismiss = () => {
    setOpen(false);
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <Collapse in={open}>
      <Alert
        severity={severity}
        variant={variant}
        icon={severityIcons[severity]}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {action}
            {dismissible && (
              <IconButton
                aria-label="close"
                color="inherit"
                size="small"
                onClick={handleDismiss}
              >
                <CloseIcon fontSize="inherit" />
              </IconButton>
            )}
          </Box>
        }
        sx={{
          mb: 2,
          '& .MuiAlert-message': {
            width: '100%',
          },
        }}
      >
        {title && <AlertTitle sx={{ fontWeight: 600 }}>{title}</AlertTitle>}
        {message}
      </Alert>
    </Collapse>
  );
};

export default AlertBanner;
