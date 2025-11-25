import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useLocation } from "react-router-dom";
import {
  Pencil,
  Map,
  Plus,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
} from "lucide-react";
import { getEstablishments, getProfile } from "../../services/api";
import PaginationControls from "../PaginationControls";
import { useLocalStoragePagination } from "../../hooks/useLocalStoragePagination";
import { useNotifications } from "../../hooks/useNotifications";
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

export default function EstablishmentList({
  onAdd,
  onEdit,
  onPolygon,
  onViewInspections,
  refreshTrigger,
  canEditEstablishments,
  canEditPolygons,
}) {
  const [establishments, setEstablishments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const notifications = useNotifications();

  // 🔒 User level for permissions
  const [userLevel, setUserLevel] = useState(null);

  // 🎯 Search highlighting
  const location = useLocation();
  const [highlightedEstId, setHighlightedEstId] = useState(null);
  const highlightedRowRef = useRef(null);

  // ✅ Pagination with localStorage
  const savedPagination = useLocalStoragePagination("establishments_list");
  const [currentPage, setCurrentPage] = useState(savedPagination.page);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);
  const [searchMode, setSearchMode] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // Filters
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [provinceFilter, setProvinceFilter] = useState([]);
  const [businessTypeFilter, setBusinessTypeFilter] = useState([]);

  // Sorting
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });

  // Export
  const [selectedEstablishments, setSelectedEstablishments] = useState([]);

  // Fetch data with server-side pagination
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Set search mode
      if (debouncedSearchQuery && debouncedSearchQuery.length >= 2) {
        setSearchMode(true);
      } else {
        setSearchMode(false);
      }

      const response = await getEstablishments({
        page: currentPage,
        page_size: pageSize,
        ...(debouncedSearchQuery &&
          debouncedSearchQuery.length >= 2 && { search: debouncedSearchQuery }),
        ...(provinceFilter.length > 0 && {
          province: provinceFilter.join(","),
        }),
        ...(businessTypeFilter.length > 0 && {
          nature_of_business: businessTypeFilter.join(","),
        }),
      });

      if (response.results) {
        // Server-side paginated response
        setEstablishments(response.results);
        setTotalCount(response.count || 0);
      } else {
        // Fallback for non-paginated response
        setEstablishments(response);
        setTotalCount(response.length);
      }
    } catch (err) {
      console.error("Error fetching establishments:", err);
      notifications.error("Error fetching establishments", {
        title: "Fetch Error",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    currentPage,
    pageSize,
    debouncedSearchQuery,
    provinceFilter,
    businessTypeFilter,
  ]);

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

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshTrigger]);

  // Reset to page 1 when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchQuery]);

  // Handle highlighting from search navigation
  useEffect(() => {
    if (
      location.state?.highlightId &&
      location.state?.entityType === "establishment"
    ) {
      setHighlightedEstId(location.state.highlightId);

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

  // Sorting handler
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

  // Filter functions
  const toggleProvince = (province) => {
    setProvinceFilter((prev) =>
      prev.includes(province)
        ? prev.filter((p) => p !== province)
        : [...prev, province]
    );
  };

  const toggleBusinessType = (businessType) => {
    setBusinessTypeFilter((prev) =>
      prev.includes(businessType)
        ? prev.filter((b) => b !== businessType)
        : [...prev, businessType]
    );
  };

  const clearProvinces = () => setProvinceFilter([]);
  const clearBusinessTypes = () => setBusinessTypeFilter([]);
  const clearSearch = () => setSearchQuery("");

  const clearAllFilters = () => {
    setSearchQuery("");
    setProvinceFilter([]);
    setBusinessTypeFilter([]);
    setSortConfig({ key: null, direction: null });
    setCurrentPage(1);
  };

  // Filter establishments locally when not in search mode
  const filteredEstablishments = useMemo(() => {
    if (searchMode) return establishments;

    let list = establishments.filter((e) => {
      const matchesProvince =
        provinceFilter.length === 0 || provinceFilter.includes(e.province);
      const matchesBusinessType =
        businessTypeFilter.length === 0 ||
        businessTypeFilter.includes(e.nature_of_business);
      return matchesProvince && matchesBusinessType;
    });

    if (sortConfig.key) {
      list = [...list].sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];

        if (sortConfig.key === "name" || sortConfig.key === "city") {
          aVal = aVal ? aVal.toLowerCase() : "";
          bVal = bVal ? bVal.toLowerCase() : "";
        }

        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return list;
  }, [
    establishments,
    provinceFilter,
    businessTypeFilter,
    sortConfig,
    searchMode,
  ]);

  // Selection
  const toggleSelect = (id) => {
    setSelectedEstablishments((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedEstablishments.length === filteredEstablishments.length) {
      setSelectedEstablishments([]);
    } else {
      setSelectedEstablishments(filteredEstablishments.map((e) => e.id));
    }
  };

  // Pagination
  const totalPages = Math.ceil(totalCount / pageSize);
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalCount);

  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  const activeFilterCount = provinceFilter.length + businessTypeFilter.length;
  const hasActiveFilters =
    searchQuery ||
    provinceFilter.length > 0 ||
    businessTypeFilter.length > 0 ||
    sortConfig.key;

  const provinces = ["LA UNION", "PANGASINAN", "ILOCOS SUR", "ILOCOS NORTE"];

  // Get unique business types from establishments
  const businessTypes = useMemo(() => {
    return [
      ...new Set(
        establishments.map((e) => e.nature_of_business).filter(Boolean)
      ),
    ].sort();
  }, [establishments]);

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
                clearProvinces();
                clearBusinessTypes();
              }}
              className="px-2 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            >
              Clear All
            </button>
          )}
        </div>

        {/* Province Section */}
        <div className="mb-3">
          <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
            Province
          </div>
          {provinces.map((province) => (
            <button
              key={province}
              onClick={() => toggleProvince(province)}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                provinceFilter.includes(province) ? "bg-sky-50 font-medium" : ""
              }`}
            >
              <div className="flex-1 text-left">
                <div className="font-medium">{province}</div>
              </div>
              {provinceFilter.includes(province) && (
                <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
              )}
            </button>
          ))}
        </div>

        {/* Business Type Section */}
        <div className="mb-2">
          <div className="px-3 py-1 text-xs font-medium text-gray-600 uppercase tracking-wide">
            Business Type
          </div>
          {businessTypes.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-500 italic">
              No business types available
            </div>
          ) : (
            businessTypes.map((businessType) => (
              <button
                key={businessType}
                onClick={() => toggleBusinessType(businessType)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                  businessTypeFilter.includes(businessType)
                    ? "bg-sky-50 font-medium"
                    : ""
                }`}
              >
                <div className="flex-1 text-left">
                  <div className="font-medium">{businessType}</div>
                </div>
                {businessTypeFilter.includes(businessType) && (
                  <div className="w-2 h-2 bg-sky-600 rounded-full"></div>
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-4 bg-white h-[calc(100vh-160px)]">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h1 className="text-2xl font-bold text-sky-600">Establishments</h1>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <TableToolbar
            searchValue={searchQuery}
            onSearchChange={setSearchQuery}
            onSearchClear={clearSearch}
            searchPlaceholder="Search..."
            sortConfig={sortConfig}
            sortFields={[
              { key: "name", label: "Name" },
              { key: "city", label: "City" },
              { key: "year_established", label: "Year Established" },
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
            exportConfig={
              canExportAndPrint(userLevel, "establishments")
                ? {
                    title: "Establishments Export Report",
                    fileName: "establishments_export",
                    columns: [
                      "ID",
                      "Name",
                      "Nature of Business",
                      "Province",
                      "City",
                      "Year Established",
                      "Status",
                    ],
                    rows:
                      selectedEstablishments.length > 0
                        ? selectedEstablishments
                            .map((id) => {
                              const establishment = filteredEstablishments.find(
                                (e) => e.id === id
                              );
                              return establishment
                                ? [
                                    establishment.id,
                                    establishment.name,
                                    establishment.nature_of_business,
                                    establishment.province,
                                    establishment.city,
                                    establishment.year_established,
                                    "Active",
                                  ]
                                : [];
                            })
                            .filter((row) => row.length > 0)
                        : filteredEstablishments.map((establishment) => [
                            establishment.id,
                            establishment.name,
                            establishment.nature_of_business,
                            establishment.province,
                            establishment.city,
                            establishment.year_established,
                            "Active",
                          ]),
                  }
                : null
            }
            printConfig={
              canExportAndPrint(userLevel, "establishments")
                ? {
                    title: "Establishments Report",
                    fileName: "establishments_report",
                    columns: [
                      "ID",
                      "Name",
                      "Nature of Business",
                      "Province",
                      "City",
                      "Year Established",
                      "Status",
                    ],
                    rows:
                      selectedEstablishments.length > 0
                        ? selectedEstablishments
                            .map((id) => {
                              const establishment = filteredEstablishments.find(
                                (e) => e.id === id
                              );
                              return establishment
                                ? [
                                    establishment.id,
                                    establishment.name,
                                    establishment.nature_of_business,
                                    establishment.province,
                                    establishment.city,
                                    establishment.year_established,
                                    "Active",
                                  ]
                                : [];
                            })
                            .filter((row) => row.length > 0)
                        : filteredEstablishments.map((establishment) => [
                            establishment.id,
                            establishment.name,
                            establishment.nature_of_business,
                            establishment.province,
                            establishment.city,
                            establishment.year_established,
                            "Active",
                          ]),
                  }
                : null
            }
            onRefresh={fetchData}
            isRefreshing={loading}
            additionalActions={
              canEditEstablishments
                ? [
                    {
                      onClick: onAdd,
                      icon: Plus,
                      title: "Add Establishment",
                      text: "Add Establishment",
                      variant: "primary",
                    },
                  ]
                : []
            }
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-auto h-[calc(100vh-260px)] border border-gray-300 rounded scroll-smooth custom-scrollbar">
        <table className="w-full">
          <thead>
            <tr className="text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700 sticky top-0 z-10">
              <th className="w-6 px-3 py-2 text-center border-b border-gray-300">
                <input
                  type="checkbox"
                  checked={
                    selectedEstablishments.length > 0 &&
                    selectedEstablishments.length ===
                      filteredEstablishments.length
                  }
                  onChange={toggleSelectAll}
                />
              </th>
              <th
                className="px-3 py-2 border-b border-gray-300 cursor-pointer"
                onClick={() => handleSort("name")}
              >
                <div className="flex items-center gap-1">
                  Name {getSortIcon("name")}
                </div>
              </th>
              <th
                className="px-3 py-2 border-b border-gray-300 cursor-pointer"
                onClick={() => handleSort("city")}
              >
                <div className="flex items-center gap-1">
                  Address {getSortIcon("city")}
                </div>
              </th>
              <th className="px-3 py-2 text-center border-b border-gray-300">
                Coordinates
              </th>
              <th className="px-3 py-2 border-b border-gray-300">
                Nature of Business
              </th>
              <th
                className="px-3 py-2 text-center border-b border-gray-300 cursor-pointer"
                onClick={() => handleSort("year_established")}
              >
                <div className="flex items-center justify-center gap-1">
                  Year Established {getSortIcon("year_established")}
                </div>
              </th>
              <th className="px-3 py-2 text-center border-b border-gray-300">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan="7"
                  className="px-2 py-6 text-center text-gray-500 border-b border-gray-300"
                >
                  <div
                    className="flex flex-col items-center justify-center"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="w-8 h-8 mb-2 border-b-2 border-gray-900 rounded-full animate-spin"></div>
                    <p className="text-sm text-gray-600">
                      Loading establishments...
                    </p>
                  </div>
                </td>
              </tr>
            ) : filteredEstablishments.length === 0 ? (
              <tr>
                <td
                  colSpan="7"
                  className="px-2 py-4 text-center text-gray-500 border-b border-gray-300"
                >
                  {hasActiveFilters ? (
                    <div>
                      No establishments found matching your criteria.
                      <br />
                      <button
                        onClick={clearAllFilters}
                        className="mt-2 underline text-sky-600 hover:text-sky-700"
                      >
                        Clear all filters
                      </button>
                    </div>
                  ) : (
                    "No establishments found."
                  )}
                </td>
              </tr>
            ) : (
              filteredEstablishments.map((e) => (
                <tr
                  key={e.id}
                  ref={e.id === highlightedEstId ? highlightedRowRef : null}
                  className={`text-xs border-b border-gray-300 hover:bg-gray-50 transition-colors ${
                    e.id === highlightedEstId ? "search-highlight-persist" : ""
                  }`}
                  onClick={() => setHighlightedEstId(e.id)}
                >
                  <td className="text-center px-3 py-2 border-b border-gray-300">
                    <input
                      type="checkbox"
                      checked={selectedEstablishments.includes(e.id)}
                      onChange={() => toggleSelect(e.id)}
                    />
                  </td>
                  <td className="px-3 py-2 font-semibold border-b border-gray-300">
                    {e.name}
                  </td>
                  <td className="px-3 py-2 border-b border-gray-300">
                    {e.street_building}, {e.barangay}, {e.city}, {e.province},{" "}
                    {e.postal_code}
                  </td>
                  <td className="px-3 py-2 text-center border-b border-gray-300">
                    {e.latitude}, {e.longitude}
                  </td>
                  <td className="px-3 py-2 border-b border-gray-300">
                    {e.nature_of_business}
                  </td>
                  <td className="px-3 py-2 text-center border-b border-gray-300">
                    {e.year_established}
                  </td>
                  <td className="px-3 py-2 text-center border-b border-gray-300">
                    <div className="flex justify-center gap-2">
                      {canEditEstablishments && (
                        <button
                          onClick={() => onEdit(e)}
                          className="flex items-center px-3 py-1 text-sm font-medium rounded-lg text-gray-700 bg-gray-200 hover:bg-gray-300"
                          title="Edit"
                        >
                          <Pencil size={14} />
                          Edit
                        </button>
                      )}
                      {canEditPolygons && (
                        <button
                          onClick={() => onPolygon(e)}
                          className="flex items-center gap-1 px-2 py-1 text-sm text-white bg-green-600 rounded hover:bg-green-700"
                          title="Polygon"
                        >
                          <Map size={14} />
                          Polygon
                        </button>
                      )}
                      <button
                        onClick={() => onViewInspections(e)}
                        className="flex items-center gap-1 px-2 py-1 text-sm text-white bg-sky-600 rounded hover:bg-sky-700"
                        title="View Closed Inspections"
                      >
                        <FileText size={14} />
                        View
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-2">
        {/* Pagination */}
        <PaginationControls
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={totalCount}
          hasActiveFilters={searchMode && debouncedSearchQuery}
          onPageChange={goToPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setCurrentPage(1);
          }}
          startItem={startItem}
          endItem={endItem}
          storageKey="establishments_list"
        />
      </div>
    </div>
  );
}
