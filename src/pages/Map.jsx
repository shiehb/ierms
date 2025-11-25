import { useState, useRef, useEffect, useMemo } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
  GeoJSON,
  useMap,
  LayersControl,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.fullscreen";
import "leaflet.fullscreen/Control.FullScreen.css";
import L from "leaflet";
import { getEstablishments, getMyEstablishments } from "../services/api";
import { useNotifications } from "../hooks/useNotifications";
import useAuth from "../hooks/useAuth";
import { getIconByNatureOfBusiness } from "../constants/markerIcons";
import { createCustomMarkerIcon } from "../components/map/CustomMarkerIcon";
import { ILOCOS_REGION_BOUNDARY } from "../data/ilocosRegionBoundary";
import { ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from "lucide-react";
import TableToolbar from "../components/common/TableToolbar";

// Fix for default markers in react-leaflet
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";
import iconRetina from "leaflet/dist/images/marker-icon-2x.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetina,
  iconUrl: icon,
  shadowUrl: iconShadow,
});

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

// Focus map on a clicked establishment
function MapFocus({ establishment }) {
  const map = useMap();
  useEffect(() => {
    if (establishment) {
      map.setView(
        [
          parseFloat(establishment.latitude),
          parseFloat(establishment.longitude),
        ],
        16
      );
    }
  }, [establishment, map]);
  return null;
}

export default function MapPage() {
  const { user } = useAuth();
  const mapRef = useRef(null);
  const [allEstablishments, setAllEstablishments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [focusedEstablishment, setFocusedEstablishment] = useState(null);
  const notifications = useNotifications();
  const notificationsRef = useRef(notifications);
  const fetchingRef = useRef(false);
  const hasFetchedRef = useRef(false);

  // Update ref when notifications change (to always have latest functions)
  useEffect(() => {
    notificationsRef.current = notifications;
  }, [notifications]);

  // 🔍 Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // 🎚 Filters
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [provinceFilter, setProvinceFilter] = useState([]);
  const [natureOfBusinessFilter, setNatureOfBusinessFilter] = useState([]);

  // ✅ Sorting
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });

  // ✅ Pagination - Load from localStorage
  const [currentPage, setCurrentPage] = useState(() => {
    const saved = localStorage.getItem("map_pagination_page");
    return saved ? parseInt(saved, 10) : 1;
  });
  const [pageSize, setPageSize] = useState(() => {
    const saved = localStorage.getItem("map_pagination_pageSize");
    return saved ? parseInt(saved, 10) : 10;
  });

  // ✅ Details Panel State
  const [showDetailsPanel, setShowDetailsPanel] = useState(true);

  // Save pagination settings to localStorage
  useEffect(() => {
    localStorage.setItem("map_pagination_page", currentPage.toString());
  }, [currentPage]);

  useEffect(() => {
    localStorage.setItem("map_pagination_pageSize", pageSize.toString());
  }, [pageSize]);

  // Fetch all establishments from API - only once when user is available
  useEffect(() => {
    // Don't fetch if no user or already fetching
    if (!user || fetchingRef.current) {
      // Clear establishments if user logged out
      if (!user) {
        setAllEstablishments([]);
        hasFetchedRef.current = false;
      }
      return;
    }

    // Only fetch if we haven't fetched yet for this user
    const userId = user.id;
    if (hasFetchedRef.current === userId) {
      return;
    }

    // Mark as fetching and track which user we're fetching for
    fetchingRef.current = true;
    hasFetchedRef.current = userId;
    setLoading(true);

    const fetchData = async () => {
      try {
        // Determine which API to call based on user role
        const isHighLevelUser =
          user?.userlevel &&
          ["Admin", "Division Chief", "Legal Unit"].includes(user.userlevel);

        let data;
        if (isHighLevelUser) {
          // High-level users see all establishments
          data = await getEstablishments({ page: 1, page_size: 10000 });
        } else {
          // Lower-level users see only their assigned establishments
          data = await getMyEstablishments({ page: 1, page_size: 10000 });
        }

        // Only update if we're still fetching for the same user
        if (hasFetchedRef.current === userId) {
          // Handle both paginated and non-paginated responses
          if (data.results) {
            setAllEstablishments(data.results);
          } else {
            setAllEstablishments(data);
          }
        }
      } catch (err) {
        console.error("Error fetching establishments:", err);
        notificationsRef.current.error("Error fetching establishments", {
          title: "Fetch Error",
          duration: 8000,
        });
        // Reset hasFetchedRef on error so we can retry
        if (hasFetchedRef.current === userId) {
          hasFetchedRef.current = false;
        }
      } finally {
        // Only reset fetching flag if we're still fetching for the same user
        if (fetchingRef.current && hasFetchedRef.current === userId) {
          fetchingRef.current = false;
        }
        setLoading(false);
      }
    };

    fetchData();
  }, [user]); // Only depend on 'user'

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
    { key: "name", label: "Name" },
    { key: "year_established", label: "Year Established" },
  ];

  // ✅ Filter + Sort with LOCAL search (client-side only)
  const filteredEstablishments = useMemo(() => {
    let list = allEstablishments.filter((e) => {
      // Apply local search filter
      const query = debouncedSearchQuery.toLowerCase();
      const matchesSearch = debouncedSearchQuery
        ? e.name.toLowerCase().includes(query) ||
          `${e.street_building}, ${e.barangay}, ${e.city}, ${e.province}, ${e.postal_code}`
            .toLowerCase()
            .includes(query) ||
          e.nature_of_business.toLowerCase().includes(query) ||
          String(e.year_established).includes(query)
        : true;

      // Apply province filter
      const matchesProvince =
        provinceFilter.length === 0 || provinceFilter.includes(e.province);

      // Apply nature of business filter
      const matchesNatureOfBusiness =
        natureOfBusinessFilter.length === 0 ||
        natureOfBusinessFilter.includes(e.nature_of_business);

      return matchesSearch && matchesProvince && matchesNatureOfBusiness;
    });

    // Apply sorting
    if (sortConfig.key) {
      list = [...list].sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];

        if (sortConfig.key === "name") {
          aVal = aVal ? aVal.toLowerCase() : "";
          bVal = bVal ? bVal.toLowerCase() : "";
        }

        if (sortConfig.key === "year_established") {
          aVal = parseInt(aVal) || 0;
          bVal = parseInt(bVal) || 0;
        }

        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return list;
  }, [
    allEstablishments,
    debouncedSearchQuery,
    sortConfig,
    provinceFilter,
    natureOfBusinessFilter,
  ]);

  // ✅ Pagination
  const paginatedEstablishments = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    return filteredEstablishments.slice(startIndex, endIndex);
  }, [filteredEstablishments, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredEstablishments.length / pageSize);

  // Toggle province filter checkbox
  const toggleProvince = (province) =>
    setProvinceFilter((prev) =>
      prev.includes(province)
        ? prev.filter((p) => p !== province)
        : [...prev, province]
    );

  // Toggle nature of business filter checkbox
  const toggleNatureOfBusiness = (business) =>
    setNatureOfBusinessFilter((prev) =>
      prev.includes(business)
        ? prev.filter((b) => b !== business)
        : [...prev, business]
    );

  // Clear functions
  const clearSearch = () => setSearchQuery("");
  const clearAllFilters = () => {
    setSearchQuery("");
    setSortConfig({ key: null, direction: null });
    setProvinceFilter([]);
    setNatureOfBusinessFilter([]);
    setCurrentPage(1);
  };

  // Get unique provinces from establishments
  const uniqueProvinces = useMemo(() => {
    const provinces = [
      ...new Set(allEstablishments.map((e) => e.province)),
    ].filter(Boolean);
    return provinces.sort();
  }, [allEstablishments]);

  // Get unique nature of business from establishments
  const uniqueNatureOfBusiness = useMemo(() => {
    const businesses = [
      ...new Set(allEstablishments.map((e) => e.nature_of_business)),
    ].filter(Boolean);
    return businesses.sort();
  }, [allEstablishments]);

  // Pagination functions
  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  const goToPreviousPage = () => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  };

  const goToNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages, prev + 1));
  };

  const hasActiveFilters =
    searchQuery ||
    sortConfig.key ||
    provinceFilter.length > 0 ||
    natureOfBusinessFilter.length > 0;

  // Custom filters dropdown for TableToolbar
  const customFiltersDropdown = (
    <div className="absolute right-0 z-20 w-64 mt-1 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg top-full max-h-96 custom-scrollbar">
      <div className="p-2">
        {/* Filters Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
          <div className="text-xs font-semibold tracking-wide text-gray-500 uppercase">
            Filters
          </div>
          {(provinceFilter.length > 0 ||
            natureOfBusinessFilter.length > 0 ||
            searchQuery) && (
            <button
              onClick={clearAllFilters}
              className="px-2 py-1 text-xs text-gray-600 transition-colors bg-gray-100 rounded hover:bg-gray-200"
            >
              Clear All
            </button>
          )}
        </div>

        {/* Province Filter */}
        <div className="mb-2">
          <div className="px-3 py-1 text-xs font-medium tracking-wide text-gray-600 uppercase">
            Province
          </div>
          {uniqueProvinces.length > 0 ? (
            uniqueProvinces.map((province) => (
              <button
                key={province}
                onClick={() => toggleProvince(province)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                  provinceFilter.includes(province)
                    ? "bg-sky-50 font-medium"
                    : ""
                }`}
              >
                <div className="flex-1 text-left">
                  <div className="font-medium">{province}</div>
                </div>
                {provinceFilter.includes(province) && (
                  <div className="w-2 h-2 rounded-full bg-sky-600"></div>
                )}
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-sm text-gray-500">
              No provinces available
            </div>
          )}
        </div>

        {/* Nature of Business Filter */}
        <div className="mb-2">
          <div className="px-3 py-1 text-xs font-medium tracking-wide text-gray-600 uppercase">
            Nature of Business
          </div>
          {uniqueNatureOfBusiness.length > 0 ? (
            uniqueNatureOfBusiness.map((business) => (
              <button
                key={business}
                onClick={() => toggleNatureOfBusiness(business)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100 transition-colors ${
                  natureOfBusinessFilter.includes(business)
                    ? "bg-sky-50 font-medium"
                    : ""
                }`}
              >
                <div className="flex-1 text-left">
                  <div className="font-medium">{business}</div>
                </div>
                {natureOfBusinessFilter.includes(business) && (
                  <div className="w-2 h-2 rounded-full bg-sky-600"></div>
                )}
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-sm text-gray-500">
              No nature of business available
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Calculate display range
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(
    currentPage * pageSize,
    filteredEstablishments.length
  );

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel="admin">
        <div className="p-4 bg-white h-[calc(100vh-165px)]">
          {/* Header with Search, Filters, and Sort */}
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <h1 className="text-2xl font-bold text-sky-600">
              Establishments Map
            </h1>

            <div className="flex flex-wrap items-center w-full gap-2 sm:w-auto">
              <TableToolbar
                searchValue={searchQuery}
                onSearchChange={setSearchQuery}
                onSearchClear={clearSearch}
                searchPlaceholder="Search establishments..."
                sortConfig={sortConfig}
                sortFields={sortFields}
                onSort={handleSort}
                onFilterClick={() => setFiltersOpen(!filtersOpen)}
                customFilterDropdown={
                  filtersOpen ? customFiltersDropdown : null
                }
                filterOpen={filtersOpen}
                onFilterClose={() => setFiltersOpen(false)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Left Column: Map + Details Panel */}
            <div className="flex flex-col gap-2 h-[calc(100vh-220px)]">
              {/* Map Container - Dynamic height */}
              <MapContainer
                center={[16.597668, 120.322477]}
                zoom={8}
                style={{ width: "100%", height: "100%" }}
                whenCreated={(mapInstance) => (mapRef.current = mapInstance)}
                maxZoom={22}
                fullscreenControl={true}
                fullscreenControlOptions={{
                  position: "topright",
                }}
              >
                <LayersControl position="topleft">
                  {/* Base Layers */}
                  <LayersControl.BaseLayer name="Satellite">
                    <TileLayer
                      url="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                      maxZoom={21}
                      subdomains={["mt1", "mt2", "mt3"]}
                      attribution="© Google"
                    />
                  </LayersControl.BaseLayer>

                  {/* 3D Map Layer with Buildings */}
                  <LayersControl.BaseLayer checked name="Streets">
                    <TileLayer
                      url="https://api.maptiler.com/maps/streets-v2/256/{z}/{x}/{y}.png?key=Usuq2JxAdrdQy7GmBVyr"
                      attribution='<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
                      maxZoom={22}
                    />
                  </LayersControl.BaseLayer>

                  {/* Ilocos Region Boundary */}
                  <LayersControl.Overlay checked name="Region I Boundary">
                    <GeoJSON
                      data={ILOCOS_REGION_BOUNDARY.data}
                      style={() => ILOCOS_REGION_BOUNDARY.style}
                    />
                  </LayersControl.Overlay>
                </LayersControl>

                <MapFocus establishment={focusedEstablishment} />

                {/* Show ALL filtered establishments on map (not just paginated ones) */}
                {filteredEstablishments.map((e) =>
                  e.polygon && e.polygon.length > 0 ? (
                    <Polygon
                      key={`poly-${e.id}`}
                      positions={e.polygon}
                      pathOptions={{
                        color:
                          focusedEstablishment?.id === e.id
                            ? "#3388ff"
                            : "#999999",
                        weight: focusedEstablishment?.id === e.id ? 4 : 2,
                        opacity: focusedEstablishment?.id === e.id ? 0.8 : 0.6,
                        fillColor:
                          focusedEstablishment?.id === e.id
                            ? "#3388ff"
                            : "#999999",
                        fillOpacity:
                          focusedEstablishment?.id === e.id ? 0.3 : 0.1,
                        dashArray:
                          focusedEstablishment?.id === e.id ? "0" : "5 5",
                      }}
                      eventHandlers={{
                        click: () => {
                          setFocusedEstablishment(e);
                          setShowDetailsPanel(true); // Show panel when clicking
                        },
                      }}
                    >
                      {/* Only show Popup when details panel is hidden */}
                      {!showDetailsPanel && (
                        <Popup>
                          <div className="p-2">
                            <strong>{e.name}</strong>
                            <br />
                            <span className="text-sm text-gray-600">
                              {e.nature_of_business}
                            </span>
                            <br />
                            <span className="text-xs text-gray-500">
                              {e.street_building}, {e.barangay}, {e.city}
                            </span>
                            <br />
                            <span className="text-xs text-gray-500">
                              Established: {e.year_established}
                            </span>
                          </div>
                        </Popup>
                      )}
                    </Polygon>
                  ) : (
                    <Marker
                      key={`marker-${e.id}`}
                      position={[
                        parseFloat(e.latitude),
                        parseFloat(e.longitude),
                      ]}
                      icon={(() => {
                        // Get custom icon based on establishment type
                        const iconData = getIconByNatureOfBusiness(
                          e.marker_icon || e.nature_of_business
                        );
                        return createCustomMarkerIcon(
                          iconData.icon,
                          iconData.color,
                          28
                        );
                      })()}
                      eventHandlers={{
                        click: () => {
                          setFocusedEstablishment(e);
                          setShowDetailsPanel(true); // Show panel when clicking
                        },
                      }}
                    >
                      {/* Only show Popup when details panel is hidden */}
                      {!showDetailsPanel && (
                        <Popup>
                          <div className="p-2">
                            <strong>{e.name}</strong>
                            <br />
                            <span className="text-sm text-gray-600">
                              {e.nature_of_business}
                            </span>
                            <br />
                            <span className="text-xs text-gray-500">
                              {e.street_building}, {e.barangay}, {e.city}
                            </span>
                            <br />
                            <span className="text-xs text-gray-500">
                              Established: {e.year_established}
                            </span>
                          </div>
                        </Popup>
                      )}
                    </Marker>
                  )
                )}
              </MapContainer>
            </div>

            {/* Right Column: Table */}
            <div className="flex flex-col h-[calc(100vh-220px)]">
              {/* Table Container */}
              <div className="flex-1 min-h-0 overflow-y-auto rounded custom-scrollbar">
                <table className="w-full border-b border-gray-300 rounded-lg">
                  <thead>
                    <tr className="sticky top-0 z-10 text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700">
                      <th
                        className="px-3 py-2 border-b border-gray-300 cursor-pointer"
                        onClick={() => {
                          if (sortConfig.key === "name") {
                            handleSort(
                              "name",
                              sortConfig.direction === "asc" ? "desc" : "asc"
                            );
                          } else {
                            handleSort("name", "asc");
                          }
                        }}
                      >
                        <div className="flex items-center gap-1">
                          Name {getSortIcon("name")}
                        </div>
                      </th>
                      <th
                        className="px-3 py-2 border-b border-gray-300 cursor-pointer"
                        onClick={() => {
                          if (sortConfig.key === "city") {
                            handleSort(
                              "city",
                              sortConfig.direction === "asc" ? "desc" : "asc"
                            );
                          } else {
                            handleSort("city", "asc");
                          }
                        }}
                      >
                        <div className="flex items-center gap-1">
                          Address {getSortIcon("city")}
                        </div>
                      </th>
                      <th className="px-3 py-2 text-center border-b border-gray-300">
                        Coordinates
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
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
                              Loading establishments...
                            </p>
                          </div>
                        </td>
                      </tr>
                    ) : paginatedEstablishments.length === 0 ? (
                      <tr>
                        <td
                          colSpan="5"
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
                      paginatedEstablishments.map((e) => (
                        <tr
                          key={e.id}
                          className={`text-xs border-b border-gray-300 hover:bg-gray-50 transition-colors cursor-pointer ${
                            focusedEstablishment?.id === e.id
                              ? "bg-green-100"
                              : ""
                          }`}
                          onClick={() => setFocusedEstablishment(e)}
                        >
                          <td className="px-3 py-2 font-semibold border-b border-gray-300">
                            {e.name}
                          </td>
                          <td className="px-3 py-2 text-left border-b border-gray-300">
                            <div
                              className="max-w-xs truncate"
                              title={`${e.street_building}, ${e.barangay}, ${e.city}, ${e.province}`}
                            >
                              {`${e.street_building}, ${e.barangay}, ${e.city}, ${e.province}`}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-center border-b border-gray-300">
                            {`${parseFloat(e.latitude).toFixed(
                              4
                            )}, ${parseFloat(e.longitude).toFixed(4)}`}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {filteredEstablishments.length > 0 && (
                <div className="flex items-center justify-between flex-shrink-0 p-2 mt-4 rounded bg-gray-50">
                  <div className="text-sm text-gray-600">
                    Showing {startItem} to {endItem} of{" "}
                    {filteredEstablishments.length} establishment(s)
                    {allEstablishments.length !==
                      filteredEstablishments.length &&
                      ` (filtered from ${allEstablishments.length} total)`}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={goToPreviousPage}
                      disabled={currentPage === 1}
                      className="p-1 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                    >
                      <ChevronLeft size={16} />
                    </button>

                    {/* Page numbers */}
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }

                      return (
                        <button
                          key={pageNum}
                          onClick={() => goToPage(pageNum)}
                          className={`px-3 py-1 text-sm rounded ${
                            currentPage === pageNum
                              ? "bg-sky-600 text-white"
                              : "hover:bg-gray-100"
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}

                    <button
                      onClick={goToNextPage}
                      disabled={currentPage === totalPages}
                      className="p-1 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                    >
                      <ChevronRight size={16} />
                    </button>
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    <span>Show:</span>
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setCurrentPage(1);
                      }}
                      className="px-2 py-1 border rounded"
                    >
                      <option value="10">10</option>
                      <option value="25">25</option>
                      <option value="50">50</option>
                      <option value="100">100</option>
                    </select>
                    <span>per page</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </LayoutWithSidebar>
      <Footer />
    </>
  );
}
