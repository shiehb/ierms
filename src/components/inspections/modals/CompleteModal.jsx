import React, { useState } from "react";
import { X, CheckCircle, XCircle, FileText, AlertTriangle } from "lucide-react";
import { useNotifications } from "../../../hooks/useNotifications";

const CompleteModal = ({ open, inspection, onClose, onSubmit, userLevel }) => {
  const [complianceDecision, setComplianceDecision] = useState("");
  const [violationsFound, setViolationsFound] = useState("");
  const [findingsSummary, setFindingsSummary] = useState("");
  const [compliancePlan, setCompliancePlan] = useState("");
  const [complianceDeadline, setComplianceDeadline] = useState("");
  const [remarks, setRemarks] = useState("");
  const [loading, setLoading] = useState(false);
  const notifications = useNotifications();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!complianceDecision) return;

    // Validate that violations are provided if non-compliant
    if (complianceDecision === "NON_COMPLIANT" && !violationsFound.trim()) {
      notifications.warning(
        "Please provide details of violations found for non-compliant inspections.",
        {
          title: "Validation Error",
        }
      );
      return;
    }

    setLoading(true);
    try {
      const data = {
        compliance_decision: complianceDecision,
        violations_found: violationsFound.trim(),
        findings_summary: findingsSummary.trim(),
        compliance_plan: compliancePlan.trim(),
        compliance_deadline: complianceDeadline || null,
        remarks: remarks.trim() || "Inspection completed",
      };

      await onSubmit(inspection.id, data);
      onClose();
    } catch (error) {
      console.error("Error completing inspection:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    // Reset form
    setComplianceDecision("");
    setViolationsFound("");
    setFindingsSummary("");
    setCompliancePlan("");
    setComplianceDeadline("");
    setRemarks("");
    onClose();
  };

  if (!open || !inspection) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
            Complete Inspection
          </h3>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          <div className="mb-6">
            <div className="bg-gray-50 p-4 rounded-md mb-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2">
                Inspection Details
              </h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Code:</span>
                  <span className="ml-2 font-medium">{inspection.code}</span>
                </div>
                <div>
                  <span className="text-gray-500">Law:</span>
                  <span className="ml-2 font-medium">{inspection.law}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-gray-500">Establishments:</span>
                  <span className="ml-2 font-medium">
                    {inspection.establishments_detail
                      ?.map((est) => est.name)
                      .join(", ") || "None"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Compliance Decision *
            </label>
            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="compliance"
                  value="COMPLIANT"
                  checked={complianceDecision === "COMPLIANT"}
                  onChange={(e) => setComplianceDecision(e.target.value)}
                  className="mr-3 text-green-600 focus:ring-green-500"
                />
                <div className="flex items-center">
                  <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
                  <div>
                    <div className="font-medium text-green-800">Compliant</div>
                    <div className="text-xs text-green-600">
                      Establishment meets all requirements
                    </div>
                  </div>
                </div>
              </label>

              <label className="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="compliance"
                  value="NON_COMPLIANT"
                  checked={complianceDecision === "NON_COMPLIANT"}
                  onChange={(e) => setComplianceDecision(e.target.value)}
                  className="mr-3 text-red-600 focus:ring-red-500"
                />
                <div className="flex items-center">
                  <XCircle className="w-5 h-5 mr-2 text-red-600" />
                  <div>
                    <div className="font-medium text-red-800">
                      Non-Compliant
                    </div>
                    <div className="text-xs text-red-600">Violations found</div>
                  </div>
                </div>
              </label>
            </div>
          </div>

          <div className="mb-4">
            <label
              htmlFor="findingsSummary"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Findings Summary *
            </label>
            <textarea
              id="findingsSummary"
              value={findingsSummary}
              onChange={(e) => setFindingsSummary(e.target.value)}
              rows={4}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
              placeholder="Describe the key findings from the inspection..."
            />
          </div>

          {complianceDecision === "NON_COMPLIANT" && (
            <>
              <div className="mb-4">
                <label
                  htmlFor="violationsFound"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  <AlertTriangle className="w-4 h-4 inline mr-1 text-red-500" />
                  Violations Found *
                </label>
                <textarea
                  id="violationsFound"
                  value={violationsFound}
                  onChange={(e) => setViolationsFound(e.target.value)}
                  rows={3}
                  required
                  className="w-full px-3 py-2 border border-red-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 text-sm"
                  placeholder="Detail the specific violations found during inspection..."
                />
              </div>

              <div className="mb-4">
                <label
                  htmlFor="compliancePlan"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Compliance Plan
                </label>
                <textarea
                  id="compliancePlan"
                  value={compliancePlan}
                  onChange={(e) => setCompliancePlan(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  placeholder="Recommended actions for compliance..."
                />
              </div>

              <div className="mb-4">
                <label
                  htmlFor="complianceDeadline"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Compliance Deadline
                </label>
                <input
                  type="date"
                  id="complianceDeadline"
                  value={complianceDeadline}
                  onChange={(e) => setComplianceDeadline(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                />
              </div>
            </>
          )}

          <div className="mb-6">
            <label
              htmlFor="remarks"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Additional Remarks
            </label>
            <textarea
              id="remarks"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
              placeholder="Any additional notes or observations..."
            />
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                !complianceDecision || !findingsSummary.trim() || loading
              }
              className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Completing...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Complete Inspection
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CompleteModal;
