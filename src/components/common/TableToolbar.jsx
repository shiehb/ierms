import { useState, useRef, useEffect } from "react";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  Filter,
  Calendar,
  Download,
  Printer,
  RefreshCw,
  X,
  Tag,
  FileText,
  FileSpreadsheet,
  Search,
} from "lucide-react";
import { useNotifications } from "../../hooks/useNotifications";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

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

/**
 * Reusable Table Toolbar with Icon-Only Buttons
 * Provides: Sort, Type Filter, Filters, Date Range, Export, Print, Refresh
 */
export default function TableToolbar({
  // Search
  searchValue = "",
  onSearchChange,
  onSearchClear,
  searchPlaceholder = "Search...",

  // Sort Configuration
  sortConfig = { key: null, direction: null },
  sortFields = [],
  onSort,

  // Type/Status Filter
  typeFilterValue = "all",
  typeFilterOptions = [],
  onTypeFilterChange,

  // Advanced Filters
  onFilterClick,
  customFilterDropdown,
  filterOpen = false,
  onFilterClose,

  // Date Range
  dateFrom = "",
  dateTo = "",
  onDateFromChange,
  onDateToChange,

  // Export
  exportConfig = null, // { title, fileName, columns, rows }

  // Print
  printConfig = null, // { title, fileName, columns, rows, selectedCount }

  // Refresh
  onRefresh,
  isRefreshing = false,

  // Additional Actions
  additionalActions = [],

  // Styling
  className = "",
  variant = "default", // "default" | "compact"
}) {
  const [sortOpen, setSortOpen] = useState(false);
  const [typeOpen, setTypeOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const sortRef = useRef(null);
  const typeRef = useRef(null);
  const dateRef = useRef(null);
  const exportRef = useRef(null);
  const filterRef = useRef(null);
  const notifications = useNotifications();

  // Close dropdowns on outside click
  useEffect(() => {
    const handles = {
      sort: (e) =>
        sortRef.current &&
        !sortRef.current.contains(e.target) &&
        setSortOpen(false),
      type: (e) =>
        typeRef.current &&
        !typeRef.current.contains(e.target) &&
        setTypeOpen(false),
      date: (e) =>
        dateRef.current &&
        !dateRef.current.contains(e.target) &&
        setDateOpen(false),
      export: (e) =>
        exportRef.current &&
        !exportRef.current.contains(e.target) &&
        setExportOpen(false),
      filter: (e) =>
        filterRef.current &&
        !filterRef.current.contains(e.target) &&
        onFilterClose &&
        onFilterClose(),
    };

    const listeners = [];
    if (sortOpen) listeners.push(["mousedown", handles.sort]);
    if (typeOpen) listeners.push(["mousedown", handles.type]);
    if (dateOpen) listeners.push(["mousedown", handles.date]);
    if (exportOpen) listeners.push(["mousedown", handles.export]);
    if (filterOpen && onFilterClose)
      listeners.push(["mousedown", handles.filter]);

    listeners.forEach(([evt, handler]) =>
      document.addEventListener(evt, handler)
    );
    return () =>
      listeners.forEach(([evt, handler]) =>
        document.removeEventListener(evt, handler)
      );
  }, [sortOpen, typeOpen, dateOpen, exportOpen, filterOpen, onFilterClose]);

  const isCompact = variant === "compact";
  const size = isCompact ? 14 : 16;

  // Date validation
  const today = new Date().toISOString().split("T")[0];
  const isDateFromInvalid = dateFrom && dateFrom > today;
  const isDateToInvalid = dateTo && dateFrom && dateTo < dateFrom;
  const hasValidationErrors = isDateFromInvalid || isDateToInvalid;

  return (
    <>
      <div
        className={`flex flex-wrap items-center gap-0 border border-gray-300 ${className}`}
      >
        {/* Search Bar */}
        {onSearchChange && (
          <div className="relative flex-1 min-w-[350px]">
            <Search className="absolute w-4 h-4 text-gray-400 -translate-y-1/2 left-3 top-1/2" />
            <input
              type="text"
              placeholder={searchPlaceholder}
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full py-1 pl-10 pr-8 focus:outline-none focus:ring-0"
            />
            {searchValue && onSearchClear && (
              <button
                onClick={onSearchClear}
                className="absolute -translate-y-1/2 right-3 top-1/2"
              >
                <X className="w-4 h-4 text-gray-400 hover:text-gray-600" />
              </button>
            )}
          </div>
        )}

        {/* Sort Dropdown */}
        {sortFields.length > 0 && onSort && (
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setSortOpen(!sortOpen)}
              className={`
              flex items-center justify-center p-2 transition-colors
              ${
                sortConfig?.key
                  ? "bg-sky-100 text-sky-700 hover:bg-sky-200"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }
            `}
              title={
                sortConfig?.key
                  ? `Sorted by ${
                      sortFields.find((f) => f.key === sortConfig.key)?.label ||
                      sortConfig.key
                    }`
                  : "Sort"
              }
            >
              <ArrowUpDown size={size} />
            </button>

            {sortOpen && (
              <div className="absolute right-0 z-20 w-56 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg top-full">
                <div className="p-2">
                  <div className="px-3 py-2 text-xs font-semibold tracking-wide text-gray-500 uppercase border-b border-gray-200">
                    Sort Options
                  </div>

                  <div className="mt-2 mb-2">
                    <div className="px-3 py-1 text-xs font-medium tracking-wide text-gray-600 uppercase">
                      Sort by
                    </div>
                    {sortFields.map((field) => (
                      <button
                        key={field.key}
                        onClick={() => {
                          if (onSort) {
                            onSort(
                              field.key,
                              sortConfig?.key === field.key
                                ? sortConfig.direction === "asc"
                                  ? "desc"
                                  : "asc"
                                : "asc"
                            );
                          }
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                          sortConfig?.key === field.key
                            ? "bg-sky-50 font-medium"
                            : ""
                        }`}
                      >
                        <span>{field.label}</span>
                        {sortConfig?.key === field.key && (
                          <div className="flex items-center gap-1">
                            {sortConfig.direction === "asc" ? (
                              <ArrowUp size={14} className="text-sky-600" />
                            ) : (
                              <ArrowDown size={14} className="text-sky-600" />
                            )}
                          </div>
                        )}
                      </button>
                    ))}
                  </div>

                  {sortConfig?.key && (
                    <>
                      <div className="my-1 border-t border-gray-200"></div>
                      <button
                        onClick={() => {
                          onSort(null, null);
                          setSortOpen(false);
                        }}
                        className="w-full px-3 py-2 text-sm text-left text-gray-600 transition-colors rounded-md hover:bg-gray-100"
                      >
                        Clear Sort
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Type Filter Dropdown */}
        {typeFilterOptions.length > 0 && onTypeFilterChange && (
          <div className="relative" ref={typeRef}>
            <button
              onClick={() => setTypeOpen(!typeOpen)}
              className={`
              flex items-center justify-center p-2 transition-colors
              ${
                typeFilterValue !== "all"
                  ? "bg-sky-100 text-sky-700 hover:bg-sky-200"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }
            `}
              title={
                typeFilterValue !== "all"
                  ? `Filter: ${
                      typeFilterOptions.find(
                        (opt) => opt.value === typeFilterValue
                      )?.label || typeFilterValue
                    }`
                  : "Filter by Type"
              }
            >
              <Filter size={size} />
            </button>

            {typeOpen && (
              <div className="absolute right-0 z-20 w-48 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
                <div className="p-2">
                  <div className="px-3 py-2 text-xs font-semibold tracking-wide text-gray-500 uppercase border-b border-gray-200">
                    Filter by Type
                  </div>
                  <div className="mt-2">
                    {typeFilterOptions.map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          onTypeFilterChange(option.value);
                          setTypeOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-md hover:bg-gray-100 transition-colors ${
                          typeFilterValue === option.value
                            ? "bg-sky-50 font-medium text-sky-700"
                            : "text-gray-700"
                        }`}
                      >
                        <span className="capitalize">{option.label}</span>
                        {typeFilterValue === option.value && (
                          <span className="text-sky-600">✓</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filters Button */}
        {onFilterClick && (
          <div className="relative" ref={filterRef}>
            <button
              onClick={onFilterClick}
              className="flex items-center justify-center p-2 text-gray-700 transition-colors bg-gray-200 hover:bg-gray-300"
              title="More Filters"
            >
              <Filter size={size} />
            </button>
            {customFilterDropdown}
          </div>
        )}

        {/* Date Range Dropdown */}
        {onDateFromChange && onDateToChange && (
          <div className="relative" ref={dateRef}>
            <button
              onClick={() => setDateOpen(!dateOpen)}
              className={`
              flex items-center justify-center p-2 transition-colors
              ${
                hasValidationErrors
                  ? "bg-red-100 text-red-700 hover:bg-red-200"
                  : dateFrom || dateTo
                  ? "bg-orange-100 text-orange-700 hover:bg-orange-200"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }
            `}
              title="Date Range Filter"
            >
              <Calendar size={size} />
            </button>

            {dateOpen && (
              <div className="absolute right-0 z-20 w-64 mt-1 bg-white border border-gray-200 rounded-lg shadow">
                <div className="p-2">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-sky-600">
                      Date Range Filter
                    </h3>
                    {(dateFrom || dateTo) && (
                      <button
                        onClick={() => {
                          onDateFromChange("");
                          onDateToChange("");
                          setDateOpen(false);
                        }}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 rounded hover:text-gray-800 hover:bg-gray-100"
                      >
                        <X size={12} />
                        Clear
                      </button>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="block mb-1 text-xs font-medium text-gray-700">
                        From
                      </label>
                      <input
                        type="date"
                        value={dateFrom}
                        onChange={(e) => onDateFromChange(e.target.value)}
                        max={today}
                        className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-sky-500"
                      />
                    </div>

                    <div>
                      <label className="block mb-1 text-xs font-medium text-gray-700">
                        To
                      </label>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => onDateToChange(e.target.value)}
                        min={dateFrom}
                        max={today}
                        className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-sky-500"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Export Dropdown */}
        {exportConfig && (
          <div className="relative" ref={exportRef}>
            <button
              onClick={() => setExportOpen(!exportOpen)}
              disabled={!exportConfig.rows || exportConfig.rows.length === 0}
              className="flex items-center justify-center p-2 text-gray-700 transition-colors bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Export Data"
            >
              <Download size={size} />
            </button>

            {exportOpen &&
              exportConfig.rows &&
              exportConfig.rows.length > 0 && (
                <div className="absolute right-0 z-20 w-56 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
                  <div className="p-2">
                    <div className="px-3 py-2 text-xs font-semibold tracking-wide text-gray-500 uppercase border-b border-gray-200">
                      Export Format
                    </div>
                    <div className="mt-2">
                      <button
                        onClick={async () => {
                          try {
                            // CSV Export
                            const csvRows = [];
                            csvRows.push(exportConfig.columns.join(","));
                            exportConfig.rows.forEach((row) => {
                              csvRows.push(
                                row.map((cell) => `"${cell}"`).join(",")
                              );
                            });
                            const csvContent =
                              "data:text/csv;charset=utf-8," +
                              csvRows.join("\n");
                            const link = document.createElement("a");
                            link.setAttribute("href", encodeURI(csvContent));
                            link.setAttribute(
                              "download",
                              `${exportConfig.fileName}.csv`
                            );
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);

                            notifications.success(
                              "CSV file exported successfully!",
                              {
                                title: "Export Complete",
                                duration: 4000,
                              }
                            );
                          } catch {
                            notifications.error("Failed to export CSV file", {
                              title: "Export Failed",
                              duration: 6000,
                            });
                          }
                          setExportOpen(false);
                        }}
                        className="flex items-center w-full gap-2 px-3 py-2 text-sm text-gray-700 transition-colors rounded-md hover:bg-gray-100"
                      >
                        <FileSpreadsheet size={14} className="text-green-600" />
                        <span>Export as CSV</span>
                      </button>

                      <button
                        onClick={async () => {
                          try {
                            const doc = new jsPDF({
                              orientation: "portrait",
                              unit: "mm",
                              format: [330.2, 215.9],
                            });

                            doc.setFont("times", "normal");

                            const pageWidth = doc.internal.pageSize.getWidth();
                            const safeDate = new Date()
                              .toISOString()
                              .split("T")[0];
                            const exportId = `RPT-${Date.now()}`;

                            doc.setFontSize(8);
                            doc.setFont("times", "bold");
                            doc.text(`${exportId}`, pageWidth - 10, 10, {
                              align: "right",
                            });
                            doc.text(`${safeDate}`, pageWidth - 10, 14, {
                              align: "right",
                            });
                            doc.setFont("times", "normal");

                            const logo1Data = await loadImageAsBase64(
                              "/assets/document/logo1.png"
                            );
                            const logo2Data = await loadImageAsBase64(
                              "/assets/document/logo2.png"
                            );

                            const logoWidth = 20;
                            const logoHeight = 20;
                            const logoY = 17;

                            const titleText =
                              "Integrated Establishment Regulatory Management System";
                            const titleTextWidth = doc.getTextWidth(titleText);

                            const leftLogoX =
                              pageWidth / 2 -
                              titleTextWidth / 2 -
                              logoWidth -
                              30;
                            const rightLogoX =
                              pageWidth / 2 + titleTextWidth / 2 + 30;

                            if (logo1Data) {
                              doc.addImage(
                                logo1Data,
                                "PNG",
                                leftLogoX,
                                logoY,
                                logoWidth,
                                logoHeight
                              );
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
                            doc.text(
                              "Environmental Management Bureau Region I",
                              pageWidth / 2,
                              34,
                              { align: "center" }
                            );

                            doc.setFont("times", "bold");
                            doc.setFontSize(12);
                            const titleUpper = exportConfig.title.toUpperCase();
                            doc.text(titleUpper, pageWidth / 2, 46, {
                              align: "center",
                            });
                            const titleWidth = doc.getTextWidth(titleUpper);
                            doc.line(
                              pageWidth / 2 - titleWidth / 2,
                              48,
                              pageWidth / 2 + titleWidth / 2,
                              48
                            );
                            doc.setFont("times", "normal");

                            autoTable(doc, {
                              head: [exportConfig.columns],
                              body: exportConfig.rows,
                              startY: 52,
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

                            const pageCount = doc.internal.getNumberOfPages();
                            for (let i = 1; i <= pageCount; i++) {
                              doc.setPage(i);
                              doc.setFontSize(10);
                              doc.text(
                                `Page ${i} of ${pageCount}`,
                                pageWidth - 15,
                                325,
                                {
                                  align: "right",
                                }
                              );
                            }

                            const blobUrl = doc.output("bloburl");
                            window.open(blobUrl, "_blank");

                            notifications.success(
                              "PDF file generated successfully!",
                              {
                                title: "Export Complete",
                                duration: 4000,
                              }
                            );
                          } catch {
                            notifications.error("Failed to generate PDF file", {
                              title: "Export Failed",
                              duration: 6000,
                            });
                          }
                          setExportOpen(false);
                        }}
                        className="flex items-center w-full gap-2 px-3 py-2 text-sm text-gray-700 transition-colors rounded-md hover:bg-gray-100"
                      >
                        <FileText size={14} className="text-red-600" />
                        <span>Export as PDF</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
          </div>
        )}

        {/* Print Button */}
        {printConfig && (
          <button
            onClick={async () => {
              try {
                const doc = new jsPDF({
                  orientation: "portrait",
                  unit: "mm",
                  format: [330.2, 215.9],
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

                const logo1Data = await loadImageAsBase64(
                  "/assets/document/logo1.png"
                );
                const logo2Data = await loadImageAsBase64(
                  "/assets/document/logo2.png"
                );

                const logoWidth = 20;
                const logoHeight = 20;
                const logoY = 17;

                const titleText =
                  "Integrated Establishment Regulatory Management System";
                const titleTextWidth = doc.getTextWidth(titleText);

                const leftLogoX =
                  pageWidth / 2 - titleTextWidth / 2 - logoWidth - 30;
                const rightLogoX = pageWidth / 2 + titleTextWidth / 2 + 30;

                if (logo1Data) {
                  doc.addImage(
                    logo1Data,
                    "PNG",
                    leftLogoX,
                    logoY,
                    logoWidth,
                    logoHeight
                  );
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
                doc.text(
                  "Environmental Management Bureau Region I",
                  pageWidth / 2,
                  34,
                  { align: "center" }
                );

                doc.setFont("times", "bold");
                doc.setFontSize(12);
                const titleUpper = printConfig.title.toUpperCase();
                doc.text(titleUpper, pageWidth / 2, 46, { align: "center" });
                const titleWidth = doc.getTextWidth(titleUpper);
                doc.line(
                  pageWidth / 2 - titleWidth / 2,
                  48,
                  pageWidth / 2 + titleWidth / 2,
                  48
                );
                doc.setFont("times", "normal");

                autoTable(doc, {
                  head: [printConfig.columns],
                  body: printConfig.rows,
                  startY: 52,
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

                const pageCount = doc.internal.getNumberOfPages();
                for (let i = 1; i <= pageCount; i++) {
                  doc.setPage(i);
                  doc.setFontSize(10);
                  doc.text(`Page ${i} of ${pageCount}`, pageWidth - 15, 325, {
                    align: "right",
                  });
                }

                doc.autoPrint();
                const blobUrl = doc.output("bloburl");
                window.open(blobUrl, "_blank");

                notifications.success("Print dialog opened successfully!", {
                  title: "Print Ready",
                  duration: 4000,
                });
              } catch {
                notifications.error("Failed to open print dialog", {
                  title: "Print Failed",
                  duration: 6000,
                });
              }
            }}
            disabled={!printConfig.rows || printConfig.rows.length === 0}
            className="flex items-center justify-center p-2 text-gray-700 transition-colors bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Print Report"
          >
            <Printer size={size} />
          </button>
        )}

        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center justify-center p-2 text-gray-700 transition-colors bg-gray-200 hover:bg-gray-300 disabled:opacity-50"
            title="Refresh Data"
          >
            <RefreshCw
              size={size}
              className={isRefreshing ? "animate-spin" : ""}
            />
          </button>
        )}

        {/* Additional Actions */}
        {additionalActions.map((action, idx) => (
          <button
            key={idx}
            onClick={action.onClick}
            disabled={action.disabled}
            className={`
            flex items-center justify-center px-2 py-1 transition-colors
            ${
              action.variant === "primary"
                ? "bg-sky-600 text-white hover:bg-sky-700"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }
            ${action.disabled ? "opacity-50 cursor-not-allowed" : ""}
          `}
            title={action.title || ""}
          >
            {action.icon && <action.icon size={size} />}
            {action.text && <span className="ml-1.5">{action.text}</span>}
          </button>
        ))}
      </div>
    </>
  );
}
