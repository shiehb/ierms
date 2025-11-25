import { Link, useNavigate, useLocation } from "react-router-dom";
import Layout from "../components/Layout";
import { useState, useRef, useEffect, useCallback } from "react";
import { Eye, EyeOff, AlertCircle, RefreshCw } from "lucide-react";
import useAuth from "../hooks/useAuth";
import { useNotifications } from "../hooks/useNotifications";
import axios from "axios";
import { API_BASE_URL } from "../config/api";

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isServerDown, setIsServerDown] = useState(false);
  const [isCheckingServer, setIsCheckingServer] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const passwordInputRef = useRef(null);
  const notifications = useNotifications();
  const { login } = useAuth();
  const shownMessageRef = useRef(null); // Track which message we've already shown

  // Check server health
  const checkServerHealth = useCallback(async () => {
    if (!navigator.onLine) {
      setIsServerDown(true);
      return;
    }

    setIsCheckingServer(true);
    let timeoutId;
    try {
      // Use a lightweight endpoint to check server availability
      // Try OPTIONS request to auth/login endpoint as it's public
      const controller = new AbortController();
      timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      await axios.options(`${API_BASE_URL}auth/login/`, {
        signal: controller.signal,
        timeout: 5000,
      });

      clearTimeout(timeoutId);
      setIsServerDown(false);
      // Clear server error if it was set
      setErrors((prev) => {
        if (
          prev.general?.includes("Server is down") ||
          prev.general?.includes("unreachable")
        ) {
          const { general: _general, ...rest } = prev;
          return rest;
        }
        return prev;
      });
    } catch (err) {
      if (timeoutId) clearTimeout(timeoutId);
      // Check if it's a network/server error
      if (
        !err.response ||
        err.code === "ECONNREFUSED" ||
        err.code === "ETIMEDOUT" ||
        err.code === "ERR_NETWORK" ||
        err.code === "ENOTFOUND" ||
        err.code === "ERR_CANCELED" ||
        err.name === "AbortError" ||
        err.message?.includes("Network Error") ||
        err.message?.includes("timeout") ||
        err.message?.includes("Failed to fetch")
      ) {
        setIsServerDown(true);
        setErrors((prev) => ({
          ...prev,
          general:
            "Server is down or unreachable. Please check your connection and try again later.",
        }));
      } else {
        // If we got a response, server is up (might be 405 for OPTIONS which is fine)
        setIsServerDown(false);
      }
    } finally {
      setIsCheckingServer(false);
    }
  }, []);

  // Check server on mount
  useEffect(() => {
    checkServerHealth();
  }, [checkServerHealth]);

  // Auto-retry health check when network comes back online
  useEffect(() => {
    const handleOnline = () => {
      checkServerHealth();
    };

    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, [checkServerHealth]);

  // Show message from state (e.g., after password change)
  useEffect(() => {
    const message = location.state?.message;
    // Only show if we have a message and haven't shown this exact message yet
    if (message && shownMessageRef.current !== message) {
      notifications.success(message, {
        title: "Success",
        duration: 5000,
      });
      // Mark this message as shown
      shownMessageRef.current = message;
      // Clear the state to prevent showing the message again
      window.history.replaceState({}, document.title, location.pathname);
    }
  }, [location.state?.message, location.pathname]); // Removed 'notifications' - it's stable from the hook

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    // Clear error when user starts typing
    if (errors[e.target.name]) {
      setErrors({
        ...errors,
        [e.target.name]: "",
      });
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = "Email is invalid";
    }

    if (!formData.password.trim()) {
      newErrors.password = "Password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) return;

    // Check server health before submission
    if (!navigator.onLine) {
      setErrors({ general: "No internet connection." });
      notifications.error("No internet connection.", {
        title: "Connection Error",
      });
      return;
    }

    // If server is down, prevent submission
    if (isServerDown) {
      setErrors({
        general:
          "Server is down or unreachable. Please check your connection and try again later.",
      });
      notifications.error(
        "Server is down or unreachable. Please check your connection and try again later.",
        {
          title: "Server Unavailable",
        }
      );
      return;
    }

    // Quick health check before submission
    setIsCheckingServer(true);
    await checkServerHealth();
    setIsCheckingServer(false);

    // If server was down and still is after check, prevent submission
    if (isServerDown) {
      setErrors({
        general:
          "Server is down or unreachable. Please check your connection and try again later.",
      });
      notifications.error(
        "Server is down or unreachable. Please check your connection and try again later.",
        {
          title: "Server Unavailable",
        }
      );
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      const result = await login(formData.email, formData.password);

      if (result.mustChangePassword) {
        navigate("/force-change-password");
      } else {
        navigate("/");
      }
    } catch (err) {
      const errorData = err.response?.data;
      const errorCode = errorData?.error_code;

      if (errorCode === "ACCOUNT_LOCKED") {
        const details = errorData?.details || {};
        const remainingMinutes = details.remaining_minutes ?? 0;
        const lockoutMinutes =
          details.lockout_duration_minutes ?? remainingMinutes;
        const unlockAtIso = details.unlock_at;
        const unlockAt = unlockAtIso ? new Date(unlockAtIso) : null;
        const unlockTimeString = unlockAt
          ? unlockAt.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })
          : null;
        const minutesLabel = (value) => (value === 1 ? "minute" : "minutes");

        const message = unlockTimeString
          ? `Account locked until ${unlockTimeString}. Try again in ${remainingMinutes} ${minutesLabel(
              remainingMinutes
            )}.`
          : `Account locked. Try again in ${remainingMinutes} ${minutesLabel(
              remainingMinutes
            )}.`;
        const extendedMessage = `${message} Lockout duration is ${lockoutMinutes} ${minutesLabel(
          lockoutMinutes
        )}. If you no longer remember your password, use “Forgot Password” or contact your administrator to regain access sooner.`;

        setErrors({ general: extendedMessage });
        notifications.error(extendedMessage, {
          title: "Account Locked",
          duration: 8000,
        });
      } else if (errorCode === "INVALID_CREDENTIALS") {
        setFormData((prev) => ({ ...prev, password: "" }));
        const details = errorData?.details || {};
        const failedAttempts = details.failed_attempts;
        const maxAttempts = details.max_attempts;
        const remainingAttempts = details.remaining_attempts;
        const isLastWindow = details.is_last_attempt_window;
        const lockoutMinutes = details.lockout_duration_minutes ?? 3;
        const unlockAtIso = details.unlock_at;
        const unlockAt = unlockAtIso ? new Date(unlockAtIso) : null;
        const unlockTimeString = unlockAt
          ? unlockAt.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })
          : null;

        const baseMessage = "Invalid email or password.";
        let warningMessage = null;
        if (
          typeof failedAttempts === "number" &&
          typeof maxAttempts === "number" &&
          typeof remainingAttempts === "number"
        ) {
          const currentAttempt = Math.min(failedAttempts, maxAttempts);
          const attemptWord = remainingAttempts === 1 ? "attempt" : "attempts";
          warningMessage = `Warning: Attempt ${currentAttempt} of ${maxAttempts}. Only ${remainingAttempts} ${attemptWord} left before a ${lockoutMinutes}-minute lockout. Double-check your credentials or use “Forgot Password” to avoid being locked out.`;
          if (unlockTimeString) {
            warningMessage += ` Locked accounts reopen at ${unlockTimeString}.`;
          }
        }

        const showWarning = Boolean(isLastWindow && warningMessage);
        const nextErrors = { password: baseMessage };
        if (showWarning) {
          nextErrors.general = warningMessage;
        }
        setErrors(nextErrors);

        notifications.error(showWarning ? warningMessage : baseMessage, {
          title: showWarning ? "Final Attempts" : "Login Failed",
        });
      } else if (errorCode === "ACCOUNT_DEACTIVATED") {
        setErrors({ general: "Account deactivated. Contact administrator." });
        notifications.error("Account deactivated. Contact administrator.", {
          title: "Account Deactivated",
        });
      } else if (!navigator.onLine) {
        setIsServerDown(true);
        setErrors({ general: "No internet connection." });
        notifications.error("No internet connection.", {
          title: "Connection Error",
        });
      } else if (
        !err.response ||
        err.code === "ECONNREFUSED" ||
        err.code === "ETIMEDOUT" ||
        err.code === "ERR_NETWORK" ||
        err.code === "ENOTFOUND" ||
        err.message?.includes("Network Error") ||
        err.message?.includes("timeout") ||
        err.message?.includes("Failed to fetch")
      ) {
        // Server is unreachable
        setIsServerDown(true);
        const message =
          "Server is down or unreachable. Please check your connection and try again later.";
        setErrors({ general: message });
        notifications.error(message, { title: "Server Unavailable" });
      } else {
        setErrors({ general: "Login failed. Please try again." });
        notifications.error("Login failed. Please try again.", {
          title: "Login Error",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Layout>
      {/* Server Down Error Container - Outside Form */}
      {isServerDown && (
        <div className="w-full max-w-md mx-auto mb-6 p-6 bg-red-50 border-2 border-red-200 rounded-xl shadow-lg animate-fade-in">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="flex items-center justify-center w-16 h-16 bg-red-100 rounded-full">
              <AlertCircle className="w-8 h-8 text-red-600" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold text-red-900">
                Server Unavailable
              </h3>
              <p className="text-sm text-red-700">
                Server is down or unreachable. Please check your connection and
                try again later.
              </p>
            </div>
            <button
              onClick={checkServerHealth}
              disabled={isCheckingServer}
              className="flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 mt-2"
              aria-label="Retry server connection"
            >
              {isCheckingServer ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Checking server...</span>
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  <span>Retry</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Login Form - Only show when server is not down */}
      {!isServerDown && (
        <div className="w-full max-w-md mx-auto p-8 bg-white shadow-lg rounded-2xl">
          <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
            Integrated Establishment Regulatory Management System
          </h2>

          {/* Regular error messages (account locked, invalid credentials, etc.) */}
          {errors.general &&
            !errors.general.includes("Server is down") &&
            !errors.general.includes("unreachable") && (
              <div className="p-3 mb-4 text-sm text-center text-red-600 bg-red-100 rounded-lg animate-fade-in">
                {errors.general}
              </div>
            )}

          {/* Checking server status indicator */}
          {isCheckingServer && (
            <div className="p-3 mb-4 text-sm text-center text-blue-600 bg-blue-100 rounded-lg flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Checking server connection...</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-gray-700"
                >
                  Email *
                </label>
                {errors.email && (
                  <p className="text-xs text-red-500">{errors.email}</p>
                )}
              </div>
              <input
                type="email"
                name="email"
                id="email"
                autoComplete="email"
                placeholder="Enter your email"
                value={formData.email}
                onChange={handleChange}
                disabled={isSubmitting || isCheckingServer}
                required
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 transition-colors ${
                  errors.email ? "border-red-500" : "border-gray-300"
                } ${
                  isSubmitting || isCheckingServer
                    ? "bg-gray-100 cursor-not-allowed opacity-60"
                    : ""
                }`}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-gray-700"
                >
                  Password *
                </label>
              </div>
              <div className="relative">
                <input
                  ref={passwordInputRef}
                  type={showPassword ? "text" : "password"}
                  name="password"
                  id="password"
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={formData.password}
                  onChange={handleChange}
                  disabled={isSubmitting || isCheckingServer}
                  required
                  className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 transition-colors ${
                    errors.password ? "border-red-500" : "border-gray-300"
                  } ${
                    isSubmitting || isCheckingServer
                      ? "bg-gray-100 cursor-not-allowed opacity-60"
                      : ""
                  }`}
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 flex items-center h-full text-gray-500 bg-transparent right-3 hover:text-sky-600"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-red-500">{errors.password}</p>
              )}
            </div>

            <Link
              to="/forgot-password"
              className="block text-sm text-right text-sky-600 hover:underline"
            >
              Forgot Password?
            </Link>

            <button
              type="submit"
              className="w-full py-3 font-medium text-white rounded-lg bg-sky-600 hover:bg-sky-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
              disabled={isSubmitting || isCheckingServer}
              aria-label="Log in to your account"
            >
              {isSubmitting ? "Logging in..." : "Log In"}
            </button>
          </form>
        </div>
      )}
    </Layout>
  );
}
