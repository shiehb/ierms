import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { CheckCircle, XCircle, AlertCircle, Info, X, Bell } from "lucide-react";
import { NOTIFICATION_TYPES } from "../constants/notificationConstants";
import { notificationManager } from "../utils/notificationManager";

// Professional notification component
function ProfessionalNotification({ notification, onClose }) {
  const [isVisible, setIsVisible] = useState(true);
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!notification.persistent && notification.duration > 0) {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev <= 0) {
            setIsVisible(false);
            setTimeout(() => onClose(notification.id), 300);
            return 0;
          }
          return prev - 100 / (notification.duration / 50);
        });
      }, 50);
      return () => clearInterval(interval);
    }
  }, [
    notification.id,
    notification.duration,
    notification.persistent,
    onClose,
  ]);

  const getIcon = (type) => {
    switch (type) {
      case NOTIFICATION_TYPES.SUCCESS:
        return <CheckCircle size={20} className="text-green-500" />;
      case NOTIFICATION_TYPES.ERROR:
        return <XCircle size={20} className="text-red-500" />;
      case NOTIFICATION_TYPES.WARNING:
        return <AlertCircle size={20} className="text-amber-500" />;
      case NOTIFICATION_TYPES.INFO:
        return <Info size={20} className="text-blue-500" />;
      case NOTIFICATION_TYPES.PASSWORD_CHANGE:
        return <CheckCircle size={20} className="text-purple-500" />;
      case NOTIFICATION_TYPES.LOGIN:
        return <Bell size={20} className="text-indigo-500" />;
      case NOTIFICATION_TYPES.SYSTEM:
        return <Info size={20} className="text-gray-500" />;
      default:
        return <Info size={20} className="text-blue-500" />;
    }
  };

  const getStyles = (type) => {
    switch (type) {
      case NOTIFICATION_TYPES.SUCCESS:
        return {
          bg: "bg-green-50 border-green-200",
          text: "text-green-800",
          title: "text-green-900",
        };
      case NOTIFICATION_TYPES.ERROR:
        return {
          bg: "bg-red-50 border-red-200",
          text: "text-red-800",
          title: "text-red-900",
        };
      case NOTIFICATION_TYPES.WARNING:
        return {
          bg: "bg-amber-50 border-amber-200",
          text: "text-amber-800",
          title: "text-amber-900",
        };
      case NOTIFICATION_TYPES.INFO:
        return {
          bg: "bg-blue-50 border-blue-200",
          text: "text-blue-800",
          title: "text-blue-900",
        };
      case NOTIFICATION_TYPES.PASSWORD_CHANGE:
        return {
          bg: "bg-purple-50 border-purple-200",
          text: "text-purple-800",
          title: "text-purple-900",
        };
      case NOTIFICATION_TYPES.LOGIN:
        return {
          bg: "bg-indigo-50 border-indigo-200",
          text: "text-indigo-800",
          title: "text-indigo-900",
        };
      case NOTIFICATION_TYPES.SYSTEM:
        return {
          bg: "bg-gray-50 border-gray-200",
          text: "text-gray-800",
          title: "text-gray-900",
        };
      default:
        return {
          bg: "bg-blue-50 border-blue-200",
          text: "text-blue-800",
          title: "text-blue-900",
        };
    }
  };

  const styles = getStyles(notification.type);

  if (!isVisible) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      className={`
        relative max-w-lg w-full flex items-start p-4 border rounded-lg shadow-xl
        transition-all duration-300 ease-in-out transform
        animate-slide-down ${styles.bg}
      `}
    >
      {/* Progress bar */}
      {!notification.persistent && notification.duration > 0 && (
        <div className="absolute top-0 left-0 w-full h-1 bg-black/10 rounded-t-lg overflow-hidden">
          <div
            className="h-full bg-current opacity-30 transition-all duration-50"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      <div className="flex-shrink-0">{getIcon(notification.type)}</div>
      <div className="ml-3 flex-1 min-w-0">
        {notification.title && (
          <p className={`text-sm font-semibold ${styles.title} mb-1`}>
            {notification.title}
          </p>
        )}
        <p className={`text-sm ${styles.text} break-words`}>
          {notification.message}
        </p>
        {notification.actions && notification.actions.length > 0 && (
          <div className="mt-3 flex gap-2">
            {notification.actions.map((action, index) => (
              <button
                key={index}
                onClick={action.onClick}
                className={`text-xs font-medium px-3 py-1 rounded-md transition-colors ${
                  action.primary
                    ? "bg-white text-gray-700 hover:bg-gray-100"
                    : "text-gray-600 hover:text-gray-800"
                }`}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <button
        onClick={() => onClose(notification.id)}
        className="ml-4 flex-shrink-0 p-1 text-gray-400 hover:text-gray-600 hover:bg-white/50 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        aria-label="Close notification"
      >
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

// Notification container component
function NotificationContainer() {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    const unsubscribe = notificationManager.subscribe(setNotifications);
    return unsubscribe;
  }, []);

  const handleClose = useCallback((id) => {
    notificationManager.remove(id);
  }, []);

  if (notifications.length === 0) return null;

  return createPortal(
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] space-y-3 max-h-screen overflow-y-auto">
      {notifications.map((notification) => (
        <ProfessionalNotification
          key={notification.id}
          notification={notification}
          onClose={handleClose}
        />
      ))}
    </div>,
    document.body
  );
}

export default NotificationContainer;
