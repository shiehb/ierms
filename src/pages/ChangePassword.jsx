// ChangePassword.jsx
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import Layout from "../components/Layout";
import { changePassword, logoutUser } from "../services/api";
import { useNavigate } from "react-router-dom";
import ConfirmationDialog from "../components/common/ConfirmationDialog";
import { useNotifications } from "../hooks/useNotifications";
import PasswordRequirements from "../components/common/PasswordRequirements";

export default function ChangePassword() {
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    oldPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [errors, setErrors] = useState({});
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const notifications = useNotifications();

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
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.oldPassword.trim()) {
      newErrors.oldPassword = "Old password is required";
    }

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
      } else if (formData.newPassword === formData.oldPassword) {
        newErrors.newPassword =
          "New password cannot be the same as old password";
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

  const handleSubmit = (e) => {
    e.preventDefault();

    if (validateForm()) {
      setShowConfirm(true);
    }
  };

  const confirmChangePassword = async () => {
    setIsSubmitting(true);
    try {
      await changePassword(formData.oldPassword, formData.newPassword);

      // Show success notification
      notifications.passwordChange(
        "Password changed successfully! You will be logged out for security.",
        {
          title: "Password Change Successful",
          duration: 3000,
        }
      );

      setFormData({
        oldPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
      setShowConfirm(false);

      // Logout user after successful password change
      const refreshToken = localStorage.getItem("refresh");
      if (refreshToken) {
        try {
          await logoutUser(refreshToken);
        } catch (logoutError) {
          console.warn("Logout failed:", logoutError);
          // Clear tokens manually if logout API fails
          localStorage.removeItem("access");
          localStorage.removeItem("refresh");
        }
      } else {
        // Clear tokens if no refresh token
        localStorage.removeItem("access");
        localStorage.removeItem("refresh");
      }

      // Redirect to login page after logout
      setTimeout(() => {
        navigate("/login", {
          state: {
            message:
              "Password changed successfully! Please login with your new password.",
          },
        });
      }, 2000);
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail ||
        err.response?.data?.old_password?.[0] ||
        err.response?.data?.new_password?.[0] ||
        err.message ||
        "Failed to change password. Please try again.";

      // Show error notification
      notifications.error(errorMessage, {
        title: "Password Change Failed",
        duration: 8000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    navigate(-1);
  };

  return (
    <Layout>
      <div className="w-full max-w-md p-8 bg-white shadow-lg rounded-2xl">
        <div className="mb-6 text-center">
          <h2 className="mb-6 text-2xl font-bold text-sky-600">
            Change Password
          </h2>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Old Password
            </label>
            <div className="relative">
              <input
                type={showOldPassword ? "text" : "password"}
                name="oldPassword"
                value={formData.oldPassword}
                onChange={handleChange}
                placeholder="Enter current password"
                className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                  errors.oldPassword ? "border-red-500" : "border-gray-300"
                }`}
                required
              />
              <button
                type="button"
                aria-label={showOldPassword ? "Hide password" : "Show password"}
                onClick={() => setShowOldPassword(!showOldPassword)}
                className="absolute inset-y-0 flex items-center h-full text-gray-500 bg-transparent right-3 hover:text-sky-600"
              >
                {showOldPassword ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>
            {errors.oldPassword && (
              <p className="mt-1 text-xs text-red-500">{errors.oldPassword}</p>
            )}
          </div>

          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              New Password
            </label>
            <div className="relative">
              <input
                type={showNewPassword ? "text" : "password"}
                name="newPassword"
                value={formData.newPassword}
                onChange={handleChange}
                placeholder="Enter new password"
                className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                  errors.newPassword ? "border-red-500" : "border-gray-300"
                }`}
                required
              />
              <button
                type="button"
                aria-label={showNewPassword ? "Hide password" : "Show password"}
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute inset-y-0 flex items-center h-full text-gray-500 bg-transparent right-3 hover:text-sky-600"
              >
                {showNewPassword ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>
            {errors.newPassword && (
              <p className="mt-1 text-xs text-red-500">{errors.newPassword}</p>
            )}
          </div>

          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Confirm Password
            </label>
            <div className="relative">
              <input
                type={showConfirmPassword ? "text" : "password"}
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Confirm new password"
                className={`w-full px-4 py-2 pr-12 border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                  errors.confirmPassword ? "border-red-500" : "border-gray-300"
                }`}
                required
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
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-500">
                {errors.confirmPassword}
              </p>
            )}
          </div>

          <div className="flex gap-3 mt-4">
            <button
              type="button"
              onClick={handleCancel}
              className="flex-1 py-3 font-medium text-gray-700 transition bg-gray-300 rounded-lg hover:bg-gray-400"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 py-3 font-medium text-white transition rounded-lg bg-sky-600 hover:bg-sky-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Changing..." : "Change Password"}
            </button>
          </div>
        </form>

        <PasswordRequirements password={formData.newPassword} />
      </div>

      <ConfirmationDialog
        open={showConfirm}
        title="Confirm Password Change"
        message="Are you sure you want to change your password?"
        loading={isSubmitting}
        onCancel={() => setShowConfirm(false)}
        onConfirm={confirmChangePassword}
      />
    </Layout>
  );
}
