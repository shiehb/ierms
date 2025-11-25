import { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useNotifications } from "../hooks/useNotifications";
import api from "../services/api";
import { X, Camera, FileText } from "lucide-react";
import LayoutForm from "../components/LayoutForm";
import ImageLightbox from "../components/inspection-form/ImageLightbox";

const InspectionReportViewPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const notifications = useNotifications();

  const [inspectionData, setInspectionData] = useState(null);
  const [formData, setFormData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Image lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  // Process compliance items for merged law citations
  const processedComplianceItems = useMemo(() => {
    if (!formData?.complianceItems || formData.complianceItems.length === 0) {
      return [];
    }

    const selectedEnvironmentalLaws =
      formData.general?.environmental_laws || [];
    const ALWAYS_INCLUDED_LAWS = [
      "DAO 2014-02 or Revised Guidelines on PCO Accreditation",
      "DAO 2014-02",
      "PCO Accreditation",
      "Pollution-Control",
      "DAO 2003-27",
      "Self-Monitoring",
      "SMR",
    ];
    const effectiveLawFilter = [
      ...new Set([
        ...(selectedEnvironmentalLaws || []),
        ...ALWAYS_INCLUDED_LAWS,
      ]),
    ];

    const filteredComplianceItems = formData.complianceItems.filter((item) => {
      const itemLawId = item.lawId || item.law_id || item.law;
      const itemLawCitation = item.lawCitation || item.law_citation;

      const matchesSelected = effectiveLawFilter.includes(itemLawId);
      const matchesCitation = effectiveLawFilter.includes(itemLawCitation);
      const isPCORelated =
        itemLawId?.includes("PCO") ||
        itemLawCitation?.includes("PCO") ||
        itemLawId?.includes("2014-02") ||
        itemLawCitation?.includes("2014-02") ||
        item.complianceRequirement?.includes("PCO") ||
        item.complianceRequirement?.includes("accreditation");
      const isSMRRelated =
        itemLawId?.includes("2003-27") ||
        itemLawCitation?.includes("2003-27") ||
        itemLawId?.includes("SMR") ||
        itemLawCitation?.includes("SMR") ||
        item.complianceRequirement?.includes("SMR") ||
        item.complianceRequirement?.includes("Self-Monitoring") ||
        item.complianceRequirement?.includes("monitoring report");

      return matchesSelected || matchesCitation || isPCORelated || isSMRRelated;
    });

    const groupedByLaw = filteredComplianceItems.reduce((acc, item) => {
      const lawCitation =
        item.lawCitation || item.law_citation || item.lawId || item.law || "-";
      if (!acc[lawCitation]) {
        acc[lawCitation] = [];
      }
      acc[lawCitation].push(item);
      return acc;
    }, {});

    const result = [];
    Object.keys(groupedByLaw).forEach((lawCitation) => {
      const itemsInGroup = groupedByLaw[lawCitation];
      itemsInGroup.forEach((item, index) => {
        result.push({
          ...item,
          lawCitation,
          isFirstInGroup: index === 0,
          rowspan: index === 0 ? itemsInGroup.length : 0,
        });
      });
    });

    return result;
  }, [formData]);

  useEffect(() => {
    if (!id) return;

    const fetchInspectionData = async () => {
      try {
        setLoading(true);
        const response = await api.get(`inspections/${id}/`);

        setInspectionData(response.data);

        const checklist = response.data.form?.checklist;
        if (checklist && Object.keys(checklist).length > 0) {
          setFormData(checklist);
        } else {
          setFormData({
            general: {},
            purpose: {},
            permits: [],
            complianceItems: [],
            systems: [],
            recommendationState: {},
          });
        }
      } catch (error) {
        console.error("Error fetching inspection:", error);
        notifications.error(`Failed to load inspection data: ${error.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchInspectionData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const formatViolationsByLaw = useCallback((violationsByLaw) => {
    if (!violationsByLaw || Object.keys(violationsByLaw).length === 0) {
      return "";
    }

    const formatted = [];
    let lawCounter = 1;

    Object.entries(violationsByLaw).forEach(([law, entries]) => {
      if (!law) return;
      formatted.push(`${lawCounter}. ${law}:`);

      if (entries.length > 0) {
        entries.forEach((entry, index) => {
          const sanitized = entry.replace(/^•\s*/, "");
          formatted.push(`   ${lawCounter}.${index + 1} ${sanitized}`);
        });
      } else {
        formatted.push(`   ${lawCounter}.1 No specific violations recorded`);
      }

      formatted.push("");
      lawCounter += 1;
    });

    return formatted.join("\n").trim();
  }, []);

  const formatLegacyViolations = useCallback(
    (rawViolations) => {
      if (!rawViolations) return "";

      const tokens = rawViolations
        .split(",")
        .map((token) => token.trim())
        .filter(Boolean);

      if (tokens.length === 0) return rawViolations.trim();

      const grouped = [];
      let currentGroup = null;

      tokens.forEach((token) => {
        const isBullet = token.startsWith("•");
        const sanitized = token.replace(/^•\s*/, "").replace(/[;]+$/, "");

        if (!isBullet) {
          const law = sanitized.replace(/[:]+$/, "").trim();
          if (!law) return;
          currentGroup = {
            law,
            items: [],
          };
          grouped.push(currentGroup);
        } else {
          if (!currentGroup) {
            currentGroup = {
              law: "Violations",
              items: [],
            };
            grouped.push(currentGroup);
          }
          if (sanitized) {
            currentGroup.items.push(sanitized);
          }
        }
      });

      const violationsByLaw = {};
      grouped.forEach(({ law, items }) => {
        violationsByLaw[law] = items;
      });

      return formatViolationsByLaw(violationsByLaw);
    },
    [formatViolationsByLaw]
  );

  // Auto-populate violations from form data
  const violationsFound = useMemo(() => {
    if (!formData) return "";

    // First check if there are existing violations from the database
    const existingViolations = inspectionData?.form?.violations_found;
    if (existingViolations) {
      const needsFormatting =
        existingViolations.includes("•") || existingViolations.includes(",");
      return needsFormatting
        ? formatLegacyViolations(existingViolations)
        : existingViolations;
    }

    // Auto-generate violations from non-compliant items
    const violationsByLaw = {};

    if (formData.complianceItems) {
      formData.complianceItems.forEach((item) => {
        if (item.compliant === "No" && item.remarks) {
          const lawInfo =
            item.lawCitation || item.lawId || "General Compliance";
          const requirement =
            item.complianceRequirement || "Compliance Requirement";

          if (!violationsByLaw[lawInfo]) {
            violationsByLaw[lawInfo] = [];
          }
          violationsByLaw[lawInfo].push(`${requirement}: ${item.remarks}`);
        }
      });
    }

    if (formData.systems) {
      formData.systems.forEach((system) => {
        if (system.nonCompliant && system.remarks) {
          const lawInfo = system.lawId || "General Findings";

          if (!violationsByLaw[lawInfo]) {
            violationsByLaw[lawInfo] = [];
          }
          violationsByLaw[lawInfo].push(`${system.system}: ${system.remarks}`);
        }
      });
    }

    return formatViolationsByLaw(violationsByLaw);
  }, [formData, inspectionData, formatLegacyViolations, formatViolationsByLaw]);

  const formatDate = (dateString) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDateOnly = (dateString) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  };

  // Get signature URLs from inspection data
  const signatureUrls = useMemo(() => {
    const signatures =
      inspectionData?.form?.checklist?.signatures || formData?.signatures || {};
    const timestamp = Date.now();
    return {
      submitted: signatures.submitted?.url
        ? `${signatures.submitted.url}?t=${timestamp}`
        : null,
      review_unit: signatures.review_unit?.url
        ? `${signatures.review_unit.url}?t=${timestamp}`
        : null,
      review_section: signatures.review_section?.url
        ? `${signatures.review_section.url}?t=${timestamp}`
        : null,
      approve_division: signatures.approve_division?.url
        ? `${signatures.approve_division.url}?t=${timestamp}`
        : null,
    };
  }, [inspectionData?.form?.checklist?.signatures, formData?.signatures]);

  // Get signature configuration for display
  const signatureConfig = useMemo(() => {
    if (!inspectionData)
      return {
        submittedRole: "Inspector",
        reviewUnit: false,
        reviewSection: false,
      };

    const inspectorLevel = inspectionData.form?.inspector_info?.level || "";

    if (inspectorLevel === "Monitoring Personnel") {
      return {
        submittedRole: "Monitoring Personnel",
        reviewUnit: true,
        reviewSection: true,
      };
    }
    if (inspectorLevel === "Unit Head") {
      return {
        submittedRole: "Unit Head",
        reviewUnit: false,
        reviewSection: true,
      };
    }
    if (inspectorLevel === "Section Chief") {
      return {
        submittedRole: "Section Chief",
        reviewUnit: false,
        reviewSection: true,
      };
    }

    return {
      submittedRole: inspectorLevel || "Inspector",
      reviewUnit: false,
      reviewSection: false,
    };
  }, [inspectionData]);

  const getComplianceStatus = () => {
    if (inspectionData?.form?.compliance_decision) {
      return inspectionData.form.compliance_decision;
    }

    if (inspectionData?.current_status) {
      const status = inspectionData.current_status;
      if (status.includes("_COMPLIANT")) {
        return "COMPLIANT";
      } else if (status.includes("_NON_COMPLIANT")) {
        return "NON_COMPLIANT";
      }
    }

    return formData?.compliance_status || "PENDING";
  };

  // Function to open lightbox with images
  const openLightbox = (images, index = 0) => {
    setLightboxImages(images);
    setLightboxIndex(index);
    setLightboxOpen(true);
  };

  if (loading && !inspectionData) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading inspection data...</p>
        </div>
      </div>
    );
  }

  if (!inspectionData) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-gray-600 text-lg mb-2">
            No inspection data available
          </p>
          <p className="text-gray-500 text-sm mb-4">
            The inspection could not be loaded. Please try again.
          </p>
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 text-white bg-sky-600 hover:bg-sky-700 rounded-md"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const complianceStatus = getComplianceStatus();
  const general = formData?.general || {};
  const purpose = formData?.purpose || {};
  const permits = formData?.permits || [];
  const systems = formData?.systems || [];
  const recommendations = formData?.recommendationState || {};

  // Custom header with only Close button
  const reportHeader = (
    <div className="bg-white border-b border-gray-300 shadow-sm print:hidden">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-4">
          <div className="text-xl font-bold text-sky-700">
            Integrated Compliance Inspection Report - Review
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              // If we came from establishment inspection records, navigate back with state
              if (
                location.state?.returnToInspections &&
                location.state?.establishmentId
              ) {
                navigate("/establishments", {
                  state: {
                    viewInspections: true,
                    establishmentId: location.state.establishmentId,
                  },
                });
              } else {
                // Otherwise, go back in history
                navigate(-1);
              }
            }}
            className="flex items-center px-3 py-1 text-sm text-black bg-gray-200 rounded hover:bg-gray-300 transition-colors"
          >
            <X className="w-4 h-4 mr-1" />
            Close
          </button>
        </div>
      </div>
    </div>
  );

  // Show loading state if data is not ready
  if (loading || !inspectionData || !formData) {
    return (
      <LayoutForm headerHeight="small">
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading inspection data...</p>
          </div>
        </div>
      </LayoutForm>
    );
  }

  return (
    <>
      <LayoutForm headerHeight="small" inspectionHeader={reportHeader}>
        <div className="w-full">
          {/* PDF Document Container */}
          <div className="bg-white shadow-lg print:shadow-none p-10">
            {/* Document Info */}
            <div className="mb-6 text-sm relative">
              <div className="text-center mb-6 relative">
                <h3 className="text-base font-semibold uppercase">
                  Inspection Report Summary
                </h3>

                {/* Overall Status Badge - Top Right Watermark */}
                <div
                  className={`absolute top-0 right-0 px-3 py-1 rounded text-sm font-semibold opacity-80 ${
                    complianceStatus === "COMPLIANT"
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {complianceStatus === "COMPLIANT"
                    ? "COMPLIANT"
                    : "NON-COMPLIANT"}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="font-semibold">Inspection Reference No.:</p>
                  <p className="text-gray-700">
                    {inspectionData?.code || "N/A"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">Date Generated:</p>
                  <p className="text-gray-700">{formatDate(new Date())}</p>
                </div>
              </div>
            </div>

            {/* I. GENERAL INFORMATION */}
            <section className="mb-8">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                I. GENERAL INFORMATION
              </h2>

              <div className="space-y-4">
                {/* Environmental Laws Section - At Top */}
                <div className="border border-gray-300 rounded-lg p-4 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-700 uppercase mb-3 border-b border-gray-300 pb-2">
                    Applicable Environmental Laws
                  </p>
                  <div className="space-y-1 text-sm">
                    {general.environmental_laws &&
                    general.environmental_laws.length > 0 ? (
                      general.environmental_laws.map((law) => (
                        <p key={law} className="text-gray-900">
                          ☑ {law}
                        </p>
                      ))
                    ) : (
                      <p className="text-gray-500 italic">No laws selected</p>
                    )}
                  </div>
                </div>

                {/* Basic and Operating Details Card - Full Width */}
                <div className="border border-gray-300 rounded-lg p-5 bg-gray-50">
                  <div>
                    <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                      Name of Establishment
                    </p>
                    <p className="text-sm text-gray-900 font-medium">
                      {general.establishment_name || "-"}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Address
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.address || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Coordinates (Decimal)
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.coordinates || "-"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                      Nature of Business
                    </p>
                    <p className="text-sm text-gray-900">
                      {general.nature_of_business || "-"}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Year Established
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.year_established || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Inspection Date & Time
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.inspection_date_time
                          ? formatDate(general.inspection_date_time)
                          : "-"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mt-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Operating Hours
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.operating_hours || "-"} hours/day
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Operating Days/Week
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.operating_days_per_week || "-"} days
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                        Operating Days/Year
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.operating_days_per_year || "-"} days
                      </p>
                    </div>
                  </div>
                </div>

                {/* Production Details Card - Full Width */}
                <div className="border border-gray-300 rounded-lg p-4 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-700 uppercase mb-3 border-b border-gray-300 pb-2">
                    Production Details
                  </p>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Product Lines
                      </p>
                      <p className="text-gray-900">
                        {general.product_lines || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Declared Production Rate
                      </p>
                      <p className="text-gray-900">
                        {general.declared_production_rate || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Actual Production Rate
                      </p>
                      <p className="text-gray-900">
                        {general.actual_production_rate || "-"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Personnel and Contact Information Card - Full Width */}
                <div className="border border-gray-300 rounded-lg p-4 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-700 uppercase mb-3 border-b border-gray-300 pb-2">
                    Personnel and Contact Information
                  </p>

                  <div className="mb-4">
                    <p className="text-xs font-semibold text-gray-600 mb-1">
                      Managing Head
                    </p>
                    <p className="text-sm text-gray-900">
                      {general.managing_head || "-"}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        PCO Name
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.pco_name || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Interviewed Person
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.interviewed_person || "-"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        PCO Accreditation No.
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.pco_accreditation_no || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Effectivity Date
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.effectivity_date
                          ? formatDateOnly(general.effectivity_date)
                          : "-"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Phone/Fax No.
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.phone_fax_no || "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">
                        Email Address
                      </p>
                      <p className="text-sm text-gray-900">
                        {general.email_address || "-"}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* II. PURPOSE OF INSPECTION */}
            <section className="mb-8 page-break-before">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                II. PURPOSE OF INSPECTION
              </h2>

              <div className="space-y-2 text-sm">
                {purpose.verify_accuracy && (
                  <div>
                    <p className="font-semibold">
                      ☑ Verify Accuracy of Data Submitted
                    </p>
                    {purpose.verify_accuracy_details &&
                      purpose.verify_accuracy_details.length > 0 && (
                        <div className="ml-6 mt-1">
                          {purpose.verify_accuracy_details.map(
                            (detail, idx) => (
                              <p key={idx} className="text-gray-700">
                                ⤷ {detail}
                              </p>
                            )
                          )}
                          {purpose.verify_accuracy_others && (
                            <p className="text-gray-700">
                              ⤷ Other: {purpose.verify_accuracy_others}
                            </p>
                          )}
                        </div>
                      )}
                  </div>
                )}

                {purpose.determine_compliance && (
                  <div>
                    <p className="font-semibold">
                      ☑ Determine Compliance with Environmental Laws
                    </p>
                    <p className="ml-6 text-gray-700">
                      All selected environmental laws and permits
                    </p>
                  </div>
                )}

                {purpose.investigate_complaints && (
                  <div>
                    <p className="font-semibold">☑ Investigate Complaints</p>
                  </div>
                )}

                {purpose.check_commitment_status && (
                  <div>
                    <p className="font-semibold">
                      ☑ Check Status of Commitments from Previous Technical
                      Conference
                    </p>
                    {purpose.commitment_status_details &&
                      purpose.commitment_status_details.length > 0 && (
                        <div className="ml-6 mt-1">
                          {purpose.commitment_status_details.map(
                            (detail, idx) => (
                              <p key={idx} className="text-gray-700">
                                ⤷ {detail}
                              </p>
                            )
                          )}
                          {purpose.commitment_status_others && (
                            <p className="text-gray-700">
                              ⤷ Other: {purpose.commitment_status_others}
                            </p>
                          )}
                        </div>
                      )}
                  </div>
                )}

                {purpose.other_purpose && (
                  <div>
                    <p className="font-semibold">☑ Other Purpose</p>
                    {purpose.other_purpose_specify && (
                      <p className="ml-6 text-gray-700">
                        {purpose.other_purpose_specify}
                      </p>
                    )}
                  </div>
                )}

                {!purpose.verify_accuracy &&
                  !purpose.determine_compliance &&
                  !purpose.investigate_complaints &&
                  !purpose.check_commitment_status &&
                  !purpose.other_purpose && (
                    <p className="text-gray-500">No purpose specified</p>
                  )}
              </div>
            </section>

            {/* III. DENR PERMITS */}
            <section className="mb-8 page-break-before">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                III. COMPLIANCE STATUS - DENR PERMITS, LICENSES & CLEARANCES
              </h2>

              <div className="overflow-x-auto">
                <table className="w-full border-collapse border border-gray-300 text-sm">
                  <thead>
                    <tr className="bg-gray-100">
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Environmental Law
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Permit Type
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Permit Number
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Date Issued
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Expiry Date
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {permits &&
                    permits.filter(
                      (p) => p.permitNumber && p.permitNumber.trim()
                    ).length > 0 ? (
                      permits
                        .filter((p) => p.permitNumber && p.permitNumber.trim())
                        .map((permit, idx) => (
                          <tr
                            key={idx}
                            className={
                              idx % 2 === 0 ? "bg-white" : "bg-gray-50"
                            }
                          >
                            <td className="border border-gray-300 px-3 py-2">
                              {permit.lawId}
                            </td>
                            <td className="border border-gray-300 px-3 py-2">
                              {permit.permitType}
                            </td>
                            <td className="border border-gray-300 px-3 py-2 font-mono">
                              {permit.permitNumber}
                            </td>
                            <td className="border border-gray-300 px-3 py-2">
                              {formatDateOnly(permit.dateIssued)}
                            </td>
                            <td className="border border-gray-300 px-3 py-2">
                              {formatDateOnly(permit.expiryDate)}
                            </td>
                          </tr>
                        ))
                    ) : (
                      <tr>
                        <td
                          colSpan="5"
                          className="border border-gray-300 px-3 py-4 text-center text-gray-500"
                        >
                          No permits recorded
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* IV. SUMMARY OF COMPLIANCE */}
            <section className="mb-8 page-break-before">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                IV. SUMMARY OF COMPLIANCE
              </h2>

              <div className="overflow-x-auto">
                <table className="w-full border-collapse border border-gray-300 text-sm">
                  <thead>
                    <tr className="bg-gray-100">
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold w-1/4">
                        Applicable Laws and Citations
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold w-1/3">
                        Compliance Requirement
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-center font-semibold w-20">
                        Status
                      </th>
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold">
                        Remarks
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {processedComplianceItems &&
                    processedComplianceItems.length > 0 ? (
                      processedComplianceItems.map((item, idx) => {
                        const complianceRequirement =
                          item.complianceRequirement ||
                          item.compliance_requirement ||
                          item.item ||
                          item.title ||
                          item.compliance_item ||
                          item.name ||
                          item.requirement ||
                          item.description ||
                          item.text ||
                          item.conditionNumber ||
                          `Compliance Item ${idx + 1}`;

                        return (
                          <tr
                            key={idx}
                            className={
                              idx % 2 === 0 ? "bg-white" : "bg-gray-50"
                            }
                          >
                            {item.isFirstInGroup && (
                              <td
                                className="border border-gray-300 px-3 py-2 font-medium text-xs align-top"
                                rowSpan={item.rowspan}
                              >
                                {item.lawCitation}
                              </td>
                            )}
                            <td className="border border-gray-300 px-3 py-2">
                              {complianceRequirement}
                            </td>
                            <td className="border border-gray-300 px-3 py-2 text-center">
                              <span className="text-black font-medium">
                                {item.compliant === "Yes" && "Yes"}
                                {item.compliant === "No" && "No"}
                                {item.compliant === "N/A" && "N/A"}
                                {!item.compliant && "N/A"}
                              </span>
                            </td>
                            <td className="border border-gray-300 px-3 py-2">
                              {item.compliant === "No" ? (
                                <div className="space-y-1">
                                  {item.remarksOption && (
                                    <div className="text-black">
                                      {item.remarksOption}
                                    </div>
                                  )}
                                  {item.remarks && item.remarks.trim() && (
                                    <div className="text-black text-sm">
                                      <span className="font-medium">
                                        Details:{" "}
                                      </span>
                                      {item.remarks}
                                    </div>
                                  )}
                                  {!item.remarksOption && !item.remarks && (
                                    <span className="text-black">
                                      Non-compliant
                                    </span>
                                  )}
                                </div>
                              ) : item.compliant === "Yes" ? (
                                <span className="text-black">Compliant</span>
                              ) : (
                                <span className="text-black">
                                  Not Applicable
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td
                          colSpan="4"
                          className="border border-gray-300 px-3 py-4 text-center text-gray-500"
                        >
                          No compliance items recorded
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* V. SUMMARY OF FINDINGS AND OBSERVATIONS */}
            <section className="mb-8 page-break-before">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                V. SUMMARY OF FINDINGS AND OBSERVATIONS
              </h2>

              <div className="space-y-4 text-sm">
                {systems &&
                systems.filter((s) => s.compliant || s.nonCompliant).length >
                  0 ? (
                  systems
                    .filter((s) => s.compliant || s.nonCompliant)
                    .map((system, idx) => {
                      const systemNonCompliantItems =
                        formData.complianceItems?.filter(
                          (item) =>
                            item.lawId === system.lawId &&
                            item.compliant === "No"
                        ) || [];
                      const hasNonCompliantItems =
                        systemNonCompliantItems.length > 0;
                      const isNonCompliant =
                        system.nonCompliant || hasNonCompliantItems;
                      const isCompliant =
                        !isNonCompliant &&
                        (system.compliant || system.compliant === "Yes");

                      return (
                        <div
                          key={idx}
                          className="border-l-4 border-gray-300 pl-4"
                        >
                          <div className="flex items-start justify-between">
                            <p className="font-semibold">
                              {idx + 1}. {system.system}
                            </p>
                            <span
                              className={`ml-4 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${
                                isNonCompliant
                                  ? "bg-red-100 text-red-800"
                                  : isCompliant
                                  ? "bg-green-100 text-green-800"
                                  : "bg-gray-100 text-gray-800"
                              }`}
                            >
                              {isNonCompliant
                                ? "❌ Non-Compliant"
                                : isCompliant
                                ? "✅ Compliant"
                                : "N/A"}
                            </span>
                          </div>
                          {isNonCompliant && system.remarks && (
                            <div className="mt-2">
                              <p className="text-gray-700 font-semibold mb-2">
                                Finding:
                              </p>
                              <div className="w-full border border-gray-300 rounded-md px-3 py-2 bg-gray-50 text-gray-900 min-h-[120px] font-mono text-sm whitespace-pre-wrap">
                                {system.remarks}
                              </div>
                            </div>
                          )}
                          {isCompliant && !isNonCompliant && system.remarks && (
                            <div className="mt-2">
                              <p className="text-gray-700 font-semibold mb-2">
                                Observation:
                              </p>
                              <div className="w-full border border-gray-300 rounded-md px-3 py-2 bg-gray-50 text-gray-900 min-h-[120px] font-mono text-sm whitespace-pre-wrap">
                                {system.remarks}
                              </div>
                            </div>
                          )}

                          {/* Display finding images if available */}
                          {formData.findingImages &&
                            formData.findingImages[system.system] &&
                            formData.findingImages[system.system].length >
                              0 && (
                              <div className="mt-3">
                                <p className="text-gray-700 font-semibold mb-2 flex items-center gap-2">
                                  <Camera className="w-4 h-4" />
                                  Photo Documentation:
                                </p>
                                <div className="flex items-center gap-2 flex-wrap">
                                  {formData.findingImages[system.system]
                                    .slice(0, 4)
                                    .map((img, imgIdx) => (
                                      <button
                                        key={img.id || imgIdx}
                                        onClick={() =>
                                          openLightbox(
                                            formData.findingImages[
                                              system.system
                                            ],
                                            imgIdx
                                          )
                                        }
                                        className="w-16 h-16 rounded-md overflow-hidden border border-gray-300 hover:border-sky-500 transition-colors"
                                      >
                                        {img.type === "application/pdf" ? (
                                          <div className="w-full h-full bg-red-50 flex items-center justify-center">
                                            <FileText className="w-6 h-6 text-red-600" />
                                          </div>
                                        ) : (
                                          <img
                                            src={img.url}
                                            alt={
                                              img.caption ||
                                              img.name ||
                                              `Photo ${imgIdx + 1}`
                                            }
                                            className="w-full h-full object-cover"
                                          />
                                        )}
                                      </button>
                                    ))}
                                  {formData.findingImages[system.system]
                                    .length > 4 && (
                                    <div className="w-16 h-16 rounded-md bg-gray-100 flex items-center justify-center text-xs text-gray-600 font-medium border border-gray-300">
                                      +
                                      {formData.findingImages[system.system]
                                        .length - 4}
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                        </div>
                      );
                    })
                ) : (
                  <p className="text-gray-500">No findings recorded</p>
                )}

                {typeof formData.generalFindings === "string" &&
                  formData.generalFindings.trim() && (
                    <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded">
                      <p className="font-semibold mb-2">General Findings:</p>
                      <p className="text-gray-700 whitespace-pre-wrap">
                        {formData.generalFindings}
                      </p>
                    </div>
                  )}
              </div>
            </section>

            {/* VI. RECOMMENDATIONS */}
            {complianceStatus !== "COMPLIANT" &&
              recommendations.checked &&
              recommendations.checked.length > 0 && (
                <section className="mb-8 page-break-before">
                  <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                    VI. RECOMMENDATIONS
                  </h2>

                  <p className="text-sm mb-4">
                    Based on the inspection findings, the following actions are
                    recommended:
                  </p>

                  <div className="space-y-3 text-sm">
                    {recommendations.checked.map((rec, idx) => (
                      <div key={idx} className="flex items-start">
                        <span className="font-semibold mr-2">☑</span>
                        <div className="flex-1">
                          <p className="font-semibold">{rec}</p>
                          <p className="text-gray-600 mt-1">Priority: HIGH</p>
                        </div>
                      </div>
                    ))}

                    {typeof recommendations.otherText === "string" &&
                      recommendations.otherText.trim() && (
                        <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded">
                          <p className="font-semibold mb-2">
                            Additional Recommendations:
                          </p>
                          <p className="text-gray-700 whitespace-pre-wrap">
                            {recommendations.otherText}
                          </p>
                        </div>
                      )}
                  </div>
                </section>
              )}

            {/* VII. VIOLATIONS FOUND */}
            {violationsFound && (
              <section className="mb-8 page-break-before">
                <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                  VII. VIOLATIONS FOUND
                </h2>

                <div className="space-y-4">
                  <p
                    className="text-sm text-gray-700 mb-4"
                    style={{ textAlign: "justify" }}
                  >
                    During the course of the inspection conducted at the
                    establishment, the following violations of environmental
                    laws, rules, and regulations were observed and documented.
                    These violations require immediate attention and corrective
                    action by the establishment management to ensure compliance
                    with applicable environmental standards and requirements.
                  </p>

                  {/* Read-only display */}
                  <div className="border-2 border-gray-300 rounded-md px-4 py-4 bg-gray-50">
                    <div
                      className="text-gray-900 text-sm leading-relaxed"
                      style={{
                        whiteSpace: "pre-wrap",
                        fontFamily: "system-ui, -apple-system, sans-serif",
                      }}
                    >
                      {violationsFound}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* VIII. SIGNATORIES */}
            <section className="mb-8 page-break-before">
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-8">
                VIII. SIGNATORIES
              </h2>

              <div
                className={`grid gap-10 text-sm mt-8 ${
                  signatureConfig.reviewUnit ? "grid-cols-4" : "grid-cols-3"
                }`}
              >
                {/* Submitted by (Inspector) */}
                <div className="flex flex-col items-center">
                  {/* Signature image if available */}
                  {signatureUrls.submitted ? (
                    <div className="relative">
                      <img
                        src={signatureUrls.submitted}
                        alt="Submitted by signature"
                        className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                        onError={(e) => {
                          console.error(
                            "Failed to load submitted signature:",
                            e
                          );
                        }}
                      />
                    </div>
                  ) : (
                    <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                      <span className="text-xs text-gray-400 italic">
                        No signature
                      </span>
                    </div>
                  )}

                  <div className="w-full border-t-2 border-black mt-2" />
                  <p className="mt-2 font-semibold uppercase text-center">
                    Submitted by:
                  </p>
                  <p className="font-bold text-center">
                    {inspectionData?.form?.checklist?.signatures?.submitted
                      ?.name ||
                      inspectionData?.form?.inspector_info?.name ||
                      inspectionData?.inspected_by_name ||
                      "_______________________"}
                  </p>
                  <p className="text-xs text-gray-700 text-center">
                    {signatureConfig.submittedRole}
                  </p>
                  {inspectionData?.form?.checklist?.signatures?.submitted
                    ?.uploaded_at && (
                    <p className="text-xs text-gray-500 text-center mt-1">
                      {new Date(
                        inspectionData.form.checklist.signatures.submitted.uploaded_at
                      ).toLocaleDateString()}
                    </p>
                  )}
                </div>

                {/* Reviewed by – Unit Head (only when Monitoring inspected) */}
                {signatureConfig.reviewUnit && (
                  <div className="flex flex-col items-center">
                    {signatureUrls.review_unit ? (
                      <div className="relative">
                        <img
                          src={signatureUrls.review_unit}
                          alt="Unit Head review signature"
                          className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                          onError={(e) => {
                            console.error(
                              "Failed to load review_unit signature:",
                              e
                            );
                          }}
                        />
                      </div>
                    ) : (
                      <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                        <span className="text-xs text-gray-400 italic">
                          No signature
                        </span>
                      </div>
                    )}

                    <div className="w-full border-t-2 border-black mt-2" />
                    <p className="mt-2 font-semibold uppercase text-center">
                      Reviewed by (Unit Head):
                    </p>
                    <p className="font-bold text-center">
                      {inspectionData?.form?.checklist?.signatures?.review_unit
                        ?.name || "_______________________"}
                    </p>
                    <p className="text-xs text-gray-700 text-center">
                      Unit Head
                    </p>
                    {inspectionData?.form?.checklist?.signatures?.review_unit
                      ?.uploaded_at && (
                      <p className="text-xs text-gray-500 text-center mt-1">
                        {new Date(
                          inspectionData.form.checklist.signatures.review_unit.uploaded_at
                        ).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                )}

                {/* Reviewed by – Section Chief */}
                {signatureConfig.reviewSection && (
                  <div className="flex flex-col items-center">
                    {signatureUrls.review_section ? (
                      <div className="relative">
                        <img
                          src={signatureUrls.review_section}
                          alt="Section Chief review signature"
                          className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                          onError={(e) => {
                            console.error(
                              "Failed to load review_section signature:",
                              e
                            );
                          }}
                        />
                      </div>
                    ) : (
                      <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                        <span className="text-xs text-gray-400 italic">
                          No signature
                        </span>
                      </div>
                    )}

                    <div className="w-full border-t-2 border-black mt-2" />
                    <p className="mt-2 font-semibold uppercase text-center">
                      Reviewed by (Section Chief):
                    </p>
                    <p className="font-bold text-center">
                      {inspectionData?.form?.checklist?.signatures
                        ?.review_section?.name || "_______________________"}
                    </p>
                    <p className="text-xs text-gray-700 text-center">
                      Section Chief
                    </p>
                    {inspectionData?.form?.checklist?.signatures?.review_section
                      ?.uploaded_at && (
                      <p className="text-xs text-gray-500 text-center mt-1">
                        {new Date(
                          inspectionData.form.checklist.signatures.review_section.uploaded_at
                        ).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                )}

                {/* Approved by – Division Chief (always shown) */}
                <div className="flex flex-col items-center">
                  {signatureUrls.approve_division ? (
                    <div className="relative">
                      <img
                        src={signatureUrls.approve_division}
                        alt="Division Chief signature"
                        className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                        onError={(e) => {
                          console.error(
                            "Failed to load approve_division signature:",
                            e
                          );
                        }}
                      />
                    </div>
                  ) : (
                    <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                      <span className="text-xs text-gray-400 italic">
                        No signature
                      </span>
                    </div>
                  )}

                  <div className="w-full border-t-2 border-black mt-2" />
                  <p className="mt-2 font-semibold uppercase text-center">
                    Approved by (Division Chief):
                  </p>
                  <p className="font-bold text-center">
                    {inspectionData?.form?.checklist?.signatures
                      ?.approve_division?.name || "_______________________"}
                  </p>
                  <p className="text-xs text-gray-700 text-center">
                    Division Chief
                  </p>
                  {inspectionData?.form?.checklist?.signatures?.approve_division
                    ?.uploaded_at && (
                    <p className="text-xs text-gray-500 text-center mt-1">
                      {new Date(
                        inspectionData.form.checklist.signatures.approve_division.uploaded_at
                      ).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            </section>

            {/* IX. PHOTO DOCUMENTATION */}
            {formData.generalFindings &&
              Array.isArray(formData.generalFindings) &&
              formData.generalFindings.length > 0 && (
                <section className="mb-8 page-break-before">
                  <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                    IX. PHOTO DOCUMENTATION
                  </h2>

                  <div className="grid grid-cols-3 gap-4">
                    {formData.generalFindings.map((doc, idx) => (
                      <div
                        key={idx}
                        className="border border-gray-300 rounded-lg overflow-hidden bg-gray-50 hover:shadow-md transition-shadow cursor-pointer"
                        onClick={() =>
                          openLightbox(formData.generalFindings, idx)
                        }
                      >
                        {doc.url && doc.url.toLowerCase().endsWith(".pdf") ? (
                          <div className="aspect-square bg-gray-200 flex items-center justify-center">
                            <div className="text-center">
                              <FileText className="w-16 h-16 mx-auto text-red-600" />
                              <p className="text-xs text-gray-600 mt-2">
                                PDF Document
                              </p>
                            </div>
                          </div>
                        ) : doc.url ? (
                          <img
                            src={doc.url}
                            alt={doc.caption || `Photo ${idx + 1}`}
                            className="w-full aspect-square object-cover hover:scale-105 transition-transform"
                          />
                        ) : null}
                        {doc.caption && (
                          <div className="p-3">
                            <p className="text-xs text-gray-700">
                              {doc.caption}
                            </p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {formData.generalFindings.length === 0 && (
                    <p className="text-sm text-gray-500 italic">
                      No photo documentation uploaded
                    </p>
                  )}
                </section>
              )}
          </div>
        </div>

        {/* Image Lightbox */}
        {lightboxOpen && (
          <ImageLightbox
            images={lightboxImages}
            currentIndex={lightboxIndex}
            onClose={() => setLightboxOpen(false)}
            onNavigate={setLightboxIndex}
          />
        )}

        {/* Print Styles */}
        <style>{`
          @media print {
            @page {
              size: A4;
              margin: 20mm;
            }
            
            .page-break-before {
              page-break-before: always;
            }
            
            body {
              print-color-adjust: exact;
              -webkit-print-color-adjust: exact;
            }
          }
        `}</style>
      </LayoutForm>
    </>
  );
};

export default InspectionReportViewPage;
