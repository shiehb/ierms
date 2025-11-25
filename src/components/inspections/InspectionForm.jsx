import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Save,
  CheckCircle,
  AlertTriangle,
  FileText,
  Calendar,
  User,
  Building,
  MapPin,
} from "lucide-react";
import {
  getInspection,
  startInspection,
  saveInspectionDraft,
} from "../../services/api";
import { useNotifications } from "../../hooks/useNotifications";

const InspectionForm = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const notifications = useNotifications();

  const [inspection, setInspection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [hasExistingData, setHasExistingData] = useState(false);
  const [formData, setFormData] = useState({
    findings_summary: "",
    compliance_observations: "",
    violations_found: "",
    recommendations: "",
    remarks: "",
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    fetchInspection();
  }, [id]);

  const fetchInspection = async () => {
    try {
      const data = await getInspection(id);
      setInspection(data);

      // Load existing form data if available
      if (data.form) {
        console.log("Loading existing form data:", data.form);

        // Extract data from checklist JSON if available
        let checklistData = {};
        if (data.form.checklist && typeof data.form.checklist === "object") {
          checklistData = data.form.checklist;
        } else if (
          data.form.checklist &&
          typeof data.form.checklist === "string"
        ) {
          try {
            checklistData = JSON.parse(data.form.checklist);
          } catch (e) {
            console.warn("Failed to parse checklist JSON:", e);
            checklistData = {};
          }
        }

        console.log("Extracted checklist data:", checklistData);

        // Check if we have any existing data (from direct fields or checklist)
        const hasDirectData =
          data.form.findings_summary ||
          data.form.compliance_observations ||
          data.form.violations_found ||
          data.form.compliance_plan ||
          data.form.inspection_notes;
        const hasChecklistData =
          checklistData.general ||
          checklistData.purpose ||
          checklistData.permits ||
          checklistData.complianceItems ||
          checklistData.systems ||
          checklistData.recommendationState;

        setHasExistingData(!!(hasDirectData || hasChecklistData));

        // Load data from both direct fields and checklist
        setFormData({
          findings_summary:
            data.form.findings_summary ||
            checklistData.general?.findings_summary ||
            "",
          compliance_observations:
            data.form.compliance_observations ||
            checklistData.general?.compliance_observations ||
            "",
          violations_found:
            data.form.violations_found ||
            checklistData.general?.violations_found ||
            "",
          recommendations:
            data.form.compliance_plan ||
            checklistData.general?.recommendations ||
            "",
          remarks: checklistData.general?.remarks || "",
        });
      }

      setLoading(false);
    } catch (error) {
      console.error("Error fetching inspection:", error);
      notifications.error("Failed to load inspection details", {
        title: "Error",
      });
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));

    // Clear error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.findings_summary.trim()) {
      newErrors.findings_summary = "Findings summary is required";
    }

    if (!formData.compliance_observations.trim()) {
      newErrors.compliance_observations =
        "Compliance observations are required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSaveDraft = async () => {
    setSavingDraft(true);
    try {
      // Format form data to match backend save_draft structure
      const formattedData = {
        general: {
          findings_summary: formData.findings_summary,
          compliance_observations: formData.compliance_observations,
          violations_found: formData.violations_found,
          recommendations: formData.recommendations,
          remarks: formData.remarks,
        },
      };

      await saveInspectionDraft(id, { form_data: formattedData });
      notifications.success("Draft saved successfully!", { title: "Success" });
      setHasExistingData(true);
    } catch (error) {
      console.error("Error saving draft:", error);
      notifications.error("Failed to save draft", { title: "Error" });
    } finally {
      setSavingDraft(false);
    }
  };

  const handleStartInspection = async () => {
    if (!validateForm()) {
      return;
    }

    setSaving(true);
    try {
      // Format form data to match backend save_draft structure
      const formattedData = {
        general: {
          findings_summary: formData.findings_summary,
          compliance_observations: formData.compliance_observations,
          violations_found: formData.violations_found,
          recommendations: formData.recommendations,
          remarks: formData.remarks,
        },
      };

      await startInspection(id, formattedData);
      notifications.success(
        hasExistingData
          ? "Inspection updated successfully!"
          : "Inspection started successfully!",
        { title: "Success" }
      );
      navigate("/inspections");
    } catch (error) {
      console.error("Error starting inspection:", error);
      notifications.error("Failed to start inspection", { title: "Error" });
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    navigate("/inspections");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!inspection) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertTriangle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Inspection Not Found
          </h2>
          <p className="text-gray-600 mb-4">
            The inspection you're looking for doesn't exist.
          </p>
          <button
            onClick={handleBack}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Back to Inspections
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <button
                onClick={handleBack}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Inspection Form
                </h1>
                <p className="text-gray-600">
                  {hasExistingData
                    ? "Continue filling out the inspection details"
                    : "Fill out the inspection details"}
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-500">Inspection Code</div>
              <div className="text-lg font-semibold text-blue-600">
                {inspection.code}
              </div>
            </div>
          </div>

          {/* Inspection Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center space-x-2">
              <Building className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-xs text-gray-500">Establishment</div>
                <div className="text-sm font-medium text-gray-900">
                  {inspection.establishments_detail?.[0]?.name || "N/A"}
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <FileText className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-xs text-gray-500">Law</div>
                <div className="text-sm font-medium text-gray-900">
                  {inspection.law}
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Calendar className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-xs text-gray-500">Created</div>
                <div className="text-sm font-medium text-gray-900">
                  {new Date(inspection.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Inspector Metadata */}
        {inspection.form?.inspector_info && (
          <div className="bg-blue-50 rounded-lg shadow-sm border border-blue-200 p-4 mb-6">
            <h3 className="text-lg font-semibold text-blue-900 mb-3">
              Inspection Information
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="flex items-center space-x-2">
                <User className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="text-xs text-blue-600">Inspected by</div>
                  <div className="text-sm font-medium text-blue-900">
                    {inspection.form.inspector_info.name}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="text-xs text-blue-600">Position</div>
                  <div className="text-sm font-medium text-blue-900">
                    {inspection.form.inspector_info.level}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Building className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="text-xs text-blue-600">Section/Unit</div>
                  <div className="text-sm font-medium text-blue-900">
                    {inspection.form.inspector_info.section || "N/A"}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <MapPin className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="text-xs text-blue-600">District</div>
                  <div className="text-sm font-medium text-blue-900">
                    {inspection.form.inspector_info.district || "N/A"}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="text-xs text-blue-600">Inspection Date</div>
                  <div className="text-sm font-medium text-blue-900">
                    {new Date(
                      inspection.form.inspector_info.inspected_at
                    ).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Form */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleStartInspection();
            }}
          >
            <div className="space-y-6">
              {/* Findings Summary */}
              <div>
                <label
                  htmlFor="findings_summary"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Findings Summary *
                </label>
                <textarea
                  id="findings_summary"
                  rows={4}
                  value={formData.findings_summary}
                  onChange={(e) =>
                    handleInputChange("findings_summary", e.target.value)
                  }
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                    errors.findings_summary
                      ? "border-red-500"
                      : "border-gray-300"
                  }`}
                  placeholder="Describe the main findings from your inspection..."
                />
                {errors.findings_summary && (
                  <p className="mt-1 text-sm text-red-600">
                    {errors.findings_summary}
                  </p>
                )}
              </div>

              {/* Compliance Observations */}
              <div>
                <label
                  htmlFor="compliance_observations"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Compliance Observations *
                </label>
                <textarea
                  id="compliance_observations"
                  rows={4}
                  value={formData.compliance_observations}
                  onChange={(e) =>
                    handleInputChange("compliance_observations", e.target.value)
                  }
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                    errors.compliance_observations
                      ? "border-red-500"
                      : "border-gray-300"
                  }`}
                  placeholder="Describe compliance observations and any issues found..."
                />
                {errors.compliance_observations && (
                  <p className="mt-1 text-sm text-red-600">
                    {errors.compliance_observations}
                  </p>
                )}
              </div>

              {/* Violations Found */}
              <div>
                <label
                  htmlFor="violations_found"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Violations Found
                </label>
                <textarea
                  id="violations_found"
                  rows={3}
                  value={formData.violations_found}
                  onChange={(e) =>
                    handleInputChange("violations_found", e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="List any violations found (if applicable)..."
                />
              </div>

              {/* Recommendations */}
              <div>
                <label
                  htmlFor="recommendations"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Recommendations
                </label>
                <textarea
                  id="recommendations"
                  rows={3}
                  value={formData.recommendations}
                  onChange={(e) =>
                    handleInputChange("recommendations", e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Provide recommendations for improvement..."
                />
              </div>

              {/* Remarks */}
              <div>
                <label
                  htmlFor="remarks"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Additional Remarks
                </label>
                <textarea
                  id="remarks"
                  rows={3}
                  value={formData.remarks}
                  onChange={(e) => handleInputChange("remarks", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Any additional remarks or notes..."
                />
              </div>
            </div>

            {/* Form Actions */}
            <div className="flex items-center justify-between pt-6 border-t border-gray-200 mt-8">
              <button
                type="button"
                onClick={handleBack}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>

              <div className="flex items-center space-x-4">
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  disabled={savingDraft}
                  className="flex items-center space-x-2 px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {savingDraft ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      <span>Save Draft</span>
                    </>
                  )}
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center space-x-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {saving ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>
                        {hasExistingData ? "Updating..." : "Starting..."}
                      </span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      <span>
                        {hasExistingData
                          ? "Update Inspection"
                          : "Start Inspection"}
                      </span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default InspectionForm;
