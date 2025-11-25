import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  Pencil,
  UserCheck,
  UserX,
  Plus,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Filter,
  User,
  MoreHorizontal,
} from "lucide-react";
import { useLocation } from "react-router-dom";
import api, { toggleUserActive, getProfile } from "../../services/api";
import ConfirmationDialog from "../common/ConfirmationDialog";
import { useNotifications } from "../../hooks/useNotifications";
import PaginationControls from "../PaginationControls";
import { useLocalStoragePagination } from "../../hooks/useLocalStoragePagination";
import { canExportAndPrint } from "../../utils/permissions";
import TableToolbar from "../common/TableToolbar";

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

// Section options depending on role
const sectionOptionsByLevel = {
  "Section Chief": [
    {
      value: "PD-1586,RA-8749,RA-9275",
      label: "EIA, Air & Water Quality Monitoring Section",
    },
    {
      value: "RA-6969",
      label: "Toxic Chemicals & Hazardous Monitoring Section",
    },
    { value: "RA-9003", label: "Ecological Solid Waste Management Section" },
  ],
  "Unit Head": [
    { value: "PD-1586", label: "EIA Monitoring Unit" },
    { value: "RA-8749", label: "Air Quality Monitoring Unit" },
    { value: "RA-9275", label: "Water Quality Monitoring Unit" },
  ],
  "Monitoring Personnel": [
    { value: "PD-1586", label: "EIA Monitoring Personnel" },
    { value: "RA-8749", label: "Air Quality Monitoring Personnel" },
    { value: "RA-9275", label: "Water Quality Monitoring Personnel" },
    { value: "RA-6969", label: "Toxic Chemicals Monitoring Personnel" },
    { value: "RA-9003", label: "Solid Waste Monitoring Personnel" },
  ],
};

// Create comprehensive section display mapping with role context
const getSectionDisplayName = (sectionValue, userlevel) => {
  if (!sectionValue) return "";

  // First, check if this section exists in the userlevel's options
  if (userlevel && sectionOptionsByLevel[userlevel]) {
    const sectionOption = sectionOptionsByLevel[userlevel].find(
      (opt) => opt.value === sectionValue
    );
    if (sectionOption) {
      return sectionOption.label;
    }
  }

  // Fallback mapping for when userlevel is not available
  const fallbackMap = {
    "PD-1586,RA-8749,RA-9275": "EIA, Air & Water Quality Monitoring Section",
    "RA-6969": "Toxic Chemicals & Hazardous Monitoring Section",
    "RA-9003": "Ecological Solid Waste Management Section",
    "PD-1586": "EIA Monitoring",
    "RA-8749": "Air Quality Monitoring",
    "RA-9275": "Water Quality Monitoring",
  };

  const baseName = fallbackMap[sectionValue] || sectionValue;

  // Add appropriate suffix based on common patterns
  if (sectionValue === "RA-6969") {
    return "Toxic Chemicals & Hazardous Monitoring Section";
  } else if (sectionValue === "RA-9003") {
    return "Ecological Solid Waste Management Section";
  }

  return baseName;
};

// Add user role display names
const userRoleDisplayNames = {
  "Legal Unit": "Legal Unit",
  "Division Chief": "Division Chief",
  "Section Chief": "Section Chief",
  "Unit Head": "Unit Head",
  "Monitoring Personnel": "Monitoring Personnel",
};

// Helper function to get full role display with section
const getRoleDisplay = (userlevel, section) => {
  const roleDisplay = userRoleDisplayNames[userlevel] || userlevel || "";

  if (section) {
    const sectionDisplay = getSectionDisplayName(section, userlevel);
    return `${roleDisplay} - ${sectionDisplay}`;
  }

  return roleDisplay;
};

export default function UsersList({ onAdd, onEdit, refreshTrigger }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);

  // 🔒 User level for permissions
  const [userLevel, setUserLevel] = useState(null);

  // 🔍 Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // 🎯 Search highlighting
  const location = useLocation();
  const [highlightedUserId, setHighlightedUserId] = useState(null);
  const highlightedRowRef = useRef(null);

  // 🎚 Filters
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [roleFilter, setRoleFilter] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // ✅ Sorting
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });

  // ✅ Pagination with localStorage
  const savedPagination = useLocalStoragePagination("users_list");
  const [currentPage, setCurrentPage] = useState(savedPagination.page);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);

  // ✅ Bulk select
  const [selectedUsers, setSelectedUsers] = useState([]);

  // 📤 Export Modal

  const fetchAllUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        page_size: pageSize.toString(),
      });

      // Add search parameter if provided
      if (debouncedSearchQuery) {
        params.append("search", debouncedSearchQuery);
      }

      // Add role filter if selected
      if (roleFilter.length > 0) {
        params.append("role", roleFilter.join(","));
      }

      // Add status filter if selected
      if (statusFilter.length > 0) {
        params.append("status", statusFilter.join(","));
      }

      const res = await api.get(`auth/list/?${params.toString()}`);

      if (res.data.results) {
        // Server-side paginated response
        setUsers(res.data.results);
        setTotalCount(res.data.count || 0);
      } else {
        // Fallback for non-paginated response
        setUsers(res.data);
        setTotalCount(res.data.length);
      }
    } catch (err) {
      console.error("Error fetching users:", err);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, debouncedSearchQuery, roleFilter, statusFilter]);

  // Fetch user level on mount
  useEffect(() => {
    const fetchUserLevel = async () => {
      try {
        const profile = await getProfile();
        setUserLevel(profile.userlevel);
      } catch (error) {
        console.error("Error fetching user profile:", error);
        // Fallback to localStorage
        setUserLevel(localStorage.getItem("userLevel") || null);
      }
    };
    fetchUserLevel();
  }, []);

  // Fetch all users on component mount and when pagination/filters change
  useEffect(() => {
    fetchAllUsers();
  }, [refreshTrigger, fetchAllUsers]);

  // Handle highlighting from search navigation
  useEffect(() => {
    if (location.state?.highlightId && location.state?.entityType === "user") {
      setHighlightedUserId(location.state.highlightId);

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

  const formatFullDate = (dateString) => {
    if (!dateString) return "";
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
    // Removed auto-close: setSortDropdownOpen(false);
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
  const filteredUsers = useMemo(() => {
    let list = users.filter((u) => {
      // Apply local search filter
      const query = debouncedSearchQuery.toLowerCase();
      const fullName = `${u.first_name || ""} ${u.middle_name || ""} ${
        u.last_name || ""
      }`.toLowerCase();
      const userRoleDisplay =
        userRoleDisplayNames[u.userlevel] || u.userlevel || "";
      const sectionDisplay =
        getSectionDisplayName(u.section, u.userlevel) || "";
      const roleWithSection = getRoleDisplay(u.userlevel, u.section) || "";

      const matchesSearch = debouncedSearchQuery
        ? fullName.includes(query) ||
          (u.email || "").toLowerCase().includes(query) ||
          userRoleDisplay.toLowerCase().includes(query) ||
          sectionDisplay.toLowerCase().includes(query) ||
          roleWithSection.toLowerCase().includes(query)
        : true;

      // Apply role filter
      const matchesRole =
        roleFilter.length === 0 || roleFilter.includes(u.userlevel);

      // Apply status filter
      const matchesStatus =
        statusFilter.length === 0
          ? true
          : statusFilter.includes(u.is_active ? "Active" : "Inactive");

      // Apply date filter
      const matchesDateFrom = dateFrom
        ? new Date(u.date_joined) >= new Date(dateFrom)
        : true;
      const matchesDateTo = dateTo
        ? new Date(u.date_joined) <= new Date(dateTo)
        : true;

      return (
        matchesSearch &&
        matchesRole &&
        matchesStatus &&
        matchesDateFrom &&
        matchesDateTo
      );
    });

    // Apply sorting
    if (sortConfig.key) {
      list = [...list].sort((a, b) => {
        let aVal, bVal;

        if (sortConfig.key === "fullname" || sortConfig.key === "user") {
          aVal = `${a.first_name || ""} ${a.middle_name || ""} ${
            a.last_name || ""
          }`.toLowerCase();
          bVal = `${b.first_name || ""} ${b.middle_name || ""} ${
            b.last_name || ""
          }`.toLowerCase();
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
    users,
    debouncedSearchQuery,
    roleFilter,
    statusFilter,
    dateFrom,
    dateTo,
    sortConfig,
  ]);

  // ✅ Pagination (using server-side pagination, so no need for paginatedUsers)

  const totalPages = Math.ceil(filteredUsers.length / pageSize);

  // ✅ Selection
  const toggleSelect = (id) => {
    setSelectedUsers((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedUsers.length === users.length) {
      setSelectedUsers([]);
    } else {
      setSelectedUsers(users.map((u) => u.id));
    }
  };

  // Toggle role & status filter checkboxes
  const toggleRole = (role) =>
    setRoleFilter((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );

  const toggleStatus = (status) =>
    setStatusFilter((prev) =>
      prev.includes(status)
        ? prev.filter((s) => s !== status)
        : [...prev, status]
    );

  // Clear functions
  const clearSearch = () => setSearchQuery("");
  const clearAllFilters = () => {
    setSearchQuery("");
    setRoleFilter([]);
    setStatusFilter([]);
    setDateFrom("");
    setDateTo("");
    setSortConfig({ key: null, direction: null });
    setCurrentPage(1);
  };

  // Pagination functions
  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  const totalUsers = totalCount;
  const filteredCount = totalCount; // Server-side filtering
  const hasActiveFilters =
    searchQuery ||
    roleFilter.length > 0 ||
    statusFilter.length > 0 ||
    dateFrom ||
    dateTo ||
    sortConfig.key;
  const activeFilterCount =
    roleFilter.length +
    statusFilter.length +
    (dateFrom ? 1 : 0) +
    (dateTo ? 1 : 0);

  // Calculate display range
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, filteredCount);

  // Custom filters dropdown for TableToolbar
  const customFiltersDropdown = (
    <div className="absolute right-0 top-full z-20 w-64 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto custom-scrollbar">
      <div className="p-2">
        {/* Header with Clear All */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Filters
          </div>
          {activeFilterCount > 0 && (
            <button
              onClick={() => {
                setRoleFilter([]);
                setStatusFilter([]);
              }}
              className="px-2 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            >
              Clear All
            </button>
          )}
        </div>

        {/* Role Section */}
        <div className="mb-3">
          <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
            User Role
          </div>
          {[
            "Legal Unit",
            "Division Chief",
            "Section Chief",
            "Unit Head",
            "Monitoring Personnel",
          ].map((role) => (
            <button
              key={role}
              onClick={() => toggleRole(role)}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                roleFilter.includes(role) ? "bg-sky-50 font-medium" : ""
              }`}
            >
              <div className="flex-1 text-left">
                <div className="font-medium">
                  {userRoleDisplayNames[role] || role}
                </div>
              </div>
              {roleFilter.includes(role) && (
                <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
              )}
            </button>
          ))}
        </div>

        {/* Status Section */}
        <div className="mb-2">
          <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
            User Status
          </div>
          {["Active", "Inactive"].map((status) => (
            <button
              key={status}
              onClick={() => toggleStatus(status)}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                statusFilter.includes(status) ? "bg-sky-50 font-medium" : ""
              }`}
            >
              <div className="flex-1 text-left">
                <div className="font-medium">{status}</div>
              </div>
              {statusFilter.includes(status) && (
                <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-4 bg-white h-[calc(100vh-160px)]">
      {/* Top controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h1 className="text-2xl font-bold text-sky-600">Users Management</h1>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <TableToolbar
            searchValue={searchQuery}
            onSearchChange={setSearchQuery}
            onSearchClear={clearSearch}
            searchPlaceholder="Search..."
            sortConfig={sortConfig}
            sortFields={[
              { key: "user", label: "User Name" },
              { key: "date_joined", label: "Date Joined" },
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
            onFilterClick={() => setFiltersOpen(!filtersOpen)}
            customFilterDropdown={filtersOpen ? customFiltersDropdown : null}
            filterOpen={filtersOpen}
            onFilterClose={() => setFiltersOpen(false)}
            dateFrom={dateFrom}
            dateTo={dateTo}
            onDateFromChange={setDateFrom}
            onDateToChange={setDateTo}
            exportConfig={
              canExportAndPrint(userLevel, "users")
                ? {
                    title: "Users Export Report",
                    fileName: "users_export",
                    columns: [
                      "ID",
                      "Name",
                      "Email",
                      "User Level",
                      "Section",
                      "Status",
                      "Date Created",
                    ],
                    rows:
                      selectedUsers.length > 0
                        ? filteredUsers
                            .filter((user) => selectedUsers.includes(user.id))
                            .map((user) => [
                              user.id,
                              `${user.first_name} ${user.last_name}`,
                              user.email,
                              user.userlevel,
                              user.section || "N/A",
                              user.is_active ? "Active" : "Inactive",
                              new Date(user.date_joined).toLocaleDateString(),
                            ])
                        : filteredUsers.map((user) => [
                            user.id,
                            `${user.first_name} ${user.last_name}`,
                            user.email,
                            user.userlevel,
                            user.section || "N/A",
                            user.is_active ? "Active" : "Inactive",
                            new Date(user.date_joined).toLocaleDateString(),
                          ]),
                  }
                : null
            }
            printConfig={
              canExportAndPrint(userLevel, "users")
                ? {
                    title: "Users Report",
                    fileName: "users_report",
                    columns: [
                      "ID",
                      "Name",
                      "Email",
                      "User Level",
                      "Section",
                      "Status",
                      "Date Created",
                    ],
                    rows:
                      selectedUsers.length > 0
                        ? filteredUsers
                            .filter((user) => selectedUsers.includes(user.id))
                            .map((user) => [
                              user.id,
                              `${user.first_name} ${user.last_name}`,
                              user.email,
                              user.userlevel,
                              user.section || "N/A",
                              user.is_active ? "Active" : "Inactive",
                              new Date(user.date_joined).toLocaleDateString(),
                            ])
                        : filteredUsers.map((user) => [
                            user.id,
                            `${user.first_name} ${user.last_name}`,
                            user.email,
                            user.userlevel,
                            user.section || "N/A",
                            user.is_active ? "Active" : "Inactive",
                            new Date(user.date_joined).toLocaleDateString(),
                          ]),
                  }
                : null
            }
            onRefresh={fetchAllUsers}
            isRefreshing={loading}
            additionalActions={[
              {
                onClick: onAdd,
                icon: Plus,
                title: "Add User",
                text: "Add User",
                variant: "primary",
              },
            ]}
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-y-auto h-[calc(100vh-260px)] border border-gray-300 rounded scroll-smooth custom-scrollbar">
        <table className="w-full">
          <thead>
            <tr className="text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700 sticky top-0 z-10">
              <th className="w-6 px-3 py-2 text-center border-b border-gray-300">
                <input
                  type="checkbox"
                  checked={
                    selectedUsers.length > 0 &&
                    selectedUsers.length === users.length
                  }
                  onChange={toggleSelectAll}
                />
              </th>
              {[
                { key: "user", label: "User", sortable: true },
                { key: "userlevel", label: "Role", sortable: false },
                { key: "is_active", label: "Status", sortable: false },
                { key: "date_joined", label: "Created Date", sortable: true },
              ].map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 border-b border-gray-300 ${
                    col.sortable ? "cursor-pointer" : ""
                  } ${col.key === "is_active" ? "text-center" : ""}`}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                >
                  <div
                    className={`flex items-center gap-1 ${
                      col.key === "is_active" ? "justify-center" : ""
                    }`}
                  >
                    {col.label} {col.sortable && getSortIcon(col.key)}
                  </div>
                </th>
              ))}

              <th className="px-3 py-2 text-right border-b border-gray-300 w-10">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan="6"
                  className="px-2 py-8 text-center border-b border-gray-300"
                >
                  <div
                    className="flex flex-col items-center justify-center p-4"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="w-8 h-8 mb-2 border-b-2 border-gray-900 rounded-full animate-spin"></div>
                    <p className="text-sm text-gray-600">Loading users...</p>
                  </div>
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td
                  colSpan="6"
                  className="px-2 py-4 text-center h-[calc(100vh-295px)] text-gray-500 border-b border-gray-300"
                >
                  <div className="flex flex-col items-center justify-center h-full gap-2">
                    {hasActiveFilters ? (
                      <>
                        <span>No users found matching your criteria.</span>
                        <button
                          onClick={clearAllFilters}
                          className="underline text-sky-600 hover:text-sky-700"
                        >
                          Clear all filters
                        </button>
                      </>
                    ) : (
                      <span>No users found.</span>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr
                  key={u.id}
                  ref={u.id === highlightedUserId ? highlightedRowRef : null}
                  className={`text-xs border-b border-gray-300 hover:bg-gray-50 transition-colors ${
                    u.id === highlightedUserId ? "search-highlight-persist" : ""
                  }`}
                  onClick={() => setHighlightedUserId(u.id)}
                >
                  <td className="text-center px-3 py-2 border-b border-gray-300">
                    <input
                      type="checkbox"
                      checked={selectedUsers.includes(u.id)}
                      onChange={() => toggleSelect(u.id)}
                    />
                  </td>
                  <td className="px-3 py-2 border-b border-gray-300">
                    <div className="flex items-center gap-2">
                      {/* Avatar */}
                      <div className="w-10 h-10 rounded-full overflow-hidden bg-gray-200 flex-shrink-0 flex items-center justify-center">
                        {u.avatar ? (
                          <img
                            src={
                              u.avatar.startsWith("http")
                                ? u.avatar
                                : u.avatar.startsWith("/")
                                ? `${window.location.origin}${u.avatar}`
                                : `${api.defaults.baseURL.replace(
                                    "/api/",
                                    ""
                                  )}${u.avatar}`
                            }
                            alt={`${u.first_name} ${u.last_name}`}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <User className="w-6 h-6 text-gray-400" />
                        )}
                      </div>
                      {/* Name and Email */}
                      <div className="flex flex-col min-w-0 flex-1">
                        <span className="font-semibold truncate">
                          {`${u.first_name}${
                            u.middle_name ? ` ${u.middle_name}` : ""
                          } ${u.last_name}`}
                        </span>
                        <span className="text-xs text-gray-600 truncate">
                          {u.email}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 border-b border-gray-300">
                    {getRoleDisplay(u.userlevel, u.section)}
                  </td>
                  <td className="px-3 py-2 text-center border-b border-gray-300 w-35">
                    {u.is_active ? (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs w-18
                     "
                      >
                        <span className="w-2 h-2 bg-green-500 rounded-full" />
                        <span>Active</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs w-18 ">
                        <span className="w-2 h-2 bg-red-500 rounded-full" />
                        <span>Inactive</span>
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 border-b border-gray-300">
                    {formatFullDate(u.date_joined)}
                  </td>
                  <td className="px-3 py-2 text-right border-b border-gray-300">
                    <ActionButtons
                      user={u}
                      onEdit={onEdit}
                      onToggleStatus={toggleUserActive}
                      onStatusChange={fetchAllUsers}
                    />
                  </td>
                </tr>
              ))
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
          totalItems={totalUsers}
          filteredItems={filteredCount}
          hasActiveFilters={hasActiveFilters}
          onPageChange={goToPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setCurrentPage(1);
          }}
          startItem={startItem}
          endItem={endItem}
          storageKey="users_list"
        />
      </div>
    </div>
  );
}

/* Action Buttons Component - 3-dot dropdown menu */
function ActionButtons({ user, onEdit, onToggleStatus, onStatusChange }) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const notifications = useNotifications();
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Keyboard navigation - Escape key to close
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && showDropdown) {
        setShowDropdown(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [showDropdown]);

  const handleEdit = () => {
    setShowDropdown(false);
    onEdit({
      id: user.id,
      first_name: user.first_name || "",
      middle_name: user.middle_name || "",
      last_name: user.last_name || "",
      email: user.email,
      userlevel: user.userlevel || "",
      section: user.section || "",
      avatar: user.avatar || null,
    });
  };

  const handleStatusClick = () => {
    setShowDropdown(false);
    setShowConfirm(true);
  };

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await onToggleStatus(user.id);

      // Refresh the user list
      if (onStatusChange) {
        onStatusChange();
      }

      // Show success notification
      notifications.success(
        `User ${user.is_active ? "deactivated" : "activated"} successfully!`,
        {
          title: "User Status Updated",
          duration: 4000,
        }
      );
    } catch (error) {
      // Show error notification
      notifications.error(
        `Failed to ${user.is_active ? "deactivate" : "activate"} user: ${
          error.response?.data?.message || error.message
        }`,
        {
          title: "Status Update Failed",
          duration: 8000,
        }
      );
    } finally {
      setLoading(false);
      setShowConfirm(false);
    }
  };

  const handleCancel = () => {
    setShowConfirm(false);
  };

  const actionText = user.is_active ? "Deactivate" : "Activate";

  return (
    <div className="relative flex justify-center" ref={dropdownRef}>
      {/* 3-dot menu button */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="relative z-10 p-1.5 rounded hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1"
        title="Actions"
        aria-label="Actions"
        aria-expanded={showDropdown}
      >
        <MoreHorizontal size={18} className="text-gray-600" />
      </button>

      {/* Dropdown menu */}
      {showDropdown && (
        <div className="absolute top-full right-0 mt-1 bg-white shadow-lg rounded-md border border-gray-200 z-50 min-w-[160px]">
          <div className="py-1">
            {/* Edit option */}
            <button
              onClick={handleEdit}
              className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer w-full text-left transition-colors"
            >
              <Pencil size={16} className="text-sky-600" />
              <span>Edit</span>
            </button>

            {/* Activate/Deactivate option */}
            <button
              onClick={handleStatusClick}
              className={`flex items-center gap-2 px-4 py-2 text-sm cursor-pointer w-full text-left transition-colors ${
                user.is_active
                  ? "text-red-700 hover:bg-red-50"
                  : "text-green-700 hover:bg-green-50"
              }`}
            >
              {user.is_active ? (
                <>
                  <UserX size={16} className="text-red-600" />
                  <span>Deactivate</span>
                </>
              ) : (
                <>
                  <UserCheck size={16} className="text-green-600" />
                  <span>Activate</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Confirmation dialog */}
      <ConfirmationDialog
        open={showConfirm}
        title={`${actionText} User`}
        message={
          <div>
            Are you sure you want to {actionText.toLowerCase()}{" "}
            <span className="font-semibold">
              {user.first_name} {user.last_name}
            </span>
            ?
            {user.is_active && (
              <p className="mt-2 text-sm text-amber-600">
                This user will no longer be able to access the system.
              </p>
            )}
          </div>
        }
        loading={loading}
        onCancel={handleCancel}
        onConfirm={handleConfirm}
        confirmText={actionText}
        cancelText="Cancel"
        confirmColor={user.is_active ? "red" : "green"}
      />
    </div>
  );
}
