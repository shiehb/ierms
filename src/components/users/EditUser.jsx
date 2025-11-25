import { useState, useEffect, useRef } from "react";
import api from "../../services/api";
import ConfirmationDialog from "../common/ConfirmationDialog";
import { useNotifications } from "../../hooks/useNotifications";
import { Upload, X, User } from "lucide-react";

export default function EditUser({ userData, onClose, onUserUpdated }) {
  const [formData, setFormData] = useState({
    firstName: userData?.first_name || "",
    middleName: userData?.middle_name || "",
    lastName: userData?.last_name || "",
    email: userData?.email || "",
    userLevel: userData?.userlevel || "",
    section: userData?.section || "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [emailChanged, setEmailChanged] = useState(false);
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

  useEffect(() => {
    setFormData({
      firstName: userData?.first_name || "",
      middleName: userData?.middle_name || "",
      lastName: userData?.last_name || "",
      email: userData?.email || "",
      userLevel: userData?.userlevel || "",
      section: userData?.section || "",
    });

    // Reset email changed flag when component re-initializes
    setEmailChanged(false);

    // Reset email validation states
    setEmailFormatValid(true);
    setEmailCheck({ checking: false, exists: false, existingUser: null });

    // Set avatar preview if user has existing avatar
    if (userData?.avatar) {
      // Handle both absolute URLs and relative paths
      let avatarUrl;
      if (
        userData.avatar.startsWith("http://") ||
        userData.avatar.startsWith("https://")
      ) {
        // Already an absolute URL
        avatarUrl = userData.avatar;
      } else if (userData.avatar.startsWith("/")) {
        // Relative path starting with / - prepend origin
        avatarUrl = `${window.location.origin}${userData.avatar}`;
      } else {
        // Relative path without / - construct full URL
        const baseUrl = api.defaults.baseURL
          .replace("/api/", "")
          .replace(/\/$/, "");
        avatarUrl = `${baseUrl}${userData.avatar.startsWith("/") ? "" : "/"}${
          userData.avatar
        }`;
      }
      setAvatarPreview(avatarUrl);
    } else {
      setAvatarPreview(null);
    }
  }, [userData]);

  // Validate email format when email changes
  useEffect(() => {
    if (formData.email) {
      const isValid = validateEmailFormat(formData.email);
      setEmailFormatValid(isValid);
    } else {
      setEmailFormatValid(true); // Reset if empty
    }
  }, [formData.email]);

  // Check if email exists (only if format is valid and email has changed)
  useEffect(() => {
    // Don't check for duplicates if format is invalid, email is too short, or email hasn't changed
    if (
      !formData.email ||
      formData.email.length < 3 ||
      !emailFormatValid ||
      !emailChanged
    ) {
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

        // Check if any result matches the exact email (excluding current user)
        const exactMatch = response.data.results?.find(
          (user) =>
            user.email.toLowerCase() === formData.email.toLowerCase() &&
            user.id !== userData?.id
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
  }, [formData.email, emailFormatValid, emailChanged, userData?.id]);

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

      // Track email changes
      if (name === "email") {
        setEmailChanged(newValue !== userData?.email);
      }

      return newFormData;
    });
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        notifications.error("Please select a valid image file", {
          title: "Invalid File",
          duration: 4000,
        });
        return;
      }
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
    if (userData?.avatar) {
      const avatarUrl = userData.avatar.startsWith("http")
        ? userData.avatar
        : userData.avatar.startsWith("/")
        ? `${window.location.origin}${userData.avatar}`
        : `${api.defaults.baseURL.replace("/api/", "")}${userData.avatar}`;
      setAvatarPreview(avatarUrl);
    } else {
      setAvatarPreview(null);
    }
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

  const confirmEdit = async () => {
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

      const response = await api.put(`auth/users/${userData.id}/`, payload, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // Update avatar preview if avatar was uploaded or if response includes updated avatar
      if (avatar || response.data?.avatar) {
        const updatedAvatar = response.data?.avatar;
        if (updatedAvatar) {
          // Handle both absolute URLs and relative paths
          let avatarUrl;
          if (
            updatedAvatar.startsWith("http://") ||
            updatedAvatar.startsWith("https://")
          ) {
            // Already an absolute URL
            avatarUrl = updatedAvatar;
          } else if (updatedAvatar.startsWith("/")) {
            // Relative path starting with / - prepend origin
            avatarUrl = `${window.location.origin}${updatedAvatar}`;
          } else {
            // Relative path without / - prepend base URL without /api/
            const baseUrl = api.defaults.baseURL
              .replace("/api/", "")
              .replace(/\/$/, "");
            avatarUrl = `${baseUrl}${
              updatedAvatar.startsWith("/") ? "" : "/"
            }${updatedAvatar}`;
          }
          setAvatarPreview(avatarUrl);
          // Update userData reference if available (for immediate display)
          if (userData) {
            userData.avatar = updatedAvatar;
          }
        }
        // Reset avatar file state since it's been uploaded
        setAvatar(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }

      notifications.success(
        `User ${formData.firstName} ${formData.lastName} has been updated successfully!`,
        {
          title: "User Updated Successfully",
          duration: 5000,
        }
      );

      if (onUserUpdated) onUserUpdated();
      onClose();
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail ||
        err.response?.data?.email?.[0] ||
        err.response?.data?.userlevel?.[0] ||
        err.response?.data?.section?.[0] ||
        "An unexpected error occurred while updating the user.";

      notifications.error(errorMessage, {
        title: "Failed to Update User",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Get auto-deactivation message
  const getAutoDeactivationMessage = () => {
    const originalLevel = userData?.userlevel;
    const originalSection = userData?.section;
    const newLevel = formData.userLevel;
    const newSection = formData.section;

    // Check if user level is being changed to Division Chief, Section Chief, or Unit Head
    if (newLevel === "Division Chief" && originalLevel !== "Division Chief") {
      return "Please note: Changing this user to Division Chief will automatically deactivate any existing active Division Chief.";
    } else if (
      newLevel === "Section Chief" &&
      (originalLevel !== "Section Chief" || originalSection !== newSection)
    ) {
      return `Please note: Changing this user to Section Chief for ${
        newSection ? `section ${newSection}` : "this section"
      } will automatically deactivate any existing active Section Chief with the same section.`;
    } else if (
      newLevel === "Unit Head" &&
      (originalLevel !== "Unit Head" || originalSection !== newSection)
    ) {
      return `Please note: Changing this user to Unit Head for ${
        newSection ? `section ${newSection}` : "this section"
      } will automatically deactivate any existing active Unit Head with the same section.`;
    }
    return null;
  };

  // Build confirmation message
  const getConfirmationMessage = () => {
    const autoDeactivationMsg = getAutoDeactivationMessage();
    const emailChangeMsg = emailChanged
      ? "Changing the email address will generate a new password and send it to the new email address. The user will be required to change their password on first login."
      : null;

    return (
      <div className="space-y-3">
        <p className="text-gray-700">
          Do you wish to proceed with updating this user account?
        </p>
        {emailChangeMsg && (
          <p className="text-sm text-gray-600 border-l-4 border-gray-400 pl-3 py-2 bg-gray-50">
            {emailChangeMsg}
          </p>
        )}
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
      <label
        htmlFor={field}
        className="flex items-center justify-between text-sm font-medium text-gray-700"
      >
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
        Edit User
      </h2>
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
          <label htmlFor="avatar-upload" className="mt-2 cursor-pointer">
            <input
              id="avatar-upload"
              name="avatar"
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
              id="firstName"
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
              id="middleName"
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
              id="lastName"
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
            id="email"
            type="email"
            name="email"
            autoComplete="email"
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
          {emailChanged && emailFormatValid && !emailCheck.exists && (
            <p className="mt-1 text-xs text-amber-600">
              Changing email will generate a new password and send it to the new
              email address
            </p>
          )}
        </div>

        {/* User Level + Section */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label field="userLevel">User Level</Label>
            <select
              id="userLevel"
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
                  id="section"
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
            className="flex-1 py-3 font-medium text-white transition rounded-lg bg-sky-600 hover:bg-sky-700"
          >
            Save Changes
          </button>
        </div>
      </form>

      <ConfirmationDialog
        open={showConfirm}
        title="User Update Confirmation"
        message={getConfirmationMessage()}
        loading={loading}
        onCancel={() => setShowConfirm(false)}
        onConfirm={confirmEdit}
        confirmText="Proceed"
        cancelText="Cancel"
        size="md"
      />
    </div>
  );
}
