import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import { useNotifications } from "../hooks/useNotifications";
import api from "../services/api";
import {
  sendNOV,
  sendNOO,
  uploadInspectionSignature,
  deleteInspectionSignature,
} from "../services/api";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowLeft,
  Send,
  FileCheck,
  Printer,
  Edit,
  X,
  UserCheck,
  Users,
  Building,
  CheckSquare,
  Scale,
  Mail,
  FileText,
  CornerDownLeft,
  Camera,
  Upload,
  Trash2,
} from "lucide-react";
import LayoutForm from "../components/LayoutForm";
import {
  getButtonVisibility as getRoleStatusButtonVisibility,
  canUserAccessInspection,
} from "../utils/roleStatusMatrix";
import ImageLightbox from "../components/inspection-form/ImageLightbox";
import NOVModal from "../components/inspections/NOVModal";
import NOOModal from "../components/inspections/NOOModal";

const InspectionReviewPage = () => {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user: currentUser, loading: userLoading } = useAuth();
  const notifications = useNotifications();

  const urlParams = new URLSearchParams(location.search);
  const mode = urlParams.get("mode") || "review";
  const reviewApproval = urlParams.get("reviewApproval") === "true";
  const tabParam = urlParams.get("tab");

  const [inspectionData, setInspectionData] = useState(null);
  const [formData, setFormData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [actionType, setActionType] = useState("");
  const [returnRemarks, setReturnRemarks] = useState("");

  // Image lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  // NOV modal state
  const [showNOVModal, setShowNOVModal] = useState(false);

  // NOO modal state
  const [showNOOModal, setShowNOOModal] = useState(false);

  // Violations found state - automatically populated from non-compliance data
  const [violationsFound, setViolationsFound] = useState("");

  // Signature upload state
  const [uploadingSignature, setUploadingSignature] = useState(false);

  // Function to automatically extract violations from non-compliant items
  const extractViolationsFromData = useCallback((formData) => {
    if (!formData) return "";

    const violations = [];
    const violationsByLaw = {};

    // Extract violations from non-compliant compliance items
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
          violationsByLaw[lawInfo].push(`• ${requirement}: ${item.remarks}`);
        }
      });
    }

    // Extract violations from non-compliant systems
    if (formData.systems) {
      formData.systems.forEach((system) => {
        if (system.nonCompliant && system.remarks) {
          const lawInfo = system.lawId || "General Findings";

          if (!violationsByLaw[lawInfo]) {
            violationsByLaw[lawInfo] = [];
          }
          violationsByLaw[lawInfo].push(
            `• ${system.system}: ${system.remarks}`
          );
        }
      });
    }

    // Format violations by law category with professional structure and numbering
    let violationCounter = 1;
    Object.entries(violationsByLaw).forEach(([law, entries]) => {
      violations.push(`${violationCounter}. ${law}:`);
      entries.forEach((violation, index) => {
        const sanitized = violation.replace(/^•\s*/, "");
        violations.push(`   ${violationCounter}.${index + 1} ${sanitized}`);
      });
      violations.push(""); // Add blank line between categories
      violationCounter += 1;
    });

    return violations.join("\n").trim();
  }, []);

  const formatLegacyViolations = useCallback((rawViolations) => {
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

    const formatted = [];
    let lawCounter = 1;

    grouped.forEach(({ law, items }) => {
      if (!law) return;
      formatted.push(`${lawCounter}. ${law}:`);
      if (items.length > 0) {
        items.forEach((item, index) => {
          formatted.push(`   ${lawCounter}.${index + 1} ${item}`);
        });
      } else {
        formatted.push(`   ${lawCounter}.1 No specific violations recorded`);
      }
      formatted.push("");
      lawCounter += 1;
    });

    return formatted.join("\n").trim();
  }, []);

  // Process compliance items for merged law citations (moved to top level)
  const processedComplianceItems = useMemo(() => {
    if (!formData?.complianceItems || formData.complianceItems.length === 0) {
      return [];
    }

    // Get selected environmental laws from general information (like in inspection form)
    const selectedEnvironmentalLaws =
      formData.general?.environmental_laws || [];

    // Always include PCO Accreditation and SMR items (like in inspection form)
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

    // Filter compliance items to only show those matching selected environmental laws + always included laws
    const filteredComplianceItems = formData.complianceItems.filter((item) => {
      const itemLawId = item.lawId || item.law_id || item.law;
      const itemLawCitation = item.lawCitation || item.law_citation;

      // Check if item matches selected laws OR always included laws OR contains related text
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

    // Group filtered items by law citation
    const groupedByLaw = filteredComplianceItems.reduce((acc, item) => {
      const lawCitation =
        item.lawCitation || item.law_citation || item.lawId || item.law || "-";
      if (!acc[lawCitation]) {
        acc[lawCitation] = [];
      }
      acc[lawCitation].push(item);
      return acc;
    }, {});

    // Flatten back to array with merge information
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

  const fetchInspectionData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get(`inspections/${id}/`, {
        params: tabParam ? { tab: tabParam } : undefined,
      });

      setInspectionData(response.data);

      // Set form data from checklist, or create empty structure if needed
      const checklist = response.data.form?.checklist;
      if (checklist && Object.keys(checklist).length > 0) {
        setFormData(checklist);
      } else {
        console.warn("⚠️ No checklist data, using empty structure");
        // Initialize with empty structure to prevent rendering issues
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
      console.error("❌ Error fetching inspection:", error);
      if (error.response?.status === 404) {
        notifications.error("Inspection not found or no longer available.");
        navigate(-1);
      } else {
        notifications.error(`Failed to load inspection data: ${error.message}`);
      }
    } finally {
      setLoading(false);
    }
  }, [id, tabParam]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset state when ID changes
  useEffect(() => {
    setInspectionData(null);
    setFormData(null);
  }, [id]);

  // Load data based on mode
  useEffect(() => {
    if (mode === "preview") {
      if (location.state?.inspectionData && location.state?.formData) {
        setFormData(location.state.formData);
        setInspectionData(location.state.inspectionData);
      } else {
        fetchInspectionData();
      }
    } else {
      // Review mode: fetch from API
      fetchInspectionData();
    }
  }, [mode, fetchInspectionData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-populate violations when form data changes
  useEffect(() => {
    if (formData) {
      // First check if there are existing violations from the database
      const existingViolations = inspectionData?.form?.violations_found;

      if (existingViolations) {
        // Use existing violations from database
        const needsFormatting =
          existingViolations.includes("•") || existingViolations.includes(",");
        const formattedViolations = needsFormatting
          ? formatLegacyViolations(existingViolations)
          : existingViolations;
        setViolationsFound(formattedViolations);
      } else {
        // Auto-generate violations from non-compliant items
        const autoViolations = extractViolationsFromData(formData);
        setViolationsFound(autoViolations);
      }
    }
  }, [
    formData,
    inspectionData,
    extractViolationsFromData,
    formatLegacyViolations,
  ]);

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

  const getComplianceStatus = () => {
    if (mode === "preview" && location.state?.compliance) {
      return location.state.compliance;
    }

    // Check form.compliance_decision if it exists in review mode (highest priority)
    if (mode === "review" && inspectionData?.form?.compliance_decision) {
      return inspectionData.form.compliance_decision;
    }

    // Fallback: extract from inspection status
    if (mode === "review" && inspectionData?.current_status) {
      const status = inspectionData.current_status;
      if (status.includes("_COMPLIANT")) {
        return "COMPLIANT";
      } else if (status.includes("_NON_COMPLIANT")) {
        return "NON_COMPLIANT";
      }
    }

    return formData?.compliance_status || "PENDING";
  };

  // Get signature slot for current user based on inspector level and user level
  const getSignatureSlotForUser = useCallback(() => {
    if (!inspectionData || !currentUser) return null;

    // Preview mode: Always upload to 'submitted' slot if in IN_PROGRESS status
    if (mode === "preview") {
      const status = inspectionData?.current_status || "";
      if (status.endsWith("_IN_PROGRESS")) {
        return "submitted";
      }
      return null;
    }

    // Review mode logic
    const inspectorLevel = inspectionData.form?.inspector_info?.level || "";
    const userLevel = currentUser?.userlevel || "";
    const inspectedById = inspectionData.form?.inspected_by;

    // Allow original inspector to upload 'submitted' signature if missing
    if (inspectedById === currentUser.id) {
      return "submitted";
    }

    // Rest of review mode logic for other reviewers
    // Monitoring inspected
    if (inspectorLevel === "Monitoring Personnel") {
      if (userLevel === "Unit Head") return "review_unit";
      if (userLevel === "Section Chief") return "review_section";
      if (userLevel === "Division Chief") return "approve_division";
    }

    // Unit Head inspected
    if (inspectorLevel === "Unit Head") {
      if (userLevel === "Section Chief") return "review_section";
      if (userLevel === "Division Chief") return "approve_division";
    }

    // Section Chief inspected
    if (inspectorLevel === "Section Chief") {
      if (userLevel === "Division Chief") return "approve_division";
    }

    return null;
  }, [inspectionData, currentUser, mode]);

  const signatureSlot = getSignatureSlotForUser();

  // Memoize signature URLs to prevent re-renders on every keystroke
  const signatureUrls = useMemo(() => {
    const signatures = inspectionData?.form?.checklist?.signatures || {};
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
  }, [inspectionData?.form?.checklist?.signatures]);

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

  // Handle signature upload
  const handleSignatureUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !signatureSlot) return;

    // Validate file size (2MB max)
    if (file.size > 2 * 1024 * 1024) {
      notifications.error("File size must not exceed 2MB");
      event.target.value = "";
      return;
    }

    // Validate file type
    const validTypes = ["image/png", "image/jpeg", "image/jpg"];
    if (!validTypes.includes(file.type)) {
      notifications.error("Only PNG and JPEG images are allowed");
      event.target.value = "";
      return;
    }

    try {
      setUploadingSignature(true);
      const formDataUpload = new FormData();
      formDataUpload.append("file", file);
      formDataUpload.append("slot", signatureSlot);

      await uploadInspectionSignature(id, formDataUpload);

      notifications.success("Signature uploaded successfully.");
      // Refresh inspection data so the image shows up
      await fetchInspectionData();
    } catch (error) {
      console.error("Error uploading signature:", error);
      notifications.error(
        error.response?.data?.detail ||
          error.response?.data?.error ||
          error.message ||
          "Failed to upload signature."
      );
    } finally {
      setUploadingSignature(false);
      // Reset input so same file can be selected again if needed
      event.target.value = "";
    }
  };

  // Handle signature delete
  const handleSignatureDelete = async (slot) => {
    if (!window.confirm("Are you sure you want to delete this signature?")) {
      return;
    }

    try {
      await deleteInspectionSignature(id, slot);
      notifications.success("Signature deleted successfully.");
      await fetchInspectionData();
    } catch (error) {
      console.error("Error deleting signature:", error);
      notifications.error(
        error.response?.data?.detail ||
          error.response?.data?.error ||
          error.message ||
          "Failed to delete signature."
      );
    }
  };

  // Function to open lightbox with images
  const openLightbox = (images, index = 0) => {
    setLightboxImages(images);
    setLightboxIndex(index);
    setLightboxOpen(true);
  };

  // Removed unused functions - navigation is handled directly in buttons

  const handleReviewAction = async () => {
    const endpoints = {
      approve_unit: `inspections/${id}/review_and_forward_unit/`,
      approve_section: `inspections/${id}/review_and_forward_section/`,
      review_division: `inspections/${id}/review_division/`,
      approve_division: `inspections/${id}/close/`,
      forward_legal: `inspections/${id}/forward_to_legal/`,
      send_nov: `inspections/${id}/send_nov/`,
      send_noo: `inspections/${id}/send_noo/`,
      return_to_monitoring: `inspections/${id}/return_to_monitoring/`,
      return_to_unit: `inspections/${id}/return_to_unit/`,
      return_to_section: `inspections/${id}/return_to_section/`,
      return_to_division: `inspections/${id}/return_to_division/`,
      mark_compliant: `inspections/${id}/close/`,
      mark_non_compliant: `inspections/${id}/close/`,
      save_and_submit: `inspections/${id}/complete/`,
      save_and_approve: `inspections/${id}/complete/`,
    };

    let endpoint = endpoints[actionType];
    if (!endpoint) {
      notifications.error("Invalid action type");
      return;
    }

    // Prepare payload based on action type
    let payload = {};
    if (actionType.startsWith("return_")) {
      if (!returnRemarks.trim()) {
        notifications.error(
          "Please provide remarks before returning the inspection."
        );
        return;
      }
      payload = { remarks: returnRemarks.trim() };
    } else if (actionType === "mark_compliant") {
      payload = {
        final_status: "CLOSED_COMPLIANT",
        remarks: "Marked as compliant by Legal Unit",
      };
    } else if (actionType === "mark_non_compliant") {
      payload = {
        final_status: "CLOSED_NON_COMPLIANT",
        remarks: "Marked as non-compliant by Legal Unit",
      };
    } else if (actionType === "forward_legal") {
      payload = { remarks: "Forwarded to Legal Unit for enforcement" };
    } else if (actionType === "approve_unit") {
      payload = {
        remarks: "Unit Head approved and forwarded to Section Chief",
      };
    } else if (actionType === "approve_section") {
      payload = {
        remarks: "Section Chief approved and forwarded to Division Chief",
      };
    } else if (actionType === "review_division") {
      payload = {
        remarks: "Division Chief reviewed and marked as DIVISION_REVIEWED",
      };
    } else if (actionType === "save_and_submit") {
      // Complete inspection from preview
      const userLevel = currentUser?.userlevel;
      const complianceDecision = getComplianceStatus();

      payload = {
        form_data: formData,
        compliance_decision: complianceDecision,
        violations_found: violationsFound
          ? violationsFound.split("\n").filter((line) => line.trim())
          : ["None"],
        findings_summary: "Inspection completed",
        remarks: `Inspection completed by ${userLevel}`,
      };
    } else if (actionType === "save_and_approve") {
      // Complete inspection and approve from preview (after edit from review)
      // Role-specific approval based on current user
      const userLevel = currentUser?.userlevel;
      const complianceDecision = getComplianceStatus();

      if (userLevel === "Unit Head") {
        // Unit Head approving - use review_and_forward_unit endpoint
        endpoint = `inspections/${id}/review_and_forward_unit/`;
        payload = {
          form_data: formData,
          compliance_decision: complianceDecision,
          remarks: "Unit Head approved and forwarded to Section Chief",
        };
      } else if (userLevel === "Section Chief") {
        // Section Chief approving - use review_and_forward_section endpoint
        endpoint = `inspections/${id}/review_and_forward_section/`;
        payload = {
          form_data: formData,
          compliance_decision: complianceDecision,
          remarks: "Section Chief approved and forwarded to Division Chief",
        };
      } else if (userLevel === "Division Chief") {
        // Division Chief approving - use close endpoint
        endpoint = `inspections/${id}/close/`;
        payload = {
          form_data: formData,
          compliance_decision: complianceDecision,
          final_status:
            complianceDecision === "COMPLIANT"
              ? "CLOSED_COMPLIANT"
              : "LEGAL_REVIEW",
          remarks: "Division Chief approved and closed",
        };
      } else {
        // Fallback to complete endpoint
        payload = {
          form_data: formData,
          compliance_decision: complianceDecision,
          violations_found: violationsFound
            ? violationsFound.split("\n").filter((line) => line.trim())
            : ["None"],
          findings_summary: "Inspection completed and approved",
          remarks: "Inspection completed and approved by reviewer",
        };
      }
    }

    try {
      setLoading(true);

      // Show loading notification for long operations
      if (
        [
          "save_and_submit",
          "save_and_approve",
          "mark_compliant",
          "mark_non_compliant",
        ].includes(actionType)
      ) {
        notifications.info("Processing your request...", {
          title: "Please Wait",
          duration: 2000,
        });
      }

      await api.post(endpoint, payload);
      setShowConfirm(false);

      // Add success notifications based on action type
      let successMessage = "";
      let successTitle = "";

      switch (actionType) {
        case "save_and_submit":
          successMessage = "Inspection completed and submitted successfully!";
          successTitle = "Inspection Submitted";
          break;
        case "save_and_approve":
          successMessage = "Inspection completed and approved successfully!";
          successTitle = "Inspection Approved";
          break;
        case "mark_compliant":
          successMessage =
            "Inspection marked as compliant and closed successfully!";
          successTitle = "Marked as Compliant";
          break;
        case "mark_non_compliant":
          successMessage =
            "Inspection marked as non-compliant and closed successfully!";
          successTitle = "Marked as Non-Compliant";
          break;
        case "approve_unit":
          successMessage =
            "Inspection approved by Unit Head and forwarded to Section Chief!";
          successTitle = "Unit Head Approved";
          break;
        case "approve_section":
          successMessage =
            "Inspection approved by Section Chief and forwarded to Division Chief!";
          successTitle = "Section Chief Approved";
          break;
        case "review_division":
          successMessage =
            "Inspection reviewed by Division Chief successfully!";
          successTitle = "Division Chief Reviewed";
          break;
        case "forward_legal":
          successMessage =
            "Inspection forwarded to Legal Unit for enforcement!";
          successTitle = "Forwarded to Legal";
          break;
        case "return_to_monitoring":
          successMessage = "Inspection returned to Monitoring with remarks.";
          successTitle = "Returned to Monitoring";
          break;
        case "return_to_unit":
          successMessage = "Inspection returned to Unit Head with remarks.";
          successTitle = "Returned to Unit";
          break;
        case "return_to_section":
          successMessage = "Inspection returned to Section Chief with remarks.";
          successTitle = "Returned to Section";
          break;
        case "return_to_division":
          successMessage =
            "Inspection returned to Division Chief with remarks.";
          successTitle = "Returned to Division";
          break;
        default:
          successMessage = "Action completed successfully!";
          successTitle = "Action Complete";
      }

      notifications.success(successMessage, {
        title: successTitle,
        duration: 5000,
      });
      setReturnRemarks("");
      navigate("/inspections");
    } catch (error) {
      console.error("❌ Error executing review action:", error);
      console.error("❌ Error response:", error.response?.data);
      notifications.error(
        error.response?.data?.error ||
          error.response?.data?.message ||
          "Action failed"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleActionClick = (type) => {
    if (type === "send_nov") {
      setShowNOVModal(true);
    } else if (type === "send_noo") {
      setShowNOOModal(true);
    } else {
      setActionType(type);
      if (type.startsWith("return_")) {
        setReturnRemarks("");
      }
      setShowConfirm(true);
    }
  };

  const handleNOVConfirm = async (novData) => {
    try {
      setLoading(true);
      await sendNOV(id, {
        recipient_email: novData.recipientEmail,
        recipient_name: novData.recipientName,
        contact_person: novData.contactPerson,
        email_subject: novData.emailSubject,
        email_body: novData.emailBody,
        violations: novData.violations,
        compliance_instructions: novData.complianceInstructions,
        compliance_deadline: new Date(novData.complianceDeadline).toISOString(),
        remarks: novData.remarks || "Notice of Violation sent",
      });

      notifications.success("Notice of Violation sent successfully!");
      setShowNOVModal(false);
      navigate("/inspections");
    } catch (error) {
      console.error("Error sending NOV:", error);
      notifications.error(
        error.response?.data?.error ||
          error.response?.data?.message ||
          "Failed to send NOV"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleNOOConfirm = async (nooData) => {
    try {
      setLoading(true);

      // Validate and format payment_deadline
      let paymentDeadline = null;
      if (nooData.paymentDeadline) {
        try {
          // If it's already a date string (YYYY-MM-DD), use it directly
          if (
            typeof nooData.paymentDeadline === "string" &&
            /^\d{4}-\d{2}-\d{2}$/.test(nooData.paymentDeadline)
          ) {
            paymentDeadline = nooData.paymentDeadline;
          } else {
            // Otherwise, try to parse it
            const date = new Date(nooData.paymentDeadline);
            if (isNaN(date.getTime())) {
              throw new Error("Invalid payment deadline date");
            }
            paymentDeadline = date.toISOString().split("T")[0];
          }
        } catch (error) {
          notifications.error(`Invalid payment deadline: ${error.message}`);
          setLoading(false);
          return;
        }
      }

      console.log("Sending NOO with data:", {
        ...nooData,
        payment_deadline: paymentDeadline,
      });

      await sendNOO(id, {
        recipient_email: nooData.recipientEmail,
        recipient_name: nooData.recipientName,
        contact_person: nooData.contactPerson,
        email_subject: nooData.emailSubject,
        email_body: nooData.emailBody,
        violation_breakdown: nooData.violationBreakdown,
        penalty_fees: nooData.penaltyFees,
        payment_deadline: paymentDeadline,
        payment_instructions: nooData.paymentInstructions,
        remarks: nooData.remarks || "Notice of Order sent",
        billing_items: nooData.billingItems || [],
      });

      notifications.success("Notice of Order sent successfully!");
      setShowNOOModal(false);
      navigate("/inspections?tab=noo_sent");
    } catch (error) {
      console.error("Error sending NOO:", error);
      console.error("Error details:", error.response?.data);
      const errorMessage =
        error.response?.data?.error ||
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to send Notice of Order. Please check the server logs for details.";
      notifications.error(errorMessage, {
        title: "NOO Send Failed",
        duration: 6000,
      });
    } finally {
      setLoading(false);
    }
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
  const general = formData.general || {};
  const purpose = formData.purpose || {};
  const permits = formData.permits || [];
  const complianceItems = formData.complianceItems || [];
  const systems = formData.systems || [];
  const recommendations = formData.recommendationState || {};

  // Get button visibility using unified role-status matrix
  const getButtonVisibility = () => {
    const userLevel = currentUser?.userlevel;
    const status = inspectionData?.current_status;
    const isPreviewMode = mode === "preview";

    if (!status || !userLevel) {
      return {
        showCloseButton: false,
        showBackButton: isPreviewMode,
        showSaveSubmitButton: false,
      };
    }

    const roleStatusConfig =
      getRoleStatusButtonVisibility(
        userLevel,
        status,
        isPreviewMode,
        null,
        reviewApproval
      ) || {};

    const isInProgressStatus =
      typeof status === "string" && status.endsWith("_IN_PROGRESS");

    if (!isPreviewMode) {
      const canAccess = canUserAccessInspection(userLevel, status);
      if (!canAccess) {
        console.warn(
          `🚫 User ${userLevel} cannot access inspection with status ${status}`
        );
        return {
          showCloseButton: false,
          showBackButton: false,
          showSaveSubmitButton: false,
        };
      }
    }

    const baseShowSaveSubmit =
      !isPreviewMode ||
      reviewApproval ||
      (isPreviewMode && roleStatusConfig.showBack);

    return {
      showCloseButton: isPreviewMode ? false : roleStatusConfig.showClose,
      showBackButton: isPreviewMode
        ? reviewApproval
          ? true
          : roleStatusConfig.showBack
        : roleStatusConfig.showBack,
      showSaveSubmitButton: isPreviewMode
        ? reviewApproval || (isInProgressStatus && roleStatusConfig.showBack)
        : baseShowSaveSubmit, // Maintain existing behaviour for review mode
    };
  };

  const buttonVisibility = getButtonVisibility();

  // Custom header for review page
  const reviewHeader = (
    <div className="bg-white border-b border-gray-300 shadow-sm print:hidden">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Left: Title */}
        <div className="flex items-center gap-4">
          <div className="text-xl font-bold text-sky-700">
            {mode === "preview"
              ? "Integrated Compliance Inspection Report - Preview"
              : "Integrated Compliance Inspection Report - Review"}
          </div>
        </div>

        {/* Right: Action Buttons */}
        <div className="flex items-center gap-2">
          {mode === "preview" ? (
            <>
              <button
                onClick={() => navigate(-1)}
                className="flex items-center px-3 py-1 text-sm text-black bg-gray-200 rounded hover:bg-gray-300 transition-colors"
              >
                <ArrowLeft className="w-4 h-4 mr-1" />
                Back
              </button>
              {buttonVisibility.showSaveSubmitButton && (
                <button
                  onClick={() => {
                    // Check if signature is required and missing
                    if (
                      mode === "preview" &&
                      signatureSlot === "submitted" &&
                      !inspectionData.form?.checklist?.signatures?.submitted
                        ?.url
                    ) {
                      notifications.error(
                        "Please upload your signature before submitting."
                      );
                      // Scroll to signatories section
                      document
                        .querySelector("#signatories-section")
                        ?.scrollIntoView({ behavior: "smooth" });
                      return;
                    }
                    handleActionClick("save_and_submit");
                  }}
                  className="flex items-center px-3 py-1 text-sm text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
                  disabled={loading}
                >
                  <Send className="w-4 h-4 mr-1" />
                  Submit
                </button>
              )}
            </>
          ) : mode === "review" ? (
            <>
              {/* Review Mode: Show Edit Inspection and Approve buttons */}
              <button
                onClick={() => navigate("/inspections")}
                className="flex items-center px-3 py-1 text-sm text-black bg-gray-200 rounded hover:bg-gray-300 transition-colors"
              >
                <X className="w-4 h-4 mr-1" />
                Close
              </button>
              {/* Hide Edit Inspection button for Division Chief and Legal Unit with LEGAL_REVIEW, NOV_SENT, or NOO_SENT status */}
              {currentUser?.userlevel !== "Division Chief" &&
                !(
                  currentUser?.userlevel === "Legal Unit" &&
                  (inspectionData?.current_status === "LEGAL_REVIEW" ||
                    inspectionData?.current_status === "NOV_SENT" ||
                    inspectionData?.current_status === "NOO_SENT")
                ) && (
                  <button
                    onClick={() =>
                      navigate(
                        `/inspections/${id}/form?returnTo=review&reviewMode=true`
                      )
                    }
                    className="flex items-center px-3 py-1 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                  >
                    <Edit className="w-4 h-4 mr-1" />
                    Edit Inspection
                  </button>
                )}
              {/* Show Approve button based on user role and status */}
              {!userLoading &&
                currentUser?.userlevel === "Unit Head" &&
                (inspectionData?.current_status ===
                  "MONITORING_COMPLETED_COMPLIANT" ||
                  inspectionData?.current_status ===
                    "MONITORING_COMPLETED_NON_COMPLIANT") && (
                  <>
                    <button
                      onClick={() => {
                        // Check if signature is required and missing
                        if (
                          signatureSlot === "review_unit" &&
                          !inspectionData.form?.checklist?.signatures
                            ?.review_unit?.url
                        ) {
                          notifications.error(
                            "Please upload your signature before approving."
                          );
                          document
                            .querySelector("#signatories-section")
                            ?.scrollIntoView({ behavior: "smooth" });
                          return;
                        }
                        handleActionClick("approve_unit");
                      }}
                      className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                      disabled={loading}
                    >
                      <UserCheck className="w-4 h-4 mr-1" />
                      Approve
                    </button>
                    <button
                      onClick={() => handleActionClick("return_to_monitoring")}
                      className="flex items-center px-3 py-1 text-sm text-white bg-gray-500 rounded hover:bg-gray-600 transition-colors"
                      disabled={loading}
                    >
                      <CornerDownLeft className="w-4 h-4 mr-1" />
                      Return
                    </button>
                  </>
                )}
              {!userLoading &&
                currentUser?.userlevel === "Section Chief" &&
                (inspectionData?.current_status ===
                  "UNIT_COMPLETED_COMPLIANT" ||
                  inspectionData?.current_status ===
                    "UNIT_COMPLETED_NON_COMPLIANT" ||
                  inspectionData?.current_status === "UNIT_REVIEWED" ||
                  inspectionData?.current_status ===
                    "MONITORING_COMPLETED_COMPLIANT" ||
                  inspectionData?.current_status ===
                    "MONITORING_COMPLETED_NON_COMPLIANT") && (
                  <>
                    <button
                      onClick={() => {
                        // Check if signature is required and missing
                        if (
                          signatureSlot === "review_section" &&
                          !inspectionData.form?.checklist?.signatures
                            ?.review_section?.url
                        ) {
                          notifications.error(
                            "Please upload your signature before approving."
                          );
                          document
                            .querySelector("#signatories-section")
                            ?.scrollIntoView({ behavior: "smooth" });
                          return;
                        }
                        handleActionClick("approve_section");
                      }}
                      className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                      disabled={loading}
                    >
                      <Users className="w-4 h-4 mr-1" />
                      Approve
                    </button>
                    {(inspectionData?.current_status ===
                      "UNIT_COMPLETED_COMPLIANT" ||
                      inspectionData?.current_status ===
                        "UNIT_COMPLETED_NON_COMPLIANT" ||
                      inspectionData?.current_status === "UNIT_REVIEWED") && (
                      <button
                        onClick={() => handleActionClick("return_to_unit")}
                        className="flex items-center px-3 py-1 text-sm text-white bg-gray-500 rounded hover:bg-gray-600 transition-colors"
                        disabled={loading}
                      >
                        <CornerDownLeft className="w-4 h-4 mr-1" />
                        Return
                      </button>
                    )}
                  </>
                )}
              {!userLoading &&
                currentUser?.userlevel === "Division Chief" &&
                (inspectionData?.current_status ===
                  "SECTION_COMPLETED_COMPLIANT" ||
                  inspectionData?.current_status ===
                    "SECTION_COMPLETED_NON_COMPLIANT" ||
                  inspectionData?.current_status === "SECTION_REVIEWED" ||
                  inspectionData?.current_status === "DIVISION_REVIEWED") && (
                  <>
                    {/* For SECTION_REVIEWED status - Division Chief can review */}
                    {inspectionData?.current_status === "SECTION_REVIEWED" && (
                      <>
                        {/* Show "Reviewed" button to transition to DIVISION_REVIEWED */}
                        <button
                          onClick={() => {
                            // Check if signature is required and missing
                            if (
                              signatureSlot === "approve_division" &&
                              !inspectionData.form?.checklist?.signatures
                                ?.approve_division?.url
                            ) {
                              notifications.error(
                                "Please upload your signature before reviewing."
                              );
                              document
                                .querySelector("#signatories-section")
                                ?.scrollIntoView({ behavior: "smooth" });
                              return;
                            }
                            handleActionClick("review_division");
                          }}
                          className="flex items-center px-3 py-1 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                          disabled={loading}
                        >
                          <CheckCircle className="w-4 h-4 mr-1" />
                          Reviewed
                        </button>
                      </>
                    )}

                    {/* For SECTION_COMPLETED_* statuses - show Reviewed button */}
                    {(inspectionData?.current_status ===
                      "SECTION_COMPLETED_COMPLIANT" ||
                      inspectionData?.current_status ===
                        "SECTION_COMPLETED_NON_COMPLIANT") && (
                      <>
                        {/* Show "Reviewed" button to transition to DIVISION_REVIEWED */}
                        <button
                          onClick={() => {
                            // Check if signature is required and missing
                            if (
                              signatureSlot === "approve_division" &&
                              !inspectionData.form?.checklist?.signatures
                                ?.approve_division?.url
                            ) {
                              notifications.error(
                                "Please upload your signature before reviewing."
                              );
                              document
                                .querySelector("#signatories-section")
                                ?.scrollIntoView({ behavior: "smooth" });
                              return;
                            }
                            handleActionClick("review_division");
                          }}
                          className="flex items-center px-3 py-1 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                          disabled={loading}
                        >
                          <CheckCircle className="w-4 h-4 mr-1" />
                          Reviewed
                        </button>
                      </>
                    )}

                    {/* For DIVISION_REVIEWED status - only show compliance action */}
                    {inspectionData?.current_status === "DIVISION_REVIEWED" && (
                      <>
                        {complianceStatus === "COMPLIANT" ? (
                          <button
                            onClick={() => {
                              // Check if signature is required and missing
                              if (
                                signatureSlot === "approve_division" &&
                                !inspectionData.form?.checklist?.signatures
                                  ?.approve_division?.url
                              ) {
                                notifications.error(
                                  "Please upload your signature before marking as compliant."
                                );
                                document
                                  .querySelector("#signatories-section")
                                  ?.scrollIntoView({ behavior: "smooth" });
                                return;
                              }
                              handleActionClick("mark_compliant");
                            }}
                            className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                            disabled={loading}
                          >
                            <CheckSquare className="w-4 h-4 mr-1" />
                            Mark as Compliant
                          </button>
                        ) : (
                          <button
                            onClick={() => {
                              // Check if signature is required and missing
                              if (
                                signatureSlot === "approve_division" &&
                                !inspectionData.form?.checklist?.signatures
                                  ?.approve_division?.url
                              ) {
                                notifications.error(
                                  "Please upload your signature before sending to legal."
                                );
                                document
                                  .querySelector("#signatories-section")
                                  ?.scrollIntoView({ behavior: "smooth" });
                                return;
                              }
                              handleActionClick("forward_legal");
                            }}
                            className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                            disabled={loading}
                          >
                            <Scale className="w-4 h-4 mr-1" />
                            Send to Legal
                          </button>
                        )}
                      </>
                    )}

                    {(inspectionData?.current_status ===
                      "SECTION_COMPLETED_COMPLIANT" ||
                      inspectionData?.current_status ===
                        "SECTION_COMPLETED_NON_COMPLIANT" ||
                      inspectionData?.current_status ===
                        "SECTION_REVIEWED") && (
                      <button
                        onClick={() => handleActionClick("return_to_section")}
                        className="flex items-center px-3 py-1 text-sm text-white bg-gray-500 rounded hover:bg-gray-600 transition-colors"
                        disabled={loading}
                      >
                        <CornerDownLeft className="w-4 h-4 mr-1" />
                        Return
                      </button>
                    )}
                  </>
                )}
              {/* Legal Unit buttons for LEGAL_REVIEW status */}
              {!userLoading &&
                currentUser?.userlevel === "Legal Unit" &&
                inspectionData?.current_status === "LEGAL_REVIEW" && (
                  <>
                    <button
                      onClick={() => handleActionClick("send_nov")}
                      className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                      disabled={loading}
                    >
                      <Mail className="w-4 h-4 mr-1" />
                      Send NOV
                    </button>
                  </>
                )}

              {/* Legal Unit buttons for NOV_SENT status */}
              {!userLoading &&
                currentUser?.userlevel === "Legal Unit" &&
                inspectionData?.current_status === "NOV_SENT" && (
                  <>
                    <button
                      onClick={() => handleActionClick("mark_compliant")}
                      className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                      disabled={loading}
                    >
                      <CheckSquare className="w-4 h-4 mr-1" />
                      Mark as Compliant
                    </button>
                    <button
                      onClick={() => handleActionClick("send_noo")}
                      className="flex items-center px-3 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                      disabled={loading}
                    >
                      <FileText className="w-4 h-4 mr-1" />
                      Send NOO
                    </button>
                  </>
                )}

              {/* Legal Unit buttons for NOO_SENT status */}
              {!userLoading &&
                currentUser?.userlevel === "Legal Unit" &&
                inspectionData?.current_status === "NOO_SENT" && (
                  <>
                    <button
                      onClick={() => handleActionClick("mark_non_compliant")}
                      className="flex items-center px-3 py-1 text-sm text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
                      disabled={loading}
                    >
                      <XCircle className="w-4 h-4 mr-1" />
                      Mark as Non-Compliant
                    </button>
                  </>
                )}
            </>
          ) : null}
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
      <LayoutForm headerHeight="small" inspectionHeader={reviewHeader}>
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
                        // Get the compliance requirement text - this should show the actual requirement
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
                            {/* Only render law citation cell for first item in group */}
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
                          {formData && (
                            <div className="text-xs mt-2">
                              Debug: formData.complianceItems ={" "}
                              {JSON.stringify(formData.complianceItems)}
                            </div>
                          )}
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
                      // Check for non-compliant items within this system's scope
                      const systemNonCompliantItems = complianceItems.filter(
                        (item) =>
                          item.lawId === system.lawId && item.compliant === "No"
                      );
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

                  {/* Editable violations textarea for preview mode or authorized users */}
                  {mode === "preview" ||
                  buttonVisibility.showSaveSubmitButton ? (
                    <div className="space-y-2">
                      <label className="block text-sm font-semibold text-gray-800 mb-2">
                        Documented Violations:
                      </label>
                      <textarea
                        value={violationsFound}
                        onChange={(e) => setViolationsFound(e.target.value)}
                        className="w-full border-2 border-gray-400 rounded-md px-4 py-3 text-gray-900 min-h-[300px] font-sans text-sm leading-relaxed resize-y focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                        placeholder="Violations will be automatically populated from non-compliant items..."
                        style={{
                          whiteSpace: "pre-wrap",
                          fontFamily: "system-ui, -apple-system, sans-serif",
                        }}
                      />
                      <p className="text-xs text-gray-600 italic bg-blue-50 border-l-4 border-blue-400 px-3 py-2 rounded">
                        <strong>Note:</strong> This field is automatically
                        populated from non-compliant items identified during the
                        inspection. You may edit or add additional details as
                        necessary to provide a comprehensive record of
                        violations.
                      </p>
                    </div>
                  ) : (
                    /* Read-only display for review mode with professional formatting */
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
                  )}
                </div>
              </section>
            )}

            {/* VIII. PHOTO DOCUMENTATION */}
            {formData.generalFindings &&
              Array.isArray(formData.generalFindings) &&
              formData.generalFindings.length > 0 && (
                <section className="mb-8 page-break-before">
                  <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-4">
                    VIII. PHOTO DOCUMENTATION
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

            {/* IX. SIGNATORIES */}
            <section
              className="mt-12 mb-8 page-break-before"
              id="signatories-section"
            >
              <h2 className="text-lg font-bold uppercase border-b-2 border-gray-800 pb-2 mb-8">
                IX. SIGNATORIES
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
                    <div className="relative group">
                      <img
                        src={signatureUrls.submitted}
                        alt="Submitted by signature"
                        className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                        onError={(e) => {
                          console.error(
                            "❌ Failed to load submitted signature:",
                            e
                          );
                          console.log("Image URL:", signatureUrls.submitted);
                        }}
                      />
                      {/* Delete button for own signature */}
                      {signatureSlot === "submitted" && (
                        <button
                          onClick={() => handleSignatureDelete("submitted")}
                          className="absolute top-0 right-0 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity print:hidden"
                          title="Delete signature"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                      {signatureSlot === "submitted" ? (
                        <label className="cursor-pointer text-center">
                          <Upload className="w-6 h-6 mx-auto text-sky-600 mb-1" />
                          <span className="text-xs text-sky-600 font-medium">
                            {uploadingSignature
                              ? "Uploading..."
                              : "Upload Signature"}
                          </span>
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/jpg"
                            className="hidden"
                            onChange={handleSignatureUpload}
                            disabled={uploadingSignature}
                          />
                        </label>
                      ) : (
                        <span className="text-xs text-gray-400 italic">
                          Pending signature
                        </span>
                      )}
                    </div>
                  )}

                  <div className="w-full border-t-2 border-black mt-2" />
                  <p className="mt-2 font-semibold uppercase text-center">
                    Submitted by:
                  </p>
                  <p className="font-bold text-center">
                    {inspectionData.form?.inspector_info?.name ||
                      inspectionData.inspected_by_name ||
                      "_______________________"}
                  </p>
                  <p className="text-xs text-gray-700 text-center">
                    {signatureConfig.submittedRole}
                  </p>
                  {inspectionData.form?.checklist?.signatures?.submitted
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
                      <div className="relative group">
                        <img
                          src={signatureUrls.review_unit}
                          alt="Unit Head review signature"
                          className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                          onError={(e) => {
                            console.error(
                              "❌ Failed to load review_unit signature:",
                              e
                            );
                            console.log(
                              "Image URL:",
                              signatureUrls.review_unit
                            );
                          }}
                        />
                        {signatureSlot === "review_unit" && (
                          <button
                            onClick={() => handleSignatureDelete("review_unit")}
                            className="absolute top-0 right-0 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity print:hidden"
                            title="Delete signature"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                        {signatureSlot === "review_unit" ? (
                          <label className="cursor-pointer text-center">
                            <Upload className="w-6 h-6 mx-auto text-sky-600 mb-1" />
                            <span className="text-xs text-sky-600 font-medium">
                              {uploadingSignature
                                ? "Uploading..."
                                : "Upload Signature"}
                            </span>
                            <input
                              type="file"
                              accept="image/png,image/jpeg,image/jpg"
                              className="hidden"
                              onChange={handleSignatureUpload}
                              disabled={uploadingSignature}
                            />
                          </label>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            Pending signature
                          </span>
                        )}
                      </div>
                    )}

                    <div className="w-full border-t-2 border-black mt-2" />
                    <p className="mt-2 font-semibold uppercase text-center">
                      Reviewed by (Unit Head):
                    </p>
                    <p className="font-bold text-center">
                      {inspectionData.form?.checklist?.signatures?.review_unit
                        ?.name || "_______________________"}
                    </p>
                    <p className="text-xs text-gray-700 text-center">
                      Unit Head
                    </p>
                    {inspectionData.form?.checklist?.signatures?.review_unit
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
                      <div className="relative group">
                        <img
                          src={signatureUrls.review_section}
                          alt="Section Chief review signature"
                          className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                          onError={(e) => {
                            console.error(
                              "❌ Failed to load review_section signature:",
                              e
                            );
                            console.log(
                              "Image URL:",
                              signatureUrls.review_section
                            );
                          }}
                        />
                        {signatureSlot === "review_section" && (
                          <button
                            onClick={() =>
                              handleSignatureDelete("review_section")
                            }
                            className="absolute top-0 right-0 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity print:hidden"
                            title="Delete signature"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                        {signatureSlot === "review_section" ? (
                          <label className="cursor-pointer text-center">
                            <Upload className="w-6 h-6 mx-auto text-sky-600 mb-1" />
                            <span className="text-xs text-sky-600 font-medium">
                              {uploadingSignature
                                ? "Uploading..."
                                : "Upload Signature"}
                            </span>
                            <input
                              type="file"
                              accept="image/png,image/jpeg,image/jpg"
                              className="hidden"
                              onChange={handleSignatureUpload}
                              disabled={uploadingSignature}
                            />
                          </label>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            Pending signature
                          </span>
                        )}
                      </div>
                    )}

                    <div className="w-full border-t-2 border-black mt-2" />
                    <p className="mt-2 font-semibold uppercase text-center">
                      Reviewed by (Section Chief):
                    </p>
                    <p className="font-bold text-center">
                      {inspectionData.form?.checklist?.signatures
                        ?.review_section?.name || "_______________________"}
                    </p>
                    <p className="text-xs text-gray-700 text-center">
                      Section Chief
                    </p>
                    {inspectionData.form?.checklist?.signatures?.review_section
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
                    <div className="relative group">
                      <img
                        src={signatureUrls.approve_division}
                        alt="Division Chief signature"
                        className="h-20 object-contain mb-1 border border-gray-200 rounded p-1"
                        onError={(e) => {
                          console.error(
                            "❌ Failed to load approve_division signature:",
                            e
                          );
                          console.log(
                            "Image URL:",
                            signatureUrls.approve_division
                          );
                        }}
                      />
                      {signatureSlot === "approve_division" && (
                        <button
                          onClick={() =>
                            handleSignatureDelete("approve_division")
                          }
                          className="absolute top-0 right-0 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity print:hidden"
                          title="Delete signature"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="h-20 flex flex-col items-center justify-center border border-dashed border-gray-300 rounded px-4">
                      {signatureSlot === "approve_division" ? (
                        <label className="cursor-pointer text-center">
                          <Upload className="w-6 h-6 mx-auto text-sky-600 mb-1" />
                          <span className="text-xs text-sky-600 font-medium">
                            {uploadingSignature
                              ? "Uploading..."
                              : "Upload Signature"}
                          </span>
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/jpg"
                            className="hidden"
                            onChange={handleSignatureUpload}
                            disabled={uploadingSignature}
                          />
                        </label>
                      ) : (
                        <span className="text-xs text-gray-400 italic">
                          Pending signature
                        </span>
                      )}
                    </div>
                  )}

                  <div className="w-full border-t-2 border-black mt-2" />
                  <p className="mt-2 font-semibold uppercase text-center">
                    Approved by (Division Chief):
                  </p>
                  <p className="font-bold text-center">
                    {inspectionData.form?.checklist?.signatures
                      ?.approve_division?.name || "_______________________"}
                  </p>
                  <p className="text-xs text-gray-700 text-center">
                    {inspectionData.form?.checklist?.signatures
                      ?.approve_division?.title || "Division Chief"}
                  </p>
                  {inspectionData.form?.checklist?.signatures?.approve_division
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
          </div>

          {/* Confirmation Modal */}
          {showConfirm && (
            <div className="fixed inset-0 bg-white/30 backdrop-blur-md flex items-center justify-center z-50 print:hidden">
              <div className="bg-white rounded-lg shadow-2xl max-w-lg w-full mx-4 p-6 border border-gray-200">
                <h3 className="text-lg font-semibold mb-4">
                  {actionType === "save_and_submit"
                    ? "Confirm Submit"
                    : actionType === "save_and_approve"
                    ? "Confirm Save & Approve"
                    : actionType === "mark_compliant"
                    ? "Mark as Compliant"
                    : actionType === "mark_non_compliant"
                    ? "Mark as Non-Compliant"
                    : actionType === "forward_legal"
                    ? "Send to Legal"
                    : actionType === "approve_unit"
                    ? "Approve & Forward"
                    : actionType === "approve_section"
                    ? "Approve & Forward"
                    : actionType === "return_to_monitoring"
                    ? "Return"
                    : actionType === "return_to_unit"
                    ? "Return"
                    : actionType === "return_to_section"
                    ? "Return"
                    : actionType === "return_to_division"
                    ? "Return"
                    : "Confirm Action"}
                </h3>

                <p className="text-gray-700 mb-4">
                  {actionType === "save_and_submit"
                    ? "This will complete the inspection and change its status to completed. Please ensure all information is correct before proceeding."
                    : actionType === "save_and_approve"
                    ? "This will save the inspection changes and approve it for the next review level. Please ensure all information is correct before proceeding."
                    : actionType === "mark_compliant"
                    ? "This will mark the inspection as compliant and close the case. The establishment will be considered in full compliance."
                    : actionType === "mark_non_compliant"
                    ? "This will mark the inspection as non-compliant and close the case. The establishment will be considered in violation of regulations."
                    : actionType === "forward_legal"
                    ? "This will forward the inspection to the Legal Unit for enforcement action. The case will be marked for legal review."
                    : actionType === "approve_unit"
                    ? "This will approve the inspection and forward it to the Section Chief for review."
                    : actionType === "approve_section"
                    ? "This will approve the inspection and forward it to the Division Chief for review."
                    : actionType === "return_to_monitoring"
                    ? "Provide remarks explaining why this inspection is being returned to the Monitoring Personnel."
                    : actionType === "return_to_unit"
                    ? "Provide remarks explaining why this inspection is being returned to the Unit Head for further action."
                    : actionType === "return_to_section"
                    ? "Provide remarks explaining why this inspection is being returned to the Section Chief for further action."
                    : actionType === "return_to_division"
                    ? "Provide remarks explaining why this inspection is being returned to the Division Chief for further action."
                    : "Are you sure you want to proceed with this action?"}
                </p>

                {actionType.startsWith("return_") && (
                  <textarea
                    value={returnRemarks}
                    onChange={(e) => setReturnRemarks(e.target.value)}
                    placeholder="Enter remarks for returning this inspection..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 min-h-[120px] focus:ring-2 focus:ring-sky-500 focus:border-sky-500 resize-y overflow-y-auto mb-4 break-words"
                    style={{
                      wordWrap: "break-word",
                      overflowWrap: "break-word",
                    }}
                    disabled={loading}
                  />
                )}

                <div className="flex justify-end gap-3 mt-6">
                  <button
                    onClick={() => {
                      setShowConfirm(false);
                      setReturnRemarks("");
                    }}
                    className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    disabled={loading}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleReviewAction}
                    className="px-4 py-2 text-white bg-sky-600 rounded-md hover:bg-sky-700 font-semibold"
                    disabled={loading}
                  >
                    {loading
                      ? "Processing..."
                      : actionType === "save_and_submit"
                      ? "Submit"
                      : actionType === "save_and_approve"
                      ? "Save & Approve"
                      : actionType === "mark_compliant"
                      ? "Mark as Compliant"
                      : actionType === "mark_non_compliant"
                      ? "Mark as Non-Compliant"
                      : actionType === "forward_legal"
                      ? "Send to Legal"
                      : actionType === "approve_unit"
                      ? "Approve & Forward"
                      : actionType === "approve_section"
                      ? "Approve & Forward"
                      : actionType === "return_to_monitoring"
                      ? "Return"
                      : actionType === "return_to_unit"
                      ? "Return"
                      : actionType === "return_to_section"
                      ? "Return"
                      : actionType === "return_to_division"
                      ? "Return"
                      : "Confirm"}
                  </button>
                </div>
              </div>
            </div>
          )}
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

      {/* NOV Modal - Outside LayoutForm for proper z-index */}
      <NOVModal
        open={showNOVModal}
        onClose={() => setShowNOVModal(false)}
        onConfirm={handleNOVConfirm}
        inspection={inspectionData}
        loading={loading}
      />

      {/* NOO Modal - Outside LayoutForm for proper z-index */}
      <NOOModal
        open={showNOOModal}
        onClose={() => setShowNOOModal(false)}
        onConfirm={handleNOOConfirm}
        inspection={inspectionData}
        loading={loading}
      />
    </>
  );
};

export default InspectionReviewPage;
