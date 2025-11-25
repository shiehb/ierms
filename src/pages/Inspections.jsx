import { useState, useEffect, useCallback } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import InspectionsList from "../components/inspections/InspectionsList";
import SimpleInspectionWizard from "../components/inspections/SimpleInspectionWizard";
import {
  getProfile,
  getEstablishments,
  getAvailableEstablishments,
  createInspection,
  startInspection,
  completeInspection,
  forwardInspection,
  reviewInspection,
  forwardToLegal,
  sendNOV,
  sendNOO,
  closeInspection,
} from "../services/api";
import ComplianceModal from "../components/inspections/modals/ComplianceModal";
import LegalUnitModal from "../components/inspections/modals/LegalUnitModal";
import ForwardModal from "../components/inspections/modals/ForwardModal";
import CompleteModal from "../components/inspections/modals/CompleteModal";
import ReviewModal from "../components/inspections/modals/ReviewModal";
import NOVModal from "../components/inspections/modals/NOVModal";
import NOOModal from "../components/inspections/modals/NOOModal";
import { useNotifications } from "../hooks/useNotifications";

export default function Inspections() {
  const notifications = useNotifications();
  const [showAdd, setShowAdd] = useState(false);
  const [workflowInspection, setWorkflowInspection] = useState(null);
  const [complianceModal, setComplianceModal] = useState({
    open: false,
    inspection: null,
  });
  const [legalUnitModal, setLegalUnitModal] = useState({
    open: false,
    inspection: null,
  });
  const [forwardModal, setForwardModal] = useState({
    open: false,
    inspection: null,
  });
  const [completeModal, setCompleteModal] = useState({
    open: false,
    inspection: null,
  });
  const [reviewModal, setReviewModal] = useState({
    open: false,
    inspection: null,
  });
  const [novModal, setNovModal] = useState({ open: false, inspection: null });
  const [nooModal, setNooModal] = useState({ open: false, inspection: null });
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [userLevel, setUserLevel] = useState("public");
  const [loading, setLoading] = useState(true);
  const [establishments, setEstablishments] = useState([]);
  const [establishmentsLoading, setEstablishmentsLoading] = useState(false);
  const [novLoading, setNovLoading] = useState(false);
  const [nooLoading, setNooLoading] = useState(false);

  const refreshInspections = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleWorkflowAction = async (inspection, actionType = "inspect") => {
    try {
      // Handle modal-based actions
      if (actionType === "forward") {
        setForwardModal({ open: true, inspection });
        return;
      } else if (actionType === "review") {
        setReviewModal({ open: true, inspection });
        return;
      } else if (actionType === "send_nov") {
        setNovModal({ open: true, inspection });
        return;
      } else if (actionType === "send_noo") {
        setNooModal({ open: true, inspection });
        return;
      } else if (actionType === "complete") {
        setCompleteModal({ open: true, inspection });
        return;
      }

      let result;
      let actionMessage = "";

      // Call the appropriate backend API based on current status and action
      if (actionType === "start") {
        result = await startInspection(inspection.id);
        actionMessage = `Inspection ${inspection.code} has been started.`;
      } else if (actionType === "forward_to_legal") {
        result = await forwardToLegal(inspection.id, {
          remarks: "Forwarded to Legal Unit",
        });
        actionMessage = `Inspection ${inspection.code} has been forwarded to Legal Unit.`;
      } else if (actionType === "close") {
        result = await closeInspection(inspection.id, {
          remarks: "Inspection closed",
        });
        actionMessage = `Inspection ${inspection.code} has been closed.`;
      } else {
        // Fallback for other actions
        actionMessage = `Workflow action for inspection: ${inspection.code}\nStatus: ${inspection.status}`;
      }

      // Show success message
      notifications.success(actionMessage);
      setWorkflowInspection(null);

      // Refresh the inspections list to show updated data
      refreshInspections();
    } catch (error) {
      console.error("Workflow action error:", error);
      notifications.error(`Error performing workflow action: ${error.message}`);
      setWorkflowInspection(null);
    }
  };

  // Handle compliance modal
  const handleComplianceSubmit = async (complianceData) => {
    try {
      // Use the new completeInspection function for compliance decisions
      await completeInspection(complianceModal.inspection.id, complianceData);
      setComplianceModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Compliance status updated successfully!");
    } catch (error) {
      console.error("Error updating compliance:", error);
      notifications.error(`Error updating compliance: ${error.message}`);
    }
  };

  // Handle Legal Unit modal
  const handleLegalUnitSubmit = async (actionType, formData) => {
    try {
      switch (actionType) {
        case "send_nov":
          await sendNOV(legalUnitModal.inspection.id, formData);
          break;
        case "send_noo":
          await sendNOO(legalUnitModal.inspection.id, formData);
          break;
        default:
          throw new Error("Invalid action type");
      }

      setLegalUnitModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success(
        `${actionType
          .replace("_", " ")
          .toUpperCase()} action completed successfully!`
      );
    } catch (error) {
      console.error("Error performing Legal Unit action:", error);
      notifications.error(`Error performing action: ${error.message}`);
    }
  };

  // Handle Forward modal
  const handleForwardSubmit = async (inspectionId, formData) => {
    try {
      await forwardInspection(inspectionId, formData);
      setForwardModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Inspection forwarded successfully!");
    } catch (error) {
      console.error("Error forwarding inspection:", error);
      notifications.error(`Error forwarding inspection: ${error.message}`);
    }
  };

  // Handle Complete modal
  const handleCompleteSubmit = async (inspectionId, formData) => {
    try {
      await completeInspection(inspectionId, formData);
      setCompleteModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Inspection completed successfully!");
    } catch (error) {
      console.error("Error completing inspection:", error);
      notifications.error(`Error completing inspection: ${error.message}`);
    }
  };

  // Handle Review modal
  const handleReviewSubmit = async (inspectionId, formData) => {
    try {
      await reviewInspection(inspectionId, formData);
      setReviewModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Review submitted successfully!");
    } catch (error) {
      console.error("Error submitting review:", error);
      notifications.error(`Error submitting review: ${error.message}`);
    }
  };

  // Handle NOV modal
  const handleNOVSubmit = async (formData) => {
    if (!novModal.inspection) return;
    setNovLoading(true);
    try {
      await sendNOV(novModal.inspection.id, formData);
      setNovModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Notice of Violation sent successfully!");
    } catch (error) {
      console.error("Error sending NOV:", error);
      notifications.error(`Error sending NOV: ${error.message}`);
    } finally {
      setNovLoading(false);
    }
  };

  // Handle NOO modal
  const handleNOOSubmit = async (formData) => {
    if (!nooModal.inspection) return;
    setNooLoading(true);
    try {
      await sendNOO(nooModal.inspection.id, formData);
      setNooModal({ open: false, inspection: null });
      refreshInspections();
      notifications.success("Notice of Order sent successfully!");
    } catch (error) {
      console.error("Error sending NOO:", error);
      notifications.error(`Error sending NOO: ${error.message}`);
    } finally {
      setNooLoading(false);
    }
  };

  // Fetch available establishments for the wizard - only those not under active inspection
  const fetchEstablishments = useCallback(
    async (searchQuery = "", page = 1, pageSize = 100) => {
      setEstablishmentsLoading(true);
      try {
        // Use the new available establishments endpoint
        const response = await getAvailableEstablishments({
          page: page,
          page_size: pageSize,
          ...(searchQuery &&
            searchQuery.length >= 2 && { search: searchQuery }),
        });

        if (response.results) {
          // Transform the data to match the expected format for wizard
          const transformedEstablishments = response.results.map((est) => ({
            id: est.id,
            name: est.name,
            address: `${est.street_building || ""}, ${est.barangay || ""}, ${
              est.city || ""
            }, ${est.province || ""}, ${est.postal_code || ""}`
              .replace(/,\s*,/g, ",")
              .replace(/^,\s*|,\s*$/g, ""),
            coordinates: `${est.latitude || ""}, ${est.longitude || ""}`
              .replace(/,\s*,/g, ",")
              .replace(/^,\s*|,\s*$/g, ""),
            nature_of_business: est.nature_of_business || "N/A",
            year_established: est.year_established || "N/A",
          }));
          setEstablishments(transformedEstablishments);
        } else {
          // Fallback for non-paginated response
          const transformedEstablishments = response.map((est) => ({
            id: est.id,
            name: est.name,
            address: `${est.street_building || ""}, ${est.barangay || ""}, ${
              est.city || ""
            }, ${est.province || ""}, ${est.postal_code || ""}`
              .replace(/,\s*,/g, ",")
              .replace(/^,\s*|,\s*$/g, ""),
            coordinates: `${est.latitude || ""}, ${est.longitude || ""}`
              .replace(/,\s*,/g, ",")
              .replace(/^,\s*|,\s*$/g, ""),
            nature_of_business: est.nature_of_business || "N/A",
            year_established: est.year_established || "N/A",
          }));
          setEstablishments(transformedEstablishments);
        }
      } catch (error) {
        console.error("Error fetching available establishments:", error);
        // Fallback to mock data on error
        setEstablishments([
          {
            id: 1,
            name: "ABC Manufacturing Corp.",
            address: "123 Industrial St, San Fernando, La Union",
            coordinates: "16.6164, 120.3162",
            nature_of_business: "Manufacturing",
            year_established: "2015",
          },
          {
            id: 2,
            name: "XYZ Industries Inc.",
            address: "456 Business Ave, Bauang, La Union",
            coordinates: "16.5308, 120.3331",
            nature_of_business: "Industrial Processing",
            year_established: "2018",
          },
        ]);
      } finally {
        setEstablishmentsLoading(false);
      }
    },
    []
  ); // Empty dependency array since this function doesn't depend on any props or state

  // Create stable callback functions for wizard props
  const handleRefreshEstablishments = useCallback(
    () => fetchEstablishments(),
    [fetchEstablishments]
  );
  const handleSearchEstablishments = useCallback(
    (searchQuery) => fetchEstablishments(searchQuery),
    [fetchEstablishments]
  );

  // Fetch user profile to get actual user level
  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        const accessToken = localStorage.getItem("access");
        if (!accessToken) {
          setUserLevel("public");
          setLoading(false);
          return;
        }

        const profile = await getProfile();
        const level = profile.userlevel || "public";

        setUserLevel(level);
        localStorage.setItem("userLevel", level);
      } catch (err) {
        console.error("Error fetching user profile:", err);
        const fallbackLevel = localStorage.getItem("userLevel") || "public";
        setUserLevel(fallbackLevel);
      } finally {
        setLoading(false);
      }
    };

    fetchUserProfile();
  }, []);

  // Fetch establishments when component mounts
  useEffect(() => {
    fetchEstablishments();
  }, [fetchEstablishments]);

  const [laws] = useState([
    { code: "PD-1586", name: "EIA Monitoring" },
    { code: "RA-8749", name: "Air Quality Monitoring" },
    { code: "RA-9275", name: "Water Quality Monitoring" },
    { code: "RA-6969", name: "Toxic Chemicals Monitoring" },
    { code: "RA-9003", name: "Solid Waste Management" },
  ]);

  // Show loading state while fetching user profile
  if (loading) {
    return (
      <>
        <Header />
        <LayoutWithSidebar userLevel="admin">
          <div className="flex items-center justify-center h-64">
            <div className="flex flex-col items-center text-gray-600">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-600 mb-2"></div>
              <span>Loading inspections...</span>
            </div>
          </div>
        </LayoutWithSidebar>
        <Footer />
      </>
    );
  }

  // If showing wizard, render the wizard component (which includes its own layout)
  if (showAdd) {
    return (
      <SimpleInspectionWizard
        onClose={() => setShowAdd(false)}
        onSave={async (formData) => {
          try {
            const selectedLaw = laws.find(
              (law) => law.code === formData.law_code
            );
            const establishmentCount = formData.establishment_ids.length;

            // Create inspection for each selected establishment
            const inspectionPromises = formData.establishment_ids.map(
              (establishmentId) => {
                const inspectionData = {
                  establishments: [establishmentId],
                  law: formData.law_code,
                  scheduled_at: formData.scheduled_at || null,
                  inspection_notes: `Inspection for ${
                    selectedLaw?.name || formData.law_code
                  }`,
                  // The backend will handle auto-assignment based on the workflow rules
                };
                return createInspection(inspectionData);
              }
            );

            // Create all inspections in parallel
            const createdInspections = await Promise.all(inspectionPromises);

            // Close wizard and refresh list
            setShowAdd(false);
            refreshInspections();

            // Show success message
            notifications.success(
              `Successfully created ${establishmentCount} inspection(s) for ${
                selectedLaw?.name || formData.law_code
              }!`
            );
          } catch (error) {
            console.error("Error creating inspections:", error);
            notifications.error(`Error creating inspections: ${error.message}`);
          }
        }}
        userProfile={{ userlevel: userLevel }}
        establishments={establishments}
        establishmentsLoading={establishmentsLoading}
        laws={laws}
        userLevel={userLevel}
        onRefreshEstablishments={handleRefreshEstablishments}
        onSearchEstablishments={handleSearchEstablishments}
      />
    );
  }

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel="admin">
        <div>
          {/* Inspections List */}
          <InspectionsList
            userLevel={userLevel}
            onAdd={() => setShowAdd(true)}
            onWorkflow={(inspection, actionType) =>
              setWorkflowInspection({ ...inspection, actionType })
            }
            onCompliance={(inspection) =>
              setComplianceModal({ open: true, inspection })
            }
            onLegalUnit={(inspection) =>
              setLegalUnitModal({ open: true, inspection })
            }
            refreshTrigger={refreshTrigger}
          />

          {/* Simple Workflow Modal */}
          {workflowInspection && (
            <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm">
              <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Workflow Action
                  </h3>
                  <button
                    onClick={() => setWorkflowInspection(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg
                      className="w-6 h-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>Inspection:</strong> {workflowInspection.code}
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>Current Status:</strong> {workflowInspection.status}
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>Establishment:</strong>{" "}
                    {workflowInspection.establishment_name}
                  </p>
                  {workflowInspection.status === "DIVISION_CREATED" && (
                    <div className="mt-3 p-3 bg-blue-50 rounded-md">
                      <p className="text-sm text-blue-800">
                        <strong>Action:</strong> This will move the inspection
                        to "My Inspections" tab with SECTION_INSPECTING status.
                      </p>
                    </div>
                  )}
                  {workflowInspection.status === "SECTION_INSPECTING" && (
                    <div className="mt-3 p-3 bg-green-50 rounded-md">
                      <p className="text-sm text-green-800">
                        <strong>Action:</strong> This will complete the
                        inspection or forward it to the next stage.
                      </p>
                    </div>
                  )}
                  {workflowInspection.status === "UNIT_REVIEW" && (
                    <div className="mt-3 p-3 bg-purple-50 rounded-md">
                      <p className="text-sm text-purple-800">
                        <strong>Action:</strong> This will move the inspection
                        to "My Inspections" tab with UNIT_INSPECTING status.
                      </p>
                    </div>
                  )}
                  {workflowInspection.status === "UNIT_INSPECTING" && (
                    <div className="mt-3 p-3 bg-indigo-50 rounded-md">
                      <p className="text-sm text-indigo-800">
                        <strong>Action:</strong> This will complete the
                        inspection or forward it to Monitoring Personnel.
                      </p>
                    </div>
                  )}
                  {workflowInspection.status === "MONITORING_INSPECTION" && (
                    <div className="mt-3 p-3 bg-cyan-50 rounded-md">
                      <p className="text-sm text-cyan-800">
                        <strong>Action:</strong> This will complete the
                        inspection and initiate the return path based on
                        compliance status.
                      </p>
                    </div>
                  )}
                  {workflowInspection.status === "LEGAL_REVIEW" && (
                    <div className="mt-3 p-3 bg-red-50 rounded-md">
                      <p className="text-sm text-red-800">
                        <strong>Action:</strong> This will send notices to the
                        establishment or close the case.
                      </p>
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={() => setWorkflowInspection(null)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() =>
                      handleWorkflowAction(
                        workflowInspection,
                        workflowInspection.actionType
                      )
                    }
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    Execute Action
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Compliance Modal */}
          <ComplianceModal
            open={complianceModal.open}
            inspection={complianceModal.inspection}
            onClose={() =>
              setComplianceModal({ open: false, inspection: null })
            }
            onSubmit={handleComplianceSubmit}
          />

          {/* Legal Unit Modal */}
          <LegalUnitModal
            open={legalUnitModal.open}
            inspection={legalUnitModal.inspection}
            onClose={() => setLegalUnitModal({ open: false, inspection: null })}
            onSubmit={handleLegalUnitSubmit}
          />

          {/* Forward Modal */}
          <ForwardModal
            open={forwardModal.open}
            inspection={forwardModal.inspection}
            onClose={() => setForwardModal({ open: false, inspection: null })}
            onSubmit={handleForwardSubmit}
            userLevel={userLevel}
          />

          {/* Complete Modal */}
          <CompleteModal
            open={completeModal.open}
            inspection={completeModal.inspection}
            onClose={() => setCompleteModal({ open: false, inspection: null })}
            onSubmit={handleCompleteSubmit}
            userLevel={userLevel}
          />

          {/* Review Modal */}
          <ReviewModal
            open={reviewModal.open}
            inspection={reviewModal.inspection}
            onClose={() => setReviewModal({ open: false, inspection: null })}
            onSubmit={handleReviewSubmit}
            userLevel={userLevel}
          />

          {/* NOV Modal */}
          <NOVModal
            open={novModal.open}
            inspection={novModal.inspection}
            onClose={() => setNovModal({ open: false, inspection: null })}
            onSubmit={handleNOVSubmit}
            loading={novLoading}
          />

          {/* NOO Modal */}
          <NOOModal
            open={nooModal.open}
            inspection={nooModal.inspection}
            onClose={() => setNooModal({ open: false, inspection: null })}
            onSubmit={handleNOOSubmit}
            loading={nooLoading}
          />
        </div>
      </LayoutWithSidebar>
      <Footer />
    </>
  );
}
