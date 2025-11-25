import { NOTIFICATION_TYPES } from "../constants/notificationConstants";
import { notificationManager } from "../utils/notificationManager";

// Hook for using notifications
export function useNotifications() {
  return {
    success: notificationManager.success.bind(notificationManager),
    error: (message, options = {}) => {
      // Use debounced error notifications to prevent spam
      notificationManager.addDebounced(
        {
          type: NOTIFICATION_TYPES.ERROR,
          message,
          duration: 8000,
          ...options,
        },
        2000
      ); // 2 second debounce for errors
    },
    warning: notificationManager.warning.bind(notificationManager),
    info: notificationManager.info.bind(notificationManager),
    passwordChange:
      notificationManager.passwordChange.bind(notificationManager),
    login: notificationManager.login.bind(notificationManager),
    system: notificationManager.system.bind(notificationManager),
    add: notificationManager.add.bind(notificationManager),
    addDebounced: notificationManager.addDebounced.bind(notificationManager),
    remove: notificationManager.remove.bind(notificationManager),
    clear: notificationManager.clear.bind(notificationManager),
  };
}

// Global notification functions for backward compatibility
export const showNotification = (type, message, options = {}) => {
  return notificationManager.add({ type, message, ...options });
};
