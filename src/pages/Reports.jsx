import { useState, useEffect } from "react";
import { Loader2, Download, RefreshCcw, Eraser, FileText } from "lucide-react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import ConfirmationDialog from "../components/common/ConfirmationDialog";
import ReportResultsTable from "../components/reports/ReportResultsTable";
import DynamicFilters from "../components/reports/DynamicFilters";
import {
  getAllowedReports,
  generateCentralizedReport,
  getFilterOptions,
} from "../services/reportsApi";
import { getProfile } from "../services/api";
import { useNotifications } from "../hooks/useNotifications";

// Helper function to load images as base64
const loadImageAsBase64 = async (imagePath) => {
  try {
    const response = await fetch(imagePath);
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error("Error loading image:", error);
    return null;
  }
};

// Report type descriptions mapping
const reportDescriptions = {
  user: "This report provides a consolidated overview of all registered users, including roles, activity logs, and account status.",
  establishment:
    "This report summarizes establishment profiles, compliance status, and inspection history.",
  law: "This report compiles all applicable environmental laws, regulations, and guidelines relevant to operational compliance.",
  quota:
    "This report outlines assigned quotas, accomplishments, and variance for the reporting period.",
  billing:
    "This report details all billing transactions, including assessments, issued statements, payments, and outstanding balances.",
  compliance:
    "This report enumerates all establishments that have fully complied with the applicable inspection requirements.",
  non_compliant:
    "This report lists all establishments that have outstanding deficiencies or violations requiring corrective action.",
  inspection:
    "This report provides inspection results, findings, corrective actions, and compliance status by period.",
  nov: "This report details all Notices of Violation (NOV) and Notices of Observation (NOO) issued within the reporting period.",
  noo: "This report details all Notices of Violation (NOV) and Notices of Observation (NOO) issued within the reporting period.",
  section_accomplishment:
    "This report provides section-level accomplishment data, including completed inspections and compliance metrics.",
  unit_accomplishment:
    "This report provides unit-level accomplishment data, including completed inspections and compliance metrics.",
  monitoring_accomplishment:
    "This report provides monitoring personnel accomplishment data, including completed inspections and compliance metrics.",
};

// Helper function to get report description
const getReportDescription = (reportType) => {
  return (
    reportDescriptions[reportType] ||
    "This report provides detailed information based on the selected filters and criteria."
  );
};

// Helper function to format reporting period
const formatReportingPeriod = (timeFilter, appliedFilters) => {
  if (timeFilter === "quarterly") {
    const quarterNames = {
      1: "Quarter 1",
      2: "Quarter 2",
      3: "Quarter 3",
      4: "Quarter 4",
    };
    const quarter =
      quarterNames[appliedFilters.quarter] || `Q${appliedFilters.quarter}`;
    return `${quarter} ${appliedFilters.year}`;
  } else if (timeFilter === "monthly") {
    const monthName = new Date(2000, appliedFilters.month - 1).toLocaleString(
      "default",
      { month: "long" }
    );
    return `${monthName} ${appliedFilters.year}`;
  } else if (timeFilter === "custom") {
    const formatDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    };
    const from = formatDate(appliedFilters.date_from);
    const to = formatDate(appliedFilters.date_to);
    return from && to ? `${from} – ${to}` : from || to || "Not specified";
  }
  return "Not specified";
};

const capitalizeWords = (str) => {
  if (!str) return str;
  return str
    .split(" ")
    .filter(Boolean)
    .map((w) =>
      w.charAt(0) ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w
    )
    .join(" ");
};

export default function Reports() {
  const notifications = useNotifications();

  // State management
  const [allowedReports, setAllowedReports] = useState([]);
  const [selectedReportType, setSelectedReportType] = useState(null);
  const [timeFilter, setTimeFilter] = useState("quarterly");
  // Helper to get current quarter/month/year
  const getCurrentPeriod = () => {
    const now = new Date();
    const month = now.getMonth() + 1; // 1-12
    const year = now.getFullYear();
    const quarter = Math.floor((month - 1) / 3) + 1;
    return { quarter, month, year };
  };

  const CURRENT = getCurrentPeriod();

  // Filter state (what user types)
  const [filters, setFilters] = useState({
    quarter: CURRENT.quarter,
    year: CURRENT.year,
    month: CURRENT.month,
    date_from: "",
    date_to: "",
  });

  // Applied filter state (what filters are actually applied to the query)
  const [appliedFilters, setAppliedFilters] = useState({
    quarter: CURRENT.quarter,
    year: CURRENT.year,
    month: CURRENT.month,
    date_from: "",
    date_to: "",
  });

  const [extraFilters, setExtraFilters] = useState({});
  const [appliedExtraFilters, setAppliedExtraFilters] = useState({});
  const [filterOptions, setFilterOptions] = useState({});
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingAccess, setLoadingAccess] = useState(true);
  const [error, setError] = useState(null);

  // Confirmation dialog state
  const [confirmationDialog, setConfirmationDialog] = useState({
    open: false,
    action: null, // 'clear', 'exportPDF', 'exportCSV'
    loading: false,
  });

  // PDF settings state
  const [pdfSettings, setPdfSettings] = useState({
    open: false,
    paperSize: "a4",
    orientation: "portrait",
  });

  // Button style constants
  const BUTTON_BASE =
    "inline-flex items-center justify-center gap-2 px-3 py-1 text-sm font-medium transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";
  const BUTTON_SUBTLE = `${BUTTON_BASE} border border-gray-200 py-1.5 text-gray-700 hover:bg-gray-50`;
  const BUTTON_MUTED = `${BUTTON_BASE} border border-gray-200 text-gray-700 hover:bg-gray-50`;
  const BUTTON_PRIMARY = `${BUTTON_BASE} bg-sky-600 text-white hover:bg-sky-700`;

  // Load allowed reports on mount
  useEffect(() => {
    loadAllowedReports();
  }, []);

  // Load filter options when report type changes
  useEffect(() => {
    if (selectedReportType) {
      loadFilterOptions(selectedReportType);
      setExtraFilters({});
      setAppliedExtraFilters({});
      setReportData(null);
    }
  }, [selectedReportType]);

  const loadAllowedReports = async () => {
    try {
      setLoadingAccess(true);
      const data = await getAllowedReports();
      setAllowedReports(data.allowed_reports || []);

      if (data.allowed_reports && data.allowed_reports.length > 0) {
        setSelectedReportType(data.allowed_reports[0].report_type);
      }
    } catch (err) {
      console.error("Error loading allowed reports:", err);
      setError("Failed to load available reports. Please try again.");
      notifications?.error("Failed to load available reports");
    } finally {
      setLoadingAccess(false);
    }
  };

  const loadFilterOptions = async (reportType) => {
    try {
      const options = await getFilterOptions(reportType);
      setFilterOptions(options);
    } catch (err) {
      console.error("Error loading filter options:", err);
      notifications?.warning("Failed to load some filter options");
    }
  };

  // Handle filter change (doesn't apply filters, just updates input)
  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  // Apply filters - copies filters to appliedFilters and triggers generation
  const handleApplyFilters = () => {
    // Copy filters into applied state for UI
    setAppliedFilters(filters);
    setAppliedExtraFilters(extraFilters);

    // Immediately generate using the freshly applied values (avoid stale state)
    handleGenerateReport(filters, extraFilters);
  };

  // Clear filters - with confirmation
  const handleClearFiltersClick = () => {
    setConfirmationDialog({
      open: true,
      action: "clear",
      loading: false,
    });
  };

  const handleClearFilters = async () => {
    try {
      const clearedFilters = {
        quarter: CURRENT.quarter,
        year: CURRENT.year,
        month: CURRENT.month,
        date_from: "",
        date_to: "",
      };
      setFilters(clearedFilters);
      setAppliedFilters(clearedFilters);
      setExtraFilters({});
      setAppliedExtraFilters({});
      setTimeFilter("quarterly");
      setReportData(null);
      notifications?.info("Filters cleared successfully");
    } finally {
      setConfirmationDialog({ open: false, action: null, loading: false });
    }
  };

  // Generate report. Accept optional filters to avoid relying on state updates
  // which are async in React. If `applied` params are provided, they take
  // precedence; otherwise fall back to current state.
  const handleGenerateReport = async (
    appliedFiltersParam = null,
    appliedExtraFiltersParam = null
  ) => {
    try {
      setLoading(true);
      setError(null);

      // Use provided applied filters when available to avoid stale state
      const usedAppliedFilters = appliedFiltersParam || appliedFilters;
      const usedAppliedExtra = appliedExtraFiltersParam || appliedExtraFilters;

      const payload = {
        report_type: selectedReportType,
        time_filter: timeFilter,
        extra_filters: usedAppliedExtra,
      };

      if (timeFilter === "quarterly") {
        payload.quarter = usedAppliedFilters.quarter;
        payload.year = usedAppliedFilters.year;
      } else if (timeFilter === "monthly") {
        payload.month = usedAppliedFilters.month;
        payload.year = usedAppliedFilters.year;
      } else if (timeFilter === "custom") {
        payload.date_from = usedAppliedFilters.date_from;
        payload.date_to = usedAppliedFilters.date_to;
      }

      if (timeFilter === "custom" && (!payload.date_from || !payload.date_to)) {
        setError(
          "Please select both start and end dates for custom date range"
        );
        notifications?.error("Please select both start and end dates");
        setLoading(false);
        return;
      }

      const data = await generateCentralizedReport(payload);
      setReportData(data);
      notifications?.success("Report generated successfully");
    } catch (err) {
      console.error("Error generating report:", err);
      const errorMsg =
        err.response?.data?.error ||
        err.response?.data?.detail ||
        "Failed to generate report";
      setError(errorMsg);
      notifications?.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Manual refresh function
  const handleRefresh = () => {
    if (reportData) {
      handleGenerateReport();
      notifications?.info("Refreshing report...");
    }
  };

  // Handle confirmation dialog actions
  const handleConfirmAction = async () => {
    try {
      switch (confirmationDialog.action) {
        case "clear":
          await handleClearFilters();
          break;
        case "exportPDF":
          await handleExportPDF();
          break;
        case "exportCSV":
          await handleExportCSV();
          break;
        default:
          setConfirmationDialog({ open: false, action: null, loading: false });
      }
    } catch (error) {
      console.error("Error in confirmation action:", error);
      setConfirmationDialog({ open: false, action: null, loading: false });
    }
  };

  const handleCancelAction = () => {
    setConfirmationDialog({ open: false, action: null, loading: false });
  };

  // Get confirmation dialog props based on action
  const getConfirmationProps = () => {
    switch (confirmationDialog.action) {
      case "clear":
        return {
          title: "Clear Filters",
          message:
            "Are you sure you want to clear all filters? This will reset all filter values to their defaults.",
          confirmText: "Clear Filters",
          cancelText: "Cancel",
          confirmColor: "sky",
          headerColor: "sky",
        };
      case "exportPDF":
        return {
          title: "Export to PDF",
          message:
            "This will generate and download a PDF report with the current filtered data. Do you want to continue?",
          confirmText: "Export PDF",
          cancelText: "Cancel",
          confirmColor: "sky",
          headerColor: "sky",
        };
      case "exportCSV":
        return {
          title: "Export to CSV",
          message:
            "This will generate and download a CSV file with the current filtered data. Do you want to continue?",
          confirmText: "Export CSV",
          cancelText: "Cancel",
          confirmColor: "sky",
          headerColor: "sky",
        };
      default:
        return {
          title: "Confirm Action",
          message: "Are you sure you want to proceed?",
          confirmText: "Confirm",
          cancelText: "Cancel",
          confirmColor: "sky",
          headerColor: "sky",
        };
    }
  };

  // Click handlers that open confirmation dialogs
  const handleExportPDFClick = () => {
    if (!reportData || !reportData.rows || reportData.rows.length === 0) {
      notifications?.warning("No data to export");
      return;
    }
    // Open PDF settings modal instead of confirmation
    setPdfSettings((prev) => ({ ...prev, open: true }));
  };

  const handleExportCSVClick = () => {
    if (!reportData || !reportData.rows || reportData.rows.length === 0) {
      notifications?.warning("No data to export");
      return;
    }
    setConfirmationDialog({
      open: true,
      action: "exportCSV",
      loading: false,
    });
  };

  // Actual export functions (called after confirmation)
  const handleExportPDF = async (
    paperSize = "a4",
    orientation = "portrait"
  ) => {
    try {
      setPdfSettings((prev) => ({ ...prev, open: false }));

      const doc = new jsPDF({
        orientation: orientation,
        unit: "mm",
        format: paperSize,
      });

      doc.setFont("times", "normal");

      const pageWidth = doc.internal.pageSize.getWidth();
      const safeDate = new Date().toISOString().split("T")[0];
      const exportId = `RPT-${Date.now()}`;

      doc.setFontSize(8);
      doc.setFont("times", "bold");
      doc.text(`${exportId}`, pageWidth - 10, 10, { align: "right" });
      doc.text(`${safeDate}`, pageWidth - 10, 14, { align: "right" });
      doc.setFont("times", "normal");

      const logo1Data = await loadImageAsBase64("/assets/document/logo1.png");
      const logo2Data = await loadImageAsBase64("/assets/document/logo2.png");

      const logoWidth = 20;
      const logoHeight = 20;
      const logoY = 17;

      const titleText = "Integrated Establishment Regulatory Management System";
      const titleTextWidth = doc.getTextWidth(titleText);

      const leftLogoX = pageWidth / 2 - titleTextWidth / 2 - logoWidth - 30;
      const rightLogoX = pageWidth / 2 + titleTextWidth / 2 + 30;

      if (logo1Data) {
        doc.addImage(logo1Data, "PNG", leftLogoX, logoY, logoWidth, logoHeight);
      }

      if (logo2Data) {
        doc.addImage(
          logo2Data,
          "PNG",
          rightLogoX,
          logoY,
          logoWidth,
          logoHeight
        );
      }

      doc.setFontSize(14);
      doc.setTextColor(0, 0, 0);
      doc.text(
        "Integrated Establishment Regulatory Management System",
        pageWidth / 2,
        24,
        { align: "center" }
      );
      doc.text(
        "Department of Environmental and Natural Resources",
        pageWidth / 2,
        29,
        { align: "center" }
      );
      doc.text("Environmental Management Bureau Region I", pageWidth / 2, 34, {
        align: "center",
      });

      // Generate report title based on report type and filters
      const reportTypeName =
        allowedReports.find((r) => r.report_type === selectedReportType)
          ?.display_name || selectedReportType;
      let reportTitle = reportTypeName;

      if (timeFilter === "quarterly") {
        reportTitle += ` - Q${appliedFilters.quarter} ${appliedFilters.year}`;
      } else if (timeFilter === "monthly") {
        const monthName = new Date(
          2000,
          appliedFilters.month - 1
        ).toLocaleString("default", { month: "long" });
        reportTitle += ` - ${monthName} ${appliedFilters.year}`;
      } else if (timeFilter === "custom") {
        reportTitle += ` - ${appliedFilters.date_from} to ${appliedFilters.date_to}`;
      }

      doc.setFont("times", "bold");
      doc.setFontSize(12);
      const titleUpper = reportTitle.toUpperCase();
      doc.text(titleUpper, pageWidth / 2, 46, { align: "center" });
      const titleWidth = doc.getTextWidth(titleUpper);
      doc.line(
        pageWidth / 2 - titleWidth / 2,
        48,
        pageWidth / 2 + titleWidth / 2,
        48
      );
      doc.setFont("times", "normal");

      // Add expanded description and reporting period information
      let currentY = 54;

      // Report Description Section Header
      doc.setFont("times", "bold");
      doc.setFontSize(10);
      doc.setTextColor(0, 0, 0);
      doc.text("Report Description", 20, currentY);
      currentY += 6;

      // Report description text
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.setTextColor(60, 60, 60);
      const description = getReportDescription(selectedReportType);
      const descriptionLines = doc.splitTextToSize(description, pageWidth - 40);
      descriptionLines.forEach((line) => {
        doc.text(line, 20, currentY);
        currentY += 5;
      });

      currentY += 4;

      // Report Information Section Header
      doc.setFont("times", "bold");
      doc.setFontSize(10);
      doc.setTextColor(0, 0, 0);
      doc.text("Report Information", 20, currentY);
      currentY += 6;

      // Generated report for line
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.setTextColor(60, 60, 60);
      doc.text(`Generated report for: ${reportTypeName}`, 20, currentY);
      currentY += 5;

      // Reporting period line
      const reportingPeriod = formatReportingPeriod(timeFilter, appliedFilters);
      doc.text(`Reporting Period: ${reportingPeriod}`, 20, currentY);
      currentY += 5;

      // Report generation date and time
      const generationDate = new Date().toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
      doc.text(`Generated on: ${generationDate}`, 20, currentY);
      currentY += 5;

      // Total records count
      if (reportData && reportData.rows) {
        const recordCount = reportData.rows.length;
        doc.text(`Total Records: ${recordCount}`, 20, currentY);
        currentY += 5;
      }

      // Data source information
      doc.text(
        "Data Source: Integrated Establishment Regulatory Management System",
        20,
        currentY
      );
      currentY += 5;

      // Purpose statement
      doc.setFont("times", "italic");
      doc.setFontSize(8);
      doc.setTextColor(100, 100, 100);
      const purposeText =
        "This document is system-generated and reflects the data available at the time of export. Prepared for internal documentation and official reference.";
      const purposeLines = doc.splitTextToSize(purposeText, pageWidth - 40);
      purposeLines.forEach((line) => {
        doc.text(line, 20, currentY);
        currentY += 4;
      });

      currentY += 4;

      // Reset font settings
      doc.setFont("times", "normal");
      doc.setFontSize(8);
      doc.setTextColor(0, 0, 0);

      // Prepare table data
      const tableColumns = reportData.columns.map((col) => col.label);
      const tableRows = reportData.rows.map((row) => {
        return reportData.columns.map((col) => {
          const raw = row[col.key];
          if (raw === null || raw === undefined || raw === "") return "N/A";
          // Format amount fields with peso sign
          const isAmountKey =
            col.key === "amount" ||
            (col.label && String(col.label).toLowerCase().includes("amount"));
          if (isAmountKey) {
            const num = parseFloat(raw) || 0;
            try {
              return `₱${num.toLocaleString("en-PH", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`;
            } catch {
              return `₱${num.toFixed(2)}`;
            }
          }
          return String(raw);
        });
      });

      autoTable(doc, {
        head: [tableColumns],
        body: tableRows,
        startY: currentY,
        styles: {
          fontSize: 8,
          font: "times",
          cellPadding: 1,
          lineWidth: 0.2,
          lineColor: [0, 0, 0],
          textColor: [0, 0, 0],
          fillColor: [255, 255, 255],
        },
        headStyles: {
          fillColor: [255, 255, 255],
          textColor: [0, 0, 0],
          fontSize: 10,
          font: "times",
          cellPadding: 1,
          fontStyle: "bold",
          lineWidth: 0.2,
          lineColor: [0, 0, 0],
        },
        margin: { left: 20, right: 20 },
        tableLineWidth: 0.2,
        tableLineColor: [0, 0, 0],
      });

      const pageHeight = doc.internal.pageSize.getHeight();
      const pageCount = doc.internal.getNumberOfPages();

      // Calculate Y positions dynamically (bottom margin area)
      const bottomMargin = 20;
      const pageNumberY = pageHeight - bottomMargin;
      const signatoryStartY = pageHeight - 60; // Position signatories 60mm from bottom

      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(10);
        doc.text(`Page ${i} of ${pageCount}`, pageWidth - 15, pageNumberY, {
          align: "right",
        });
      }

      // Add signatories on the last page
      doc.setPage(pageCount);

      // Get user profile for "Submitted by"
      let submittedByName = "System User";
      let submittedByUserLevel = "";
      try {
        const userProfile = await getProfile();
        if (userProfile) {
          const firstName = userProfile.first_name || "";
          const lastName = userProfile.last_name || "";
          submittedByName =
            `${firstName} ${lastName}`.trim() ||
            userProfile.email ||
            "System User";
          // Only title-case when it's a name (not an email) and not the fallback string
          if (
            submittedByName &&
            !submittedByName.includes("@") &&
            submittedByName !== "System User"
          ) {
            submittedByName = capitalizeWords(submittedByName);
          }
          submittedByUserLevel = userProfile.userlevel || "";
        }
      } catch (err) {
        console.warn("Could not fetch user profile for PDF:", err);
      }

      // Add spacing line above signatories
      doc.setDrawColor(200, 200, 200);
      doc.line(20, signatoryStartY - 3, pageWidth - 20, signatoryStartY - 3);

      // Signatories section
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.setTextColor(0, 0, 0);

      // Left side - Submitted by
      const leftX = 30;
      let leftY = signatoryStartY;

      // Submitted by section
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.setTextColor(0, 0, 0);
      doc.text("Submitted by:", leftX, leftY);
      leftY += 8;

      // Name line with underline
      doc.setFont("times", "bold");
      doc.setFontSize(10);
      doc.text(submittedByName, leftX, leftY);
      doc.setDrawColor(0, 0, 0);
      doc.line(leftX, leftY + 2, leftX + 60, leftY + 2);

      // User Level/Role
      leftY += 6;
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      if (submittedByUserLevel) {
        doc.text(submittedByUserLevel, leftX, leftY);
      }

      // Right side - Submitted to (positioned on right side)
      const rightSideX = pageWidth - 90; // Position for right column
      let rightY = signatoryStartY;
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.setTextColor(0, 0, 0);
      doc.text("Submitted to:", rightSideX, rightY);
      rightY += 8;

      // Position/Title line (Regional Director - position name, not a signature field)
      doc.setFont("times", "normal");
      doc.setFontSize(10);
      doc.text(capitalizeWords("Regional Director"), rightSideX, rightY);

      // Signature line below position
      rightY += 6;
      doc.setDrawColor(0, 0, 0);
      doc.line(rightSideX, rightY, rightSideX + 60, rightY);

      // Department/Bureau info
      rightY += 6;
      doc.setFont("times", "normal");
      doc.setFontSize(9);
      doc.text(
        capitalizeWords("Environmental Management Bureau"),
        rightSideX,
        rightY
      );
      rightY += 4;
      doc.text(capitalizeWords("Region I"), rightSideX, rightY);

      const blobUrl = doc.output("bloburl");
      window.open(blobUrl, "_blank");

      notifications?.success("PDF report exported successfully");
      setPdfSettings((prev) => ({ ...prev, open: false }));
    } catch (err) {
      console.error("Error exporting PDF:", err);
      notifications?.error("Failed to export PDF report");
      setPdfSettings((prev) => ({ ...prev, open: false }));
    }
  };

  const handleExportCSV = async () => {
    try {
      setConfirmationDialog((prev) => ({ ...prev, loading: true }));

      const headers = reportData.columns.map((col) => col.label).join(",");
      const rows = reportData.rows.map((row) => {
        return reportData.columns
          .map((col) => {
            let value = row[col.key];
            if (value === null || value === undefined) value = "";
            // Format amount fields with peso sign
            const isAmountKey =
              col.key === "amount" ||
              (col.label && String(col.label).toLowerCase().includes("amount"));
            if (isAmountKey) {
              const num = parseFloat(value) || 0;
              try {
                value = `₱${num.toLocaleString("en-PH", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`;
              } catch {
                value = `₱${num.toFixed(2)}`;
              }
            }

            if (
              typeof value === "string" &&
              (value.includes(",") || value.includes('"'))
            ) {
              return `"${String(value).replace(/"/g, '""')}"`;
            }
            return value;
          })
          .join(",");
      });

      const csvContent = [headers, ...rows].join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);

      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `${selectedReportType}_report_${
          new Date().toISOString().split("T")[0]
        }.csv`
      );
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifications?.success("Report exported successfully");
      setConfirmationDialog({ open: false, action: null, loading: false });
    } catch (err) {
      console.error("Error exporting CSV:", err);
      notifications?.error("Failed to export report");
      setConfirmationDialog({ open: false, action: null, loading: false });
    }
  };

  const hasActiveFilters = reportData !== null;

  // Render filter controls
  const renderFilterControls = () => (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
      {/* Report Type */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700">Report Type</label>
        <select
          value={selectedReportType || ""}
          onChange={(e) => setSelectedReportType(e.target.value)}
          className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        >
          <option value="">Select Report Type</option>
          {allowedReports.map((report) => (
            <option key={report.report_type} value={report.report_type}>
              {report.display_name}
            </option>
          ))}
        </select>
      </div>

      {/* Time Period Type */}
      {selectedReportType && (
        <div className="flex flex-col">
          <label className="text-sm font-medium text-gray-700">
            Time Period
          </label>
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            <option value="quarterly">Quarterly</option>
            <option value="monthly">Monthly</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>
      )}

      {/* Quarter/Month/Date Selection */}
      {selectedReportType && timeFilter === "quarterly" && (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">Quarter</label>
            <select
              value={filters.quarter}
              onChange={(e) =>
                handleFilterChange("quarter", parseInt(e.target.value))
              }
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value={1}>First Quarter</option>
              <option value={2}>Second Quarter</option>
              <option value={3}>Third Quarter</option>
              <option value={4}>Fourth Quarter</option>
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">Year</label>
            <select
              value={filters.year}
              onChange={(e) =>
                handleFilterChange("year", parseInt(e.target.value))
              }
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {Array.from(
                { length: 10 },
                (_, i) => new Date().getFullYear() - i
              ).map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {selectedReportType && timeFilter === "monthly" && (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">Month</label>
            <select
              value={filters.month}
              onChange={(e) =>
                handleFilterChange("month", parseInt(e.target.value))
              }
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => (
                <option key={month} value={month}>
                  {new Date(2000, month - 1).toLocaleString("default", {
                    month: "long",
                  })}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">Year</label>
            <select
              value={filters.year}
              onChange={(e) =>
                handleFilterChange("year", parseInt(e.target.value))
              }
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {Array.from(
                { length: 10 },
                (_, i) => new Date().getFullYear() - i
              ).map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {selectedReportType && timeFilter === "custom" && (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">
              Date From
            </label>
            <input
              type="date"
              value={filters.date_from}
              max={filters.date_to || undefined}
              onChange={(e) => handleFilterChange("date_from", e.target.value)}
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700">Date To</label>
            <input
              type="date"
              value={filters.date_to}
              min={filters.date_from || undefined}
              onChange={(e) => handleFilterChange("date_to", e.target.value)}
              className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </div>
        </>
      )}

      {/* Generate Report Button */}
      {selectedReportType && (
        <div className="flex flex-col">
          <label className="invisible text-sm font-medium text-gray-700">
            Generate
          </label>
          <button
            onClick={handleApplyFilters}
            disabled={loading}
            className={`${BUTTON_PRIMARY} mt-1 py-2 rounded self-end`}
            title="Generate report"
            type="button"
          >
            <Download size={16} />
            Generate Report
          </button>
        </div>
      )}
    </div>
  );

  const pageContent = (
    <div className="space-y-2">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-sky-600">
            Report Gerneration
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={!reportData || loading}
            className={BUTTON_SUBTLE}
            title="Refresh data"
            type="button"
          >
            <RefreshCcw size={16} className={loading ? "animate-spin" : ""} />
          </button>
          <button
            onClick={handleClearFiltersClick}
            className={BUTTON_MUTED}
            title="Clear filters"
            type="button"
          >
            <Eraser size={16} />
            Clear Filters
          </button>
          {reportData && (
            <>
              <button
                onClick={handleExportPDFClick}
                disabled={loading}
                className={BUTTON_PRIMARY}
                title="Export to PDF"
                type="button"
              >
                <FileText size={16} />
                Export PDF
              </button>
              <button
                onClick={handleExportCSVClick}
                disabled={loading}
                className={BUTTON_PRIMARY}
                title="Export to CSV"
                type="button"
              >
                <Download size={16} />
                Export CSV
              </button>
            </>
          )}
        </div>
      </div>

      {/* Filters */}
      <div>
        {renderFilterControls()}

        {/* Dynamic Filters based on Report Type */}
        {selectedReportType && (
          <div className="mt-6">
            <DynamicFilters
              reportType={selectedReportType}
              extraFilters={extraFilters}
              onExtraFiltersChange={setExtraFilters}
              filterOptions={filterOptions}
            />
          </div>
        )}
      </div>

      {/* Report Description */}
      {selectedReportType && (
        <div className="p-4 mt-4 border border-gray-200 rounded-md bg-gray-50">
          <p className="text-sm leading-relaxed text-gray-700">
            {getReportDescription(selectedReportType)}
          </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="p-4 border border-red-200 rounded bg-red-50">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Table */}
      {selectedReportType && (
        <ReportResultsTable
          columns={reportData?.columns || []}
          rows={reportData?.rows || []}
          metadata={reportData?.metadata}
          loading={loading}
          hasActiveFilters={hasActiveFilters}
        />
      )}
    </div>
  );

  const confirmationProps = getConfirmationProps();

  if (loadingAccess) {
    return (
      <>
        <Header />
        <LayoutWithSidebar>
          <div className="flex items-center justify-center min-h-screen">
            <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
          </div>
        </LayoutWithSidebar>
        <Footer />
      </>
    );
  }

  if (!allowedReports || allowedReports.length === 0) {
    return (
      <>
        <Header />
        <LayoutWithSidebar>
          <div className="p-4">
            <div className="p-4 border border-red-200 rounded bg-red-50">
              <p className="text-red-800">
                You do not have access to any reports. Please contact your
                administrator.
              </p>
            </div>
          </div>
        </LayoutWithSidebar>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Header />
      <LayoutWithSidebar>
        <div className="p-4">{pageContent}</div>
      </LayoutWithSidebar>
      <Footer />

      <ConfirmationDialog
        open={confirmationDialog.open}
        title={confirmationProps.title}
        message={confirmationProps.message}
        confirmText={confirmationProps.confirmText}
        cancelText={confirmationProps.cancelText}
        confirmColor={confirmationProps.confirmColor}
        headerColor={confirmationProps.headerColor}
        loading={confirmationDialog.loading}
        onConfirm={handleConfirmAction}
        onCancel={handleCancelAction}
      />

      {/* PDF Settings Modal */}
      {pdfSettings.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 mx-4 bg-white rounded-lg shadow-xl">
            <div className="pb-4 mb-4 border-b border-gray-200">
              <h2 className="text-lg font-bold text-gray-800">
                PDF Export Settings
              </h2>
            </div>

            <div className="space-y-4">
              {/* Paper Size */}
              <div className="flex flex-col">
                <label className="mb-2 text-sm font-medium text-gray-700">
                  Paper Size
                </label>
                <select
                  value={pdfSettings.paperSize}
                  onChange={(e) =>
                    setPdfSettings((prev) => ({
                      ...prev,
                      paperSize: e.target.value,
                    }))
                  }
                  className="px-3 py-2 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                >
                  <option value="a4">A4 (210 × 297 mm)</option>
                  <option value="a3">A3 (297 × 420 mm)</option>
                  <option value="letter">Letter (8.5 × 11 in)</option>
                  <option value="legal">Legal (8.5 × 13 in)</option>
                </select>
              </div>

              {/* Orientation */}
              <div className="flex flex-col">
                <label className="mb-2 text-sm font-medium text-gray-700">
                  Orientation
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="orientation"
                      value="portrait"
                      checked={pdfSettings.orientation === "portrait"}
                      onChange={(e) =>
                        setPdfSettings((prev) => ({
                          ...prev,
                          orientation: e.target.value,
                        }))
                      }
                      className="w-4 h-4 border-gray-300 text-sky-600 focus:ring-sky-500"
                    />
                    <span className="text-sm text-gray-700">Portrait</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="orientation"
                      value="landscape"
                      checked={pdfSettings.orientation === "landscape"}
                      onChange={(e) =>
                        setPdfSettings((prev) => ({
                          ...prev,
                          orientation: e.target.value,
                        }))
                      }
                      className="w-4 h-4 border-gray-300 text-sky-600 focus:ring-sky-500"
                    />
                    <span className="text-sm text-gray-700">Landscape</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-4 mt-6 border-t border-gray-200">
              <button
                onClick={() =>
                  setPdfSettings((prev) => ({ ...prev, open: false }))
                }
                className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleExportPDF(
                    pdfSettings.paperSize,
                    pdfSettings.orientation
                  )
                }
                className="px-4 py-2 text-sm font-medium text-white rounded-md bg-sky-600 hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                Export PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
