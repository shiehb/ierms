// src/pages/DatabaseBackup.jsx
import React, { useState, useEffect, useMemo } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import ConfirmationDialog from "../components/common/ConfirmationDialog";
import { useNotifications } from "../hooks/useNotifications";
import ExportDropdown from "../components/ExportDropdown";
import PrintPDF from "../components/PrintPDF";
import DateRangeDropdown from "../components/DateRangeDropdown";
import PaginationControls from "../components/PaginationControls";
import TableToolbar from "../components/common/TableToolbar";
import { useLocalStoragePagination } from "../hooks/useLocalStoragePagination";
import useDebounce from "../hooks/useDebounce";
import {
  Save,
  Upload,
  Database,
  RotateCcw,
  RefreshCw,
  Search,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import {
  getProfile,
  createBackup,
  restoreBackupFromFile,
  restoreBackupById,
  getBackups,
  deleteBackup,
} from "../services/api";

const DatabaseBackup = () => {
  const [userLevel, setUserLevel] = useState("public");
  const [loadingUser, setLoadingUser] = useState(true);

  const [restoreFile, setRestoreFile] = useState(null);
  const [restoreFileName, setRestoreFileName] = useState("");

  const [processing, setProcessing] = useState(false);
  const [processingAction, setProcessingAction] = useState(""); // "backup", "restore", "delete"
  const notifications = useNotifications();

  const [restoreConfirm, setRestoreConfirm] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [backupToDelete, setBackupToDelete] = useState(null);
  const [backupConfirm, setBackupConfirm] = useState(false);
  const [backupPath, setBackupPath] = useState("");

  const [backups, setBackups] = useState([]);
  const [loadingBackups, setLoadingBackups] = useState(true);

  // 🔍 Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // 🎚 Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [backupTypeFilter, setBackupTypeFilter] = useState("all"); // "all", "backup", "restore"

  // ✅ Sorting
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });

  // ✅ Pagination with localStorage
  const savedPagination = useLocalStoragePagination("backups_list");
  const [currentPage, setCurrentPage] = useState(savedPagination.page);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);

  // ✅ Bulk select
  const [selectedBackups, setSelectedBackups] = useState([]);

  // fetch user level
  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        const profile = await getProfile();
        setUserLevel(profile.userlevel || "public");
      } catch (err) {
        console.error("Error fetching profile:", err);
        showMessage("Failed to load user profile", "error");
      } finally {
        setLoadingUser(false);
      }
    };
    fetchUserProfile();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // load backups list
  const loadBackups = async () => {
    try {
      setLoadingBackups(true);
      const data = await getBackups();
      setBackups(data.backups || []);
    } catch (error) {
      console.error("Error loading backups:", error);
      const errorMessage =
        error.response?.data?.error || "Failed to load backups";
      showMessage(errorMessage, "error");
    } finally {
      setLoadingBackups(false);
    }
  };

  useEffect(() => {
    loadBackups();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const showMessage = (msg, type = "success") => {
    if (type === "success") {
      notifications.success(msg, {
        title: "Backup Operation",
        duration: 4000,
      });
    } else if (type === "error") {
      notifications.error(msg, {
        title: "Backup Error",
        duration: 6000,
      });
    }
  };

  const handleBackup = async () => {
    // Prompt for directory selection first
    let selectedPath = "";

    try {
      // Check if the File System Access API is supported (Chrome/Edge)
      if ("showDirectoryPicker" in window) {
        const directoryHandle = await window.showDirectoryPicker({
          mode: "readwrite",
        });

        try {
          const permissionStatus = await directoryHandle.requestPermission({
            mode: "readwrite",
          });

          if (permissionStatus === "granted") {
            const name = directoryHandle.name;
            let pathInfo = name;

            if ("path" in directoryHandle && directoryHandle.path) {
              pathInfo = directoryHandle.path;
            }

            selectedPath = pathInfo;
          } else {
            selectedPath = directoryHandle.name;
          }
        } catch {
          selectedPath = directoryHandle.name;
        }
      } else {
        // Fallback for browsers that don't support File System Access API
        const manualPath = prompt(
          "Enter the full backup directory path:\n\n" +
            "Example Windows: C:\\Users\\YourName\\Documents\\backups\n" +
            "Example Linux: /home/username/backups\n" +
            "Example Mac: /Users/username/backups"
        );
        if (!manualPath) return;
        selectedPath = manualPath.trim();
      }

      if (!selectedPath) {
        showMessage("Please select a backup directory", "error");
        return;
      }

      // Validate that it's not a system directory path
      const normalizedPath = selectedPath.toLowerCase().replace(/\\/g, "/");
      const systemDirectories = [
        "windows",
        "program files",
        "program files (x86)",
        "system32",
        "syswow64",
        "programdata",
      ];

      const isSystemDirectory = systemDirectories.some(
        (sysDir) =>
          normalizedPath.includes(`/${sysDir}/`) ||
          normalizedPath.includes(`/${sysDir}\\`) ||
          normalizedPath.endsWith(`/${sysDir}`) ||
          normalizedPath === sysDir ||
          normalizedPath.startsWith(`${sysDir}/`) ||
          normalizedPath.startsWith(`${sysDir}\\`)
      );

      if (isSystemDirectory) {
        showMessage(
          "System directories are protected and cannot be used. Please use a safe location like Documents, Desktop, or create a custom backup folder (e.g., C:\\Users\\YourName\\Documents\\backups).",
          "error"
        );
        return;
      }

      // Store the selected path and show confirmation dialog
      setBackupPath(selectedPath);
      setBackupConfirm(true);
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Backup error:", error);
        const errorMessage =
          error.response?.data?.error ||
          error.message ||
          "Failed to create backup";
        showMessage(errorMessage, "error");
      }
    }
  };

  const handleConfirmBackup = async () => {
    if (!backupPath) return;

    try {
      setProcessing(true);
      setProcessingAction("backup");

      const response = await createBackup(backupPath);
      showMessage(response.message || "Backup created successfully!");
      loadBackups();
    } catch (error) {
      console.error("Backup error:", error);
      const errorMessage =
        error.response?.data?.error ||
        error.message ||
        "Failed to create backup";
      showMessage(errorMessage, "error");
    } finally {
      setProcessing(false);
      setProcessingAction("");
      setBackupConfirm(false);
      setBackupPath("");
    }
  };

  const handleRestore = async (backupId = null) => {
    try {
      setProcessing(true);
      setProcessingAction("restore");
      let response;

      if (backupId) {
        // Restore by backup record ID
        response = await restoreBackupById(backupId);
      } else if (restoreFile) {
        response = await restoreBackupFromFile(restoreFile);
      } else {
        showMessage("Please choose a backup file", "error");
        return;
      }

      showMessage(
        response.message || "Database restored successfully!",
        "success"
      );
      // Reset form
      setRestoreFile(null);
      setRestoreFileName("");
      loadBackups();
    } catch (error) {
      console.error("Restore error:", error);
      const errorMessage =
        error.response?.data?.error || "Failed to restore backup";
      showMessage(errorMessage, "error");
    } finally {
      setProcessing(false);
      setProcessingAction("");
      setRestoreConfirm(false);
    }
  };

  const handleDeleteBackup = async () => {
    if (!backupToDelete) return;

    try {
      setProcessing(true);
      setProcessingAction("delete");
      await deleteBackup(backupToDelete.fileName);
      showMessage("Backup deleted successfully!");
      loadBackups();
    } catch (error) {
      console.error("Delete error:", error);
      const errorMessage =
        error.response?.data?.error || "Failed to delete backup";
      showMessage(errorMessage, "error");
    } finally {
      setProcessing(false);
      setProcessingAction("");
      setDeleteConfirm(false);
      setBackupToDelete(null);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.name.endsWith(".sql")) {
        setRestoreFile(file);
        setRestoreFileName(file.name);
      } else {
        showMessage("Please select a .sql file", "error");
      }
    }
  };

  const formatFullDate = (dateString) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  // ✅ Sorting handler
  const handleSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        if (prev.direction === "asc") return { key, direction: "desc" };
        if (prev.direction === "desc") return { key: null, direction: null };
      }
      return { key, direction: "asc" };
    });
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return <ArrowUpDown size={14} />;
    return sortConfig.direction === "asc" ? (
      <ArrowUp size={14} />
    ) : (
      <ArrowDown size={14} />
    );
  };

  // ✅ Filter + Sort with LOCAL search (client-side only)
  const filteredBackups = useMemo(() => {
    let list = backups.filter((backup) => {
      // Apply local search filter
      const query = debouncedSearchQuery.toLowerCase();
      const fileName = (backup.fileName || "").toLowerCase();
      const location = (backup.location || "").toLowerCase();

      const matchesSearch = debouncedSearchQuery
        ? fileName.includes(query) || location.includes(query)
        : true;

      // Apply date filter
      const matchesDateFrom = dateFrom
        ? new Date(backup.created_at) >= new Date(dateFrom)
        : true;
      const matchesDateTo = dateTo
        ? new Date(backup.created_at) <= new Date(dateTo)
        : true;

      // Apply backup type filter
      const matchesTypeFilter =
        backupTypeFilter === "all"
          ? true
          : (backup.backup_type || "backup") === backupTypeFilter;

      return (
        matchesSearch && matchesDateFrom && matchesDateTo && matchesTypeFilter
      );
    });

    // Apply sorting
    if (sortConfig.key) {
      list = [...list].sort((a, b) => {
        let aVal, bVal;

        if (sortConfig.key === "created_at") {
          aVal = new Date(a.created_at).getTime();
          bVal = new Date(b.created_at).getTime();
        } else if (sortConfig.key === "backup_type") {
          aVal = a.backup_type || "backup";
          bVal = b.backup_type || "backup";
        } else {
          aVal = a[sortConfig.key] || "";
          bVal = b[sortConfig.key] || "";
        }

        if (typeof aVal === "string") aVal = aVal.toLowerCase();
        if (typeof bVal === "string") bVal = bVal.toLowerCase();

        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return list;
  }, [
    backups,
    debouncedSearchQuery,
    dateFrom,
    dateTo,
    sortConfig,
    backupTypeFilter,
  ]);

  // ✅ Pagination (client-side for now)
  const totalPages = Math.ceil(filteredBackups.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedBackups = filteredBackups.slice(startIndex, endIndex);

  // ✅ Selection
  const toggleSelect = (fileName) => {
    setSelectedBackups((prev) =>
      prev.includes(fileName)
        ? prev.filter((x) => x !== fileName)
        : [...prev, fileName]
    );
  };

  const toggleSelectAll = () => {
    if (selectedBackups.length === paginatedBackups.length) {
      setSelectedBackups([]);
    } else {
      setSelectedBackups(paginatedBackups.map((backup) => backup.fileName));
    }
  };

  // Clear functions
  const clearSearch = () => setSearchQuery("");
  const clearAllFilters = () => {
    setSearchQuery("");
    setDateFrom("");
    setDateTo("");
    setBackupTypeFilter("all");
    setSortConfig({ key: null, direction: null });
    setCurrentPage(1);
  };

  // Pagination functions
  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  const totalBackups = backups.length;
  const filteredCount = filteredBackups.length;
  const hasActiveFilters =
    searchQuery ||
    dateFrom ||
    dateTo ||
    backupTypeFilter !== "all" ||
    sortConfig.key;

  // Calculate display range
  const startItem = startIndex + 1;
  const endItem = Math.min(endIndex, filteredCount);

  if (loadingUser) {
    return (
      <>
        <Header />
        <LayoutWithSidebar>
          <div className="flex flex-col items-center justify-center min-h-[200px]">
            <div className="w-8 h-8 mb-2 border-b-2 rounded-full border-sky-600 animate-spin"></div>
            <p className="text-gray-600">Loading Backup Page...</p>
          </div>
        </LayoutWithSidebar>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel={userLevel}>
        <div className="p-4 bg-white overflow-y-auto">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h1 className="text-2xl font-bold text-sky-600">
              Database Backup & Restore
            </h1>

            <TableToolbar
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              onSearchClear={clearSearch}
              searchPlaceholder="Search..."
              sortConfig={sortConfig}
              sortFields={[
                { key: "fileName", label: "File Name" },
                { key: "location", label: "Location" },
                { key: "created_at", label: "Created Date" },
                { key: "backup_type", label: "Type" },
              ]}
              onSort={(fieldKey, directionKey) => {
                if (fieldKey === null && directionKey === null) {
                  setSortConfig({ key: null, direction: null });
                } else {
                  setSortConfig({
                    key: fieldKey,
                    direction: directionKey || "asc",
                  });
                }
              }}
              typeFilterValue={backupTypeFilter}
              typeFilterOptions={[
                { value: "all", label: "Show All" },
                { value: "backup", label: "Backup" },
                { value: "restore", label: "Restore" },
              ]}
              onTypeFilterChange={setBackupTypeFilter}
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFromChange={setDateFrom}
              onDateToChange={setDateTo}
              exportConfig={{
                title: "Backups Export Report",
                fileName: "backups_export",
                columns: ["File Name", "Type", "Location", "Created At"],
                rows:
                  selectedBackups.length > 0
                    ? selectedBackups
                        .map((fileName) => {
                          const backup = backups.find(
                            (b) => b.fileName === fileName
                          );
                          return backup
                            ? [
                                backup.fileName,
                                backup.backup_type === "restore"
                                  ? "Restore"
                                  : "Backup",
                                backup.location || "-",
                                formatFullDate(backup.created_at),
                              ]
                            : [];
                        })
                        .filter((row) => row.length > 0)
                    : backups.map((backup) => [
                        backup.fileName,
                        backup.backup_type === "restore" ? "Restore" : "Backup",
                        backup.location || "-",
                        formatFullDate(backup.created_at),
                      ]),
              }}
              printConfig={{
                title: "Backups Report",
                fileName: "backups_report",
                columns: ["File Name", "Type", "Location", "Created At"],
                rows:
                  selectedBackups.length > 0
                    ? selectedBackups
                        .map((fileName) => {
                          const backup = backups.find(
                            (b) => b.fileName === fileName
                          );
                          return backup
                            ? [
                                backup.fileName,
                                backup.backup_type === "restore"
                                  ? "Restore"
                                  : "Backup",
                                backup.location || "-",
                                formatFullDate(backup.created_at),
                              ]
                            : [];
                        })
                        .filter((row) => row.length > 0)
                    : backups.map((backup) => [
                        backup.fileName,
                        backup.backup_type === "restore" ? "Restore" : "Backup",
                        backup.location || "-",
                        formatFullDate(backup.created_at),
                      ]),
              }}
              onRefresh={loadBackups}
              isRefreshing={loadingBackups}
            />
          </div>

          {/* Updated Layout: Left (backup/restore cards) - Right (table) */}
          <div className="grid grid-cols-1 lg:grid-cols-[30%_70%] gap-4">
            {/* Left Column: Backup & Restore Cards */}
            <div className="flex flex-col gap-6">
              {/* Create Backup Card */}
              <div className="flex flex-col p-4 bg-white border border-gray-200 rounded-lg shadow">
                <h2 className="mb-2 text-lg font-semibold text-sky-600">
                  Create Backup
                </h2>
                <div className="flex-1 space-y-4">
                  <p className="text-sm text-gray-600">
                    Click the button below to create a new backup. You will be
                    prompted to select where to save the backup file.
                  </p>
                  <button
                    onClick={handleBackup}
                    disabled={processing && processingAction === "backup"}
                    className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white transition-colors bg-sky-600 rounded-md hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed w-full"
                  >
                    {processing && processingAction === "backup" ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        Creating Backup...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4" />
                        Create Backup
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Restore Backup Card */}
              <div className="flex flex-col p-4 bg-white border border-gray-200 rounded-lg shadow">
                <h2 className="mb-4 text-lg font-semibold text-sky-600">
                  Restore Backup
                </h2>
                <div className="flex-1 space-y-6">
                  {/* Restore File Selection */}
                  <div>
                    <label className="block mb-1 text-sm font-medium text-gray-700">
                      Select Backup File
                    </label>
                    <div
                      onDrop={(e) => {
                        e.preventDefault();
                        if (e.dataTransfer.files.length > 0) {
                          const file = e.dataTransfer.files[0];
                          if (file.name.endsWith(".sql")) {
                            setRestoreFile(file);
                            setRestoreFileName(file.name);
                          } else {
                            showMessage("Please drop a .sql file", "error");
                          }
                        }
                      }}
                      onDragOver={(e) => e.preventDefault()}
                      className={`flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-6 cursor-pointer transition 
                        ${
                          restoreFile
                            ? "border-green-600 bg-green-50"
                            : "border-gray-300 hover:border-sky-500 hover:bg-sky-50"
                        }`}
                      onClick={() =>
                        document.getElementById("fileInput").click()
                      }
                    >
                      {restoreFile ? (
                        <>
                          <p className="text-sm font-medium text-gray-800">
                            {restoreFileName}
                          </p>
                          <p className="mt-1 text-xs text-gray-500">
                            File ready to restore
                          </p>
                          <p className="mt-2 text-xs font-medium text-green-600">
                            ✓ Ready to restore
                          </p>
                        </>
                      ) : (
                        <>
                          <Upload className="mb-2 text-gray-400" size={24} />
                          <p className="text-sm text-gray-600">
                            Drag & drop a backup file here
                          </p>
                          <p className="mt-1 text-xs text-gray-400">
                            or click to browse (.sql files only)
                          </p>
                        </>
                      )}
                      <input
                        id="fileInput"
                        type="file"
                        className="hidden"
                        accept=".sql"
                        onChange={handleFileSelect}
                      />
                    </div>
                  </div>
                </div>
                <div className="flex justify-end mt-6">
                  <button
                    onClick={() => setRestoreConfirm(true)}
                    disabled={processing || !restoreFile}
                    className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white transition-colors bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed w-full"
                  >
                    {processing && processingAction === "restore" ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        Restoring...
                      </>
                    ) : (
                      <>
                        <RotateCcw className="w-4 h-4" />
                        Restore Backup
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Backup & Restore Records Table */}
            <div className="bg-white pr-4">
              {/* Table */}
              <div className="overflow-y-auto h-[calc(100vh-280px)] border border-gray-300 rounded scroll-smooth custom-scrollbar">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700 sticky top-0 z-10">
                      <th className="w-6 px-3 py-2 text-center border-b border-gray-300">
                        <input
                          type="checkbox"
                          checked={
                            selectedBackups.length > 0 &&
                            selectedBackups.length === paginatedBackups.length
                          }
                          onChange={toggleSelectAll}
                        />
                      </th>
                      {[
                        { key: "fileName", label: "File Name", sortable: true },
                        { key: "backup_type", label: "Type", sortable: true },
                        { key: "location", label: "Location", sortable: true },
                        {
                          key: "created_at",
                          label: "Created At",
                          sortable: true,
                        },
                      ].map((col) => (
                        <th
                          key={col.key}
                          className={`px-3 py-2 border-b border-gray-300 ${
                            col.sortable ? "cursor-pointer" : ""
                          }`}
                          onClick={
                            col.sortable ? () => handleSort(col.key) : undefined
                          }
                        >
                          <div className="flex items-center gap-1">
                            {col.label} {col.sortable && getSortIcon(col.key)}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loadingBackups ? (
                      <tr>
                        <td
                          colSpan="5"
                          className="px-2 py-8 text-center border-b border-gray-300"
                        >
                          <div
                            className="flex flex-col items-center justify-center p-4"
                            role="status"
                            aria-live="polite"
                          >
                            <div className="w-8 h-8 mb-2 border-b-2 border-gray-900 rounded-full animate-spin"></div>
                            <p className="text-sm text-gray-600">
                              Loading backups...
                            </p>
                          </div>
                        </td>
                      </tr>
                    ) : paginatedBackups.length === 0 ? (
                      <tr>
                        <td
                          colSpan="5"
                          className="px-2 py-4 text-center text-gray-500 border-b border-gray-300"
                        >
                          {hasActiveFilters ? (
                            <div>
                              No backups found matching your criteria.
                              <br />
                              <button
                                onClick={clearAllFilters}
                                className="mt-2 underline text-sky-600 hover:text-sky-700"
                              >
                                Clear all filters
                              </button>
                            </div>
                          ) : (
                            <div className="flex flex-col items-center justify-center">
                              <Database
                                className="mb-2 text-gray-400"
                                size={32}
                              />
                              <p className="text-sm">No backups available</p>
                              <p className="mt-1 text-xs">
                                Create your first backup using the form above
                              </p>
                            </div>
                          )}
                        </td>
                      </tr>
                    ) : (
                      paginatedBackups.map((backup) => {
                        const backupType = backup.backup_type || "backup";
                        const isBackup = backupType === "backup";
                        const isRestore = backupType === "restore";

                        return (
                          <tr
                            key={backup.fileName}
                            className={`text-xs border-b border-gray-300 transition-colors ${
                              isBackup
                                ? "bg-blue-50 hover:bg-blue-100"
                                : isRestore
                                ? "bg-green-50 hover:bg-green-100"
                                : "hover:bg-gray-50"
                            }`}
                          >
                            <td className="text-center px-3 py-2 border-b border-gray-300">
                              <input
                                type="checkbox"
                                checked={selectedBackups.includes(
                                  backup.fileName
                                )}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  toggleSelect(backup.fileName);
                                }}
                              />
                            </td>
                            <td className="px-3 py-2 border-b border-gray-300">
                              <span className="font-semibold text-gray-900">
                                {backup.fileName}
                              </span>
                            </td>
                            <td className="px-3 py-2 border-b border-gray-300">
                              <span
                                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                  isBackup
                                    ? "bg-blue-100 text-blue-800"
                                    : isRestore
                                    ? "bg-green-100 text-green-800"
                                    : "bg-gray-100 text-gray-800"
                                }`}
                              >
                                {isBackup
                                  ? "Backup"
                                  : isRestore
                                  ? "Restore"
                                  : backupType}
                              </span>
                            </td>
                            <td className="px-3 py-2 border-b border-gray-300">
                              <span
                                className="truncate max-w-xs block text-gray-600"
                                title={backup.location}
                              >
                                {backup.location || "-"}
                              </span>
                            </td>
                            <td className="px-3 py-2 border-b border-gray-300">
                              <span className="text-gray-500">
                                {formatFullDate(backup.created_at)}
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              <PaginationControls
                currentPage={currentPage}
                totalPages={totalPages}
                pageSize={pageSize}
                totalItems={totalBackups}
                filteredItems={filteredCount}
                hasActiveFilters={hasActiveFilters}
                onPageChange={goToPage}
                onPageSizeChange={(newSize) => {
                  setPageSize(newSize);
                  setCurrentPage(1);
                }}
                startItem={startItem}
                endItem={endItem}
                storageKey="backups_list"
              />
            </div>
          </div>

          <ConfirmationDialog
            open={restoreConfirm}
            title="Confirm Database Restore"
            message={
              <div>
                <p className="mb-2 font-semibold text-red-600">
                  WARNING: This action cannot be undone!
                </p>
                <p className="mb-2">Restoring will:</p>
                <ul className="mb-3 ml-4 text-sm list-disc">
                  <li>Overwrite all existing data</li>
                  <li>Replace current database contents</li>
                  <li>Potentially cause data loss</li>
                </ul>
                <p className="text-sm">
                  <strong>Backup to restore:</strong> {restoreFileName}
                </p>
                <p className="mt-2">Are you sure you want to continue?</p>
              </div>
            }
            loading={processing && processingAction === "restore"}
            onCancel={() => {
              setRestoreConfirm(false);
            }}
            onConfirm={() => handleRestore()}
            confirmText="Yes, Restore Now"
            cancelText="Cancel"
            confirmColor="red"
            size="md"
          />

          <ConfirmationDialog
            open={backupConfirm}
            title="Confirm Backup Creation"
            message={
              <div>
                <p className="mb-2">
                  You are about to create a database backup.
                </p>
                <p className="mb-2 text-sm text-gray-600">
                  <strong>Backup location:</strong> {backupPath}
                </p>
                <p className="text-sm">
                  This may take a few moments. Do you want to continue?
                </p>
              </div>
            }
            loading={processing && processingAction === "backup"}
            onCancel={() => {
              setBackupConfirm(false);
              setBackupPath("");
            }}
            onConfirm={handleConfirmBackup}
            confirmText="Create Backup"
            cancelText="Cancel"
            confirmColor="sky"
            size="md"
          />

          <ConfirmationDialog
            open={deleteConfirm}
            title="Confirm Backup Deletion"
            message={`Are you sure you want to delete backup "${backupToDelete?.fileName}"? This action cannot be undone.`}
            loading={processing && processingAction === "delete"}
            onCancel={() => {
              setDeleteConfirm(false);
              setBackupToDelete(null);
            }}
            onConfirm={handleDeleteBackup}
            confirmText="Delete Backup"
            cancelText="Cancel"
            confirmColor="red"
          />
        </div>
      </LayoutWithSidebar>
      <Footer />
    </>
  );
};

export default DatabaseBackup;
