import { useState, useRef } from "react";
import {
  Download,
  FileText,
  FileSpreadsheet,
  ChevronDown,
  Check,
} from "lucide-react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
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

// Export format options
const EXPORT_FORMATS = [
  {
    id: "csv",
    name: "CSV",
    icon: FileSpreadsheet,
    description: "Comma Separated Values",
    color: "text-green-600",
  },
  {
    id: "pdf",
    name: "PDF",
    icon: FileText,
    description: "Portable Document Format",
    color: "text-red-600",
  },
];

export default function ExportDropdown({
  title,
  fileName,
  columns,
  rows,
  customPdfGenerator,
  className = "",
  disabled = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const dropdownRef = useRef(null);
  const notifications = useNotifications();

  // Close dropdown when clicking outside
  const handleClickOutside = (event) => {
    if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
      setIsOpen(false);
    }
  };

  // Add event listener for outside clicks
  useState(() => {
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  });

  // CSV Export
  const handleExportCSV = () => {
    try {
      const csvRows = [];
      csvRows.push(columns.join(","));
      rows.forEach((row) => {
        csvRows.push(row.map((cell) => `"${cell}"`).join(","));
      });

      const csvContent = "data:text/csv;charset=utf-8," + csvRows.join("\n");
      const link = document.createElement("a");
      link.setAttribute("href", encodeURI(csvContent));
      link.setAttribute("download", `${fileName}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifications.success("CSV file exported successfully!", {
        title: "Export Complete",
        duration: 4000,
      });
    } catch {
      notifications.error("Failed to export CSV file", {
        title: "Export Failed",
        duration: 6000,
      });
    }
  };

  // PDF Export
  const handleExportPDF = async () => {
    try {
      setIsExporting(true);
      const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: [330.2, 215.9],
      });

      if (customPdfGenerator) {
        customPdfGenerator(doc, columns, rows);
      } else {
        // Default PDF generation with logos and formatting
        doc.setFont("times", "normal");

        // Add header information
        const pageWidth = doc.internal.pageSize.getWidth();
        const safeDate = new Date().toISOString().split("T")[0];
        const exportId = `RPT-${Date.now()}`;

        doc.setFontSize(8);
        doc.setFont("times", "bold");
        doc.text(`${exportId}`, pageWidth - 10, 10, { align: "right" });
        doc.text(`${safeDate}`, pageWidth - 10, 14, { align: "right" });
        doc.setFont("times", "normal");

        // Load and add logos
        const logo1Data = await loadImageAsBase64("/assets/document/logo1.png");
        const logo2Data = await loadImageAsBase64("/assets/document/logo2.png");

        const logoWidth = 20; // mm
        const logoHeight = 20; // mm
        const logoY = 17; // Y position for logos

        // Calculate title text width to position logos closer
        const titleText =
          "Integrated Establishment Regulatory Management System";
        const titleTextWidth = doc.getTextWidth(titleText);

        // Position logos with more spacing from the title text
        const leftLogoX = pageWidth / 2 - titleTextWidth / 2 - logoWidth - 30; // 10mm gap
        const rightLogoX = pageWidth / 2 + titleTextWidth / 2 + 30; // 10mm gap

        // Add logo1 on the left (closer to title)
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

        // Add logo2 on the right (closer to title)
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

        // Header text (centered)
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

        // add line here up to 70 mm

        // Report title
        doc.setFont("times", "bold");
        doc.setFontSize(12);
        const titleUpper = title.toUpperCase();
        doc.text(titleUpper, pageWidth / 2, 46, { align: "center" });
        const titleWidth = doc.getTextWidth(titleUpper);
        doc.line(
          pageWidth / 2 - titleWidth / 2,
          48,
          pageWidth / 2 + titleWidth / 2,
          48
        );
        doc.setFont("times", "normal");

        // Table
        autoTable(doc, {
          head: [columns],
          body: rows,
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

        // Footer
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
          doc.setPage(i);
          doc.setFontSize(10);
          doc.text(`Page ${i} of ${pageCount}`, pageWidth - 15, 325, {
            align: "right",
          });
        }
      }

      // Open PDF in new tab for viewing/printing
      const blobUrl = doc.output("bloburl");
      window.open(blobUrl, "_blank");

      notifications.success("PDF file generated successfully!", {
        title: "Export Complete",
        duration: 4000,
      });
    } catch {
      notifications.error("Failed to generate PDF file", {
        title: "Export Failed",
        duration: 6000,
      });
    } finally {
      setIsExporting(false);
    }
  };

  // Handle format selection
  const handleFormatSelect = (format) => {
    setSelectedFormat(format);
    setShowConfirmation(true);
    setIsOpen(false);
  };

  // Handle export confirmation
  const handleConfirmExport = async () => {
    if (!selectedFormat) return;

    try {
      switch (selectedFormat.id) {
        case "csv":
          handleExportCSV();
          break;
        case "pdf":
          await handleExportPDF();
          break;
        default:
          break;
      }
    } catch (err) {
      console.error("Export error:", err);
    } finally {
      setSelectedFormat(null);
      setShowConfirmation(false);
    }
  };

  return (
    <>
      <div className={`relative ${className}`} ref={dropdownRef}>
        {/* Export Button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled || isExporting}
          className={`
            flex items-center px-3 py-1 text-sm font-medium rounded
            text-gray-700 bg-gray-200 hover:bg-gray-300 disabled:bg-gray-400 disabled:cursor-not-allowed
            transition-colors duration-200
            ${isExporting ? "opacity-75" : ""}
          `}
        >
          <Download size={16} />
          {isExporting ? "Exporting..." : "Export"}
          <ChevronDown
            size={14}
            className={`transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div className="absolute right-0 top-full z-50 w-56 mt-1 bg-white border border-gray-200 rounded shadow">
            <div className="p-2">
              <div className="px-3 py-2 text-xs font-semibold text-sky-600 uppercase tracking-wide">
                Export Format
              </div>

              {/* Export Options */}
              {EXPORT_FORMATS.map((format) => {
                const IconComponent = format.icon;
                return (
                  <button
                    key={format.id}
                    onClick={() => handleFormatSelect(format)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors"
                  >
                    <IconComponent size={16} className={format.color} />
                    <div className="flex-1 text-left">
                      <div className="font-medium">{format.name}</div>
                      <div className="text-xs text-gray-500">
                        {format.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {showConfirmation && selectedFormat && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40">
          <div className="relative p-6 bg-white rounded-lg shadow-lg w-96">
            <div className="flex items-center gap-3 mb-4">
              <selectedFormat.icon size={24} className={selectedFormat.color} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Confirm Export
                </h3>
                <p className="text-sm text-gray-600">
                  Export as {selectedFormat.name} format
                </p>
              </div>
            </div>

            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <div className="text-sm text-gray-700">
                <div>
                  <strong>Title:</strong> {title}
                </div>
                <div>
                  <strong>File:</strong> {fileName}.{selectedFormat.id}
                </div>
                <div>
                  <strong>Records:</strong> {rows.length} rows
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setSelectedFormat(null);
                  setShowConfirmation(false);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmExport}
                disabled={isExporting}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-sky-600 rounded-lg hover:bg-sky-700 disabled:bg-gray-400 transition-colors"
              >
                {isExporting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Exporting...
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    Confirm Export
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
