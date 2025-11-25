import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, Eraser, Filter, RefreshCcw } from "lucide-react";
import api from "../services/api";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import PaginationControls from "../components/PaginationControls";
import { useLocalStoragePagination } from "../hooks/useLocalStoragePagination";

const ACTION_TYPE_OPTIONS = [
  { label: "All Actions", value: "" },
  { label: "Create", value: "create" },
  { label: "Update", value: "update" },
  { label: "Delete", value: "delete" },
  { label: "Login", value: "login" },
  { label: "Logout", value: "logout" },
  { label: "System", value: "system" },
  { label: "Backup", value: "backup" },
  { label: "Restore", value: "restore" },
];

const ROLE_OPTIONS = [
  { label: "All Roles", value: "" },
  { label: "Admin", value: "Admin" },
  { label: "Inspector", value: "Inspector" },
  { label: "Section Chief", value: "Section Chief" },
  { label: "Unit Head", value: "Unit Head" },
  { label: "Legal Unit", value: "Legal Unit" },
  { label: "Monitoring Personnel", value: "Monitoring Personnel" },
  { label: "Public", value: "public" },
];

const INITIAL_FILTERS = {
  dateFrom: "",
  dateTo: "",
  user: "",
  role: "",
  actionType: "",
  keyword: "",
};

const ACTION_COLORS = {
  create: "bg-green-100 text-green-700 border-green-200",
  update: "bg-yellow-100 text-yellow-700 border-yellow-200",
  delete: "bg-red-100 text-red-700 border-red-200",
  login: "bg-blue-100 text-blue-700 border-blue-200",
  logout: "bg-blue-100 text-blue-700 border-blue-200",
  system: "bg-purple-100 text-purple-700 border-purple-200",
  backup: "bg-purple-100 text-purple-700 border-purple-200",
  restore: "bg-purple-100 text-purple-700 border-purple-200",
};

const DEFAULT_PAGE_SIZE = 25;
const COLUMN_COUNT = 6;
const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded px-3 py-1 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60";
const BUTTON_SUBTLE = `${BUTTON_BASE} border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-sky-500`;
const BUTTON_MUTED = `${BUTTON_BASE} border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-sky-500`;
const BUTTON_PRIMARY = `${BUTTON_BASE} bg-sky-600 text-white shadow-sm hover:bg-sky-700 focus:ring-sky-500`;
const BUTTON_ACCENT = `${BUTTON_BASE} bg-sky-600 text-white shadow-sm hover:bg-sky-700 focus:ring-sky-500`;

function normalizeAction(action) {
  if (!action) return "Unknown";
  const normalized = String(action).toLowerCase();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatDateTime(value) {
  if (!value) return "—";
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("en-PH", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  } catch {
    return value;
  }
}

function buildQueryParams(filters, page, pageSize) {
  const params = {
    ordering: "-created_at",
    page,
    page_size: pageSize,
  };

  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.user) params.user = filters.user.trim();
  if (filters.role) params.role = filters.role;
  if (filters.actionType) params.action_type = filters.actionType;
  if (filters.keyword) params.search = filters.keyword.trim();

  return params;
}

function getColorClass(action) {
  if (!action) return "bg-gray-100 text-gray-600 border-gray-200";
  const key = String(action).toLowerCase();
  return ACTION_COLORS[key] || "bg-gray-100 text-gray-600 border-gray-200";
}

function getUserDisplay(log) {
  return (
    log.user_name ||
    log.user_email ||
    log.user ||
    (log.user_details && (log.user_details.email || log.user_details.name)) ||
    "System"
  );
}

function getRoleDisplay(log) {
  return (
    log.role ||
    (log.user_details && log.user_details.role) ||
    log.user_role ||
    "—"
  );
}

function getModuleDisplay(log) {
  const moduleValue =
    log.module ??
    log.section ??
    log.context ??
    (log.metadata && (log.metadata.module || log.metadata.section));
  if (!moduleValue) {
    return "—";
  }
  return moduleValue;
}

function getDescription(log) {
  return log.description || log.message || "";
}

function hasMetadata(log) {
  return (
    !!log &&
    !!log.metadata &&
    typeof log.metadata === "object" &&
    Object.keys(log.metadata).length > 0
  );
}

function getBeforeAfter(log) {
  const before =
    log.before || log.before_state || log.before_data || log.previous_data;
  const after =
    log.after || log.after_state || log.after_data || log.current_data;
  return { before, after };
}

export default function AuditLogs() {
  const storageKey = "audit_logs";
  const savedPagination = useLocalStoragePagination(
    storageKey,
    DEFAULT_PAGE_SIZE
  );

  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(INITIAL_FILTERS);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(savedPagination.page);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedLog, setSelectedLog] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [endpoint, setEndpoint] = useState("audit-logs/");

  const persistPagination = useCallback(
    (nextPage, nextPageSize = pageSize) => {
      try {
        localStorage.setItem(
          `${storageKey}_pagination`,
          JSON.stringify({
            page: Math.max(1, nextPage),
            pageSize: Math.max(10, Math.min(100, nextPageSize)),
            timestamp: Date.now(),
          })
        );
      } catch (error) {
        console.warn("Failed to save audit pagination:", error);
      }
    },
    [pageSize, storageKey]
  );

  useEffect(() => {
    let isMounted = true;

    async function fetchLogs() {
      setLoading(true);
      setError(null);

      try {
        const params = buildQueryParams(appliedFilters, page, pageSize);
        const endpointsToTry =
          endpoint === "audit-logs/"
            ? ["audit-logs/", "activity-logs/"]
            : [endpoint];
        let data;
        let lastError = null;

        for (const url of endpointsToTry) {
          try {
            const response = await api.get(url, { params });
            data = response.data;
            if (url !== endpoint) {
              setEndpoint(url);
            }
            lastError = null;
            break;
          } catch (err) {
            lastError = err;
            if (!(err.response?.status === 404 && url === "audit-logs/")) {
              throw err;
            }
          }
        }

        if (lastError) {
          throw lastError;
        }

        if (!isMounted) return;

        if (Array.isArray(data)) {
          setLogs(data);
          setTotalCount(data.length);
        } else {
          setLogs(data.results || []);
          setTotalCount(
            typeof data.count === "number"
              ? data.count
              : (data.results || []).length
          );
        }
      } catch (err) {
        if (!isMounted) return;
        console.error("Failed to fetch audit logs", err);
        setError(
          err.response?.data?.detail ||
            err.message ||
            "Unable to fetch audit logs. Please try again."
        );
        setLogs([]);
        setTotalCount(0);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchLogs();

    return () => {
      isMounted = false;
    };
  }, [appliedFilters, endpoint, page, pageSize, refreshTrigger]);

  const totalPages = useMemo(() => {
    if (pageSize <= 0) return 1;
    return Math.max(1, Math.ceil(totalCount / pageSize));
  }, [totalCount, pageSize]);

  const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = totalCount === 0 ? 0 : Math.min(page * pageSize, totalCount);
  const hasActiveFilters = Object.values(appliedFilters).some((value) => value);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
      persistPagination(totalPages);
    }
  }, [totalPages, page, persistPagination]);

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApplyFilters = () => {
    setAppliedFilters(filters);
    setPage(1);
    persistPagination(1);
  };

  const handleClearFilters = () => {
    setFilters(INITIAL_FILTERS);
    setAppliedFilters(INITIAL_FILTERS);
    setPage(1);
    persistPagination(1);
  };

  const handleExportCsv = async () => {
    setIsExporting(true);
    try {
      const params = buildQueryParams(appliedFilters, 1, 1000);
      params.export = "csv";

      const exportEndpoints =
        endpoint === "audit-logs/"
          ? ["audit-logs/", "activity-logs/"]
          : [endpoint];
      let exportData = null;
      let exportError = null;

      for (const url of exportEndpoints) {
        try {
          const response = await api.get(url, { params });
          exportData = response.data;
          exportError = null;
          if (url !== endpoint) {
            setEndpoint(url);
          }
          break;
        } catch (err) {
          exportError = err;
          if (!(err.response?.status === 404 && url === "audit-logs/")) {
            throw err;
          }
        }
      }

      if (exportError) {
        throw exportError;
      }

      const rows = Array.isArray(exportData)
        ? exportData
        : exportData.results || [];

      if (rows.length === 0) {
        throw new Error("No audit logs found for export.");
      }

      const headers = [
        "Date & Time",
        "User",
        "Role",
        "Action Type",
        "Module",
        "Description",
        "IP Address",
      ];

      const csvRows = rows.map((log) => {
        const action = normalizeAction(log.action_type || log.action);
        const { before, after } = getBeforeAfter(log);
        const details = [
          formatDateTime(log.created_at),
          getUserDisplay(log),
          getRoleDisplay(log),
          action,
          getModuleDisplay(log),
          getDescription(log),
          log.ip_address || "—",
        ];

        if (before || after) {
          headers.includes("Before Data") ||
            headers.push("Before Data", "After Data");
          details.push(
            before ? JSON.stringify(before) : "",
            after ? JSON.stringify(after) : ""
          );
        }

        return details;
      });

      const headerLine = headers.join(",");
      const bodyLines = csvRows.map((row) =>
        row
          .map((cell) => {
            if (cell === undefined || cell === null) return "";
            const str = String(cell).replace(/"/g, '""');
            return `"${str}"`;
          })
          .join(",")
      );

      const csvContent = [headerLine, ...bodyLines].join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute(
        "download",
        `audit-logs-${new Date().toISOString().split("T")[0]}.csv`
      );
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export CSV", err);
      setError(
        err?.message ||
          "Failed to export CSV. Please try again or adjust filters."
      );
    } finally {
      setIsExporting(false);
    }
  };

  const handleRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const renderTableBody = () => {
    if (loading) {
      return (
        <tr>
          <td
            colSpan={COLUMN_COUNT}
            className="px-4 py-12 text-center text-gray-500"
          >
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-b-2 rounded-full animate-spin border-sky-600" />
              <span className="text-sm text-gray-600">
                Loading audit logs...
              </span>
            </div>
          </td>
        </tr>
      );
    }

    if (error) {
      return (
        <tr>
          <td colSpan={COLUMN_COUNT} className="px-4 py-8 text-center">
            <div className="inline-flex items-center justify-center px-4 py-3 text-sm text-red-700 border border-red-200 rounded-md bg-red-50">
              {error}
            </div>
          </td>
        </tr>
      );
    }

    if (!logs.length) {
      return (
        <tr>
          <td
            colSpan={COLUMN_COUNT}
            className="px-4 py-10 text-center text-gray-500"
          >
            <p className="text-sm text-gray-600">
              No audit logs found. Adjust your filters or refresh the page.
            </p>
          </td>
        </tr>
      );
    }

    return logs.map((log) => {
      const action = normalizeAction(log.action_type || log.action);
      const colorClass = getColorClass(log.action_type || log.action);

      return (
        <tr
          key={log.id ?? `${log.created_at}-${log.user}-${log.module}`}
          className="text-sm transition-colors border-b border-gray-200 cursor-pointer hover:bg-sky-50"
          onClick={() => setSelectedLog(log)}
        >
          <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
            {formatDateTime(log.created_at)}
          </td>
          <td className="min-w-[220px] px-4 py-3 text-gray-700">
            <div className="font-medium text-gray-900">
              {getUserDisplay(log)}
            </div>
            <div className="text-xs text-gray-500">{getRoleDisplay(log)}</div>
          </td>
          <td className="px-4 py-3 text-sm whitespace-nowrap">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium border ${colorClass}`}
            >
              {action}
            </span>
          </td>
          <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
            {getModuleDisplay(log)}
          </td>
          <td className="px-4 py-3 text-sm text-gray-600">
            <div className="leading-snug line-clamp-2">
              {getDescription(log) || "—"}
            </div>
          </td>
        </tr>
      );
    });
  };

  const selectedBeforeAfter = selectedLog ? getBeforeAfter(selectedLog) : null;

  const pageContent = (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-sky-600">Audit Trail</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleRefresh}
            className={BUTTON_SUBTLE}
            title="Refresh audit logs"
            type="button"
          >
            <RefreshCcw size={16} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            onClick={handleClearFilters}
            className={BUTTON_MUTED}
            title="Clear filters"
            type="button"
          >
            <Eraser size={16} />
            Clear
          </button>
          <button
            onClick={handleExportCsv}
            disabled={isExporting || loading || totalCount === 0}
            className={BUTTON_PRIMARY}
            title="Export filtered results as CSV"
            type="button"
          >
            <Download size={16} />
            {isExporting ? "Exporting..." : "Export CSV"}
          </button>
          <button
            onClick={handleApplyFilters}
            className={BUTTON_ACCENT}
            title="Apply filters"
            type="button"
          >
            <Filter size={16} />
            Apply Filters
          </button>
        </div>
      </div>

      <div>
        <div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">
                Date From
              </label>
              <input
                type="date"
                value={filters.dateFrom}
                max={filters.dateTo || undefined}
                onChange={(e) => handleFilterChange("dateFrom", e.target.value)}
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">
                Date To
              </label>
              <input
                type="date"
                value={filters.dateTo}
                min={filters.dateFrom || undefined}
                onChange={(e) => handleFilterChange("dateTo", e.target.value)}
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">User</label>
              <input
                type="text"
                value={filters.user}
                onChange={(e) => handleFilterChange("user", e.target.value)}
                placeholder="Email or name"
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">Role</label>
              <select
                value={filters.role}
                onChange={(e) => handleFilterChange("role", e.target.value)}
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">
                Action Type
              </label>
              <select
                value={filters.actionType}
                onChange={(e) =>
                  handleFilterChange("actionType", e.target.value)
                }
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              >
                {ACTION_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-700">
                Keyword
              </label>
              <input
                type="text"
                value={filters.keyword}
                onChange={(e) => handleFilterChange("keyword", e.target.value)}
                placeholder="Search description or module"
                className="px-3 py-2 mt-1 text-sm border border-gray-300 rounded-md shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"></div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded">
        <div className="overflow-x-auto">
          <div className="custom-scrollbar max-h-[calc(100vh-360px)] overflow-y-auto">
            <table className="min-w-full">
              <thead>
                <tr className="sticky top-0 z-10 text-xs font-semibold tracking-wide text-left text-white uppercase bg-gradient-to-r from-sky-600 to-sky-700">
                  <th className="px-4 py-3">Date &amp; Time</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Action Type</th>
                  <th className="px-4 py-3">Module / Section</th>
                  <th className="px-4 py-3">Description</th>
                </tr>
              </thead>
              <tbody className="bg-white">{renderTableBody()}</tbody>
            </table>
          </div>
        </div>
      </div>
      <div>
        <PaginationControls
          currentPage={page}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={totalCount}
          filteredItems={totalCount}
          hasActiveFilters={hasActiveFilters}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          startItem={startItem}
          endItem={endItem}
          storageKey={storageKey}
        />
      </div>

      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/50">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded bg-white shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Audit Log Details
                </h2>
                <p className="text-sm text-gray-500">
                  Logged on {formatDateTime(selectedLog.created_at)}
                </p>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="px-3 py-1 text-sm font-medium text-gray-600 border rounded-md border-gray-00 hover:bg-gray-100"
              >
                Close
              </button>
            </div>

            <div className="px-5 py-4 space-y-4">
              <section className="grid gap-4 md:grid-cols-2">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase">
                    User
                  </h3>
                  <p className="mt-1 text-sm font-medium text-gray-900">
                    {getUserDisplay(selectedLog)}
                  </p>
                  <p className="text-sm text-gray-600">
                    Role: {getRoleDisplay(selectedLog)}
                  </p>
                  {selectedLog.user_details?.email && (
                    <p className="text-sm text-gray-600">
                      Email: {selectedLog.user_details.email}
                    </p>
                  )}
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase">
                    Action
                  </h3>
                  <p className="mt-1 text-sm font-medium text-gray-900">
                    {normalizeAction(
                      selectedLog.action_type || selectedLog.action
                    )}
                  </p>
                  <p className="text-sm text-gray-600">
                    Module: {getModuleDisplay(selectedLog)}
                  </p>
                  <p className="text-sm text-gray-600">
                    IP Address: {selectedLog.ip_address || "—"}
                  </p>
                </div>
              </section>

              <section>
                <h3 className="text-xs font-semibold text-gray-500 uppercase">
                  Description
                </h3>
                <p className="p-3 mt-1 text-sm text-gray-700 whitespace-pre-wrap border border-gray-200 rounded-lg bg-gray-50">
                  {getDescription(selectedLog) || "No description provided."}
                </p>
              </section>

              {(selectedBeforeAfter?.before || selectedBeforeAfter?.after) && (
                <section className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 uppercase">
                      Before Data
                    </h3>
                    <pre className="p-3 mt-1 overflow-auto text-xs text-gray-700 border border-gray-200 rounded-lg max-h-60 bg-gray-50">
                      {selectedBeforeAfter.before
                        ? JSON.stringify(selectedBeforeAfter.before, null, 2)
                        : "—"}
                    </pre>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 uppercase">
                      After Data
                    </h3>
                    <pre className="p-3 mt-1 overflow-auto text-xs text-gray-700 border border-gray-200 rounded-lg max-h-60 bg-gray-50">
                      {selectedBeforeAfter.after
                        ? JSON.stringify(selectedBeforeAfter.after, null, 2)
                        : "—"}
                    </pre>
                  </div>
                </section>
              )}

              {hasMetadata(selectedLog) && (
                <section>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase">
                    Additional Details
                  </h3>
                  <div className="mt-1 overflow-hidden border border-gray-200 rounded-lg">
                    <dl className="divide-y divide-gray-200">
                      {Object.entries(selectedLog.metadata).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="grid grid-cols-3 gap-4 px-4 py-2 text-sm text-gray-700"
                          >
                            <dt className="font-medium text-gray-600 capitalize">
                              {key.replace(/_/g, " ")}
                            </dt>
                            <dd className="col-span-2 text-gray-800 break-words">
                              {typeof value === "object"
                                ? JSON.stringify(value, null, 2)
                                : String(value)}
                            </dd>
                          </div>
                        )
                      )}
                    </dl>
                  </div>
                </section>
              )}

              {selectedLog.user_details?.email && (
                <section>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase">
                    User Details
                  </h3>
                  <div className="p-3 mt-1 text-sm text-gray-700 border border-gray-200 rounded-lg bg-gray-50">
                    <p>Email: {selectedLog.user_details.email}</p>
                    {selectedLog.user_details.name && (
                      <p>Name: {selectedLog.user_details.name}</p>
                    )}
                  </div>
                </section>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel="admin">
        <div className="p-4">{pageContent}</div>
      </LayoutWithSidebar>
      <Footer />
    </>
  );
}
