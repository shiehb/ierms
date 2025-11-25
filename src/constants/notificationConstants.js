// Notification types
export const NOTIFICATION_TYPES = {
  SUCCESS: "success",
  ERROR: "error",
  WARNING: "warning",
  INFO: "info",
  PASSWORD_CHANGE: "password_change",
  LOGIN: "login",
  SYSTEM: "system",
};

// Default durations
export const NOTIFICATION_DURATION = {
  SHORT: 3000,
  DEFAULT: 5000,
  LONG: 8000,
};

// For backwards compatibility
export const NOT_TYPES = NOTIFICATION_TYPES;
export const NOT_DURATION = NOTIFICATION_DURATION;
