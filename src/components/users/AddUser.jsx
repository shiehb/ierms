import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../services/api";
import ConfirmationDialog from "../common/ConfirmationDialog";
import { useNotifications } from "../../hooks/useNotifications";
import { AlertTriangle, Upload, X, User, Info } from "lucide-react";

export default function AddUser({ onClose, onUserAdded }) {
  const [formData, setFormData] = useState({
    firstName: "",
    middleName: "",
    lastName: "",
    email: "",
    userLevel: "",
    section: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [emailValidation, setEmailValidation] = useState({
    loading: true,
    valid: false,
    configured: false,
    connectivity: false,
    errors: [],
    message: "",
  });
  const [emailCheck, setEmailCheck] = useState({
    checking: false,
    exists: false,
    existingUser: null,
  });
  const [emailFormatValid, setEmailFormatValid] = useState(true);
  const [avatar, setAvatar] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const fileInputRef = useRef(null);
  const emailCheckTimeoutRef = useRef(null);
  const notifications = useNotifications();
  const navigate = useNavigate();

  // Email format validation function
  const validateEmailFormat = (email) => {
    if (!email || email.trim() === "") {
      return true; // Empty is okay, will be caught by required validation
    }

    // Email regex pattern
    const emailRegex =
      /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

    return emailRegex.test(email.trim().toLowerCase());
  };

  // Validate email configuration on mount
  useEffect(() => {
    const validateEmailConfig = async () => {
      try {
        const response = await api.get("system/config/validate-email/");
        setEmailValidation({
          loading: false,
          ...response.data,
        });

        if (!response.data.valid) {
          // Different notifications based on the issue
          if (!response.data.configured) {
            // Email not configured - show warning
            notifications.warning(
              "Email configuration is incomplete. Please configure email settings.",
              {
                title: "Email Configuration Required",
                duration: 8000,
              }
            );
          } else if (!response.data.connectivity) {
            // Connectivity issue - show error
            notifications.error(
              "Cannot connect to email server. Please check your internet connection and try again.",
              {
                title: "Connection Error",
                duration: 8000,
              }
            );
          }
        }
      } catch (error) {
        console.error("Email validation error:", error);
        setEmailValidation({
          loading: false,
          valid: false,
          configured: false,
          connectivity: false,
          errors: ["Failed to validate email configuration"],
          message: "Email validation failed",
        });
      }
    };

    validateEmailConfig();
  }, []);

  // Validate email format when email changes
  useEffect(() => {
    if (formData.email) {
      const isValid = validateEmailFormat(formData.email);
      setEmailFormatValid(isValid);
    } else {
      setEmailFormatValid(true); // Reset if empty
    }
  }, [formData.email]);

  // Check if email exists (only if format is valid)
  useEffect(() => {
    // Don't check for duplicates if format is invalid or email is too short
    if (!formData.email || formData.email.length < 3 || !emailFormatValid) {
      setEmailCheck({ checking: false, exists: false, existingUser: null });
      return;
    }

    // Clear previous timeout
    if (emailCheckTimeoutRef.current) {
      clearTimeout(emailCheckTimeoutRef.current);
    }

    // Debounce email check
    emailCheckTimeoutRef.current = setTimeout(async () => {
      setEmailCheck({ checking: true, exists: false, existingUser: null });
      try {
        const response = await api.get("auth/search/", {
          params: { q: formData.email },
        });

        // Check if any result matches the exact email
        const exactMatch = response.data.results?.find(
          (user) => user.email.toLowerCase() === formData.email.toLowerCase()
        );

        if (exactMatch) {
          setEmailCheck({
            checking: false,
            exists: true,
            existingUser: exactMatch,
          });
        } else {
          setEmailCheck({ checking: false, exists: false, existingUser: null });
        }
      } catch (error) {
        console.error("Email check error:", error);
        setEmailCheck({ checking: false, exists: false, existingUser: null });
      }
    }, 500);

    return () => {
      if (emailCheckTimeoutRef.current) {
        clearTimeout(emailCheckTimeoutRef.current);
      }
    };
  }, [formData.email, emailFormatValid]);

  // Section options depending on role
  const sectionOptionsByLevel = {
    "Section Chief": [
      {
        value: "PD-1586,RA-8749,RA-9275",
        label: "EIA, Air & Water Quality Monitoring Section",
      },
      {
        value: "RA-6969",
        label: "Toxic Chemicals & Hazardous Monitoring Section",
      },
      { value: "RA-9003", label: "Ecological Solid Waste Management Section" },
    ],
    "Unit Head": [
      { value: "PD-1586", label: "EIA Monitoring Unit" },
      { value: "RA-8749", label: "Air Quality Monitoring Unit" },
      { value: "RA-9275", label: "Water Quality Monitoring Unit" },
    ],
    "Monitoring Personnel": [
      { value: "PD-1586", label: "EIA Monitoring Personnel" },
      { value: "RA-8749", label: "Air Quality Monitoring Personnel" },
      { value: "RA-9275", label: "Water Quality Monitoring Personnel" },
      { value: "RA-6969", label: "Toxic Chemicals Monitoring Personnel" },
      { value: "RA-9003", label: "Solid Waste Monitoring Personnel" },
    ],
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    let newValue = value;
    if (["firstName", "middleName", "lastName"].includes(name)) {
      newValue = value.toUpperCase();
    } else if (name === "email") {
      newValue = value.toLowerCase();
    }

    setFormData((prev) => {
      let newFormData = { ...prev, [name]: newValue };

      // Reset section when user level changes
      if (name === "userLevel") {
        newFormData.section = "";
      }

      return newFormData;
    });
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith("image/")) {
        notifications.error("Please select a valid image file", {
          title: "Invalid File",
          duration: 4000,
        });
        return;
      }
      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        notifications.error(
          "Image size must be less than 5MB. The image will be automatically optimized after upload.",
          {
            title: "File Too Large",
            duration: 5000,
          }
        );
        return;
      }
      setAvatar(file);
      setAvatarPreview(URL.createObjectURL(file));
    }
  };

  const removeAvatar = () => {
    setAvatar(null);
    setAvatarPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);

    if (
      !formData.firstName.trim() ||
      !formData.lastName.trim() ||
      !formData.email.trim() ||
      !formData.userLevel.trim() ||
      (sectionOptionsByLevel[formData.userLevel] && !formData.section.trim())
    ) {
      return;
    }
    setShowConfirm(true);
  };

  const confirmAdd = async () => {
    setLoading(true);
    try {
      const payload = new FormData();
      payload.append("email", formData.email);
      payload.append("first_name", formData.firstName);
      if (formData.middleName.trim()) {
        payload.append("middle_name", formData.middleName);
      }
      payload.append("last_name", formData.lastName);
      payload.append("userlevel", formData.userLevel);
      if (formData.section) {
        payload.append("section", formData.section);
      }
      if (avatar) {
        payload.append("avatar", avatar);
      }

      await api.post("auth/register/", payload, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      notifications.success(
        `User ${formData.firstName} ${formData.lastName} has been added successfully!`,
        {
          title: "User Added Successfully",
          duration: 5000,
        }
      );

      if (onUserAdded) onUserAdded();
      onClose();
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail ||
        err.response?.data?.email?.[0] ||
        err.response?.data?.userlevel?.[0] ||
        err.response?.data?.section?.[0] ||
        "An unexpected error occurred while creating the user.";

      notifications.error(errorMessage, {
        title: "Failed to Add User",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Get auto-deactivation message
  const getAutoDeactivationMessage = () => {
    if (formData.userLevel === "Division Chief") {
      return "Please note: Creating a new Division Chief will automatically deactivate any existing active Division Chief.";
    } else if (formData.userLevel === "Section Chief") {
      return `Please note: Creating a new Section Chief for ${
        formData.section ? `section ${formData.section}` : "this section"
      } will automatically deactivate any existing active Section Chief with the same section.`;
    } else if (formData.userLevel === "Unit Head") {
      return `Please note: Creating a new Unit Head for ${
        formData.section ? `section ${formData.section}` : "this section"
      } will automatically deactivate any existing active Unit Head with the same section.`;
    }
    return null;
  };

  // Build confirmation message
  const getConfirmationMessage = () => {
    const autoDeactivationMsg = getAutoDeactivationMessage();

    return (
      <div className="space-y-3">
        <p className="text-gray-700">
          Do you wish to proceed with the registration of this user account?
        </p>
        {autoDeactivationMsg && (
          <p className="text-sm text-gray-600 border-l-4 border-gray-400 pl-3 py-2 bg-gray-50">
            {autoDeactivationMsg}
          </p>
        )}
      </div>
    );
  };

  const Label = ({ field, children, required = true }) => {
    return (
      <label className="flex items-center justify-between text-sm font-medium text-gray-700">
        <span>
          {children} {required && <span className="text-red-500">*</span>}
        </span>
        {field === "email" && formData.email && !emailFormatValid && (
          <span className="text-xs text-red-500 font-medium">
            Invalid email format
          </span>
        )}
        {field === "email" && emailCheck.exists && emailFormatValid && (
          <span className="text-xs text-red-500 font-medium">
            Email already exists
          </span>
        )}
        {field === "section" &&
          submitted &&
          sectionOptionsByLevel[formData.userLevel] &&
          !formData.section.trim() && (
            <span className="text-xs text-red-500">Required</span>
          )}
        {field !== "section" &&
          field !== "email" &&
          required &&
          submitted &&
          !formData[field]?.trim() && (
            <span className="text-xs text-red-500">Required</span>
          )}
      </label>
    );
  };

  return (
    <div className="w-full max-w-2xl p-8 bg-white shadow-lg rounded-2xl">
      <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
        Add User
      </h2>

      {/* Email Configuration Warning Banner */}
      {!emailValidation.loading && !emailValidation.valid && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-yellow-800 mb-1">
                {!emailValidation.configured
                  ? "Email Configuration Required"
                  : "Connection Issue"}
              </h3>
              <p className="text-sm text-yellow-700 mb-2">
                {emailValidation.message}
              </p>
              {emailValidation.errors.length > 0 && (
                <ul className="text-xs text-yellow-600 space-y-1 mb-3">
                  {emailValidation.errors.map((error, index) => (
                    <li key={index}>• {error}</li>
                  ))}
                </ul>
              )}
              {/* Show link ONLY if email is not configured */}
              {!emailValidation.configured && (
                <p className="text-sm font-medium text-sky-600">
                  Email configuration is required. Contact your system
                  administrator.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5 text-sm">
        {/* Avatar Upload */}
        <div className="flex flex-col items-center mb-4">
          <div className="relative">
            <div className="w-24 h-24 rounded-full overflow-hidden bg-gray-200 border-2 border-gray-300 flex items-center justify-center">
              {avatarPreview ? (
                <img
                  src={avatarPreview}
                  alt="Avatar preview"
                  className="w-full h-full object-cover"
                />
              ) : (
                <User className="w-12 h-12 text-gray-400" />
              )}
            </div>
            {avatarPreview && (
              <button
                type="button"
                onClick={removeAvatar}
                className="absolute top-0 right-0 p-1 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
              >
                <X size={16} />
              </button>
            )}
          </div>
          <label className="mt-2 cursor-pointer">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="hidden"
            />
            <span className="text-xs text-sky-600 hover:text-sky-700 underline cursor-pointer">
              {avatarPreview ? "Change Avatar" : "Upload Avatar"}
            </span>
          </label>
          <p className="text-xs text-gray-500 mt-1">
            Maximum file size: 5MB. Images are automatically optimized for web
            display.
          </p>
        </div>

        {/* Names */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <Label field="firstName">First Name</Label>
            <input
              type="text"
              name="firstName"
              value={formData.firstName}
              onChange={handleChange}
              className={`w-full p-2 border rounded-lg ${
                submitted && !formData.firstName.trim()
                  ? "border-red-500"
                  : "border-gray-300"
              }`}
            />
          </div>
          <div>
            <Label field="middleName" required={false}>
              Middle Name
            </Label>
            <input
              type="text"
              name="middleName"
              value={formData.middleName}
              onChange={handleChange}
              className="w-full p-2 border rounded-lg border-gray-300"
            />
          </div>
          <div>
            <Label field="lastName">Last Name</Label>
            <input
              type="text"
              name="lastName"
              value={formData.lastName}
              onChange={handleChange}
              className={`w-full p-2 border rounded-lg ${
                submitted && !formData.lastName.trim()
                  ? "border-red-500"
                  : "border-gray-300"
              }`}
            />
          </div>
        </div>

        {/* Email */}
        <div>
          <Label field="email">Email</Label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            className={`w-full p-2 border rounded-lg ${
              submitted && !formData.email.trim()
                ? "border-red-500"
                : formData.email && !emailFormatValid
                ? "border-red-500"
                : emailCheck.exists
                ? "border-red-500"
                : "border-gray-300"
            }`}
          />
          {emailCheck.checking && (
            <p className="mt-1 text-xs text-gray-500">Checking email...</p>
          )}
        </div>

        {/* User Level + Section */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label field="userLevel">User Level</Label>
            <select
              name="userLevel"
              value={formData.userLevel}
              onChange={handleChange}
              className={`w-full p-2 border rounded-lg ${
                submitted && !formData.userLevel.trim()
                  ? "border-red-500"
                  : "border-gray-300"
              }`}
            >
              <option value="">Select User Level</option>
              <option value="Legal Unit">Legal Unit</option>
              <option value="Division Chief">Division Chief</option>
              <option value="Section Chief">Section Chief</option>
              <option value="Unit Head">Unit Head</option>
              <option value="Monitoring Personnel">Monitoring Personnel</option>
            </select>
          </div>
          <div>
            {sectionOptionsByLevel[formData.userLevel] ? (
              <>
                <Label field="section">Section</Label>
                <select
                  name="section"
                  value={formData.section}
                  onChange={handleChange}
                  className={`w-full p-2 border rounded-lg ${
                    submitted &&
                    sectionOptionsByLevel[formData.userLevel] &&
                    !formData.section.trim()
                      ? "border-red-500"
                      : "border-gray-300"
                  }`}
                >
                  <option value="">Select Section</option>
                  {sectionOptionsByLevel[formData.userLevel]?.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </>
            ) : (
              <div className="h-full flex items-end">
                {/* Empty space to maintain 2-column layout */}
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-4 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-3 font-medium text-gray-700 transition bg-gray-300 rounded-lg hover:bg-gray-400"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!emailValidation.valid || emailValidation.loading}
            className={`flex-1 py-3 font-medium text-white transition rounded-lg ${
              !emailValidation.valid || emailValidation.loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-sky-600 hover:bg-sky-700"
            }`}
            title={
              !emailValidation.valid
                ? "Please configure email settings first"
                : ""
            }
          >
            {emailValidation.loading ? "Validating..." : "Save"}
          </button>
        </div>
      </form>

      <ConfirmationDialog
        open={showConfirm}
        title="User Registration Confirmation"
        message={getConfirmationMessage()}
        loading={loading}
        onCancel={() => setShowConfirm(false)}
        onConfirm={confirmAdd}
        confirmText="Proceed"
        cancelText="Cancel"
        size="md"
      />
    </div>
  );
}
