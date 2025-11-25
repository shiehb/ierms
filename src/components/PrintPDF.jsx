import { useState, useEffect, useCallback } from "react";
import { Printer } from "lucide-react";
import { useNotifications } from "../hooks/useNotifications";

export default function PrintPDF({
  title,
  columns,
  rows,
  className = "",
  disabled = false,
}) {
  const [isPrinting, setIsPrinting] = useState(false);
  const notifications = useNotifications();

  const handlePrint = useCallback(() => {
    try {
      // Validate data before printing
      if (!rows || rows.length === 0) {
        notifications.warning("No data available to print.", {
          title: "⚠️ No Data",
          duration: 3000,
        });
        return;
      }

      // Show confirmation for large datasets
      if (rows.length > 100) {
        const confirmed = window.confirm(
          `This will print ${rows.length} records. Continue?`
        );
        if (!confirmed) {
          notifications.info("Print cancelled by user.", {
            title: "⏹️ Print Cancelled",
            duration: 2000,
          });
          return;
        }
      }

      setIsPrinting(true);

      // Hybrid detection approach: Media query + time-based
      const dialogStartTime = Date.now();
      let printModeDetected = false;

      // Monitor print mode using media query (most reliable)
      const printMedia = window.matchMedia("print");
      const checkPrintMode = setInterval(() => {
        if (printMedia.matches) {
          printModeDetected = true;
        }
      }, 100);

      // Show initial notification
      notifications.info(`Opening print dialog for ${title}...`, {
        title: "🖨️ Print Ready",
        duration: 2000,
      });

      // Set up afterprint event handler with hybrid detection
      const afterPrintHandler = () => {
        clearInterval(checkPrintMode);

        // Remove the event listener
        window.removeEventListener("afterprint", afterPrintHandler);
        setIsPrinting(false);

        const dialogDuration = Date.now() - dialogStartTime;

        // Hybrid detection logic:
        // 1. Primary: Check if print mode was actually activated (most reliable)
        // 2. Fallback: Use time-based detection for edge cases

        if (printModeDetected) {
          // Print mode was activated = user actually printed
          notifications.success(
            `${title} has been sent to your printer successfully!`,
            {
              title: "✅ Print Complete",
              duration: 3000,
            }
          );
        } else if (dialogDuration < 500) {
          // Very quick close = definitely cancelled
          notifications.warning(
            `Print ${title} was cancelled. You can try again anytime.`,
            {
              title: "⏹️ Print Cancelled",
              duration: 4000,
            }
          );
        } else {
          // Longer duration but no print mode detected = cancelled after review
          notifications.info(
            `Print dialog closed. If you printed, check your printer output.`,
            {
              title: "ℹ️ Print Dialog Closed",
              duration: 4000,
            }
          );
        }
      };

      // Add the afterprint event listener
      window.addEventListener("afterprint", afterPrintHandler);

      // Open print dialog
      window.print();
    } catch (error) {
      setIsPrinting(false);

      // More specific error handling
      let errorMessage = `Unable to open print dialog for ${title}.`;
      let errorTitle = "❌ Print Error";

      if (error.name === "NotAllowedError") {
        errorMessage =
          "Print blocked by browser. Please allow popups and try again.";
        errorTitle = "🚫 Print Blocked";
      } else if (error.name === "SecurityError") {
        errorMessage =
          "Print not allowed in current context. Please refresh the page and try again.";
        errorTitle = "🔒 Security Error";
      } else {
        errorMessage =
          "Print failed. Please check your browser settings or try refreshing the page.";
      }

      notifications.error(errorMessage, {
        title: errorTitle,
        duration: 6000,
      });
    }
  }, [title, rows, notifications]);

  // Add keyboard shortcut support (Ctrl+P)
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.ctrlKey && e.key === "p" && !disabled && rows.length > 0) {
        e.preventDefault();
        handlePrint();
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [disabled, rows.length, handlePrint]);

  const currentDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const reportId = `RPT-${Date.now()}`;

  return (
    <>
      <button
        onClick={handlePrint}
        disabled={disabled || isPrinting || rows.length === 0}
        title={
          rows.length === 0
            ? "No data to print"
            : `Print ${title} report (Ctrl+P)`
        }
        className={`
          flex items-center px-3 py-1 text-sm font-medium rounded
          text-gray-700 bg-gray-200 hover:bg-gray-300 disabled:bg-gray-400 disabled:cursor-not-allowed
          transition-colors duration-200
          ${isPrinting ? "opacity-75" : ""}
          ${className}
        `}
      >
        <Printer size={16} />
        {isPrinting ? "Preparing..." : "Print"}
      </button>

      {/* Hidden Print Template - Compact Structure */}
      <div id="print-template" className="hidden print:block">
        {/* Professional Data Table with Integrated Header */}
        <table className="report-table">
          <thead>
            {/* Header Row with Logos and Title - Repeats on each page! */}
            <tr className="report-header-row">
              <th colSpan={columns.length} className="print-header-cell">
                {/* Report Meta Info - Ultra-compact positioning */}
                <div
                  className="print-meta-info"
                  data-print-time={new Date().toLocaleString()}
                >
                  <div className="font-bold">{reportId}</div>
                  <div>{currentDate}</div>
                </div>
                {/* Main Header Content */}
                <div className="print-header-content">
                  <img
                    src="/assets/document/logo1.png"
                    alt="Logo 1"
                    className="print-logo-img"
                  />
                  <div className="print-title-text">
                    <div className="print-main-title">
                      Integrated Establishment Regulatory Management System
                    </div>
                    <div className="print-subtitle">
                      Department of Environmental and Natural Resources
                    </div>
                    <div className="print-subtitle">
                      Environmental Management Bureau Region I
                    </div>
                    <div className="print-report-title">
                      {title.toUpperCase()}
                    </div>
                  </div>
                  <img
                    src="/assets/document/logo2.png"
                    alt="Logo 2"
                    className="print-logo-img"
                  />
                </div>
              </th>
            </tr>

            {/* Column Headers Row */}
            <tr className="data-columns-row">
              {columns.map((col, idx) => (
                <th key={idx} className="data-column-header">
                  {col}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>

          <tfoot>
            <tr>
              <td colSpan={columns.length} className="print-footer-cell">
                <div className="print-footer-content">
                  <p className="font-bold">*** End of Report ***</p>
                  <p>Generated on {currentDate}</p>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
