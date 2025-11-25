// ResetPassword.jsx
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { useState, useEffect } from "react";
import { Eye, EyeOff, RotateCcw } from "lucide-react";
import { resetPasswordWithOtp, sendOtp, verifyOtp } from "../services/api";
import OTPInput from "../components/common/OTPInput";
import { useNotifications } from "../hooks/useNotifications";
import PasswordRequirements from "../components/common/PasswordRequirements";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1); // 1: OTP Verification, 2: Set Password
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: "",
    otp: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState({});
  const [countdown, setCountdown] = useState(0);
  const notifications = useNotifications();

  useEffect(() => {
    const savedEmail = localStorage.getItem("resetEmail");
    if (savedEmail) {
      setFormData((prev) => ({ ...prev, email: savedEmail }));
      setCountdown(60);
    } else {
      navigate("/forgot-password");
    }
  }, [navigate]);

  useEffect(() => {
    let timer;
    if (countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [countdown]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });

    if (errors[e.target.name]) {
      setErrors({
        ...errors,
        [e.target.name]: "",
      });
    }

    if (message) {
      setMessage("");
    }
  };

  const handleOTPChange = (otp) => {
    setFormData({
      ...formData,
      otp: otp,
    });

    if (errors.otp) {
      setErrors({
        ...errors,
        otp: "",
      });
    }

    if (message) {
      setMessage("");
    }
  };

  const handleOTPComplete = () => {
    // Optional: Auto-submit when OTP is complete
    // You can uncomment this if you want auto-submission
    // if (formData.newPassword && formData.confirmPassword) {
    //   handleSubmit();
    // }
  };

  const validatePasswordForm = () => {
    const newErrors = {};

    if (!formData.newPassword.trim()) {
      newErrors.newPassword = "New password is required";
    } else {
      // Combined validation checks
      if (formData.newPassword.length < 8) {
        newErrors.newPassword = "Password must be at least 8 characters long";
      } else if (
        !/(?=.*[a-z])/.test(formData.newPassword) ||
        !/(?=.*[A-Z])/.test(formData.newPassword)
      ) {
        newErrors.newPassword =
          "Password must include both lowercase and uppercase character";
      } else if (
        !/(?=.*\d)/.test(formData.newPassword) &&
        !/(?=.*[@$!%*?&])/.test(formData.newPassword)
      ) {
        newErrors.newPassword =
          "Password must include at least one number or symbol";
      }
    }

    if (!formData.confirmPassword.trim()) {
      newErrors.confirmPassword = "Please confirm your password";
    } else if (formData.confirmPassword !== formData.newPassword) {
      newErrors.confirmPassword = "Passwords do not match";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle Step 1: OTP Verification
  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setMessage("");
    setErrors({});

    if (!formData.otp.trim()) {
      // Set error state for visual outline
      setErrors({ otp: "OTP is required" });

      // Show popup notification for missing OTP
      notifications.error("Please enter the 6-digit OTP code", {
        title: "OTP Required",
        duration: 5000,
      });
      return;
    }

    if (formData.otp.length !== 6) {
      // Set error state for visual outline
      setErrors({ otp: "OTP must be exactly 6 digits" });

      // Show popup notification for invalid OTP length
      notifications.error("OTP must be exactly 6 digits", {
        title: "Invalid OTP Format",
        duration: 5000,
      });
      return;
    }

    setLoading(true);

    try {
      const response = await verifyOtp(formData.email, formData.otp);

      // Show success notification
      notifications.success(response.detail || "OTP verified successfully!", {
        title: "OTP Verified",
        duration: 4000,
      });

      // Move to step 2
      setCurrentStep(2);
    } catch (error) {
      let errorMessage = "Invalid or expired OTP. Please try again.";

      // Check for different types of errors
      if (
        error.code === "NETWORK_ERROR" ||
        error.message?.includes("Network Error") ||
        !navigator.onLine
      ) {
        errorMessage =
          "No internet connection. Please check your network and try again.";
      } else if (
        error.response?.status === 0 ||
        error.message?.includes("fetch")
      ) {
        errorMessage =
          "Unable to connect to server. Please check your connection and try again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      // Set error state for visual outline
      setErrors({ otp: errorMessage });

      // Show error notification
      notifications.error(errorMessage, {
        title: "OTP Verification Failed",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle Step 2: Password Reset
  const handlePasswordReset = async (e) => {
    e.preventDefault();
    setMessage("");

    if (!validatePasswordForm()) {
      return;
    }

    setLoading(true);

    try {
      const response = await resetPasswordWithOtp(
        formData.email,
        formData.otp,
        formData.newPassword
      );

      // Show success notification
      notifications.passwordChange(
        response.detail || "Password reset successfully!",
        {
          title: "Password Reset Successful",
          duration: 4000,
        }
      );

      localStorage.removeItem("resetEmail");

      setTimeout(() => {
        navigate("/login", {
          state: {
            message:
              "Password reset successfully! Please login with your new password.",
            email: formData.email,
          },
        });
      }, 2000);
    } catch (error) {
      let errorMessage = "Failed to reset password. Please try again.";

      // Check for different types of errors
      if (
        error.code === "NETWORK_ERROR" ||
        error.message?.includes("Network Error") ||
        !navigator.onLine
      ) {
        errorMessage =
          "No internet connection. Please check your network and try again.";
      } else if (
        error.response?.status === 0 ||
        error.message?.includes("fetch")
      ) {
        errorMessage =
          "Unable to connect to server. Please check your connection and try again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      // Show error notification
      notifications.error(errorMessage, {
        title: "Password Reset Failed",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (countdown > 0) return;

    setResendLoading(true);
    setMessage("");

    try {
      const response = await sendOtp(formData.email);

      // Show success notification
      notifications.success(response.detail || "OTP sent successfully!", {
        title: "OTP Sent",
        duration: 4000,
      });

      setCountdown(60);
    } catch (error) {
      let errorMessage = "Failed to resend OTP. Please try again.";

      // Check for different types of errors
      if (
        error.code === "NETWORK_ERROR" ||
        error.message?.includes("Network Error") ||
        !navigator.onLine
      ) {
        errorMessage =
          "No internet connection. Please check your network and try again.";
      } else if (
        error.response?.status === 0 ||
        error.message?.includes("fetch")
      ) {
        errorMessage =
          "Unable to connect to server. Please check your connection and try again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      // Show error notification
      notifications.error(errorMessage, {
        title: "OTP Send Failed",
        duration: 8000,
      });
    } finally {
      setResendLoading(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Function to mask email address
  const maskEmail = (email) => {
    if (!email || !email.includes("@")) return email;

    const [localPart, domain] = email.split("@");

    if (localPart.length <= 2) {
      // If local part is 2 chars or less, just show asterisks
      return `${localPart.charAt(0)}****@${domain}`;
    } else if (localPart.length === 3) {
      // If local part is 3 chars, show first and last
      return `${localPart.charAt(0)}*${localPart.charAt(2)}@${domain}`;
    } else {
      // Show first 2 chars, then asterisks, then last char
      const firstTwo = localPart.substring(0, 2);
      const lastChar = localPart.charAt(localPart.length - 1);
      const asterisks = "*".repeat(Math.max(1, localPart.length - 3));
      return `${firstTwo}${asterisks}${lastChar}@${domain}`;
    }
  };

  // Step 1: OTP Verification UI
  const renderStep1 = () => (
    <>
      {/* Back button */}
      <button
        onClick={() => navigate("/forgot-password")}
        className="mb-4 text-left text-gray-600 hover:text-gray-800 transition-colors"
      >
        ← Back
      </button>

      <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
        Verify OTP
      </h2>

      {/* Descriptive text */}
      <p className="mb-6 text-sm text-gray-600 text-center">
        Enter the 6-digit code sent to {maskEmail(formData.email)}
      </p>

      <form className="space-y-5" onSubmit={handleVerifyOtp}>
        <input type="hidden" name="email" value={formData.email} />

        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="block text-sm font-medium text-gray-700">
              6-Digit Verification Code
            </label>
            <button
              type="button"
              onClick={handleResendOtp}
              disabled={countdown > 0 || resendLoading}
              className="flex items-center text-xs bg-transparent text-sky-600 hover:text-sky-700 disabled:text-gray-400 disabled:cursor-not-allowed"
            >
              <RotateCcw className="w-3 h-3 mr-1" />
              {resendLoading
                ? "Sending..."
                : countdown > 0
                ? `Resend in ${formatTime(countdown)}`
                : "Resend OTP"}
            </button>
          </div>

          <OTPInput
            length={6}
            value={formData.otp}
            onChange={handleOTPChange}
            onComplete={handleOTPComplete}
            disabled={loading}
            error={!!errors.otp}
            className="mb-2"
          />
        </div>

        {/* Single Continue button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 font-medium text-white transition rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Verifying..." : "Continue"}
          </button>
        </div>
      </form>
    </>
  );

  // Step 2: Set Password UI
  const renderStep2 = () => (
    <>
      {/* Back button */}
      <button
        onClick={() => setCurrentStep(1)}
        className="mb-4 text-left text-gray-600 hover:text-gray-800 transition-colors"
      >
        ← Back
      </button>

      <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
        Set password
      </h2>

      <form className="space-y-5" onSubmit={handlePasswordReset}>
        <input type="hidden" name="email" value={formData.email} />
        <input type="hidden" name="otp" value={formData.otp} />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            New Password
          </label>
          <div className="relative">
            <input
              type={showNewPassword ? "text" : "password"}
              name="newPassword"
              placeholder="Password"
              value={formData.newPassword}
              onChange={handleChange}
              required
              className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                errors.newPassword ? "border-red-500" : "border-gray-300"
              }`}
            />
            <button
              type="button"
              aria-label={showNewPassword ? "Hide password" : "Show password"}
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute inset-y-0 flex items-center h-full text-gray-500 bg-transparent right-3 hover:text-sky-600"
            >
              {showNewPassword ? (
                <EyeOff className="w-6 h-6" />
              ) : (
                <Eye className="w-6 h-6" />
              )}
            </button>
          </div>
          {errors.newPassword && (
            <p className="mt-1 text-xs text-red-500">{errors.newPassword}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Confirm Password
          </label>
          <div className="relative">
            <input
              type={showConfirmPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder="Confirm password"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                errors.confirmPassword ? "border-red-500" : "border-gray-300"
              }`}
            />
            <button
              type="button"
              aria-label={
                showConfirmPassword ? "Hide password" : "Show password"
              }
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 flex items-center h-full text-gray-500 bg-transparent right-3 hover:text-sky-600"
            >
              {showConfirmPassword ? (
                <EyeOff className="w-6 h-6" />
              ) : (
                <Eye className="w-6 h-6" />
              )}
            </button>
          </div>
          {errors.confirmPassword && (
            <p className="mt-1 text-xs text-red-500">
              {errors.confirmPassword}
            </p>
          )}
        </div>

        {/* Single Continue button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 font-medium text-white transition rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Processing..." : "Continue"}
          </button>
        </div>
      </form>

      <PasswordRequirements password={formData.newPassword} />
    </>
  );

  return (
    <Layout>
      <div className="w-full max-w-md p-8 bg-white shadow-lg rounded-2xl">
        {currentStep === 1 ? renderStep1() : renderStep2()}
      </div>
    </Layout>
  );
}
