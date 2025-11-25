import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { useState } from "react";
import { sendOtp } from "../services/api";
import { useNotifications } from "../hooks/useNotifications";

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const notifications = useNotifications();

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await sendOtp(email);

      // Show success notification
      notifications.success(response.detail, {
        title: "OTP Sent",
        duration: 4000,
      });

      // ✅ Automatically redirect to reset password page after successful OTP send
      if (response.detail.includes("sent")) {
        // Store email in localStorage for the reset password page
        localStorage.setItem("resetEmail", email);

        // Redirect after a short delay to show success message
        setTimeout(() => {
          navigate("/reset-password");
        }, 1500);
      }
    } catch (error) {
      let errorMessage = "Failed to send OTP. Please try again.";

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
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="w-full max-w-md p-8 bg-white shadow-lg rounded-2xl">
        {/* Back button */}
        <button
          onClick={() => navigate("/")}
          className="mb-4 text-left text-gray-600 hover:text-gray-800 transition-colors"
        >
          ← Back
        </button>

        <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
          Forgot password
        </h2>

        {/* Descriptive text */}
        <p className="mb-6 text-sm text-gray-600 text-center">
          Enter the email associated with your account, and we will email you a
          verification code to reset your password
        </p>

        <form className="space-y-5" onSubmit={handleSendOtp}>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {/* Single Continue button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 font-medium text-white transition rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Sending..." : "Continue"}
            </button>
          </div>
        </form>
      </div>
    </Layout>
  );
}
