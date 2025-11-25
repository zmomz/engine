import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button } from '@mui/material';
import useConfirmStore from '../store/confirmStore';

const GlobalConfirmDialog: React.FC = () => {
  const { isOpen, options, closeConfirm } = useConfirmStore();

  return (
    <Dialog
      open={isOpen}
      onClose={() => closeConfirm(false)}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
    >
      <DialogTitle id="confirm-dialog-title">
        {options.title || 'Confirm Action'}
      </DialogTitle>
      <DialogContent>
        <DialogContentText id="confirm-dialog-description">
          {options.message}
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => closeConfirm(false)} color="inherit">
          {options.cancelText || 'Cancel'}
        </Button>
        <Button onClick={() => closeConfirm(true)} color="primary" variant="contained" autoFocus>
          {options.confirmText || 'Confirm'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default GlobalConfirmDialog;
