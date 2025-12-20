import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface KeyboardShortcutsOptions {
  onRefresh?: () => void;
  onForceStart?: () => void;
  onForceStop?: () => void;
  onRunRiskEvaluation?: () => void;
}

export const useKeyboardShortcuts = (options: KeyboardShortcutsOptions = {}) => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const isInputField = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

      // Don't trigger shortcuts if user is typing in an input field
      if (isInputField) {
        return;
      }

      // Navigation shortcuts (Alt + number)
      if (event.altKey && !event.ctrlKey && !event.shiftKey) {
        switch (event.key) {
          case '1':
            event.preventDefault();
            navigate('/overview');
            break;
          case '2':
            event.preventDefault();
            navigate('/dashboard');
            break;
          case '3':
            event.preventDefault();
            navigate('/positions');
            break;
          case '4':
            event.preventDefault();
            navigate('/queue');
            break;
          case '5':
            event.preventDefault();
            navigate('/risk');
            break;
          case '6':
            event.preventDefault();
            navigate('/analytics');
            break;
          case '7':
            event.preventDefault();
            navigate('/settings');
            break;
          default:
            break;
        }
      }

      // Global refresh (Ctrl/Cmd + R)
      if ((event.ctrlKey || event.metaKey) && event.key === 'r' && !event.shiftKey) {
        event.preventDefault();
        if (options.onRefresh) {
          options.onRefresh();
        }
      }

      // Risk management shortcuts (only on Risk/Overview pages)
      const isRiskOrOverviewPage = location.pathname === '/risk' || location.pathname === '/overview';

      if (isRiskOrOverviewPage && !event.ctrlKey && !event.altKey && !event.metaKey) {
        switch (event.key.toLowerCase()) {
          case 'f':
            event.preventDefault();
            if (options.onForceStart) {
              options.onForceStart();
            }
            break;
          case 's':
            event.preventDefault();
            if (options.onForceStop) {
              options.onForceStop();
            }
            break;
          case 'e':
            event.preventDefault();
            if (options.onRunRiskEvaluation) {
              options.onRunRiskEvaluation();
            }
            break;
          default:
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [navigate, location, options]);
};

export default useKeyboardShortcuts;
