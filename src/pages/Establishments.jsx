import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import LayoutWithSidebar from "../components/LayoutWithSidebar";
import EstablishmentList from "../components/establishments/EstablishmentList";
import AddEstablishment from "../components/establishments/AddEstablishment";
import EditEstablishment from "../components/establishments/EditEstablishment";
import PolygonMap from "../components/establishments/PolygonMap";
import EstablishmentDetailsPanel from "../components/establishments/EstablishmentDetailsPanel";
import EstablishmentInspectionsContent from "../components/establishments/EstablishmentInspectionsContent";
import {
  getEstablishments,
  getProfile,
  setEstablishmentPolygon,
} from "../services/api";
import { useNotifications } from "../hooks/useNotifications";

export default function Establishments() {
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(false);
  const [editEstablishment, setEditEstablishment] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [userRole, setUserRole] = useState("");
  const notifications = useNotifications();

  // 🔹 Inspection view state
  const [inspectionsEstablishment, setInspectionsEstablishment] =
    useState(null);

  // 🔹 View state: 'list', 'polygon', or 'inspections'
  const [currentView, setCurrentView] = useState("list");
  const [polygonEstablishment, setPolygonEstablishment] = useState(null);
  const [polygonEditMode, setPolygonEditMode] = useState(false);
  const [hasPolygonChanges, setHasPolygonChanges] = useState(false);

  // 🔹 Polygon control states
  const [showOtherPolygons] = useState(true);
  const [snapEnabled] = useState(true);
  const [snapDistance] = useState(10);

  // 🔹 Polygon validation state
  const [isPolygonValid, setIsPolygonValid] = useState(true);

  // 🔹 establishments state (used in polygon functionality)
  const [establishments, setEstablishments] = useState([]);

  // 🔹 loading state
  const [loading, setLoading] = useState(false);

  // 🔹 Fetch user profile and establishments on component mount
  useEffect(() => {
    fetchUserProfile();
    fetchEstablishments();
  }, [refreshTrigger]);

  // 🔹 Handle navigation state to show inspection records
  useEffect(() => {
    if (location.state?.viewInspections && location.state?.establishmentId) {
      const establishmentId = location.state.establishmentId;
      // Find the establishment from the list or fetch it
      const foundEstablishment = establishments.find(
        (e) => e.id === establishmentId
      );
      if (foundEstablishment) {
        setInspectionsEstablishment(foundEstablishment);
        setCurrentView("inspections");
      } else {
        // If not found in list, fetch it
        const fetchEstablishment = async () => {
          try {
            const response = await getEstablishments({
              page: 1,
              page_size: 10000,
            });
            const data = response.results || response;
            const establishment = data.find((e) => e.id === establishmentId);
            if (establishment) {
              setInspectionsEstablishment(establishment);
              setCurrentView("inspections");
            }
          } catch (err) {
            console.error("Error fetching establishment:", err);
          }
        };
        fetchEstablishment();
      }
    }
  }, [location.state, establishments]);

  const fetchUserProfile = async () => {
    try {
      const profile = await getProfile();
      setUserRole(profile.userlevel);
    } catch (err) {
      console.error("Error fetching user profile:", err);
    }
  };

  const fetchEstablishments = async () => {
    try {
      const response = await getEstablishments({ page: 1, page_size: 10000 });
      const data = response.results || response;
      setEstablishments(data);
    } catch (err) {
      console.error("Error fetching establishments:", err);
      notifications.error("Error fetching establishments", {
        title: "Fetch Error",
        duration: 8000,
      });
    }
  };

  // 🔹 Check if user can add/edit establishments (form only)
  const canEditEstablishments = () => {
    return ["Division Chief", "Section Chief", "Unit Head"].includes(userRole);
  };

  // 🔹 Check if user can edit polygons
  const canEditPolygons = () => {
    return [
      "Division Chief",
      "Section Chief",
      "Unit Head",
      "Monitoring Personnel",
    ].includes(userRole);
  };

  // 🔹 Check if polygon has changes
  const checkPolygonChanges = (newPolygon) => {
    if (!polygonEstablishment) return false;

    const originalPolygon = polygonEstablishment.originalPolygon || [];
    const currentPolygon = newPolygon || polygonEstablishment.polygon || [];

    // If both are empty, no changes
    if (originalPolygon.length === 0 && currentPolygon.length === 0) {
      return false;
    }

    // If lengths are different, definitely changes
    if (originalPolygon.length !== currentPolygon.length) {
      return true;
    }

    // Check if any coordinate has changed
    for (let i = 0; i < originalPolygon.length; i++) {
      const [origLat, origLng] = originalPolygon[i];
      const [currLat, currLng] = currentPolygon[i];

      if (origLat !== currLat || origLng !== currLng) {
        return true;
      }
    }

    return false;
  };

  // 🔹 save polygon with API call
  const confirmSavePolygon = async () => {
    if (!polygonEstablishment) return;
    setLoading(true);
    try {
      const response = await setEstablishmentPolygon(
        polygonEstablishment.id,
        polygonEstablishment.polygon || [],
        polygonEstablishment.marker_icon || null
      );

      // Use the polygon from response (backend may have adjusted it)
      const savedPolygon =
        response.polygon || polygonEstablishment.polygon || [];
      const savedIcon =
        response.marker_icon || polygonEstablishment.marker_icon;

      // Update local state with the saved polygon and icon
      setPolygonEstablishment((prev) => ({
        ...prev,
        polygon: savedPolygon,
        marker_icon: savedIcon,
        originalPolygon: [...savedPolygon],
      }));

      setEstablishments((prev) =>
        prev.map((e) =>
          e.id === polygonEstablishment.id
            ? { ...e, polygon: savedPolygon, marker_icon: savedIcon }
            : e
        )
      );
      setPolygonEditMode(false);
      setHasPolygonChanges(false);
      setRefreshTrigger((prev) => prev + 1);

      // Show notification with adjustment info if applicable
      const message =
        response.was_adjusted && response.adjustment_message
          ? `Polygon saved! ${response.adjustment_message}`
          : "Polygon saved successfully!";

      notifications.success(message, {
        title: "Polygon Saved",
        duration: response.was_adjusted ? 6000 : 4000,
      });
    } catch (err) {
      console.error("Error saving polygon:", err);
      notifications.error("Failed to save polygon", {
        title: "Save Failed",
        duration: 8000,
      });
    } finally {
      setLoading(false);
    }
  };

  // 🔹 handle polygon view
  const handleShowPolygon = (est) => {
    setPolygonEstablishment({
      ...est,
      originalPolygon: est.polygon ? [...est.polygon] : [],
      originalIcon: est.marker_icon || est.nature_of_business,
    });
    setCurrentView("polygon");
    setPolygonEditMode(false);
    setHasPolygonChanges(false);
  };

  // 🔹 handle cancel polygon and return to list
  const handleCancelPolygon = () => {
    setCurrentView("list");
    setPolygonEstablishment(null);
    setPolygonEditMode(false);
    setHasPolygonChanges(false);
  };

  // 🔹 handle cancel polygon edit (keep in polygon view but exit edit mode)
  const handleCancelPolygonEdit = () => {
    setPolygonEditMode(false);
    setHasPolygonChanges(false);
    // Reset polygon and icon to original state
    if (polygonEstablishment && polygonEstablishment.originalPolygon) {
      setPolygonEstablishment((prev) => ({
        ...prev,
        polygon: [...prev.originalPolygon],
        marker_icon:
          prev.originalIcon || prev.marker_icon || prev.nature_of_business,
      }));
    }
  };

  // 🔹 handle start editing polygon
  const handleStartPolygonEdit = () => {
    setPolygonEditMode(true);
  };

  // 🔹 handle polygon changes
  const handlePolygonChange = (polygon, isValid = true, markerIcon = null) => {
    setPolygonEstablishment((prev) => {
      if (!prev) return prev;
      const updated = { ...prev, polygon };
      if (markerIcon) {
        updated.marker_icon = markerIcon;
      }
      return updated;
    });

    // Check if there are changes compared to original
    const hasChanges = checkPolygonChanges(polygon);
    setHasPolygonChanges(hasChanges);

    // Update validation state
    setIsPolygonValid(isValid);
  };

  // 🔹 handle establishment added/updated
  const handleEstablishmentChanged = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  // 🔹 handle view inspections
  const handleViewInspections = (establishment) => {
    setInspectionsEstablishment(establishment);
    setCurrentView("inspections");
  };

  // 🔹 handle back to establishments
  const handleBackToEstablishments = () => {
    setCurrentView("list");
    setInspectionsEstablishment(null);
  };

  // 🔹 handle polygon creation redirect
  const handlePolygonCreate = (establishment) => {
    // Close modals
    setShowAdd(false);
    setEditEstablishment(null);

    // Navigate to polygon view with edit mode enabled
    setPolygonEstablishment({
      ...establishment,
      originalPolygon: establishment.polygon ? [...establishment.polygon] : [],
      originalIcon:
        establishment.marker_icon || establishment.nature_of_business,
    });
    setCurrentView("polygon");
    setPolygonEditMode(true);
    setHasPolygonChanges(false);
  };

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel="admin">
        <div>
          {/* Show either the list view, polygon view, or inspections view */}
          {currentView === "list" ? (
            <EstablishmentList
              onAdd={() => setShowAdd(true)}
              onEdit={(est) => setEditEstablishment(est)}
              onPolygon={handleShowPolygon}
              onViewInspections={handleViewInspections}
              refreshTrigger={refreshTrigger}
              canEditEstablishments={canEditEstablishments()}
              canEditPolygons={canEditPolygons()}
            />
          ) : currentView === "polygon" ? (
            <div className="p-4 bg-white rounded shadow">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h1 className="text-2xl font-bold text-sky-600">
                  {polygonEditMode
                    ? `Update Polygon Boundary - ${polygonEstablishment.name}`
                    : `Polygon Boundary - ${polygonEstablishment.name}`}
                </h1>
                <div className="flex gap-2">
                  {canEditPolygons() ? (
                    <>
                      {/* View Mode - Show Create/Update button and Back to List */}
                      {!polygonEditMode && (
                        <>
                          <button
                            onClick={handleCancelPolygon}
                            className="px-3 py-1 text-gray-700 bg-gray-300 rounded hover:bg-gray-400"
                          >
                            Back to List
                          </button>
                          <button
                            onClick={handleStartPolygonEdit}
                            className="px-3 py-1 text-white rounded bg-sky-600 hover:bg-sky-700"
                          >
                            {polygonEstablishment.polygon &&
                            polygonEstablishment.polygon.length > 0
                              ? "Update Polygon"
                              : "Create Polygon"}
                          </button>
                        </>
                      )}

                      {/* Edit Mode - Show Save/Cancel buttons (hide Back to List) */}
                      {polygonEditMode && (
                        <>
                          <button
                            onClick={handleCancelPolygonEdit}
                            className="px-3 py-1 text-gray-700 bg-gray-300 rounded hover:bg-gray-400"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => {
                              if (hasPolygonChanges && isPolygonValid) {
                                confirmSavePolygon();
                              }
                            }}
                            disabled={!hasPolygonChanges || !isPolygonValid}
                            className={`px-3 py-1 text-white rounded ${
                              hasPolygonChanges && isPolygonValid
                                ? "bg-sky-600 hover:bg-sky-700"
                                : "bg-gray-400 cursor-not-allowed"
                            }`}
                            title={
                              !isPolygonValid
                                ? "Establishment marker must be inside polygon"
                                : ""
                            }
                          >
                            Save Polygon
                          </button>
                        </>
                      )}
                    </>
                  ) : (
                    // For users who can't edit polygons, always show Back to List
                    <button
                      onClick={handleCancelPolygon}
                      className="px-3 py-1 text-gray-700 bg-gray-300 rounded hover:bg-gray-400"
                    >
                      Back to List
                    </button>
                  )}
                </div>
              </div>

              {/* Grid Layout */}
              <div className="grid grid-cols-3 gap-4 mt-4">
                {/* Left Column - Establishment Details */}
                <div className="col-span-1">
                  <EstablishmentDetailsPanel
                    establishment={polygonEstablishment}
                  />
                </div>

                {/* Right Column - Map (2 spans) */}
                <div className="col-span-2">
                  <PolygonMap
                    establishment={polygonEstablishment}
                    userRole={userRole}
                    editMode={polygonEditMode}
                    onSave={handlePolygonChange}
                    showOtherPolygons={showOtherPolygons}
                    snapEnabled={snapEnabled}
                    snapDistance={snapDistance}
                  />
                </div>
              </div>
            </div>
          ) : currentView === "inspections" ? (
            <div className="p-4 bg-white rounded shadow">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h1 className="text-2xl font-bold text-sky-600">
                  Inspection Records
                </h1>
                <button
                  onClick={handleBackToEstablishments}
                  className="px-3 py-1 text-gray-700 bg-gray-300 rounded hover:bg-gray-400"
                >
                  Back to List
                </button>
              </div>

              {/* Inspection Records Content */}
              <EstablishmentInspectionsContent
                establishment={inspectionsEstablishment}
              />
            </div>
          ) : null}
        </div>
      </LayoutWithSidebar>
      <Footer />

      {/* Add Establishment Modal */}
      {showAdd && canEditEstablishments() && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <AddEstablishment
            onClose={() => setShowAdd(false)}
            onEstablishmentAdded={handleEstablishmentChanged}
            onPolygonCreate={handlePolygonCreate}
          />
        </div>
      )}

      {/* Edit Establishment Modal */}
      {editEstablishment && canEditEstablishments() && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <EditEstablishment
            establishmentData={editEstablishment}
            onClose={() => setEditEstablishment(null)}
            onEstablishmentUpdated={handleEstablishmentChanged}
            onPolygonCreate={handlePolygonCreate}
          />
        </div>
      )}
    </>
  );
}
