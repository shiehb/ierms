import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Plus,
  ArrowUp,
  ArrowDown,
  AlertCircle,
  CheckCircle2,
  Scale,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  Send,
  FileText,
  Building,
  RotateCcw,
  X,
  CornerDownLeft,
} from "lucide-react";
import { getProfile, deleteInspection } from "../../services/api";
import StatusBadge from "./StatusBadge";
import InspectionTabs from "./InspectionTabs";
import InspectionActions from "./InspectionActions";
import {
  roleTabs,
  tabDisplayNames,
  canUserPerformActions,
} from "../../constants/inspectionConstants";
import ConfirmationDialog from "../common/ConfirmationDialog";
import TableToolbar from "../common/TableToolbar";
import { useNotifications } from "../../hooks/useNotifications";
import PaginationControls from "../PaginationControls";
import {
  useLocalStoragePagination,
  useLocalStorageTab,
} from "../../hooks/useLocalStoragePagination";
import { useInspectionActions } from "../../hooks/useInspectionActions";
import { useOptimizedInspections } from "../../hooks/useOptimizedInspections";
import MonitoringPersonnelModal from "./modals/MonitoringPersonnelModal";
import { canExportAndPrint } from "../../utils/permissions";

// Debounce hook
const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// Helper function to calculate days until/past deadline
const getDeadlineStatus = (deadline) => {
  if (!deadline)
    return {
      status: "none",
      days: null,
      text: "No deadline",
      color: "text-gray-400",
    };

  const now = new Date();
  const deadlineDate = new Date(deadline);
  const diffTime = deadlineDate - now;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return {
      status: "overdue",
      days: Math.abs(diffDays),
      text: `${Math.abs(diffDays)} days overdue`,
      color: "text-red-600 font-bold",
      bgColor: "bg-red-50",
    };
  }
  if (diffDays <= 3) {
    return {
      status: "urgent",
      days: diffDays,
      text: `${diffDays} days left`,
      color: "text-orange-600 font-semibold",
      bgColor: "bg-orange-50",
    };
  }
  if (diffDays <= 7) {
    return {
      status: "warning",
      days: diffDays,
      text: `${diffDays} days left`,
      color: "text-yellow-600",
      bgColor: "bg-yellow-50",
    };
  }
  return {
    status: "normal",
    days: diffDays,
    text: `${diffDays} days left`,
    color: "text-green-600",
    bgColor: "",
  };
};

// Helper function to calculate days since submission
const getSubmissionAge = (date) => {
  if (!date) return { days: null, text: "Unknown", color: "text-gray-400" };

  const now = new Date();
  const submittedDate = new Date(date);
  const diffTime = now - submittedDate;
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return { days: 0, text: "Today", color: "text-green-600" };
  } else if (diffDays === 1) {
    return { days: 1, text: "1 day ago", color: "text-green-600" };
  } else if (diffDays <= 2) {
    return {
      days: diffDays,
      text: `${diffDays} days ago`,
      color: "text-green-600",
    };
  } else if (diffDays <= 7) {
    return {
      days: diffDays,
      text: `${diffDays} days ago`,
      color: "text-yellow-600",
    };
  } else {
    return {
      days: diffDays,
      text: `${diffDays} days ago`,
      color: "text-red-600 font-semibold",
    };
  }
};

// Helper function to get payment status for NOO
const getPaymentStatus = (noo) => {
  if (!noo)
    return {
      status: "no_noo",
      text: "No NOO",
      color: "text-gray-400",
      daysOverdue: 0,
    };

  if (!noo.payment_deadline) {
    return {
      status: "no_deadline",
      text: "No deadline",
      color: "text-gray-400",
      daysOverdue: 0,
    };
  }

  const now = new Date();
  const deadline = new Date(noo.payment_deadline);
  const diffTime = deadline - now;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  // Check if paid (you'll need payment status field)
  if (noo.payment_status === "PAID") {
    return {
      status: "paid",
      text: "Paid",
      color: "text-green-600 bg-green-50",
      daysOverdue: 0,
    };
  }

  if (diffDays < 0) {
    return {
      status: "overdue",
      text: "Overdue",
      color: "text-red-600 bg-red-50 font-bold",
      daysOverdue: Math.abs(diffDays),
    };
  }

  if (diffDays <= 7) {
    return {
      status: "urgent",
      text: "Due Soon",
      color: "text-orange-600 bg-orange-50",
      daysOverdue: 0,
    };
  }

  return {
    status: "pending",
    text: "Unpaid",
    color: "text-yellow-600 bg-yellow-50",
    daysOverdue: 0,
  };
};

// Helper function to calculate days since assignment
const getAssignmentAge = (date) => {
  if (!date) return { days: null, text: "Unknown", color: "text-gray-400" };

  const now = new Date();
  const assignedDate = new Date(date);
  const diffTime = now - assignedDate;
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0)
    return { days: 0, text: "Today", color: "text-green-600" };
  if (diffDays === 1)
    return { days: 1, text: "1 day", color: "text-green-600" };
  if (diffDays <= 3)
    return {
      days: diffDays,
      text: `${diffDays} days`,
      color: "text-green-600",
    };
  if (diffDays <= 7)
    return {
      days: diffDays,
      text: `${diffDays} days`,
      color: "text-yellow-600",
    };
  return {
    days: diffDays,
    text: `${diffDays} days`,
    color: "text-red-600 font-semibold",
  };
};

// Helper function to format date as MM/DD/YYYY
const formatDate = (date) => {
  if (!date) return "N/A";
  return new Date(date).toLocaleDateString();
};

// Helper function to get column span for different tabs
const getTabColspan = (activeTab, userLevel = null) => {
  // Special case: Legal Unit in noo_sent tab has 7 columns (no Payment Status)
  if (activeTab === "noo_sent" && userLevel === "Legal Unit") {
    return 7;
  }

  const tabColspans = {
    nov_sent: 8, // 1 checkbox + 4 core (Code, Establishments, Law, Status) + 2 tab-specific + 1 Actions
    noo_sent: 8, // 1 checkbox + 4 core + 2 tab-specific + 1 Actions
    section_assigned: 8,
    section_in_progress: 8,
    unit_assigned: 8,
    unit_in_progress: 8,
    inspection_complete: 6,
    under_review: 7,
    forwarded: 8,
    assigned: 7, // 1 checkbox + 4 core + 1 tab-specific + 1 Actions
    in_progress: 8,
    compliant: 6, // Same as completed tab
    non_compliant: 6, // Same as completed tab
    returned_inspection: 6, // 1 checkbox + 4 core + Status + Actions
    returned_reports: 6, // 1 checkbox + 4 core + Status + Actions
    default: 6,
  };
  return tabColspans[activeTab] || tabColspans["default"];
};

// Helper function to get empty state message based on tab and user level
const getEmptyStateMessage = (activeTab, userLevel) => {
  const emptyStateMessages = {
    "Division Chief": {
      all_inspections:
        "No inspections available. Create a new inspection to get started.",
      inspection_complete:
        "No inspections marked complete yet. Check back soon.",
      review: "All caught up! No inspections pending your review.",
      reviewed: "No inspections have been marked as reviewed yet.",
      under_review: "All caught up! No inspections pending your review.",
    },
    "Section Chief": {
      section_assigned:
        "No new assignments. Check back later or view forwarded inspections.",
      section_in_progress:
        "No inspections currently in progress. Start by assigning yourself to an inspection.",
      forwarded: "No inspections forwarded to other personnel.",
      inspection_complete: "No inspections completed yet.",
      review: "All caught up! No inspections pending your review.",
      under_review: "All caught up! No inspections pending your review.",
      returned_inspection:
        "No returned inspections waiting to start in Section.",
      returned_reports:
        "No returned reports found that have completed monitoring.",
    },
    "Unit Head": {
      unit_assigned: "No new assignments from Section Chief.",
      unit_in_progress: "No inspections currently in progress.",
      forwarded: "No inspections forwarded to Monitoring Personnel.",
      inspection_complete: "No inspections completed yet.",
      review: "All caught up! No inspections pending your review.",
      under_review: "All caught up! No inspections pending your review.",
      returned_inspection: "No returned inspections waiting to start in Unit.",
      returned_reports:
        "No returned reports found that have completed monitoring.",
    },
    "Monitoring Personnel": {
      assigned: "No new assignments waiting to start.",
      in_progress: "No inspections currently in progress.",
      inspection_complete: "No completed inspections to display.",
      under_review: "All caught up! Nothing pending review.",
      returned_reports:
        "No returned reports found that have completed monitoring.",
    },
    "Legal Unit": {
      legal_review: "No cases assigned for legal review.",
      nov_sent: "No Notice of Violation (NOV) cases.",
      noo_sent: "No Notice of Order (NOO) cases.",
    },
  };

  return emptyStateMessages[userLevel]?.[activeTab] || "No inspections found.";
};

const actionKeyMap = {
  send_to_legal: "forward_to_legal",
  forward_to_legal: "forward_to_legal",
  mark_as_compliant: "close",
};

const normalizeActionKey = (action) => actionKeyMap[action] || action;

const getReturnTargetLabel = (target) => {
  if (target === "section") return "Section Chief";
  if (target === "unit") return "Unit Head";
  return "previous stage";
};

// Helper function to create action-specific dialog content
const getActionDialogContent = (
  rawAction,
  inspection,
  userLevel,
  pendingForwardAction
) => {
  const action = normalizeActionKey(rawAction);
  const establishmentNames =
    inspection?.establishments_detail?.length > 0
      ? inspection.establishments_detail.map((est) => est.name).join(", ")
      : "No establishments";

  const actionConfig = {
    inspect: {
      title: "Confirm Inspection Assignment",
      confirmColor: "sky",
      confirmText: "Confirm",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Assign inspection{" "}
            <span className="font-medium">{inspection?.code}</span> to yourself
            and open the inspection form?
          </p>
          <p className="text-xs text-gray-500">
            This moves the inspection into your active workload.
          </p>
        </div>
      ),
    },
    start: {
      title: "Start Inspection",
      confirmColor: "sky",
      confirmText: "Start Inspection",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Begin work on inspection{" "}
            <span className="font-medium">{inspection?.code}</span> now?
          </p>
          <p className="text-xs text-gray-500">
            The inspection status will move to In Progress.
          </p>
        </div>
      ),
    },
    continue: {
      icon: <FileText className="w-5 h-5 text-sky-600" />,
      headerColor: "sky",
      title: "Resume Inspection Form",
      confirmColor: "sky",
      confirmText: "Open Form",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Reopen the form for inspection{" "}
            <span className="font-medium">{inspection?.code}</span>?
          </p>
          <p className="text-xs text-gray-500">
            You can continue editing the inspection details.
          </p>
        </div>
      ),
    },
    review: {
      icon: <Eye className="w-5 h-5 text-indigo-600" />,
      headerColor: "sky",
      title: "Open Review Workspace",
      confirmColor: "sky",
      confirmText: "Open Review",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Request review access for inspection{" "}
            <span className="font-medium">{inspection?.code}</span> and open the
            review workspace?
          </p>
          <p className="text-xs text-gray-500">
            Access is validated before the review page opens.
          </p>
        </div>
      ),
    },
    forward: {
      title: "Confirm Forward Action",
      confirmColor: "sky",
      confirmText: "Confirm Forward",
      message: () => {
        const selectedPersonnel = pendingForwardAction?.selectedPersonnelName;
        const selectedInspections = pendingForwardAction?.inspections || [];
        const selectionCount = pendingForwardAction?.inspectionIds?.length || 1;
        return (
          <div className="space-y-3">
            <p>
              Are you sure you want to forward
              {selectionCount > 1
                ? ` these ${selectionCount} inspections?`
                : " this inspection?"}
            </p>
            {selectionCount > 1 && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
                  Selected Inspections
                </p>
                <ul className="space-y-1 text-sm text-gray-700 list-disc list-inside">
                  {selectedInspections.slice(0, 3).map((item) => (
                    <li key={item.id}>
                      <span className="font-medium">{item.code}</span>
                      {item.establishments_detail?.length ? (
                        <span className="text-gray-500">
                          {" "}
                          —{" "}
                          {item.establishments_detail
                            .map((est) => est.name)
                            .join(", ")}
                        </span>
                      ) : null}
                    </li>
                  ))}
                  {selectionCount > 3 && (
                    <li className="text-gray-500">
                      + {selectionCount - 3} more
                    </li>
                  )}
                </ul>
              </div>
            )}
            {selectedPersonnel && (
              <div className="bg-sky-50 border border-sky-200 rounded-lg p-3">
                <p className="text-sm font-medium text-sky-900">
                  Forward to: {selectedPersonnel}
                </p>
              </div>
            )}
          </div>
        );
      },
    },
    return_to_previous: {
      icon: <RotateCcw className="w-5 h-5 text-gray-600" />,
      headerColor: null,
      title: "Confirm Return",
      confirmColor: "sky",
      confirmText: "Return",
      message: () => (
        <p className="text-sm text-gray-700">
          Send inspection{" "}
          <span className="font-medium">{inspection?.code}</span> back to the
          previous stage?
        </p>
      ),
    },
    return_to_monitoring: {
      icon: <RotateCcw className="w-5 h-5 text-sky-600" />,
      headerColor: "sky",
      title: "Return to Monitoring",
      confirmColor: "sky",
      confirmText: "Return",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Send inspection{" "}
            <span className="font-medium">{inspection?.code}</span> back to the
            Monitoring Personnel for additional action?
          </p>
          <p className="text-xs text-gray-500">
            The monitoring team will be notified and the inspection will resume
            from their completed stage.
          </p>
        </div>
      ),
    },
    return_to_unit: {
      icon: <RotateCcw className="w-5 h-5 text-sky-600" />,
      headerColor: "sky",
      title: "Return to Unit Head",
      confirmColor: "sky",
      confirmText: "Return",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Send inspection{" "}
            <span className="font-medium">{inspection?.code}</span> back to the
            Unit Head for corrections?
          </p>
          <p className="text-xs text-gray-500">
            The inspection will reopen at the unit stage and the previous
            assignee will be notified.
          </p>
        </div>
      ),
    },
    return_to_section: {
      icon: <RotateCcw className="w-5 h-5 text-sky-600" />,
      headerColor: "sky",
      title: "Return to Section Chief",
      confirmColor: "sky",
      confirmText: "Return",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Send inspection{" "}
            <span className="font-medium">{inspection?.code}</span> back to the
            Section Chief for further review?
          </p>
          <p className="text-xs text-gray-500">
            The section stage will become active again and the Section Chief
            will receive your remarks.
          </p>
        </div>
      ),
    },
    forward_to_legal: {
      icon: <Scale className="w-5 h-5 text-orange-600" />,
      headerColor: "sky",
      title: "Forward to Legal Unit",
      confirmColor: "sky",
      confirmText: "Forward to Legal",
      message: (
        <div className="space-y-4">
          {/* Inspection Details Card */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-gray-600" />
              <span className="font-medium text-gray-800">
                Inspection Details
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-700">Code:</span>
                <span className="text-gray-900">{inspection?.code}</span>
              </div>
              <div className="flex items-center gap-2">
                <Building className="w-4 h-4 text-gray-500" />
                <span className="text-gray-700">{establishmentNames}</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-500" />
                <span className="text-gray-700">
                  Status: {inspection?.current_status}
                </span>
              </div>
            </div>
          </div>

          {/* Legal Review Process */}
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Scale className="w-4 h-4 text-orange-600" />
              <span className="font-medium text-orange-800">
                Legal Review Process
              </span>
            </div>
            <div className="space-y-2 text-sm text-orange-700">
              <p>
                • This inspection will be forwarded to the Legal Unit for review
              </p>
              <p>
                • Legal Unit will assess compliance and determine next steps
              </p>
              <p>
                • They may issue NOV (Notice of Violation) or NOO (Notice of
                Order)
              </p>
              <p>• The case will be marked for legal review in the system</p>
            </div>
          </div>

          {/* Warning */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="w-4 h-4 text-amber-600" />
              <span className="font-medium text-amber-800">Important Note</span>
            </div>
            <p className="text-sm text-amber-700">
              Legal review is a critical step in the regulatory process. Ensure
              all documentation is complete before forwarding.
            </p>
          </div>

          <div className="text-sm text-gray-600">
            <p>
              Are you sure you want to forward this inspection to the Legal
              Unit?
            </p>
          </div>
        </div>
      ),
    },
    close: {
      icon:
        userLevel === "Legal Unit" || userLevel === "Division Chief" ? (
          <CheckCircle2 className="w-5 h-5 text-green-600" />
        ) : (
          <CheckCircle className="w-5 h-5 text-green-600" />
        ),
      headerColor: "sky",
      title:
        userLevel === "Legal Unit" || userLevel === "Division Chief"
          ? "Mark as Compliant"
          : "Close Inspection",
      confirmColor: "sky",
      confirmText:
        userLevel === "Legal Unit" || userLevel === "Division Chief"
          ? "Mark as Compliant"
          : "Close Inspection",
      message: (
        <div className="space-y-4">
          {/* Inspection Details Card */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-gray-600" />
              <span className="font-medium text-gray-800">
                Inspection Details
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-700">Code:</span>
                <span className="text-gray-900">{inspection?.code}</span>
              </div>
              <div className="flex items-center gap-2">
                <Building className="w-4 h-4 text-gray-500" />
                <span className="text-gray-700">{establishmentNames}</span>
              </div>
            </div>
          </div>

          {/* Completion Info */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-green-600" />
              <span className="font-medium text-green-800">Final Status</span>
            </div>
            <div className="space-y-2 text-sm text-green-700">
              {userLevel === "Legal Unit" || userLevel === "Division Chief" ? (
                <>
                  <p>
                    • This inspection will be marked as{" "}
                    <strong>Compliant</strong>
                  </p>
                  <p>
                    • The establishment will be considered in full compliance
                  </p>
                  <p>• The case will be closed and archived</p>
                  <p>• A compliance certificate may be issued</p>
                </>
              ) : (
                <>
                  <p>• This inspection will be closed</p>
                  <p>• The case will be marked as completed</p>
                  <p>• No further action will be required</p>
                </>
              )}
            </div>
          </div>

          <div className="text-sm text-gray-600">
            <p>
              Are you sure you want to{" "}
              {userLevel === "Legal Unit" || userLevel === "Division Chief"
                ? "mark this as compliant"
                : "close this inspection"}
              ?
            </p>
          </div>
        </div>
      ),
    },
    complete: {
      icon: <CheckCircle className="w-5 h-5 text-green-600" />,
      headerColor: "sky",
      title: "Complete Inspection",
      confirmColor: "sky",
      confirmText: "Complete Inspection",
      message: (
        <div className="space-y-4">
          {/* Inspection Details Card */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-gray-600" />
              <span className="font-medium text-gray-800">
                Inspection Details
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-700">Code:</span>
                <span className="text-gray-900">{inspection?.code}</span>
              </div>
              <div className="flex items-center gap-2">
                <Building className="w-4 h-4 text-gray-500" />
                <span className="text-gray-700">{establishmentNames}</span>
              </div>
            </div>
          </div>

          {/* Completion Info */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="font-medium text-green-800">
                Completion Process
              </span>
            </div>
            <div className="space-y-2 text-sm text-green-700">
              <p>• This inspection will be marked as completed</p>
              <p>• All inspection data will be finalized</p>
              <p>• The case will move to the next stage in the workflow</p>
            </div>
          </div>

          <div className="text-sm text-gray-600">
            <p>Are you sure you want to complete this inspection?</p>
          </div>
        </div>
      ),
    },
    send_noo: {
      icon: <Send className="w-5 h-5 text-red-600" />,
      headerColor: "sky",
      title: "Open NOO Workflow",
      confirmColor: "sky",
      confirmText: "Open Review",
      message: () => (
        <div className="space-y-3">
          <p className="text-sm text-gray-700">
            Open the review workspace for inspection{" "}
            <span className="font-medium">{inspection?.code}</span> to process
            the Notice of Order?
          </p>
          <p className="text-xs text-gray-500">
            You will be redirected to the inspection review page to finalize the
            NOO.
          </p>
        </div>
      ),
    },
  };

  // Default fallback for unknown actions
  const defaultConfig = {
    icon: <AlertCircle className="w-5 h-5 text-gray-600" />,
    headerColor: "sky",
    title: "Confirm Action",
    confirmColor: "sky",
    confirmText: "Confirm",
    message: (
      <div className="space-y-4">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-gray-600" />
            <span className="font-medium text-gray-800">
              Inspection Details
            </span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-700">Code:</span>
              <span className="text-gray-900">{inspection?.code}</span>
            </div>
            <div className="flex items-center gap-2">
              <Building className="w-4 h-4 text-gray-500" />
              <span className="text-gray-700">{establishmentNames}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-700">Action:</span>
              <span className="text-gray-900">
                {(rawAction || action)?.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>
          </div>
        </div>
        <div className="text-sm text-gray-600">
          <p>Are you sure you want to perform this action?</p>
        </div>
      </div>
    ),
  };

  return actionConfig[action] || defaultConfig;
};

const formatActionLabel = (action) => {
  if (!action) return "Action";
  return action
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

const getActionNotificationOverrides = (action, inspection, context = {}) => {
  if (!inspection) {
    return {};
  }

  const code = inspection.code || inspection.id;
  const baseLabel = `Inspection ${code}`;

  switch (action) {
    case "inspect":
      return {
        successTitle: "Inspection Assigned",
        successMessage: `${baseLabel} assigned to you.`,
      };
    case "start":
      return {
        successTitle: "Inspection Started",
        successMessage: `${baseLabel} started successfully.`,
      };
    case "review":
      return {
        successTitle: "Review Access Granted",
        successMessage: `Review access granted for ${baseLabel}.`,
      };
    case "forward":
      if (context.isBulk) {
        return {
          successTitle: null,
          successMessage: null,
        };
      }
      if (context.selectedPersonnelName) {
        return {
          successTitle: "Inspection Forwarded",
          successMessage: `${baseLabel} forwarded to ${context.selectedPersonnelName}.`,
        };
      }
      if (context.destinationLabel) {
        return {
          successTitle: "Inspection Forwarded",
          successMessage: `${baseLabel} forwarded to the ${context.destinationLabel}.`,
        };
      }
      return {
        successTitle: "Inspection Forwarded",
        successMessage: `${baseLabel} forwarded successfully.`,
      };
    case "return_to_previous": {
      const destination = context.destinationLabel || "previous stage";
      return {
        successTitle: "Inspection Returned",
        successMessage: `${baseLabel} returned to the ${destination}.`,
      };
    }
    case "return_to_monitoring":
      return {
        successTitle: "Inspection Returned",
        successMessage: `${baseLabel} returned to the Monitoring Personnel.`,
      };
    case "return_to_unit": {
      const status = inspection.current_status || "";
      const destination =
        status === "UNIT_COMPLETED_COMPLIANT" ||
        status === "UNIT_COMPLETED_NON_COMPLIANT"
          ? "Unit Head"
          : "Monitoring Personnel";
      return {
        successTitle: "Inspection Returned",
        successMessage: `${baseLabel} returned to the ${destination}.`,
      };
    }
    case "return_to_section": {
      const status = inspection.current_status || "";
      const destination =
        status === "SECTION_COMPLETED_COMPLIANT" ||
        status === "SECTION_COMPLETED_NON_COMPLIANT"
          ? "Section Chief"
          : "previous stage";
      return {
        successTitle: "Inspection Returned",
        successMessage: `${baseLabel} returned to the ${destination}.`,
      };
    }
    case "forward_to_legal":
      return {
        successTitle: "Forwarded to Legal",
        successMessage: `${baseLabel} forwarded to the Legal Unit.`,
      };
    case "close": {
      const isCompliance =
        context.userLevel === "Legal Unit" ||
        context.userLevel === "Division Chief";
      return {
        successTitle: isCompliance
          ? "Marked as Compliant"
          : "Inspection Closed",
        successMessage: isCompliance
          ? `${baseLabel} marked as compliant.`
          : `${baseLabel} closed successfully.`,
      };
    }
    case "complete":
      return {
        successTitle: "Inspection Completed",
        successMessage: `${baseLabel} marked as completed.`,
      };
    default:
      return {
        successTitle: "Action Completed",
        successMessage: `${baseLabel} ${formatActionLabel(
          action
        )} successfully.`,
      };
  }
};

export default function InspectionsList({
  onAdd,
  refreshTrigger,
  userLevel = "Division Chief",
}) {
  const notifications = useNotifications();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);

  // 🎯 Search highlighting
  const location = useLocation();
  const [highlightedInspId, setHighlightedInspId] = useState(null);
  const highlightedRowRef = useRef(null);

  // 🔍 Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // 🎚 Filters
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sectionFilter, setSectionFilter] = useState([]);
  const [lawFilter, setLawFilter] = useState([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showOnlyMyAssignments, setShowOnlyMyAssignments] = useState(false);

  // 🔄 Action loading state
  const [actionLoading, setActionLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // 🔄 Monitoring personnel selection state
  const [showMonitoringModal, setShowMonitoringModal] = useState(false);
  const [pendingForwardAction, setPendingForwardAction] = useState(null);

  // 📑 Tab state for role-based tabs with localStorage persistence
  const {
    loadFromStorage: loadTabFromStorage,
    saveToStorage: saveTabToStorage,
  } = useLocalStorageTab("inspections_list");
  const [activeTab, setActiveTab] = useState(() => {
    // Normalize userLevel to match constants (capitalize first letter, lowercase rest)
    const normalizedUserLevel = userLevel
      ? userLevel
          .split(" ")
          .map(
            (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
          )
          .join(" ")
      : "Admin";
    const availableTabs = roleTabs[normalizedUserLevel] ||
      roleTabs["Admin"] || ["all_inspections"];
    const savedTab = loadTabFromStorage();
    // Check if saved tab is still available for current user level
    if (savedTab && availableTabs.includes(savedTab)) {
      return savedTab;
    }
    return availableTabs[0];
  });

  // ✅ Sorting
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });

  // ✅ Pagination with localStorage
  const savedPagination = useLocalStoragePagination("inspections_list");
  const [currentPage, setCurrentPage] = useState(savedPagination.page);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);

  // 🗑️ Delete confirmation state
  const [deleteConfirmation, setDeleteConfirmation] = useState({
    open: false,
    inspection: null,
  });

  // ✅ Bulk select
  const [selectedInspections, setSelectedInspections] = useState([]);
  const [isBulkForward, setIsBulkForward] = useState(false);

  // Use optimized inspections hook
  const {
    inspections,
    tabCounts,
    paginationMeta,
    loading,

    fetchInspections,
    refreshData,
  } = useOptimizedInspections(userLevel, currentUser);

  const fetchAllInspections = useCallback(
    async (options = {}) => {
      if (!currentUser) return;

      const { overrideTab, overridePage, overridePageSize, ...restOptions } =
        options;

      const params = {
        page: overridePage ?? currentPage,
        page_size: overridePageSize ?? pageSize,
        tab: overrideTab ?? activeTab,
      };

      // Add search parameter if provided
      if (debouncedSearchQuery) {
        params.search = debouncedSearchQuery;
      }

      // Add law filter (server-side)
      if (lawFilter.length > 0) {
        params.law = lawFilter.join(",");
      }

      // Add date filters (server-side)
      if (dateFrom) {
        params.date_from = dateFrom;
      }
      if (dateTo) {
        params.date_to = dateTo;
      }

      // Add assignment filter (server-side)
      if (showOnlyMyAssignments) {
        params.assigned_to_me = "true";
      }

      // Add sorting parameters (server-side)
      if (sortConfig.key) {
        params.order_by = sortConfig.key;
        params.order_direction = sortConfig.direction;
      }

      await fetchInspections(params, restOptions);
    },
    [
      currentPage,
      pageSize,
      debouncedSearchQuery,
      lawFilter,
      dateFrom,
      dateTo,
      showOnlyMyAssignments,
      sortConfig.key,
      sortConfig.direction,
      activeTab,
      currentUser,
      fetchInspections,
    ]
  );

  // Handle tab change with localStorage persistence
  const handleTabChange = useCallback(
    (newTab) => {
      setActiveTab(newTab);
      saveTabToStorage(newTab);
      // Reset to page 1 when changing tabs
      setCurrentPage(1);
      // Trigger an immediate refresh for the newly selected tab
      fetchAllInspections({
        force: true,
        overrideTab: newTab,
        overridePage: 1,
      });
    },
    [fetchAllInspections, saveTabToStorage]
  );

  const handleManualRefresh = useCallback(async () => {
    if (!currentUser) return;
    setRefreshing(true);
    try {
      await fetchAllInspections({ force: true });
      refreshData("inspections");
    } finally {
      setRefreshing(false);
    }
  }, [currentUser, fetchAllInspections, refreshData]);

  // All filtering and sorting is handled server-side
  const filteredInspections = inspections;

  // Get unique laws from current inspections
  const availableLaws = useMemo(() => {
    const lawSet = new Set();
    inspections.forEach((inspection) => {
      if (inspection.law) {
        lawSet.add(inspection.law);
      }
    });
    return Array.from(lawSet).sort();
  }, [inspections]);

  // Tab counts are now handled by the optimized hook

  // Use the inspection actions hook
  const { handleAction, isActionLoading } =
    useInspectionActions(fetchAllInspections);

  // Action confirmation states
  const [actionConfirmation, setActionConfirmation] = useState({
    open: false,
    inspection: null,
    action: null,
  });
  const [actionRemarks, setActionRemarks] = useState("");

  // Modal state for Return Remarks
  const [remarksModal, setRemarksModal] = useState({
    open: false,
    inspection: null,
    latest: null,
    all: [],
  });

  const extractReturnEntries = useCallback((inspection) => {
    const entries = (inspection?.history || [])
      .filter((h) => h?.remarks && h.remarks.includes("Returned"))
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    const latest = entries[0] || null;
    const extractClean = (remarks) => {
      if (!remarks) return "";
      return remarks.includes(":") ? remarks.split(":")[1].trim() : remarks;
    };

    return {
      latestText: extractClean(
        latest?.remarks || inspection?.return_remarks || ""
      ),
      entries: entries.map((e) => ({
        id: e.id,
        created_at: e.created_at,
        previous_status: e.previous_status,
        new_status: e.new_status,
        assigned_to_name: e.assigned_to_name,
        changed_by_name: e.changed_by_name,
        remarks: extractClean(e.remarks),
      })),
    };
  }, []);

  const openRemarksModal = useCallback(
    (inspection) => {
      const { latestText, entries } = extractReturnEntries(inspection);
      setRemarksModal({
        open: true,
        inspection,
        latest: latestText || "No remarks",
        all: entries,
      });
    },
    [extractReturnEntries]
  );

  const closeRemarksModal = useCallback(() => {
    setRemarksModal({ open: false, inspection: null, latest: null, all: [] });
  }, []);

  // Copy latest remarks to clipboard
  const copyLatestRemarks = useCallback(() => {
    if (remarksModal.latest) {
      try {
        navigator.clipboard.writeText(remarksModal.latest);
      } catch {
        // ignore clipboard errors silently
      }
    }
  }, [remarksModal.latest]);
  const [remarksError, setRemarksError] = useState(null);

  const actionRequiresRemarks = useCallback(
    (action) =>
      [
        "return_to_previous",
        "return_to_monitoring",
        "return_to_unit",
        "return_to_section",
      ].includes(action || ""),
    []
  );

  const openActionDialog = useCallback(
    (config) => {
      const normalizedAction = normalizeActionKey(config.action);
      if (actionRequiresRemarks(normalizedAction)) {
        setActionRemarks("");
        setRemarksError(null);
      }
      setActionConfirmation({
        open: true,
        ...config,
        action: normalizedAction,
      });
    },
    [actionRequiresRemarks]
  );

  // Helper function to determine if actions should be shown
  const shouldShowActions = useCallback((userLevel, activeTab) => {
    if (activeTab === "inspection_complete") return false;
    // Closed tabs are view-only
    if (activeTab === "compliant" || activeTab === "non_compliant")
      return false;
    // Division Chief actions handled via dedicated buttons
    if (userLevel === "Division Chief") {
      return activeTab === "review";
    }

    // Legal Unit users in legal_review tab should see review buttons, but noo_sent tab should only see view buttons
    if (userLevel === "Legal Unit" && activeTab === "noo_sent") {
      return false;
    }

    return canUserPerformActions(userLevel);
  }, []);

  // Handle action clicks with standardized confirmation
  const handleActionClick = useCallback(
    async (actionKey, inspectionId) => {
      const inspection = inspections.find((i) => i.id === inspectionId);
      if (!inspection) {
        console.error("Inspection not found:", inspectionId);
        return;
      }

      setIsBulkForward(false);

      const action = normalizeActionKey(actionKey);

      if (action === "forward") {
        // Check if this requires monitoring personnel selection
        const isCombinedSection =
          currentUser?.section === "PD-1586,RA-8749,RA-9275";

        if (userLevel === "Section Chief" && isCombinedSection) {
          // Combined section forwards to Unit - show confirmation directly
          setPendingForwardAction({
            inspection,
            inspections: [inspection],
            inspectionIds: [inspection.id],
            action: "forward",
            forwardData: { target: "unit", remarks: "Forwarded to next level" },
          });
          openActionDialog({
            inspection,
            action,
          });
        } else if (userLevel === "Section Chief" || userLevel === "Unit Head") {
          // Individual sections and Unit Head - show monitoring modal first
          setPendingForwardAction({
            inspection,
            inspections: [inspection],
            inspectionIds: [inspection.id],
            action: "forward",
            forwardData: { target: "monitoring" },
          });
          setShowMonitoringModal(true);
        }
        return;
      }

      if (action === "return_to_previous") {
        const defaultReturnTarget =
          inspection.current_status === "UNIT_ASSIGNED" ? "section" : null;

        setPendingForwardAction({
          inspection,
          action: "return_to_previous",
          returnTarget: defaultReturnTarget,
        });
        openActionDialog({
          inspection,
          action: "return_to_previous",
        });
        return;
      }

      // Actions that redirect after confirmation
      if (action === "continue" || action === "send_noo") {
        openActionDialog({
          inspection,
          action,
        });
        return;
      }

      // Review action routed through confirmation to ensure access validation
      if (action === "review") {
        openActionDialog({
          inspection,
          action,
        });
        return;
      }

      // Normalize send_to_legal to forward_to_legal for confirmation
      if (action === "forward_to_legal") {
        openActionDialog({
          inspection,
          action: "forward_to_legal",
        });
        return;
      }

      // Finalization actions (inspect, start, close, complete, etc.)
      openActionDialog({
        inspection,
        action,
      });
    },
    [
      inspections,
      currentUser,
      userLevel,
      setIsBulkForward,
      openActionDialog,
      setPendingForwardAction,
      setShowMonitoringModal,
    ]
  );

  // Execute confirmed action
  const executeAction = useCallback(async () => {
    const { inspection, action: rawAction } = actionConfirmation;
    if (!rawAction) return;

    const action = normalizeActionKey(rawAction);

    if (!inspection && action !== "forward") return;

    const closeDialog = () => {
      setActionConfirmation({ open: false, inspection: null, action: null });
      setActionRemarks("");
      setRemarksError(null);
    };

    const requiresRemarks = actionRequiresRemarks(action);
    const trimmedRemarks = actionRemarks.trim();
    if (requiresRemarks && !trimmedRemarks) {
      setRemarksError("Remarks are required.");
      return;
    }
    if (requiresRemarks) {
      setRemarksError(null);
    }

    if (action === "continue") {
      closeDialog();
      if (inspection) {
        window.location.href = `/inspections/${inspection.id}/form`;
      }
      return;
    }

    if (action === "send_noo") {
      closeDialog();
      if (inspection) {
        window.location.href = `/inspections/${inspection.id}/review`;
      }
      return;
    }

    setActionLoading(true);

    try {
      if (action === "inspect") {
        const overrides = getActionNotificationOverrides(action, inspection, {
          userLevel,
        });
        await handleAction(action, inspection.id, {}, overrides);
        closeDialog();
        window.location.href = `/inspections/${inspection.id}/form`;
        return;
      }

      if (action === "start") {
        const overrides = getActionNotificationOverrides(
          action,
          inspection,
          {}
        );
        await handleAction("start", inspection.id, {}, overrides);
        closeDialog();
        window.location.href = `/inspections/${inspection.id}/form`;
        return;
      }

      if (action === "review") {
        const overrides = getActionNotificationOverrides(
          action,
          inspection,
          {}
        );
        await handleAction(action, inspection.id, {}, overrides);
        closeDialog();
        window.location.href = `/inspections/${inspection.id}/review`;
        return;
      }

      if (action === "forward") {
        if (isBulkForward && pendingForwardAction?.inspectionIds?.length) {
          const ids = pendingForwardAction.inspectionIds;
          const forwardData = {
            remarks: "Forwarded to next level",
            ...(pendingForwardAction.forwardData || {}),
          };

          for (const id of ids) {
            const targetInspection =
              pendingForwardAction.inspections?.find?.(
                (item) => item.id === id
              ) || inspections.find((item) => item.id === id);
            const overrides = getActionNotificationOverrides(
              action,
              targetInspection || inspection,
              { isBulk: true }
            );
            await handleAction(action, id, forwardData, overrides);
          }

          notifications.success(
            `${ids.length} inspection${
              ids.length > 1 ? "s" : ""
            } forwarded successfully`,
            { title: "Inspections Forwarded" }
          );

          setPendingForwardAction(null);
          closeDialog();
          setSelectedInspections([]);
          setIsBulkForward(false);
          await fetchAllInspections({ force: true });
          return;
        }

        let forwardData = {
          remarks: "Forwarded to next level",
        };

        if (pendingForwardAction?.forwardData?.assigned_monitoring_id) {
          forwardData = { ...pendingForwardAction.forwardData };
          const overrides = getActionNotificationOverrides(action, inspection, {
            selectedPersonnelName: pendingForwardAction.selectedPersonnelName,
          });

          await handleAction(action, inspection.id, forwardData, overrides);

          setPendingForwardAction(null);
          closeDialog();
          setSelectedInspections((prev) =>
            prev.filter((id) => id !== inspection.id)
          );
          await fetchAllInspections({ force: true });
          return;
        }

        if (userLevel === "Section Chief") {
          const isCombinedSection =
            currentUser?.section === "PD-1586,RA-8749,RA-9275";

          if (isCombinedSection) {
            const combinedForwardData = { ...forwardData, target: "unit" };
            const overrides = getActionNotificationOverrides(
              action,
              inspection,
              {
                destinationLabel: "Unit Head",
              }
            );
            await handleAction(
              action,
              inspection.id,
              combinedForwardData,
              overrides
            );
            closeDialog();
            setPendingForwardAction(null);
            setSelectedInspections((prev) =>
              prev.filter((id) => id !== inspection.id)
            );
            await fetchAllInspections({ force: true });
            return;
          }
        }

        const overrides = getActionNotificationOverrides(
          action,
          inspection,
          {}
        );
        await handleAction(action, inspection.id, forwardData, overrides);
        setPendingForwardAction(null);
        closeDialog();
        setSelectedInspections((prev) =>
          prev.filter((id) => id !== inspection.id)
        );
        return;
      }

      if (action === "return_to_previous") {
        const payload = { remarks: trimmedRemarks };

        if (pendingForwardAction?.returnTarget) {
          payload.target = pendingForwardAction.returnTarget;
        }

        const overrides = getActionNotificationOverrides(action, inspection, {
          destinationLabel: getReturnTargetLabel(
            pendingForwardAction?.returnTarget
          ),
        });

        await handleAction(action, inspection.id, payload, overrides);
        closeDialog();
        setPendingForwardAction(null);
        await fetchAllInspections({ force: true });
        return;
      }

      if (
        [
          "return_to_monitoring",
          "return_to_unit",
          "return_to_section",
        ].includes(action)
      ) {
        const overrides = getActionNotificationOverrides(action, inspection, {
          userLevel,
        });
        await handleAction(
          action,
          inspection.id,
          { remarks: trimmedRemarks },
          overrides
        );
        if (pendingForwardAction) {
          setPendingForwardAction(null);
        }
        closeDialog();
        await fetchAllInspections({ force: true });
        return;
      }

      const overrides = getActionNotificationOverrides(action, inspection, {
        userLevel,
      });
      await handleAction(action, inspection.id, {}, overrides);
      closeDialog();
    } catch {
      // Error is already handled in the hook
    } finally {
      setActionLoading(false);
      if (action === "forward" && isBulkForward) {
        setIsBulkForward(false);
      }
    }
  }, [
    actionConfirmation,
    actionRemarks,
    actionRequiresRemarks,
    handleAction,
    userLevel,
    inspections,
    notifications,
    currentUser,
    isBulkForward,
    pendingForwardAction,
    fetchAllInspections,
    setSelectedInspections,
    setPendingForwardAction,
  ]);

  const handleActionDialogCancel = useCallback(() => {
    setActionConfirmation({ open: false, inspection: null, action: null });
    setActionRemarks("");
    setRemarksError(null);
    if (isBulkForward) {
      setPendingForwardAction(null);
      setIsBulkForward(false);
    }
  }, [isBulkForward, setPendingForwardAction, setIsBulkForward]);

  // Handle monitoring personnel selection
  const handleMonitoringPersonnelSelect = useCallback(
    (monitoringId, selectedPerson) => {
      if (!pendingForwardAction) return;

      // Get the selected personnel name
      const selectedPersonnelName = selectedPerson
        ? `${selectedPerson.first_name} ${selectedPerson.last_name}`
        : "Selected Personnel";
      const inspectionForConfirmation =
        pendingForwardAction.inspection ||
        pendingForwardAction.inspections?.[0] ||
        null;

      // Close monitoring modal
      setShowMonitoringModal(false);

      // Add monitoring ID and personnel name to pending action
      setPendingForwardAction((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          forwardData: {
            ...(prev.forwardData || {}),
            assigned_monitoring_id: monitoringId,
          },
          selectedPersonnelName,
        };
      });

      // Show confirmation dialog
      openActionDialog({
        inspection: inspectionForConfirmation,
        action: "forward",
      });
    },
    [pendingForwardAction, openActionDialog]
  );

  // Handle monitoring modal close
  const handleMonitoringModalClose = useCallback(() => {
    setShowMonitoringModal(false);
    setPendingForwardAction(null);
    setIsBulkForward(false);
  }, []);

  // Delete inspection function
  const handleDeleteInspection = useCallback(
    async (inspection) => {
      try {
        await deleteInspection(inspection.id);
        notifications.success(
          `Inspection ${inspection.code} deleted successfully`,
          { title: "Success" }
        );
        fetchAllInspections();
        setDeleteConfirmation({ open: false, inspection: null });
      } catch (error) {
        console.error("Error deleting inspection:", error);
        notifications.error(`Error deleting inspection: ${error.message}`, {
          title: "Error",
        });
      }
    },
    [fetchAllInspections, notifications]
  );

  // Fetch user profile (only once on mount)
  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        const profile = await getProfile();
        setCurrentUser(profile);

        // Normalize userLevel from profile to match constants
        const normalizedUserLevel = profile?.userlevel
          ? profile.userlevel
              .split(" ")
              .map(
                (word) =>
                  word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
              )
              .join(" ")
          : userLevel;

        // Set default tab based on user level
        const availableTabs = roleTabs[normalizedUserLevel] ||
          roleTabs["Admin"] || ["all_inspections"];
        const tabs = availableTabs.map((tab) => ({
          id: tab,
          label: tabDisplayNames[tab] || tab,
          count: 0,
        }));
        if (tabs.length > 0 && !activeTab) {
          setActiveTab(tabs[0].id);
        }
      } catch (error) {
        console.error("Error fetching user profile:", error);
      }
    };
    fetchUserProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch on mount, not on every tab change

  // Update activeTab when userLevel changes
  useEffect(() => {
    const normalizedUserLevel = userLevel
      ? userLevel
          .split(" ")
          .map(
            (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
          )
          .join(" ")
      : "Admin";
    const availableTabs = roleTabs[normalizedUserLevel] ||
      roleTabs["Admin"] || ["all_inspections"];

    // If current activeTab is not in available tabs, reset to first available tab
    if (availableTabs.length > 0 && !availableTabs.includes(activeTab)) {
      setActiveTab(availableTabs[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userLevel]);

  // Fetch inspections when dependencies change
  useEffect(() => {
    if (currentUser) {
      fetchAllInspections();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    currentPage,
    pageSize,
    activeTab,
    debouncedSearchQuery,
    lawFilter.join(","), // Convert array to string for proper comparison
    dateFrom,
    dateTo,
    showOnlyMyAssignments,
    sortConfig.key,
    sortConfig.direction,
    refreshTrigger,
    currentUser,
    // Note: fetchAllInspections is intentionally excluded to prevent infinite loop
  ]);

  // Refresh data when refreshTrigger changes
  useEffect(() => {
    if (refreshTrigger > 0) {
      refreshData();
    }
  }, [refreshTrigger, refreshData]);

  // Handle highlighting from search navigation
  useEffect(() => {
    if (
      location.state?.highlightId &&
      location.state?.entityType === "inspection"
    ) {
      setHighlightedInspId(location.state.highlightId);

      // Scroll to highlighted row after render
      setTimeout(() => {
        if (highlightedRowRef.current) {
          highlightedRowRef.current.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
        }
      }, 500);
    }
  }, [location.state]);

  // ✅ Sorting handler
  const handleSort = (fieldKey, directionKey = null) => {
    if (fieldKey === null) {
      setSortConfig({ key: null, direction: null });
    } else {
      setSortConfig({ key: fieldKey, direction: directionKey || "asc" });
    }
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.direction === "asc" ? (
      <ArrowUp size={14} />
    ) : (
      <ArrowDown size={14} />
    );
  };

  // Sort options for dropdown
  const sortFields = [
    { key: "code", label: "Inspection Code" },
    { key: "created_at", label: "Created Date" },
  ];

  // ✅ Pagination (using server-side pagination)
  const totalPages = Math.ceil(
    (paginationMeta?.count || filteredInspections.length) / pageSize
  );
  const totalInspections = paginationMeta?.count || filteredInspections.length;
  const filteredCount = totalInspections;

  // ✅ Selection
  const toggleSelect = (id) => {
    setSelectedInspections((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedInspections.length === inspections.length) {
      setSelectedInspections([]);
    } else {
      setSelectedInspections(inspections.map((i) => i.id));
    }
  };

  const handleBulkForwardClick = useCallback(() => {
    if (selectedInspections.length === 0) return;

    const selectedItems = inspections.filter((inspection) =>
      selectedInspections.includes(inspection.id)
    );

    if (selectedItems.length === 0) return;

    setIsBulkForward(true);

    const inspectionIds = selectedItems.map((item) => item.id);
    const isCombinedSection =
      currentUser?.section === "PD-1586,RA-8749,RA-9275";

    if (userLevel === "Section Chief" && isCombinedSection) {
      setPendingForwardAction({
        inspection: selectedItems[0],
        inspections: selectedItems,
        inspectionIds,
        action: "forward",
        forwardData: { target: "unit", remarks: "Forwarded to next level" },
      });
      openActionDialog({
        inspection: selectedItems[0],
        action: "forward",
      });
      return;
    }

    setPendingForwardAction({
      inspection: selectedItems[0],
      inspections: selectedItems,
      inspectionIds,
      action: "forward",
      forwardData: { target: "monitoring" },
    });
    setShowMonitoringModal(true);
  }, [
    selectedInspections,
    inspections,
    currentUser,
    userLevel,
    setPendingForwardAction,
    setShowMonitoringModal,
    openActionDialog,
  ]);

  // Toggle filter checkboxes
  const toggleLaw = (law) =>
    setLawFilter((prev) =>
      prev.includes(law) ? prev.filter((l) => l !== law) : [...prev, law]
    );

  // Clear functions
  const clearSearch = () => setSearchQuery("");
  const clearAllFilters = () => {
    setSearchQuery("");
    setSectionFilter([]);
    setLawFilter([]);
    setDateFrom("");
    setDateTo("");
    setShowOnlyMyAssignments(false);
    setSortConfig({ key: null, direction: null });
    setCurrentPage(1);
  };

  // Pagination functions
  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  const hasActiveFilters =
    searchQuery ||
    sectionFilter.length > 0 ||
    lawFilter.length > 0 ||
    dateFrom ||
    dateTo ||
    showOnlyMyAssignments ||
    sortConfig.key;
  const activeFilterCount =
    sectionFilter.length +
    lawFilter.length +
    (dateFrom ? 1 : 0) +
    (dateTo ? 1 : 0) +
    (showOnlyMyAssignments ? 1 : 0);

  // Calculate display range (for server-side pagination)
  const startItem = totalInspections > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = Math.min(currentPage * pageSize, totalInspections);

  // Helper function to get export/print columns based on activeTab
  const getExportColumns = useCallback(() => {
    if (activeTab === "nov_sent")
      return [
        "Code",
        "Establishments",
        "Law",
        "Compliance Deadline",
        "Deadline Status",
        "Status",
      ];
    if (activeTab === "noo_sent" && userLevel !== "Legal Unit")
      return [
        "Code",
        "Establishments",
        "Law",
        "Payment Deadline",
        "Payment Status",
        "Status",
      ];
    if (activeTab === "noo_sent" && userLevel === "Legal Unit")
      return ["Code", "Establishments", "Law", "Payment Deadline", "Status"];
    if (["section_assigned", "unit_assigned"].includes(activeTab))
      return [
        "Code",
        "Establishments",
        "Law",
        "Days Waiting",
        "Assigned Date",
        "Status",
      ];
    if (["section_in_progress", "unit_in_progress"].includes(activeTab))
      return [
        "Code",
        "Establishments",
        "Law",
        "Days Active",
        "Started Date",
        "Status",
      ];
    if (activeTab === "forwarded")
      return [
        "Code",
        "Establishments",
        "Law",
        "Days Since Forward",
        "Forwarded To",
        "Status",
      ];
    if (activeTab === "assigned")
      return ["Code", "Establishments", "Law", "Assigned Date", "Status"];
    if (activeTab === "in_progress")
      return [
        "Code",
        "Establishments",
        "Law",
        "Days Active",
        "Last Activity",
        "Status",
      ];
    if (activeTab === "inspection_complete")
      return ["Code", "Establishments", "Law", "Status"];
    if (activeTab === "review" || activeTab === "under_review")
      return ["Code", "Establishments", "Law", "Submitted On", "Status"];
    if (activeTab === "compliant")
      return ["Code", "Establishments", "Law", "Status"];
    if (activeTab === "non_compliant")
      return ["Code", "Establishments", "Law", "Status"];
    if (activeTab === "reviewed")
      return ["Code", "Establishments", "Law", "Reviewed On", "Status"];
    if (activeTab === "returned_inspection")
      return ["Code", "Establishments", "Law", "Return Remarks", "Status"];
    if (activeTab === "returned_reports")
      return ["Code", "Establishments", "Law", "Return Remarks", "Status"];
    return ["Code", "Establishments", "Law", "Status"];
  }, [activeTab, userLevel]);

  // Helper function to get export/print rows based on activeTab
  const getExportRows = useCallback(
    (inspectionList) => {
      return inspectionList.map((inspection) => {
        if (activeTab === "nov_sent") {
          const deadlineStatus = getDeadlineStatus(
            inspection.form?.nov?.compliance_deadline
          );
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.form?.nov?.compliance_deadline
              ? new Date(
                  inspection.form.nov.compliance_deadline
                ).toLocaleDateString()
              : "No deadline",
            deadlineStatus.text,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "noo_sent" && userLevel !== "Legal Unit") {
          const paymentStatus = getPaymentStatus(inspection.form?.noo);
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.form?.noo?.payment_deadline
              ? new Date(
                  inspection.form.noo.payment_deadline
                ).toLocaleDateString()
              : "No deadline",
            paymentStatus.text,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "noo_sent" && userLevel === "Legal Unit") {
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.form?.noo?.payment_deadline
              ? new Date(
                  inspection.form.noo.payment_deadline
                ).toLocaleDateString()
              : "No deadline",
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (["section_assigned", "unit_assigned"].includes(activeTab)) {
          const assignmentAge = getAssignmentAge(inspection.updated_at);
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            assignmentAge.text,
            formatDate(inspection.updated_at),
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (
          ["section_in_progress", "unit_in_progress"].includes(activeTab)
        ) {
          const daysActive = getAssignmentAge(inspection.updated_at);
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            daysActive.text,
            formatDate(inspection.updated_at),
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "forwarded") {
          const forwardedAge = getAssignmentAge(inspection.updated_at);
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            forwardedAge.text,
            inspection.assigned_to_name || "Not assigned",
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "assigned") {
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            formatDate(inspection.updated_at),
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "in_progress") {
          const daysActive = getAssignmentAge(inspection.updated_at);
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            daysActive.text,
            formatDate(inspection.form?.updated_at || inspection.updated_at),
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "inspection_complete") {
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "review" || activeTab === "under_review") {
          const submissionAge = getSubmissionAge(
            inspection.form?.updated_at || inspection.updated_at
          );
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            submissionAge.text,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "compliant") {
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "non_compliant") {
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "reviewed") {
          const reviewedDate =
            inspection.reviewed_at ||
            inspection.form?.updated_at ||
            inspection.updated_at;
          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            reviewedDate ? new Date(reviewedDate).toLocaleDateString() : "N/A",
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "returned_inspection") {
          // Extract return remarks same way as in table display
          let returnRemarks = null;
          if (inspection.return_remarks) {
            returnRemarks = inspection.return_remarks;
          } else if (inspection.history && Array.isArray(inspection.history)) {
            const returnEntry = inspection.history
              .filter((h) => h.remarks && h.remarks.includes("Returned"))
              .sort(
                (a, b) => new Date(b.created_at) - new Date(a.created_at)
              )[0];
            if (returnEntry) {
              const remarks = returnEntry.remarks;
              returnRemarks = remarks.includes(":")
                ? remarks.split(":")[1].trim()
                : remarks;
            }
          }

          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            returnRemarks || "N/A",
            inspection.simplified_status || inspection.current_status,
          ];
        } else if (activeTab === "returned_reports") {
          // Extract return remarks same way as in table display
          let returnRemarks = null;
          if (inspection.return_remarks) {
            returnRemarks = inspection.return_remarks;
          } else if (inspection.history && Array.isArray(inspection.history)) {
            const returnEntry = inspection.history
              .filter((h) => h.remarks && h.remarks.includes("Returned"))
              .sort(
                (a, b) => new Date(b.created_at) - new Date(a.created_at)
              )[0];
            if (returnEntry) {
              const remarks = returnEntry.remarks;
              returnRemarks = remarks.includes(":")
                ? remarks.split(":")[1].trim()
                : remarks;
            }
          }

          return [
            inspection.code,
            inspection.establishments_detail &&
            inspection.establishments_detail.length > 0
              ? inspection.establishments_detail
                  .map((est) => est.name)
                  .join(", ")
              : "No establishments",
            inspection.law,
            returnRemarks || "N/A",
            inspection.simplified_status || inspection.current_status,
          ];
        }
        return [
          inspection.code,
          inspection.establishments_detail &&
          inspection.establishments_detail.length > 0
            ? inspection.establishments_detail.map((est) => est.name).join(", ")
            : "No establishments",
          inspection.law,
          inspection.simplified_status || inspection.current_status,
        ];
      });
    },
    [activeTab, userLevel]
  );

  const toolbarActions = useMemo(() => {
    const actions = [];

    const normalizedUserLevel = currentUser?.userlevel || userLevel;

    if (
      (normalizedUserLevel === "Section Chief" ||
        normalizedUserLevel === "Unit Head") &&
      selectedInspections.length > 0
    ) {
      actions.push({
        onClick: handleBulkForwardClick,
        icon: Send,
        title: "Forward Selected",
        text: "Forward Selected",
        variant: "primary",
      });
    }

    if (normalizedUserLevel === "Division Chief") {
      actions.push({
        onClick: onAdd,
        icon: Plus,
        title: "Add Inspection",
        text: "Add Inspection",
        variant: "primary",
      });
    }

    return actions;
  }, [
    currentUser?.userlevel,
    userLevel,
    selectedInspections.length,
    handleBulkForwardClick,
    onAdd,
  ]);

  // Custom filters dropdown
  const customFiltersDropdown = useMemo(() => {
    return (
      <div className="absolute right-0 z-20 w-64 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto custom-scrollbar">
        <div className="p-2">
          {/* Header with Clear All */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Filters
            </div>
            {activeFilterCount > 0 && (
              <button
                onClick={() => {
                  setSectionFilter([]);
                  setLawFilter([]);
                  setDateFrom("");
                  setDateTo("");
                  setShowOnlyMyAssignments(false);
                }}
                className="px-2 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
              >
                Clear All
              </button>
            )}
          </div>

          {/* Assignment Filter */}
          {(userLevel === "Section Chief" ||
            userLevel === "Unit Head" ||
            userLevel === "Monitoring Personnel") && (
            <div className="mb-2">
              <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
                Assignment
              </div>
              <button
                onClick={() => setShowOnlyMyAssignments(!showOnlyMyAssignments)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                  showOnlyMyAssignments ? "bg-sky-50 font-medium" : ""
                }`}
              >
                <div className="flex-1 text-left">
                  <div className="font-medium">My Assignments Only</div>
                  <div className="text-xs text-gray-500">
                    Show only inspections assigned to me
                  </div>
                </div>
                {showOnlyMyAssignments && (
                  <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
                )}
              </button>
            </div>
          )}

          {/* Law Section */}
          <div className="mb-2">
            <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
              Law
            </div>
            {availableLaws.length === 0 ? (
              <div className="px-3 py-2 text-xs text-gray-500 italic">
                No laws available
              </div>
            ) : (
              availableLaws.map((law) => (
                <button
                  key={law}
                  onClick={() => toggleLaw(law)}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                    lawFilter.includes(law) ? "bg-sky-50 font-medium" : ""
                  }`}
                >
                  <div className="flex-1 text-left">
                    <div className="font-medium">{law}</div>
                  </div>
                  {lawFilter.includes(law) && (
                    <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    );
  }, [
    filtersOpen,
    lawFilter,
    showOnlyMyAssignments,
    availableLaws,
    userLevel,
    activeFilterCount,
    toggleLaw,
  ]);

  // Removed handleRowClick to prevent navigation on row click

  const renderPreviewButton = useCallback(
    (inspectionId, tab) => (
      <button
        onClick={() =>
          navigate(
            `/inspections/${inspectionId}/review?mode=preview${
              tab ? `&tab=${tab}` : ""
            }`
          )
        }
        className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
      >
        <Eye size={14} />
        Preview
      </button>
    ),
    [navigate]
  );

  const renderDivisionChiefReviewButton = useCallback(
    (inspectionId) => (
      <button
        onClick={() => handleActionClick("review", inspectionId)}
        className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
      >
        <Eye size={14} />
        Review
      </button>
    ),
    [handleActionClick]
  );

  return (
    <div className="p-4 bg-white h-[calc(100vh-160px)]">
      {/* Top controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <h1 className="text-2xl font-bold text-sky-600">
            Inspections Management
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <TableToolbar
            searchValue={searchQuery}
            onSearchChange={setSearchQuery}
            onSearchClear={clearSearch}
            searchPlaceholder="Search..."
            sortConfig={sortConfig}
            sortFields={sortFields}
            onSort={handleSort}
            onFilterClick={() => setFiltersOpen(!filtersOpen)}
            customFilterDropdown={filtersOpen ? customFiltersDropdown : null}
            filterOpen={filtersOpen}
            onFilterClose={() => setFiltersOpen(false)}
            dateFrom={dateFrom}
            dateTo={dateTo}
            onDateFromChange={setDateFrom}
            onDateToChange={setDateTo}
            onRefresh={handleManualRefresh}
            isRefreshing={refreshing || loading}
            exportConfig={
              canExportAndPrint(userLevel, "inspections")
                ? {
                    title: "Inspections Export Report",
                    fileName:
                      activeTab === "nov_sent"
                        ? "nov_inspections_export"
                        : activeTab === "review" || activeTab === "under_review"
                        ? "review_inspections_export"
                        : activeTab === "reviewed"
                        ? "reviewed_inspections_export"
                        : activeTab === "inspection_complete"
                        ? "inspection_complete_export"
                        : "inspections_export",
                    columns: getExportColumns(),
                    rows: getExportRows(
                      selectedInspections.length > 0
                        ? selectedInspections
                        : inspections
                    ),
                  }
                : undefined
            }
            printConfig={
              canExportAndPrint(userLevel, "inspections")
                ? {
                    title: "Inspections Report",
                    fileName: "inspections_report",
                    columns: getExportColumns(),
                    rows: getExportRows(
                      selectedInspections.length > 0
                        ? selectedInspections
                        : inspections
                    ),
                    selectedCount: selectedInspections.length,
                  }
                : undefined
            }
            additionalActions={toolbarActions}
          />
        </div>
      </div>

      {/* Role-based Tabs */}
      <InspectionTabs
        userLevel={userLevel}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        tabCounts={tabCounts}
      />

      {/* Table Container with Scroll */}
      <div className="overflow-auto border border-gray-300 rounded h-[calc(100vh-315px)] scroll-smooth custom-scrollbar">
        <table className="w-full min-w-[800px]">
          <thead>
            <tr className="text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700 sticky top-0 z-10">
              <th className="w-6 px-3 py-2 text-center border-b border-gray-300">
                <input
                  type="checkbox"
                  checked={
                    selectedInspections.length > 0 &&
                    selectedInspections.length === inspections.length
                  }
                  onChange={toggleSelectAll}
                />
              </th>
              <th
                className="px-3 py-2 border-b border-gray-300 cursor-pointer"
                onClick={() => handleSort("code")}
              >
                <div className="flex items-center gap-1">
                  Code {getSortIcon("code")}
                </div>
              </th>
              <th className="px-3 py-2 border-b border-gray-300">
                Establishments
              </th>
              <th className="px-3 py-2 border-b border-gray-300">Law</th>

              {/* Conditionally show NOV-specific columns */}
              {activeTab === "nov_sent" && (
                <>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Compliance Deadline
                  </th>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Deadline Status
                  </th>
                </>
              )}

              {/* Conditionally show NOO-specific columns */}
              {activeTab === "noo_sent" && userLevel !== "Legal Unit" && (
                <>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Payment Deadline
                  </th>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Payment Status
                  </th>
                </>
              )}
              {activeTab === "noo_sent" && userLevel === "Legal Unit" && (
                <>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Payment Deadline
                  </th>
                </>
              )}

              {/* Conditionally show Under Review columns */}
              {(activeTab === "under_review" || activeTab === "review") && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Submitted On
                  </th>
                </>
              )}
              {activeTab === "reviewed" && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Reviewed On
                  </th>
                </>
              )}

              {/* Conditionally show Assigned columns */}
              {["section_assigned", "unit_assigned"].includes(activeTab) && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Days Waiting
                  </th>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Assigned Date
                  </th>
                </>
              )}

              {/* Conditionally show In Progress columns for Section/Unit */}
              {["section_in_progress", "unit_in_progress"].includes(
                activeTab
              ) && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Days Active
                  </th>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Started Date
                  </th>
                </>
              )}

              {/* Conditionally show Forwarded columns */}
              {activeTab === "forwarded" && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Days Since Forward
                  </th>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Forwarded To
                  </th>
                </>
              )}

              {/* Conditionally show Compliance columns */}
              {/* Conditionally show Assigned columns (Monitoring Personnel) */}
              {activeTab === "assigned" && (
                <>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Assigned Date
                  </th>
                </>
              )}

              {/* Conditionally show In Progress columns (Monitoring Personnel) */}
              {activeTab === "in_progress" && (
                <>
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Days Active
                  </th>
                  <th className="px-3 py-2 border-b border-gray-300">
                    Last Activity
                  </th>
                </>
              )}

              <th className="px-3 py-2 text-center border-b border-gray-300">
                Status
              </th>
              {!(
                currentUser?.userlevel === "Admin" &&
                activeTab === "all_inspections"
              ) &&
                !(
                  currentUser?.userlevel === "Division Chief" &&
                  activeTab === "all_inspections"
                ) && (
                  <th className="px-3 py-2 text-center border-b border-gray-300">
                    Actions
                  </th>
                )}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={getTabColspan(activeTab, userLevel)}
                  className="px-2 py-6 text-center text-gray-500 border-b border-gray-300"
                >
                  <div
                    className="flex flex-col items-center justify-center p-4"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="w-8 h-8 mb-2 border-b-2 border-gray-900 rounded-full animate-spin"></div>
                    <p className="text-sm text-gray-600">
                      Loading inspections...
                    </p>
                  </div>
                </td>
              </tr>
            ) : filteredInspections.length === 0 ? (
              <tr>
                <td
                  colSpan={getTabColspan(activeTab, userLevel)}
                  className="px-2 py-8 border-b border-gray-300"
                >
                  <div className="flex flex-col items-center justify-center text-sm text-gray-600 text-center space-y-2">
                    {hasActiveFilters ? (
                      <>
                        <span>
                          No inspections found matching your criteria.
                        </span>
                        <button
                          onClick={clearAllFilters}
                          className="underline text-sky-600 hover:text-sky-700"
                        >
                          Clear all filters
                        </button>
                      </>
                    ) : (
                      <span>{getEmptyStateMessage(activeTab, userLevel)}</span>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              filteredInspections.map((inspection) => {
                // NOV tab data
                const deadlineStatus =
                  activeTab === "nov_sent"
                    ? getDeadlineStatus(
                        inspection.form?.nov?.compliance_deadline
                      )
                    : null;

                // NOO tab data
                const paymentStatus =
                  activeTab === "noo_sent"
                    ? getPaymentStatus(inspection.form?.noo)
                    : null;

                // Review tab data
                const submissionAge =
                  activeTab === "under_review" || activeTab === "review"
                    ? getSubmissionAge(
                        inspection.form?.updated_at || inspection.updated_at
                      )
                    : null;
                const reviewedDate =
                  activeTab === "reviewed"
                    ? inspection.reviewed_at ||
                      inspection.form?.updated_at ||
                      inspection.updated_at
                    : null;

                // Assigned tab data
                const assignmentAge = [
                  "section_assigned",
                  "unit_assigned",
                ].includes(activeTab)
                  ? getAssignmentAge(inspection.updated_at)
                  : null;

                // In Progress tab data
                const daysActive =
                  ["section_in_progress", "unit_in_progress"].includes(
                    activeTab
                  ) || activeTab === "in_progress"
                    ? getAssignmentAge(inspection.updated_at)
                    : null;

                // Forwarded tab data
                const forwardedAge =
                  activeTab === "forwarded"
                    ? getAssignmentAge(inspection.updated_at)
                    : null;

                // Returned tabs: remarks are shown via modal button in Actions

                // Compliance / Completed tab data

                return (
                  <tr
                    key={inspection.id}
                    ref={
                      inspection.id === highlightedInspId
                        ? highlightedRowRef
                        : null
                    }
                    className={`text-xs border-b border-gray-300 hover:bg-gray-50 transition-colors ${
                      inspection.id === highlightedInspId
                        ? "search-highlight-persist"
                        : ""
                    } ${deadlineStatus?.bgColor || ""}`}
                    onClick={() => setHighlightedInspId(inspection.id)}
                  >
                    <td className="px-3 py-2 text-center border-b border-gray-300">
                      <input
                        type="checkbox"
                        checked={selectedInspections.includes(inspection.id)}
                        onChange={() => toggleSelect(inspection.id)}
                      />
                    </td>
                    <td className="px-3 py-2 font-semibold border-b border-gray-300">
                      {inspection.code}
                    </td>
                    <td className="px-3 py-2 border-b border-gray-300">
                      {inspection.establishments_detail &&
                      inspection.establishments_detail.length > 0
                        ? inspection.establishments_detail
                            .map((e) => e.name)
                            .join(", ")
                        : "No establishments"}
                    </td>
                    <td className="px-3 py-2 border-b border-gray-300">
                      {inspection.law}
                    </td>

                    {/* Conditionally show NOV-specific data */}
                    {activeTab === "nov_sent" && (
                      <>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {inspection.form?.nov?.compliance_deadline
                            ? new Date(
                                inspection.form.nov.compliance_deadline
                              ).toLocaleDateString()
                            : "No deadline"}
                        </td>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${deadlineStatus?.color}`}
                        >
                          <div className="flex items-center justify-center gap-1">
                            {deadlineStatus?.status === "overdue" && (
                              <AlertCircle className="w-3 h-3" />
                            )}
                            {deadlineStatus?.status === "urgent" && (
                              <Clock className="w-3 h-3" />
                            )}
                            <span>{deadlineStatus?.text}</span>
                          </div>
                        </td>
                      </>
                    )}

                    {/* Conditionally show NOO-specific data */}
                    {activeTab === "noo_sent" && userLevel !== "Legal Unit" && (
                      <>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {inspection.form?.noo?.payment_deadline
                            ? formatDate(inspection.form.noo.payment_deadline)
                            : "No deadline"}
                        </td>
                        <td className="px-3 py-2 text-center border-b border-gray-300">
                          <span
                            className={`px-2 py-0.5 text-xs rounded-full ${paymentStatus?.color}`}
                          >
                            {paymentStatus?.text}
                            {paymentStatus?.daysOverdue > 0 &&
                              ` (${paymentStatus.daysOverdue}d)`}
                          </span>
                        </td>
                      </>
                    )}
                    {activeTab === "noo_sent" && userLevel === "Legal Unit" && (
                      <>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {inspection.form?.noo?.payment_deadline
                            ? formatDate(inspection.form.noo.payment_deadline)
                            : "No deadline"}
                        </td>
                      </>
                    )}

                    {/* Conditionally show Under Review data */}
                    {(activeTab === "under_review" ||
                      activeTab === "review") && (
                      <>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${submissionAge?.color}`}
                        >
                          {submissionAge?.text}
                        </td>
                      </>
                    )}
                    {activeTab === "reviewed" && (
                      <>
                        <td className="px-3 py-2 text-center border-b border-gray-300">
                          {reviewedDate
                            ? new Date(reviewedDate).toLocaleDateString()
                            : "N/A"}
                        </td>
                      </>
                    )}

                    {/* Conditionally show Assigned columns */}
                    {["section_assigned", "unit_assigned"].includes(
                      activeTab
                    ) && (
                      <>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${assignmentAge?.color}`}
                        >
                          {assignmentAge?.text}
                        </td>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {formatDate(inspection.updated_at)}
                        </td>
                      </>
                    )}

                    {/* Conditionally show Section/Unit In Progress columns */}
                    {["section_in_progress", "unit_in_progress"].includes(
                      activeTab
                    ) && (
                      <>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${daysActive?.color}`}
                        >
                          {daysActive?.text}
                        </td>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {formatDate(inspection.updated_at)}
                        </td>
                      </>
                    )}

                    {/* Conditionally show Forwarded columns */}
                    {activeTab === "forwarded" && (
                      <>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${forwardedAge?.color}`}
                        >
                          {forwardedAge?.text}
                        </td>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {inspection.assigned_to_name || "Not assigned"}
                        </td>
                      </>
                    )}

                    {/* Conditionally show Compliance columns */}
                    {/* Conditionally show Assigned columns (Monitoring Personnel) */}
                    {activeTab === "assigned" && (
                      <>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {formatDate(inspection.updated_at)}
                        </td>
                      </>
                    )}

                    {/* Conditionally show In Progress columns (Monitoring Personnel) */}
                    {activeTab === "in_progress" && (
                      <>
                        <td
                          className={`px-3 py-2 text-center border-b border-gray-300 ${daysActive?.color}`}
                        >
                          {daysActive?.text}
                        </td>
                        <td className="px-3 py-2 border-b border-gray-300">
                          {formatDate(
                            inspection.form?.updated_at || inspection.updated_at
                          )}
                        </td>
                      </>
                    )}

                    <td className="px-3 py-2 text-center border-b border-gray-300">
                      <StatusBadge status={inspection.current_status} />
                    </td>
                    {!(
                      currentUser?.userlevel === "Admin" &&
                      activeTab === "all_inspections"
                    ) &&
                      !(
                        currentUser?.userlevel === "Division Chief" &&
                        activeTab === "all_inspections"
                      ) && (
                        <td
                          className="px-3 py-2 text-center border-b border-gray-300"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {activeTab === "inspection_complete" ? (
                            renderPreviewButton(inspection.id, activeTab)
                          ) : (
                            <div className="flex items-center justify-center gap-1">
                              {[
                                "returned_inspection",
                                "returned_reports",
                              ].includes(activeTab) ? (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openRemarksModal(inspection);
                                  }}
                                  className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-sky-700 bg-sky-50 border border-sky-200 rounded hover:bg-sky-100"
                                >
                                  View Return
                                </button>
                              ) : currentUser?.userlevel === "Division Chief" &&
                                activeTab === "reviewed" ? (
                                renderDivisionChiefReviewButton(inspection.id)
                              ) : shouldShowActions(userLevel, activeTab) ? (
                                <InspectionActions
                                  inspection={inspection}
                                  availableActions={(
                                    inspection.available_actions || []
                                  ).filter((action) => {
                                    // Remove return_to_monitoring for Section Chief in review tab
                                    if (
                                      userLevel === "Section Chief" &&
                                      activeTab === "review" &&
                                      action === "return_to_monitoring"
                                    ) {
                                      return false;
                                    }
                                    if (
                                      activeTab === "review" &&
                                      userLevel === "Division Chief"
                                    ) {
                                      return action === "review";
                                    }
                                    if (action !== "forward") {
                                      return true;
                                    }
                                    const status = inspection.current_status;
                                    if (
                                      status === "SECTION_IN_PROGRESS" &&
                                      userLevel === "Section Chief"
                                    ) {
                                      return false;
                                    }
                                    if (
                                      status === "UNIT_IN_PROGRESS" &&
                                      userLevel === "Unit Head"
                                    ) {
                                      return false;
                                    }
                                    if (
                                      status === "MONITORING_IN_PROGRESS" &&
                                      userLevel === "Monitoring Personnel"
                                    ) {
                                      return false;
                                    }
                                    return true;
                                  })}
                                  onAction={handleActionClick}
                                  loading={isActionLoading(inspection.id)}
                                  userLevel={userLevel}
                                />
                              ) : userLevel === "Legal Unit" &&
                                activeTab === "noo_sent" &&
                                inspection.current_status !==
                                  "CLOSED_NON_COMPLIANT" ? (
                                <button
                                  onClick={() =>
                                    navigate(
                                      `/inspections/${inspection.id}/review`
                                    )
                                  }
                                  className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
                                >
                                  <XCircle size={14} />
                                  Mark as Non-Compliance
                                </button>
                              ) : userLevel === "Legal Unit" &&
                                activeTab === "noo_sent" &&
                                inspection.current_status ===
                                  "CLOSED_NON_COMPLIANT" ? (
                                <div className="text-sm text-gray-500">
                                  No actions available
                                </div>
                              ) : ["compliant", "non_compliant"].includes(
                                  activeTab
                                ) ? (
                                [
                                  "Admin",
                                  "Division Chief",
                                  "Legal Unit",
                                ].includes(
                                  userLevel || currentUser?.userlevel
                                ) ? (
                                  <button
                                    onClick={() =>
                                      navigate(
                                        `/inspections/${inspection.id}/view`
                                      )
                                    }
                                    className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
                                  >
                                    <Eye size={14} />
                                    View Details
                                  </button>
                                ) : (
                                  <div className="text-sm text-gray-500">
                                    No actions available
                                  </div>
                                )
                              ) : userLevel === "Division Chief" &&
                                (activeTab === "review" ||
                                  activeTab ===
                                    "reviewed") ? null : userLevel ===
                                "Division Chief" ? (
                                <div className="text-sm text-gray-500">
                                  No actions available
                                </div>
                              ) : (
                                <button
                                  onClick={() =>
                                    navigate(
                                      `/inspections/${inspection.id}/view`
                                    )
                                  }
                                  className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-sky-600 rounded hover:bg-sky-700 transition-colors"
                                >
                                  <Eye size={14} />
                                  View Details
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-2">
        {/* Pagination Controls */}
        <PaginationControls
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={totalInspections}
          filteredItems={filteredCount}
          hasActiveFilters={hasActiveFilters}
          onPageChange={goToPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setCurrentPage(1);
          }}
          startItem={startItem}
          endItem={endItem}
          storageKey="inspections_list"
        />
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmationDialog
        open={deleteConfirmation.open}
        title="Delete Inspection"
        message={`Are you sure you want to delete inspection ${
          deleteConfirmation.inspection?.code ||
          deleteConfirmation.inspection?.id
        }? This action cannot be undone.${
          userLevel === "Admin"
            ? " As an Admin, you can delete any inspection."
            : ' Only inspections in "Created" status can be deleted.'
        }`}
        confirmText="Delete"
        cancelText="Cancel"
        confirmColor="red"
        size="md"
        onCancel={() =>
          setDeleteConfirmation({ open: false, inspection: null })
        }
        onConfirm={() => handleDeleteInspection(deleteConfirmation.inspection)}
      />

      {/* Action Confirmation Dialog */}
      {actionConfirmation.open &&
        (() => {
          const dialogContent = getActionDialogContent(
            actionConfirmation.action,
            actionConfirmation.inspection,
            userLevel,
            pendingForwardAction
          );
          const requireRemarks = actionRequiresRemarks(
            actionConfirmation.action
          );

          return (
            <ConfirmationDialog
              open={actionConfirmation.open}
              title={dialogContent.title}
              icon={dialogContent.icon}
              headerColor={dialogContent.headerColor}
              message={dialogContent.message}
              confirmText={dialogContent.confirmText}
              cancelText="Cancel"
              confirmColor={dialogContent.confirmColor}
              size="md"
              loading={actionLoading}
              onCancel={handleActionDialogCancel}
              onConfirm={executeAction}
            >
              {requireRemarks && (
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Remarks <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 break-words ${
                      remarksError ? "border-red-500" : "border-gray-300"
                    }`}
                    style={{
                      wordWrap: "break-word",
                      overflowWrap: "break-word",
                    }}
                    rows={4}
                    value={actionRemarks}
                    onChange={(event) => {
                      setActionRemarks(event.target.value);
                      if (remarksError) {
                        setRemarksError(null);
                      }
                    }}
                    placeholder="Provide detailed remarks for the return action"
                  />
                  <p className="text-xs text-gray-500">
                    Remarks are shared with the new assignee and included in the
                    audit trail.
                  </p>
                  {remarksError && (
                    <p className="text-xs text-red-600">{remarksError}</p>
                  )}
                </div>
              )}
            </ConfirmationDialog>
          );
        })()}

      {/* Monitoring Personnel Selection Modal */}
      <MonitoringPersonnelModal
        open={showMonitoringModal}
        inspection={pendingForwardAction?.inspection}
        onClose={handleMonitoringModalClose}
        onSelect={handleMonitoringPersonnelSelect}
        loading={actionLoading}
      />

      {/* Return Remarks Modal */}
      {remarksModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/20 backdrop-blur-sm">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
            {/* Header Section */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                <CornerDownLeft className="w-5 h-5 mr-2 text-orange-600" />
                Return Remarks
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyLatestRemarks}
                  className="px-3 py-1.5 text-xs font-medium text-sky-700 bg-sky-50 border border-sky-200 rounded-md hover:bg-sky-100 transition-colors"
                >
                  Copy
                </button>
                <button
                  onClick={closeRemarksModal}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content Section */}
            <div className="p-6 space-y-4">
              {/* Inspection Details */}
              {remarksModal.inspection && (
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="flex items-center mb-2">
                    <Building className="w-4 h-4 mr-2 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">
                      Inspection Details
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-500">Code:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {remarksModal.inspection.code}
                      </span>
                    </div>
                    {remarksModal.all?.length > 0 && (
                      <div>
                        <span className="text-gray-500">Returned by:</span>
                        <span className="ml-2 font-medium text-gray-900">
                          {remarksModal.all[0]?.changed_by_name || "—"}
                        </span>
                      </div>
                    )}
                    {remarksModal.all?.length > 0 && (
                      <div className="col-span-2">
                        <span className="text-gray-500">Date:</span>
                        <span className="ml-2 font-medium text-gray-900">
                          {new Date(
                            remarksModal.all[0]?.created_at
                          ).toLocaleString()}
                        </span>
                      </div>
                    )}
                    {remarksModal.all?.[0]?.previous_status &&
                      remarksModal.all[0]?.new_status && (
                        <div className="col-span-2">
                          <span className="text-gray-500">Status Change:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {remarksModal.all[0].previous_status} →{" "}
                            {remarksModal.all[0].new_status}
                          </span>
                        </div>
                      )}
                  </div>
                </div>
              )}

              {/* Latest Remarks */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Latest Remarks
                </label>
                <div className="bg-gray-50 p-4 rounded-md border border-gray-200">
                  <div className="text-sm text-gray-800 whitespace-pre-wrap">
                    {remarksModal.latest || "No remarks"}
                  </div>
                </div>
              </div>
            </div>

            {/* Footer Section */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
              <button
                onClick={closeRemarksModal}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => {
                  if (remarksModal.inspection?.id) {
                    closeRemarksModal();
                    navigate(`/inspections/${remarksModal.inspection.id}/form`);
                  }
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-sky-600 rounded-md hover:bg-sky-700 transition-colors flex items-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                Re-inspect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
