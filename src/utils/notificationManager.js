import {
  NOTIFICATION_TYPES,
  NOTIFICATION_DURATION,
} from "../constants/notificationConstants";

// Notification manager class
export class NotificationManager {
  constructor() {
    this.notifications = [];
    this.listeners = [];
    this.nextId = 1;
    this.debounceMap = new Map(); // Track debounced notifications
  }

  // Add notification
  add(notification) {
    // Check for duplicate notifications (same type, title, and message)
    const isDuplicate = this.notifications.some(
      (existing) =>
        existing.type === (notification.type || NOTIFICATION_TYPES.INFO) &&
        existing.title === (notification.title || "") &&
        existing.message === (notification.message || "") &&
        Date.now() - existing.timestamp.getTime() < 1000 // Within last second
    );

    if (isDuplicate) {
      console.log("Duplicate notification prevented:", notification);
      return null;
    }

    const id = this.nextId++;
    const newNotification = {
      id,
      type: notification.type || NOTIFICATION_TYPES.INFO,
      title: notification.title || "",
      message: notification.message || "",
      duration: notification.duration || 5000,
      persistent: notification.persistent || false,
      actions: notification.actions || [],
      timestamp: new Date(),
      ...notification,
    };

    this.notifications.push(newNotification);
    this.notifyListeners();

    // Auto-remove after duration (unless persistent)
    if (!newNotification.persistent && newNotification.duration > 0) {
      setTimeout(() => {
        this.remove(id);
      }, newNotification.duration);
    }

    return id;
  }

  // Add notification with debouncing
  addDebounced(notification, debounceMs = 1000) {
    const key = `${notification.type || NOTIFICATION_TYPES.INFO}-${
      notification.title || ""
    }-${notification.message || ""}`;

    // Clear existing timeout for this key
    if (this.debounceMap.has(key)) {
      clearTimeout(this.debounceMap.get(key));
    }

    // Set new timeout
    const timeoutId = setTimeout(() => {
      this.add(notification);
      this.debounceMap.delete(key);
    }, debounceMs);

    this.debounceMap.set(key, timeoutId);
  }

  // Remove notification
  remove(id) {
    this.notifications = this.notifications.filter((n) => n.id !== id);
    this.notifyListeners();
  }

  // Clear all notifications
  clear() {
    this.notifications = [];
    this.notifyListeners();
  }

  // Subscribe to changes
  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  // Notify all listeners
  notifyListeners() {
    this.listeners.forEach((listener) => listener([...this.notifications]));
  }

  // Convenience methods
  success(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.SUCCESS,
      message,
      ...options,
    });
  }

  error(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.ERROR,
      message,
      duration: 8000, // Longer duration for errors
      ...options,
    });
  }

  warning(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.WARNING,
      message,
      ...options,
    });
  }

  info(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.INFO,
      message,
      ...options,
    });
  }

  passwordChange(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.PASSWORD_CHANGE,
      title: "Password Change",
      message,
      duration: 6000,
      ...options,
    });
  }

  login(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.LOGIN,
      title: "Login",
      message,
      ...options,
    });
  }

  system(message, options = {}) {
    return this.add({
      type: NOTIFICATION_TYPES.SYSTEM,
      title: "System",
      message,
      ...options,
    });
  }
}

// Global notification manager instance
export const notificationManager = new NotificationManager();
