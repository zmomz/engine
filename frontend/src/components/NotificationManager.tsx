import React, { useEffect, useState } from 'react';
import { Snackbar, Alert } from '@mui/material';
import useNotificationStore, { Notification } from '../store/notificationStore';

const NotificationManager: React.FC = () => {
  const { notifications, hideNotification } = useNotificationStore();
  const [open, setOpen] = useState(false);
  const [currentNotification, setCurrentNotification] = useState<Notification | null>(notifications[0] || null);

  useEffect(() => {
    if (notifications.length > 0 && !open) {
      setCurrentNotification(notifications[0]);
      setOpen(true);
    } else if (notifications.length > 0 && open && currentNotification && notifications[0].id !== currentNotification.id) {
       // If we have a new notification and one is already open, 
       // typically we wait for the first to close.
       // But if we want to replace immediately:
       setOpen(false);
       setTimeout(() => {
         setCurrentNotification(notifications[0]);
         setOpen(true);
       }, 150);
    }
  }, [notifications, open, currentNotification]);

  const handleClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  const handleExited = () => {
      if (currentNotification) {
        hideNotification(currentNotification.id);
        setCurrentNotification(null);
      }
  };

  if (!currentNotification) return null;

  return (
    <Snackbar
      open={open}
      autoHideDuration={6000}
      onClose={handleClose}
      TransitionProps={{ onExited: handleExited }}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    >
      <Alert onClose={handleClose} severity={currentNotification.type} sx={{ width: '100%' }}>
        {currentNotification.message}
      </Alert>
    </Snackbar>
  );
};

export default NotificationManager;
