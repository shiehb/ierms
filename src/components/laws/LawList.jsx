import { useEffect, useMemo, useState } from "react";
import { Loader2, MoreHorizontal, Plus } from "lucide-react";
import ConfirmationDialog from "../common/ConfirmationDialog";
import TableToolbar from "../common/TableToolbar";
import PaginationControls from "../PaginationControls";
import { useLocalStoragePagination } from "../../hooks/useLocalStoragePagination";
import { useNotifications } from "../../hooks/useNotifications";

export default function LawList({
  laws = [],
  loading = false,
  error = "",
  onRefresh,
  onAdd,
  onEdit,
  onView,
  onStatusChange,
}) {
  const notifications = useNotifications();

  const [search, setSearch] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [selectedIds, setSelectedIds] = useState([]);
  const [statusDialog, setStatusDialog] = useState({
    open: false,
    law: null,
    nextStatus: "Active",
  });
  const [statusSubmitting, setStatusSubmitting] = useState(false);

  const savedPagination = useLocalStoragePagination("laws_list", 25);
  const [pageSize, setPageSize] = useState(savedPagination.pageSize);
  const [currentPage, setCurrentPage] = useState(savedPagination.page);

  const filteredLaws = useMemo(() => {
    return laws.filter((law) => {
      const matchesSearch =
        !search ||
        [law.law_title, law.reference_code, law.description]
          .filter(Boolean)
          .some((value) => value.toLowerCase().includes(search.toLowerCase()));

      return matchesSearch;
    });
  }, [laws, search]);

  const filteredAndSortedLaws = useMemo(() => {
    const toSort = [...filteredLaws];
    if (sortConfig.key) {
      toSort.sort((a, b) => {
        const direction = sortConfig.direction === "desc" ? -1 : 1;
        switch (sortConfig.key) {
          case "law_title":
            return (
              a.law_title.localeCompare(b.law_title, undefined, {
                sensitivity: "base",
              }) * direction
            );
          case "effective_date": {
            const aDate = a.effective_date ? new Date(a.effective_date) : null;
            const bDate = b.effective_date ? new Date(b.effective_date) : null;
            if (!aDate && !bDate) return 0;
            if (!aDate) return 1 * direction;
            if (!bDate) return -1 * direction;
            return (aDate.getTime() - bDate.getTime()) * direction;
          }
          case "status":
            return a.status.localeCompare(b.status) * direction;
          default:
            return 0;
        }
      });
    }
    return toSort;
  }, [filteredLaws, sortConfig]);

  const totalFiltered = filteredAndSortedLaws.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize) || 1);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedLaws = filteredAndSortedLaws.slice(
    startIndex,
    startIndex + pageSize
  );

  useEffect(() => {
    const totalPages = Math.max(
      1,
      Math.ceil(filteredAndSortedLaws.length / pageSize) || 1
    );
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [filteredAndSortedLaws, pageSize, currentPage]);

  useEffect(() => {
    setSelectedIds((prev) => {
      const filtered = prev.filter((id) =>
        paginatedLaws.some((law) => law.id === id)
      );
      if (filtered.length === prev.length) {
        let unchanged = true;
        for (let i = 0; i < filtered.length; i += 1) {
          if (filtered[i] !== prev[i]) {
            unchanged = false;
            break;
          }
        }
        if (unchanged) {
          return prev;
        }
      }
      return filtered;
    });
  }, [paginatedLaws]);

  const handleSelectAll = (checked) => {
    if (checked) {
      const pageIds = paginatedLaws.map((law) => law.id);
      setSelectedIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    } else {
      const pageIds = new Set(paginatedLaws.map((law) => law.id));
      setSelectedIds((prev) => prev.filter((id) => !pageIds.has(id)));
    }
  };

  const handleRowSelect = (id, checked) => {
    setSelectedIds((prev) => {
      if (checked) {
        return prev.includes(id) ? prev : [...prev, id];
      }
      return prev.filter((selectedId) => selectedId !== id);
    });
  };

  const openStatusDialog = (law) => {
    const nextStatus = law.status === "Active" ? "Inactive" : "Active";
    setStatusDialog({
      open: true,
      law,
      nextStatus,
    });
  };

  const closeStatusDialog = () => {
    setStatusDialog({
      open: false,
      law: null,
      nextStatus: "Active",
    });
    setStatusSubmitting(false);
  };

  const handleConfirmStatusChange = async () => {
    if (!statusDialog.law) return;

    setStatusSubmitting(true);
    const nextStatus = statusDialog.nextStatus;
    const lawId = statusDialog.law.id;

    try {
      await Promise.resolve(onStatusChange?.(lawId, nextStatus));
      notifications.success(
        `Law ${
          nextStatus === "Active" ? "activated" : "deactivated"
        } successfully.`,
        {
          title: "Status Updated",
          duration: 3000,
        }
      );
    } catch (error) {
      console.error("Failed to update law status:", error);
      notifications.error("Failed to update law status.", {
        title: "Update Error",
        duration: 6000,
      });
    } finally {
      setStatusSubmitting(false);
      closeStatusDialog();
    }
  };

  const allSelected =
    paginatedLaws.length > 0 &&
    paginatedLaws.every((law) => selectedIds.includes(law.id));

  const handleSearchChange = (value) => {
    setSearch(value);
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size) => {
    setPageSize(size);
    setCurrentPage(1);
  };

  const totalItems = laws.length;
  const startItem = totalFiltered === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem =
    totalFiltered === 0 ? 0 : Math.min(currentPage * pageSize, totalFiltered);
  const hasActiveFilters = Boolean(search);

  return (
    <div className="p-4 bg-white h-[calc(100vh-160px)]">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h1 className="text-2xl font-bold text-sky-600">Law Management</h1>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <TableToolbar
            searchValue={search}
            onSearchChange={handleSearchChange}
            onSearchClear={() => handleSearchChange("")}
            searchPlaceholder="Search..."
            sortConfig={sortConfig}
            sortFields={[
              { key: "law_title", label: "Law" },
              { key: "effective_date", label: "Effective Date" },
              { key: "status", label: "Status" },
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
            onRefresh={onRefresh}
            isRefreshing={loading}
            additionalActions={
              onAdd
                ? [
                    {
                      onClick: onAdd,
                      icon: Plus,
                      text: "Add Law",
                      title: "Add Law",
                      variant: "primary",
                    },
                  ]
                : []
            }
            className="rounded-lg bg-white shadow-sm"
          />
        </div>
      </div>

      <div className="rounded border border-slate-200 bg-white shadow-sm h-[calc(100%-90px)] flex flex-col">
        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
              <p className="text-sm text-slate-500">Loading laws...</p>
            </div>
          </div>
        ) : totalFiltered === 0 ? (
          <div className="flex flex-1 items-center justify-center p-10 text-center">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">
                No laws found
              </h3>
              <p className="mt-2 text-sm text-slate-500">
                Try adjusting your search or filters, or add a new law.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-left text-white bg-gradient-to-r from-sky-600 to-sky-700 sticky top-0 z-10">
                  <th className="w-6 px-3 py-2 text-center border-b border-sky-500/50">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={(event) =>
                        handleSelectAll(event.target.checked)
                      }
                    />
                  </th>
                  {[
                    "Law",
                    "Category",
                    "Effective Date",
                    "Status",
                    "Actions",
                  ].map((label, index) => (
                    <th
                      key={label}
                      className={`px-3 py-2 border-b border-sky-500/50 ${
                        index === 2
                          ? "text-left"
                          : index === 3
                          ? "text-center"
                          : ""
                      }`}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginatedLaws.map((law) => {
                  const isSelected = selectedIds.includes(law.id);
                  const effectiveDate = law.effective_date
                    ? new Date(law.effective_date).toLocaleDateString(
                        undefined,
                        {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        }
                      )
                    : "—";

                  return (
                    <tr
                      key={law.id}
                      className={`border-b border-gray-200 text-sm ${
                        isSelected ? "bg-sky-50" : ""
                      }`}
                    >
                      <td className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(event) =>
                            handleRowSelect(law.id, event.target.checked)
                          }
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-col min-w-0">
                          <span className="font-semibold text-slate-800 truncate">
                            {law.law_title}
                          </span>
                          <span className="text-xs text-slate-500 truncate">
                            {law.reference_code}
                          </span>
                        </div>
                      </td>

                      <td className="px-3 py-3 text-slate-600">
                        {law.category || "Uncategorized"}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {effectiveDate}
                      </td>
                      <td className="px-3 py-3 text-center">
                        <span
                          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
                            law.status === "Active"
                              ? "bg-green-100 text-green-700"
                              : "bg-rose-100 text-rose-600"
                          }`}
                        >
                          <span
                            className={`h-2.5 w-2.5 rounded-full ${
                              law.status === "Active"
                                ? "bg-green-500"
                                : "bg-rose-500"
                            }`}
                          />
                          {law.status}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <LawActionButtons
                          law={law}
                          onView={() => onView?.(law)}
                          onEdit={() => onEdit?.(law)}
                          onToggle={() => openStatusDialog(law)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mt-4">
        <PaginationControls
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={totalItems}
          filteredItems={totalFiltered}
          hasActiveFilters={hasActiveFilters}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          startItem={startItem}
          endItem={endItem}
          storageKey="laws_list"
        />
      </div>

      {error && !loading && (
        <div className="fixed bottom-6 right-6 max-w-sm rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 shadow-lg text-sm text-amber-700">
          {error}
        </div>
      )}

      <ConfirmationDialog
        open={statusDialog.open}
        title={`Set law to ${statusDialog.nextStatus}?`}
        message={
          statusDialog.law ? (
            <div className="space-y-2 text-sm">
              <p>
                You are about to mark{" "}
                <span className="font-semibold text-slate-800">
                  {statusDialog.law.law_title}
                </span>{" "}
                as{" "}
                <span className="font-semibold">{statusDialog.nextStatus}</span>
                .
              </p>
              <p className="text-slate-500">
                This affects its availability in inspection forms and reports.
              </p>
            </div>
          ) : null
        }
        confirmText="Confirm"
        cancelText="Cancel"
        loading={statusSubmitting}
        confirmColor={statusDialog.nextStatus === "Active" ? "green" : "amber"}
        onCancel={closeStatusDialog}
        onConfirm={handleConfirmStatusChange}
      />
    </div>
  );
}

function LawActionButtons({ law, onView, onEdit, onToggle }) {
  const [open, setOpen] = useState(false);
  const dropdownId = `law-actions-${law.id}`;

  useEffect(() => {
    const handler = (event) => {
      if (
        open &&
        event.target.closest?.(`#${dropdownId}`) === null &&
        event.target.closest?.(`#${dropdownId}-trigger`) === null
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, dropdownId]);

  const actionText = law.status === "Active" ? "Deactivate" : "Activate";

  return (
    <div className="relative inline-flex justify-end" id={dropdownId}>
      <button
        id={`${dropdownId}-trigger`}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="rounded-full p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreHorizontal size={18} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-48 rounded-md border border-slate-200 bg-white shadow-lg">
          <div className="py-1 text-sm text-slate-600">
            <button
              onClick={() => {
                setOpen(false);
                onView?.(law);
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-slate-50"
            >
              View Details
            </button>
            <button
              onClick={() => {
                setOpen(false);
                onEdit?.(law);
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-slate-50"
            >
              Edit
            </button>
            <button
              onClick={() => {
                setOpen(false);
                onToggle?.(law);
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-left text-amber-600 hover:bg-amber-50"
            >
              {actionText}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
