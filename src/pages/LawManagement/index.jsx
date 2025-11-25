import { useEffect, useMemo, useState } from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import LayoutWithSidebar from "../../components/LayoutWithSidebar";
import LawList from "../../components/laws/LawList";
import AddLawModal from "../../components/laws/AddLawModal";
import EditLawModal from "../../components/laws/EditLawModal";
import LawDetailsModal from "../../components/laws/LawDetailsModal";
import { useNotifications } from "../../hooks/useNotifications";
import * as lawApi from "../../services/lawApi";

export default function LawManagement() {
  const notifications = useNotifications();
  const [laws, setLaws] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [editContext, setEditContext] = useState(null);
  const [viewLaw, setViewLaw] = useState(null);

  // Fetch laws on mount
  useEffect(() => {
    fetchLaws();
  }, []);

  const fetchLaws = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await lawApi.getLaws();
      setLaws(data);
    } catch (err) {
      console.error("Error fetching laws:", err);
      setError(err.message || "Failed to load laws.");
      notifications.error("Failed to load laws.", {
        title: "Error",
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    fetchLaws();
  };

  const handleStatusChange = async (lawId, nextStatus) => {
    try {
      const updatedLaw = await lawApi.toggleLawStatus(lawId);
      setLaws((prev) =>
        prev.map((law) => (law.id === lawId ? updatedLaw : law))
      );
      notifications.success(
        `Law ${
          nextStatus === "Active" ? "activated" : "deactivated"
        } successfully.`,
        {
          title: "Status Updated",
          duration: 3000,
        }
      );
    } catch (err) {
      console.error("Error updating law status:", err);
      notifications.error(err.message || "Failed to update law status.", {
        title: "Update Error",
        duration: 5000,
      });
      throw err;
    }
  };

  const handleLawAdded = (newLaw) => {
    setLaws((prev) => [newLaw, ...prev]);
  };

  const handleLawUpdated = (updatedLaw) => {
    setLaws((prev) =>
      prev.map((law) => (law.id === updatedLaw.id ? updatedLaw : law))
    );
  };

  const currentLawForEdit = useMemo(() => {
    if (!editContext) return null;
    const existing = laws.find((law) => law.id === editContext.id);
    return existing || editContext;
  }, [editContext, laws]);

  return (
    <>
      <Header />
      <LayoutWithSidebar userLevel="admin">
        <div>
          <LawList
            laws={laws}
            loading={loading}
            error={error}
            onRefresh={handleRefresh}
            onAdd={() => setAddOpen(true)}
            onEdit={(law) => setEditContext(law)}
            onView={setViewLaw}
            onStatusChange={handleStatusChange}
          />
        </div>
      </LayoutWithSidebar>
      <Footer />

      {addOpen && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
          <AddLawModal
            onClose={() => setAddOpen(false)}
            onLawAdded={(law) => {
              handleLawAdded(law);
              setAddOpen(false);
            }}
          />
        </div>
      )}

      {currentLawForEdit && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
          <EditLawModal
            law={currentLawForEdit}
            onClose={() => setEditContext(null)}
            onLawUpdated={(law) => {
              handleLawUpdated(law);
              setEditContext(null);
            }}
          />
        </div>
      )}

      {viewLaw && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
          <LawDetailsModal law={viewLaw} onClose={() => setViewLaw(null)} />
        </div>
      )}
    </>
  );
}
