import { useState, useRef, useEffect } from "react";
import { useNotifications } from "../../hooks/useNotifications";
import ConfirmationDialog from "../common/ConfirmationDialog";
import * as lawApi from "../../services/lawApi";

export default function AddLawModal({ onClose, onLawAdded }) {
  const [formData, setFormData] = useState({
    law_title: "",
    reference_code: "",
    description: "",
    category: "",
    effective_date: "",
    status: "Active",
  });
  const [submitted, setSubmitted] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validatingCode, setValidatingCode] = useState(false);
  const [codeExists, setCodeExists] = useState(false);
  const [validatingTitle, setValidatingTitle] = useState(false);
  const [titleExists, setTitleExists] = useState(false);
  const codeCheckTimeoutRef = useRef(null);
  const titleCheckTimeoutRef = useRef(null);
  const notifications = useNotifications();

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (codeCheckTimeoutRef.current) {
        clearTimeout(codeCheckTimeoutRef.current);
      }
      if (titleCheckTimeoutRef.current) {
        clearTimeout(titleCheckTimeoutRef.current);
      }
    };
  }, []);

  const handleReferenceCodeValidation = async (code) => {
    // Clear existing timeout
    if (codeCheckTimeoutRef.current) {
      clearTimeout(codeCheckTimeoutRef.current);
    }

    // Don't check if code is empty
    if (!code || code.trim().length === 0) {
      setCodeExists(false);
      return;
    }

    // Debounce the check by 500ms
    codeCheckTimeoutRef.current = setTimeout(async () => {
      setValidatingCode(true);
      try {
        const exists = await lawApi.checkReferenceCodeExists(code);
        setCodeExists(exists);
      } catch (error) {
        console.error("Error validating reference code:", error);
      } finally {
        setValidatingCode(false);
      }
    }, 500);
  };

  const handleLawTitleValidation = async (title) => {
    // Clear existing timeout
    if (titleCheckTimeoutRef.current) {
      clearTimeout(titleCheckTimeoutRef.current);
    }

    // Don't check if title is empty or too short
    if (!title || title.trim().length < 3) {
      setTitleExists(false);
      return;
    }

    // Debounce the check by 500ms
    titleCheckTimeoutRef.current = setTimeout(async () => {
      setValidatingTitle(true);
      try {
        const exists = await lawApi.checkLawTitleExists(title);
        setTitleExists(exists);
      } catch (error) {
        console.error("Error validating law title:", error);
      } finally {
        setValidatingTitle(false);
      }
    }, 500);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;

    if (name === "reference_code") {
      const upperValue = value.toUpperCase();
      setFormData((prev) => ({ ...prev, [name]: upperValue }));
      handleReferenceCodeValidation(upperValue);
    } else if (name === "law_title") {
      setFormData((prev) => ({ ...prev, [name]: value }));
      handleLawTitleValidation(value);
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);

    // Don't proceed if code exists or is being validated
    if (codeExists || validatingCode) {
      return;
    }

    // Don't proceed if title exists or is being validated
    if (titleExists || validatingTitle) {
      return;
    }

    // Validate required fields
    if (
      !formData.reference_code.trim() ||
      !formData.law_title.trim() ||
      formData.law_title.trim().length < 3 ||
      !formData.description.trim() ||
      formData.description.trim().length < 10 ||
      !formData.category.trim() ||
      formData.category.trim().length < 2 ||
      !formData.effective_date.trim()
    ) {
      return;
    }

    setShowConfirm(true);
  };

  const confirmAdd = async () => {
    setLoading(true);
    try {
      const newLaw = await lawApi.createLaw(formData);

      notifications.success("Law created successfully.", {
        title: "Law Created",
        duration: 3000,
      });

      if (onLawAdded) onLawAdded(newLaw);
      onClose();
    } catch (error) {
      console.error("Error creating law:", error);
      notifications.error(error.message || "Failed to create law.", {
        title: "Creation Error",
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  const getConfirmationMessage = () => {
    return (
      <div className="space-y-3">
        <p className="text-gray-700">
          Do you wish to proceed with creating this law?
        </p>
        <div className="text-sm text-gray-600 border-l-4 border-sky-400 pl-3 py-2 bg-sky-50 space-y-1">
          <p>
            <span className="font-medium">Code:</span>{" "}
            {formData.reference_code || "N/A"}
          </p>
          <p>
            <span className="font-medium">Law:</span> {formData.law_title}
          </p>
          <p>
            <span className="font-medium">Category:</span> {formData.category}
          </p>
          <p>
            <span className="font-medium">Effective Date:</span>{" "}
            {formData.effective_date}
          </p>
        </div>
      </div>
    );
  };

  const Label = ({ field, children, required = true }) => {
    const hasError = submitted && required && !formData[field]?.trim();
    const isTooShort =
      submitted &&
      formData[field]?.trim() &&
      ((field === "law_title" && formData[field].trim().length < 3) ||
        (field === "description" && formData[field].trim().length < 10) ||
        (field === "category" && formData[field].trim().length < 2));

    return (
      <label className="flex items-center justify-between text-sm font-medium text-gray-700">
        <span>
          {children} {required && <span className="text-red-500">*</span>}
        </span>
        {field === "reference_code" &&
          formData.reference_code &&
          codeExists && (
            <span className="text-xs text-amber-600 font-medium">
              Code already exists
            </span>
          )}
        {field === "law_title" && formData.law_title && titleExists && (
          <span className="text-xs text-amber-600 font-medium">
            Title already exists
          </span>
        )}
        {field !== "reference_code" && field !== "law_title" && hasError && (
          <span className="text-xs text-red-500">Required</span>
        )}
        {field !== "reference_code" &&
          field !== "law_title" &&
          isTooShort &&
          !hasError && (
            <span className="text-xs text-red-500">
              {field === "description" && "Min 10 characters"}
              {field === "category" && "Min 2 characters"}
            </span>
          )}
        {field === "law_title" && hasError && (
          <span className="text-xs text-red-500">Required</span>
        )}
        {field === "law_title" && isTooShort && !hasError && !titleExists && (
          <span className="text-xs text-red-500">Min 3 characters</span>
        )}
      </label>
    );
  };

  return (
    <div className="w-full max-w-2xl p-8 bg-white shadow-lg rounded-2xl">
      <h2 className="mb-6 text-2xl font-bold text-center text-sky-600">
        Add Law
      </h2>

      <form onSubmit={handleSubmit} className="space-y-5 text-sm">
        {/* Reference Code + Law Title */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label field="reference_code">Reference Code</Label>
            <div className="relative">
              <input
                type="text"
                name="reference_code"
                value={formData.reference_code}
                onChange={handleChange}
                className={`w-full p-2 pr-10 border rounded-lg ${
                  submitted && !formData.reference_code.trim()
                    ? "border-red-500"
                    : codeExists
                    ? "border-amber-400 bg-amber-50"
                    : validatingCode
                    ? "border-blue-400"
                    : "border-gray-300"
                }`}
                placeholder="e.g., RA-8749"
              />

              {/* Validation Status Icons */}
              {validatingCode && (
                <div className="absolute right-3 top-3">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                </div>
              )}
              {codeExists && !validatingCode && (
                <div className="absolute right-3 top-3">
                  <svg
                    className="w-5 h-5 text-amber-500"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              )}
              {!codeExists &&
                !validatingCode &&
                formData.reference_code.trim() && (
                  <div className="absolute right-3 top-3">
                    <svg
                      className="w-5 h-5 text-green-500"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                )}
            </div>
          </div>
          <div>
            <Label field="law_title">Law Title</Label>
            <div className="relative">
              <input
                type="text"
                name="law_title"
                value={formData.law_title}
                onChange={handleChange}
                className={`w-full p-2 pr-10 border rounded-lg ${
                  submitted &&
                  (!formData.law_title.trim() ||
                    formData.law_title.trim().length < 3)
                    ? "border-red-500"
                    : titleExists
                    ? "border-amber-400 bg-amber-50"
                    : validatingTitle
                    ? "border-blue-400"
                    : "border-gray-300"
                }`}
                placeholder="e.g., Philippine Clean Air Act"
              />

              {/* Validation Status Icons */}
              {validatingTitle && (
                <div className="absolute right-3 top-3">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                </div>
              )}
              {titleExists && !validatingTitle && (
                <div className="absolute right-3 top-3">
                  <svg
                    className="w-5 h-5 text-amber-500"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              )}
              {!titleExists &&
                !validatingTitle &&
                formData.law_title.trim() &&
                formData.law_title.trim().length >= 3 && (
                  <div className="absolute right-3 top-3">
                    <svg
                      className="w-5 h-5 text-green-500"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                )}
            </div>
          </div>
        </div>

        {/* Category + Effective Date */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label field="category">Category</Label>
            <input
              type="text"
              name="category"
              value={formData.category}
              onChange={handleChange}
              className={`w-full p-2 border rounded-lg ${
                submitted &&
                (!formData.category.trim() ||
                  formData.category.trim().length < 2)
                  ? "border-red-500"
                  : "border-gray-300"
              }`}
              placeholder="e.g., Air Quality Management"
            />
          </div>
          <div>
            <Label field="effective_date">Effective Date</Label>
            <input
              type="date"
              name="effective_date"
              value={formData.effective_date}
              onChange={handleChange}
              className={`w-full p-2 border rounded-lg ${
                submitted && !formData.effective_date.trim()
                  ? "border-red-500"
                  : "border-gray-300"
              }`}
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <Label field="description">Description</Label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={5}
            className={`w-full p-2 border rounded-lg ${
              submitted &&
              (!formData.description.trim() ||
                formData.description.trim().length < 10)
                ? "border-red-500"
                : "border-gray-300"
            }`}
            placeholder="Describe the scope and intent of the law..."
          />
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
            Save
          </button>
        </div>
      </form>

      <ConfirmationDialog
        open={showConfirm}
        title="Law Creation Confirmation"
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
