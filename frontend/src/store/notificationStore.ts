import { create } from 'zustand';

export type NotificationType = 'success' | 'error' | 'info' | 'warning';

export interface Notification {
  id: string;
  message: string;
  type: NotificationType;
}

interface NotificationState {
  notifications: Notification[];
  showNotification: (message: string, type: NotificationType) => void;
  hideNotification: (id: string) => void;
}

const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  showNotification: (message, type) => {
    const id = Date.now().toString();
    set((state) => ({
      notifications: [...state.notifications, { id, message, type }],
    }));
    // Auto-dismiss after 6 seconds (optional, but Snackbar handles autoHideDuration too)
    setTimeout(() => {
        set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
        }));
    }, 6000);
  },
  hideNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}));

export default useNotificationStore;
