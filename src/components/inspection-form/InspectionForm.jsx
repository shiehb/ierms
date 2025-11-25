import React, { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import * as InspectionConstants from "../../constants/inspectionform/index";
import LayoutForm from "../LayoutForm";
import { validateEmailAddress } from "./utils";
import {
  saveInspectionDraft,
  completeInspection,
  getInspection,
  closeInspection,
  sendNOV,
  sendNOO,
  uploadFindingDocument,
  getFindingDocuments,
  deleteFindingDocument,
  getUsers,
  getPreviousViolations,
} from "../../services/api";
import ConfirmationDialog from "../common/ConfirmationDialog";
import { useNotifications } from "../../hooks/useNotifications";
import {
  getButtonVisibility as getRoleStatusButtonVisibility,
  canUserAccessInspection,
} from "../../utils/roleStatusMatrix";
import { API_BASE_URL } from "../../config/api";

// Import all section components
import UnifiedInspectionHeader from "./UnifiedInspectionHeader";
import GeneralInformation from "./GeneralInformation";
import PurposeOfInspection from "./PurposeOfInspection";
import ComplianceStatus from "./ComplianceStatus";
import SummaryOfCompliance from "./SummaryOfCompliance";
import SummaryOfFindingsAndObservations from "./SummaryOfFindingsAndObservations";
import Recommendations from "./Recommendations";
import InspectionPolygonMap from "./InspectionPolygonMap";
import ValidationSummary from "./ValidationSummary";
import PreviousViolations from "./PreviousViolations";

/* ---------------------------
   Main Inspection Form Component
   ---------------------------*/
export default function InspectionForm({ inspectionData }) {
  const navigate = useNavigate();
  const { id } = useParams();
  const location = useLocation();
  const urlParams = new URLSearchParams(location.search);
  const returnTo = urlParams.get("returnTo");
  const reviewMode = urlParams.get("reviewMode") === "true";
  const inspectionId = id || inspectionData?.id;
  const storageKey = `inspection-form-${inspectionId || "draft"}`;
  const notifications = useNotifications();

  // Load saved draft
  const loadSavedData = () => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.error("loadSavedData error", e);
    }
    return null;
  };

  const savedData = loadSavedData();

  // State
  const [general, setGeneral] = useState(
    savedData?.general || {
      establishment_name: "",
      address: "",
      coordinates: "",
      nature_of_business: "",
      year_established: "",
      inspection_date_time: "",
      environmental_laws: [],
      operating_hours: "",
      operating_days_per_week: "",
      operating_days_per_year: "",
      product_lines: "",
      declared_production_rate: "",
      actual_production_rate: "",
      managing_head: "",
      pco_name: "",
      interviewed_person: "",
      pco_accreditation_no: "",
      effectivity_date: "",
      phone_fax_no: "",
      email_address: "",
    }
  );

  const [purpose, setPurpose] = useState(
    savedData?.purpose || {
      verify_accuracy: false,
      verify_accuracy_details: [],
      verify_accuracy_others: "",
      determine_compliance: false,
      investigate_complaints: false,
      check_commitment_status: false,
      commitment_status_details: [],
      commitment_status_others: "",
      other_purpose: false,
      other_purpose_specify: "",
    }
  );

  const [permits, setPermits] = useState(
    savedData?.permits || InspectionConstants.initialPermits || []
  );
  const [complianceItems, setComplianceItems] = useState(
    savedData?.complianceItems ||
      InspectionConstants.initialComplianceItems ||
      []
  );
  const [systems, setSystems] = useState(
    savedData?.systems || InspectionConstants.INSPECTION_SYSTEMS || []
  );
  const [recommendationState, setRecommendationState] = useState(
    savedData?.recommendationState || { checked: [], otherText: "" }
  );

  const [lawFilter, setLawFilter] = useState(savedData?.lawFilter || []);

  // Finding images state - stores images for each finding system
  const [findingImages, setFindingImages] = useState(
    savedData?.findingImages || {}
  );

  // General findings documents state
  const [generalFindings, setGeneralFindings] = useState(
    savedData?.generalFindings || []
  );
  const [lastSaveTime, setLastSaveTime] = useState(
    savedData?.lastSaved || null
  );
  const [errors, setErrors] = useState({});
  const [currentUser, setCurrentUser] = useState(null);
  const [inspectionStatus, setInspectionStatus] = useState(null);
  const [fullInspectionData, setFullInspectionData] = useState(null);
  const [isDataLoaded, setIsDataLoaded] = useState(false);

  // Confirmation dialog states
  const [completeConfirmation, setCompleteConfirmation] = useState({
    open: false,
    compliance: "",
    violations: "",
    findings: "",
  });
  const [closeConfirmation, setCloseConfirmation] = useState({ open: false });
  const [actionConfirmation, setActionConfirmation] = useState({
    open: false,
    inspection: null,
    action: null,
  });
  const [loading, setLoading] = useState(false);
  const [hasFormChanges, setHasFormChanges] = useState(false);
  const [hasActionTaken, setHasActionTaken] = useState(false);
  const [autoSaveStatus] = useState("saved"); // 'saving', 'saved', 'error'
  const [systemUserEmails, setSystemUserEmails] = useState([]);

  // Tab navigation state and refs
  const [activeSection, setActiveSection] = useState("general");
  const [isMapPanelOpen, setIsMapPanelOpen] = useState(false);
  const [isPreviousViolationsOpen, setIsPreviousViolationsOpen] =
    useState(false);
  const generalRef = useRef(null);
  const purposeRef = useRef(null);
  const complianceStatusRef = useRef(null);
  const summaryComplianceRef = useRef(null);
  const findingsRef = useRef(null);
  const recommendationsRef = useRef(null);

  const sectionRefs = useMemo(
    () => ({
      general: generalRef,
      purpose: purposeRef,
      "compliance-status": complianceStatusRef,
      "summary-compliance": summaryComplianceRef,
      findings: findingsRef,
      recommendations: recommendationsRef,
    }),
    []
  );

  useEffect(() => {
    let isMounted = true;

    const fetchSystemUserEmails = async () => {
      try {
        const data = await getUsers({ page_size: 1000 });
        const users = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
          ? data
          : [];
        const emailList = users
          .map((user) => user?.email?.trim().toLowerCase())
          .filter(Boolean);

        if (isMounted) {
          setSystemUserEmails([...new Set(emailList)]);
        }
      } catch (error) {
        console.error("Failed to load system user emails:", error);
      }
    };

    fetchSystemUserEmails();

    return () => {
      isMounted = false;
    };
  }, []);

  // Function to determine compliance status based on form data
  const determineComplianceStatus = () => {
    // Check compliance items
    const hasNonCompliantItems = complianceItems.some(
      (item) => item.compliant === "No"
    );
    const hasCompliantItems = complianceItems.some(
      (item) => item.compliant === "Yes"
    );

    // Check systems (findings)
    const hasNonCompliantSystems = systems.some(
      (system) => system.nonCompliant
    );
    const hasCompliantSystems = systems.some((system) => system.compliant);

    // Determine overall compliance
    if (hasNonCompliantItems || hasNonCompliantSystems) {
      return "NON_COMPLIANT";
    } else if (hasCompliantItems || hasCompliantSystems) {
      return "COMPLIANT";
    } else {
      // If no compliance data is filled, assume compliant (user hasn't marked anything as non-compliant)
      return "COMPLIANT";
    }
  };

  // Determine button visibility and access control based on unified role-status matrix
  const getButtonVisibility = () => {
    const userLevel = currentUser?.userlevel;
    const status = inspectionStatus;

    // Check if we're in preview mode
    const isPreviewMode = urlParams.get("mode") === "preview";

    // If status is null or user is not loaded yet, show default buttons for Section Chief
    if (!status || !userLevel) {
      console.warn(
        `⚠️ Status or user not loaded yet: status=${status}, userLevel=${userLevel}`
      );
      // Return default permissions for Section Chief while data loads
      if (userLevel === "Section Chief") {
        return {
          showCloseButton: true,
          showBackButton: false,
          showDraftButton: true,
          showSubmitButton: true,
          isReadOnly: false,
          canEditRecommendation: false,
          isDivisionChief: false,
        };
      }
      return {
        showCloseButton: false,
        showBackButton: false,
        showDraftButton: false,
        showSubmitButton: false,
        isReadOnly: true,
        canEditRecommendation: false,
        isDivisionChief: false,
      };
    }

    // Check if user can access this inspection
    const canAccess = canUserAccessInspection(userLevel, status);
    if (!canAccess) {
      console.warn(
        `🚫 User ${userLevel} cannot access inspection with status ${status}`
      );
      return {
        showCloseButton: false,
        showBackButton: false,
        showDraftButton: false,
        showSubmitButton: false,
        isReadOnly: true,
        canEditRecommendation: false,
        isDivisionChief: userLevel === "Division Chief",
      };
    }

    // Get button visibility from unified role-status matrix
    const roleStatusConfig = getRoleStatusButtonVisibility(
      userLevel,
      status,
      isPreviewMode,
      returnTo
    );

    // Additional role-specific logic
    const isDivisionChief = userLevel === "Division Chief";

    // console.log('🔍 Unified button visibility debug:', {
    //   userLevel,
    //   status,
    //   isPreviewMode,
    //   returnTo,
    //   canAccess,
    //   roleStatusConfig
    // });

    const buttonVisibility = {
      // Use unified role-status matrix configuration
      showCloseButton: roleStatusConfig.showClose,
      showBackButton: roleStatusConfig.showBack,
      showDraftButton: roleStatusConfig.showDraft,
      showSubmitButton: roleStatusConfig.showSubmit,

      // Access control
      isReadOnly: roleStatusConfig.isReadOnly,

      // Role-specific permissions
      canEditRecommendation: isDivisionChief,
      isDivisionChief: isDivisionChief,
    };

    // console.log('🎯 Final unified button visibility result:', buttonVisibility);

    return buttonVisibility;
  };

  const buttonVisibility = useMemo(
    () => getButtonVisibility(),
    [
      currentUser?.userlevel,
      inspectionStatus,
      urlParams.get("mode"),
      returnTo,
      reviewMode,
    ]
  );

  // Local storage autosave (30-second interval)
  useEffect(() => {
    const timer = setTimeout(() => {
      const saveData = {
        general,
        purpose,
        permits,
        complianceItems,
        systems,
        recommendationState,
        lawFilter,
        findingImages,
        generalFindings,
        lastSaved: new Date().toISOString(),
      };
      try {
        localStorage.setItem(storageKey, JSON.stringify(saveData));
      } catch (e) {
        console.error("localStorage backup error", e);
      }
    }, 30000); // 30 seconds

    return () => clearTimeout(timer);
  }, [
    general,
    purpose,
    permits,
    complianceItems,
    systems,
    recommendationState,
    lawFilter,
    findingImages,
    generalFindings,
    storageKey,
  ]);

  // Prefill law filter from fullInspectionData
  useEffect(() => {
    if (
      fullInspectionData?.law &&
      !lawFilter.includes(fullInspectionData.law)
    ) {
      setLawFilter([fullInspectionData.law]);
    }
  }, [fullInspectionData, lawFilter]);

  // Load photos from backend
  const loadPhotosFromBackend = async (inspectionId) => {
    try {
      const documents = await getFindingDocuments(inspectionId);

      // Filter for general photos (system_id: general)
      const generalPhotos = documents.filter(
        (doc) =>
          doc.description && doc.description.includes("system_id:general")
      );

      if (generalPhotos.length > 0) {
        // Convert backend documents to frontend format
        const convertedPhotos = generalPhotos.map((doc) => {
          // Parse metadata from description
          const metadata = {};
          if (doc.description) {
            const parts = doc.description.split("|");
            parts.forEach((part) => {
              const [key, value] = part.split(":");
              if (key && value) {
                metadata[key] = value;
              }
            });
          }

          return {
            id: `backend-${doc.id}`,
            file: null, // No file object for backend photos
            url: doc.file_url || doc.file,
            name:
              (doc.file_url || doc.file)?.split("/").pop() || `Photo ${doc.id}`,
            type: (doc.file_url || doc.file)?.toLowerCase().includes(".pdf")
              ? "application/pdf"
              : "image/jpeg",
            size: 0, // Unknown size for backend photos
            caption: metadata.caption || "",
            uploaded: true,
            uploadProgress: 100,
            error: null,
            systemId: "general",
            backendId: doc.id,
          };
        });

        // Update general findings with backend photos
        setGeneralFindings((prevPhotos) => {
          // Merge with existing photos, avoiding duplicates
          const existingIds = new Set(prevPhotos.map((p) => p.backendId));
          const newPhotos = convertedPhotos.filter(
            (p) => !existingIds.has(p.backendId)
          );
          return [...prevPhotos, ...newPhotos];
        });
      }
    } catch (error) {
      console.error("Failed to load photos from backend:", error);
      // Don't show error notification for photos as it's not critical
    }
  };

  // Function to refresh photos (can be called manually if needed)
  const _refreshPhotos = async () => {
    if (inspectionId) {
      await loadPhotosFromBackend(inspectionId);
    }
  };

  // Function to delete photo from backend
  const deletePhotoFromBackend = async (imageId, backendId) => {
    try {
      if (backendId && inspectionId) {
        await deleteFindingDocument(inspectionId, backendId);
      }
    } catch (error) {
      console.error("Failed to delete photo from backend:", error);
      notifications.error(
        "Failed to delete photo from server. Please try again.",
        {
          title: "Delete Error",
          duration: 3000,
        }
      );
      throw error; // Re-throw to prevent frontend removal if backend fails
    }
  };

  // Load draft from backend when component mounts
  useEffect(() => {
    const loadDraftFromBackend = async () => {
      if (!inspectionId || isDataLoaded) return;

      try {
        // Use the API service instead of direct fetch
        const inspectionData = await getInspection(inspectionId);

        // Store full inspection data for autofill
        setFullInspectionData(inspectionData);

        // Store inspection status for completion logic
        setInspectionStatus(
          inspectionData.current_status || inspectionData.status
        );

        // Check if we have localStorage data and determine loading priority
        const hasLocalStorageData =
          savedData && Object.keys(savedData).length > 0;
        const isReviewMode = reviewMode || returnTo === "review";
        const isInProgressStatus =
          inspectionData.current_status &&
          [
            "SECTION_IN_PROGRESS",
            "UNIT_IN_PROGRESS",
            "MONITORING_IN_PROGRESS",
          ].includes(inspectionData.current_status);

        // If we have localStorage data and (we're in review mode OR it's an in-progress status), prioritize localStorage
        if (hasLocalStorageData && (isReviewMode || isInProgressStatus)) {
          // Load localStorage data into form state
          if (savedData.general) {
            setGeneral((prevGeneral) => ({
              ...prevGeneral,
              ...savedData.general,
            }));
          }

          if (savedData.purpose) {
            setPurpose((prevPurpose) => ({
              ...prevPurpose,
              ...savedData.purpose,
            }));
          }

          if (savedData.permits) {
            setPermits(savedData.permits);
          }

          if (savedData.complianceItems) {
            setComplianceItems(savedData.complianceItems);
          }

          if (savedData.systems) {
            // Clean systems data - remove all auto-summary properties
            const cleanedSystems = savedData.systems.map((system) => {
              // Create a clean system object with only core properties
              const cleanedSystem = {
                // Core system properties only
                system: system.system || "",
                lawId: system.lawId || "",
                compliant: system.compliant || "",
                nonCompliant: system.nonCompliant || false,
                remarks: system.remarks || "",
                remarksOption: system.remarksOption || "",

                // Preserve other essential properties
                id: system.id || null,
                createdAt: system.createdAt || null,
                updatedAt: system.updatedAt || null,
              };

              return cleanedSystem;
            });

            setSystems(cleanedSystems);
          }

          if (savedData.recommendationState) {
            setRecommendationState(savedData.recommendationState);
          }

          if (savedData.lawFilter) {
            setLawFilter(savedData.lawFilter);
          }

          if (savedData.findingImages) {
            setFindingImages(savedData.findingImages);
          }

          if (savedData.generalFindings) {
            setGeneralFindings(savedData.generalFindings);
          }

          if (savedData.lastSaved) {
            setLastSaveTime(savedData.lastSaved);
          }
        }
        // Otherwise, check if there's checklist data to load (draft or completed)
        else if (
          inspectionData.form?.checklist &&
          (inspectionData.form.checklist.is_draft ||
            inspectionData.form.checklist.completed_at)
        ) {
          const checklistData = inspectionData.form.checklist;

          // Load checklist data into form state, preserving existing values if they exist
          if (checklistData.general) {
            setGeneral((prevGeneral) => ({
              ...prevGeneral,
              ...checklistData.general,
              // Ensure required fields from inspection data are preserved only if not in checklist
              establishment_name:
                checklistData.general.establishment_name ||
                prevGeneral.establishment_name,
              address: checklistData.general.address || prevGeneral.address,
              coordinates:
                checklistData.general.coordinates || prevGeneral.coordinates,
              nature_of_business:
                checklistData.general.nature_of_business ||
                prevGeneral.nature_of_business,
              year_established:
                checklistData.general.year_established ||
                prevGeneral.year_established,
            }));
          }

          if (checklistData.purpose) {
            setPurpose(checklistData.purpose);
          }

          if (checklistData.permits) {
            setPermits(checklistData.permits);
          }

          if (checklistData.complianceItems) {
            setComplianceItems(checklistData.complianceItems);
          }

          if (checklistData.systems) {
            setSystems(checklistData.systems);
          }

          if (checklistData.recommendationState) {
            setRecommendationState(checklistData.recommendationState);
          }

          if (checklistData.lawFilter) {
            setLawFilter(checklistData.lawFilter);
          }

          if (checklistData.findingImages) {
            setFindingImages(checklistData.findingImages);
          }

          if (checklistData.generalFindings) {
            setGeneralFindings(checklistData.generalFindings);
          }

          // Update last save time from checklist
          if (checklistData.last_saved) {
            setLastSaveTime(checklistData.last_saved);
          }

          // Draft notification removed as per requirements
        }

        // Load photos from backend
        await loadPhotosFromBackend(inspectionId);

        // Check if this is a reinspection and auto-open previous violations panel
        // Also check if there might be previous violations even if not explicitly marked
        const isReinspection =
          inspectionData.is_reinspection || inspectionData.previous_inspection;
        const hasEstablishments =
          inspectionData.establishments_detail &&
          inspectionData.establishments_detail.length > 0;

        // Try to fetch previous violations to see if they exist
        if (hasEstablishments && inspectionId) {
          // Check for previous violations asynchronously
          getPreviousViolations(inspectionId)
            .then((data) => {
              console.log("Previous violations check:", {
                hasViolations: data.has_previous_violations,
                count: data.previous_violations?.length || 0,
                isReinspection,
              });
              if (
                data.has_previous_violations &&
                data.previous_violations.length > 0
              ) {
                console.log(
                  "Opening previous violations panel - violations found"
                );
                setIsPreviousViolationsOpen(true);
              } else if (isReinspection) {
                // If marked as reinspection, open even if no violations found yet
                console.log(
                  "Opening previous violations panel - marked as reinspection"
                );
                setIsPreviousViolationsOpen(true);
              }
            })
            .catch((err) => {
              // If error, still open if marked as reinspection
              console.log("Error fetching previous violations:", err);
              if (isReinspection) {
                console.log(
                  "Opening previous violations panel - reinspection (error case)"
                );
                setIsPreviousViolationsOpen(true);
              }
            });
        } else if (isReinspection) {
          // If marked as reinspection, open panel
          console.log(
            "Opening previous violations panel - reinspection (no establishments check)"
          );
          setIsPreviousViolationsOpen(true);
        }

        // Mark data as loaded to prevent duplicate loading
        setIsDataLoaded(true);
      } catch (error) {
        console.error("Failed to load draft from backend:", error);
        notifications.error(
          "Failed to load inspection data. Please refresh the page.",
          {
            title: "Loading Error",
            duration: 5000,
          }
        );
        setIsDataLoaded(true); // Still mark as loaded to prevent infinite retries
      }
    };

    loadDraftFromBackend();
  }, [inspectionId, isDataLoaded, reviewMode, returnTo, savedData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load current user
  useEffect(() => {
    const loadCurrentUser = async () => {
      try {
        const token = localStorage.getItem("access");
        const response = await fetch(`${API_BASE_URL}auth/me/`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const contentType = response.headers.get("content-type");
          if (contentType && contentType.includes("application/json")) {
            const userData = await response.json();
            setCurrentUser(userData);
          } else {
            console.error("❌ Received HTML instead of JSON for user profile");
          }
        } else {
          console.error(
            "❌ Failed to load user profile, status:",
            response.status
          );
        }
      } catch (error) {
        console.error("Failed to load current user:", error);
      }
    };

    loadCurrentUser();
  }, []);

  // Scroll detection for tab navigation
  useEffect(() => {
    const mainContainer = document.getElementById("inspection-form-container");

    if (!mainContainer) return;

    const observerOptions = {
      root: mainContainer, // Watch the scrollable container, not the window
      rootMargin: "-20% 0px -70% 0px", // Trigger when section is 20% from top of viewport
      threshold: [0, 0.1, 0.5, 1],
    };

    const observerCallback = (entries) => {
      // Find the entry with the highest intersection ratio
      let maxRatio = 0;
      let activeEntry = null;

      entries.forEach((entry) => {
        if (entry.intersectionRatio > maxRatio) {
          maxRatio = entry.intersectionRatio;
          activeEntry = entry;
        }
      });

      if (activeEntry && activeEntry.isIntersecting) {
        const sectionId = activeEntry.target.getAttribute("data-section");
        if (sectionId) {
          setActiveSection(sectionId);
        }
      }
    };

    const observer = new IntersectionObserver(
      observerCallback,
      observerOptions
    );

    // Observe all section refs
    Object.values(sectionRefs).forEach((ref) => {
      if (ref.current) {
        observer.observe(ref.current);
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [sectionRefs]);

  // Scroll to section handler - Enhanced for sticky tabs
  const scrollToSection = (sectionId) => {
    // Handle map tab specially - toggle map panel instead of scrolling
    if (sectionId === "map") {
      setIsMapPanelOpen(true);
      return;
    }

    const ref = sectionRefs[sectionId];

    if (ref && ref.current) {
      // Use scrollIntoView which respects scroll-margin-top CSS
      ref.current.scrollIntoView({
        behavior: "smooth",
        block: "start",
        inline: "nearest",
      });

      // Update active section immediately for better UX
      setActiveSection(sectionId);
    }
  };

  // Determine if form is compliant, non-compliant, or mixed
  const determineOverallCompliance = () => {
    const hasNonCompliantItems = complianceItems.some(
      (item) => item.compliant === "No"
    );
    const hasNonCompliantSystems = systems.some(
      (system) => system.nonCompliant
    );

    return {
      isCompliant: !hasNonCompliantItems && !hasNonCompliantSystems,
      isNonCompliant: hasNonCompliantItems || hasNonCompliantSystems,
      hasCompliantItems:
        complianceItems.some((item) => item.compliant === "Yes") ||
        systems.some((system) => system.compliant === "Yes"),
      hasNonCompliantItems: hasNonCompliantItems || hasNonCompliantSystems,
    };
  };

  // Auto-clear recommendations when inspection becomes compliant
  useEffect(() => {
    const complianceStatus = determineOverallCompliance();

    // If inspection is compliant and recommendations exist, clear them
    if (complianceStatus.isCompliant) {
      const hasRecommendations =
        recommendationState.checked?.length > 0 ||
        recommendationState.otherText?.trim();

      if (hasRecommendations) {
        setRecommendationState({ checked: [], otherText: "" });
        setHasFormChanges(true);
      }
    }
  }, [complianceItems, systems]); // Watch for changes in compliance data

  /* ======================
     Validation
     ====================== */
  const validateForm = () => {
    const errs = {};

    // General Info
    if (!general.establishment_name)
      errs.establishment_name = "Establishment name is required.";
    if (!general.address) errs.address = "Address is required.";

    // Coordinates (now required)
    if (!general.coordinates) {
      errs.coordinates = "Coordinates are required.";
    } else {
      const parts = general.coordinates.split(",").map((s) => s.trim());
      if (
        parts.length !== 2 ||
        isNaN(Number(parts[0])) ||
        isNaN(Number(parts[1]))
      ) {
        errs.coordinates = "Coordinates must be in 'lat, lon' decimal format.";
      }
    }

    // Nature of Business (now required)
    if (!general.nature_of_business) {
      errs.nature_of_business = "Nature of Business is required.";
    }

    if (general.year_established) {
      if (!/^\d{4}$/.test(general.year_established)) {
        errs.year_established = "Enter a 4-digit year.";
      } else if (Number(general.year_established) > new Date().getFullYear()) {
        errs.year_established = "Year cannot be in the future.";
      }
    } else {
      errs.year_established = "Year established is required.";
    }

    // Operating Hours (required and must be 1–24)
    if (!general.operating_hours) {
      errs.operating_hours = "Operating Hours is required.";
    } else if (general.operating_hours < 1 || general.operating_hours > 24) {
      errs.operating_hours = "Operating Hours must be between 1 and 24.";
    }

    // Operating Days/Week (now required and must be 1–7)
    if (!general.operating_days_per_week) {
      errs.operating_days_per_week = "Operating Days/Week is required.";
    } else if (
      general.operating_days_per_week < 1 ||
      general.operating_days_per_week > 7
    ) {
      errs.operating_days_per_week =
        "Operating Days/Week must be between 1 and 7.";
    }

    // Operating Days/Year (now required and must be 1–365)
    if (!general.operating_days_per_year) {
      errs.operating_days_per_year = "Operating Days/Year is required.";
    } else if (
      general.operating_days_per_year < 1 ||
      general.operating_days_per_year > 365
    ) {
      errs.operating_days_per_year =
        "Operating Days/Year must be between 1 and 365.";
    }

    // Product Lines (now required)
    if (!general.product_lines || !general.product_lines.trim()) {
      errs.product_lines = "Product Lines is required.";
    }

    // Declared Production Rate (now required)
    if (
      !general.declared_production_rate ||
      !general.declared_production_rate.trim()
    ) {
      errs.declared_production_rate = "Declared Production Rate is required.";
    }

    // Actual Production Rate (now required)
    if (
      !general.actual_production_rate ||
      !general.actual_production_rate.trim()
    ) {
      errs.actual_production_rate = "Actual Production Rate is required.";
    }

    // Managing Head (now required)
    if (!general.managing_head || !general.managing_head.trim()) {
      errs.managing_head = "Managing Head is required.";
    }

    // PCO Name (now required)
    if (!general.pco_name || !general.pco_name.trim()) {
      errs.pco_name = "PCO Name is required.";
    }

    // PCO Accreditation No. (now required)
    if (!general.pco_accreditation_no || !general.pco_accreditation_no.trim()) {
      errs.pco_accreditation_no = "PCO Accreditation No. is required.";
    }

    // Interviewed Person (now required)
    if (!general.interviewed_person || !general.interviewed_person.trim()) {
      errs.interviewed_person = "Interviewed Person is required.";
    }

    // Effectivity Date (now required)
    if (!general.effectivity_date || !general.effectivity_date.trim()) {
      errs.effectivity_date = "Effectivity Date is required.";
    }

    // Phone/Fax No. (now required)
    if (!general.phone_fax_no) {
      errs.phone_fax_no = "Phone/Fax No. is required.";
    }

    // Email Address (now required)
    if (!general.email_address) {
      errs.email_address = "Email Address is required.";
    } else {
      const emailValidation = validateEmailAddress(general.email_address, {
        disallowedEmails: systemUserEmails,
      });
      if (!emailValidation.isValid) {
        errs.email_address = emailValidation.message || "Enter a valid email.";
      }
    }

    if (general.inspection_date_time) {
      const inspDate = new Date(general.inspection_date_time);
      if (isNaN(inspDate.getTime())) {
        errs.inspection_date_time = "Invalid inspection date/time.";
      } else if (inspDate > new Date()) {
        errs.inspection_date_time =
          "Inspection date/time cannot be in the future.";
      } else if (fullInspectionData?.created_at) {
        const creationDate = new Date(fullInspectionData.created_at);
        if (!isNaN(creationDate.getTime()) && inspDate < creationDate) {
          errs.inspection_date_time =
            "Inspection date/time cannot be before the creation date.";
        }
      }
    } else {
      errs.inspection_date_time = "Inspection date/time is required.";
    }

    // Environmental Laws (at least one must be selected)
    if (
      !general.environmental_laws ||
      general.environmental_laws.length === 0
    ) {
      errs.environmental_laws =
        "At least one environmental law must be selected.";
    }

    // DENR Permits Validation - At least one permit must be filled
    const selectedLaws = general.environmental_laws || [];
    const permitsForSelectedLaws = permits.filter((p) =>
      selectedLaws.includes(p.lawId)
    );
    const hasAtLeastOnePermitFilled = permitsForSelectedLaws.some(
      (p) => p.permitNumber && p.permitNumber.trim() !== ""
    );

    if (selectedLaws.length > 0 && !hasAtLeastOnePermitFilled) {
      errs.permits =
        "At least one DENR Permit, License, or Clearance is required.";
    }

    // Summary of Compliance Validation - REMOVED (no validation required)

    // Compliance - validate individual items for selected environmental laws - REMOVED (no validation required)

    // Findings - only validate systems for selected environmental laws
    systems.forEach((s, i) => {
      // Only validate if the system's law is selected (exclude "Commitment/s from previous Technical Conference")
      const shouldValidate =
        selectedLaws.includes(s.lawId) &&
        s.system !== "Commitment/s from previous Technical Conference";

      if (shouldValidate) {
        if (!s.compliant && !s.nonCompliant)
          errs[`systemStatus-${i}`] = `Select status for "${s.system}".`;
        if (s.nonCompliant) {
          if (!s.remarks || s.remarks.trim() === "")
            errs[`sysRemarks-${i}`] = "Enter findings summary.";
        }
      }
    });

    // Recommendations - Conditional validation based on compliance status
    const complianceStatus = determineOverallCompliance();
    if (complianceStatus.isNonCompliant) {
      // If non-compliant, at least one recommendation is required
      const hasRecommendation =
        recommendationState.checked && recommendationState.checked.length > 0;
      if (!hasRecommendation) {
        errs.recommendations =
          "At least one recommendation is required for non-compliant inspections.";
      }
    }

    setErrors(errs);

    return Object.keys(errs).length === 0;
  };

  // Function to clear specific field errors
  const clearError = (fieldName) => {
    if (errors[fieldName]) {
      setErrors((prevErrors) => {
        const newErrors = { ...prevErrors };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  };

  // Function to clear system data when environmental law is unchecked
  const clearSystemsForUnselectedLaws = (selectedLaws) => {
    const updatedSystems = systems.map((system) => {
      // If the system's law is not selected and it's not the "Commitment/s from previous Technical Conference"
      // Also, only clear if the system has a lawId (to avoid clearing systems without lawId)
      if (
        !selectedLaws.includes(system.lawId) &&
        system.system !== "Commitment/s from previous Technical Conference" &&
        system.lawId
      ) {
        return {
          ...system,
          compliant: false,
          nonCompliant: false,
          notApplicable: false,
          remarks: "",
          remarksOption: "",
        };
      }
      return system;
    });
    setSystems(updatedSystems);
    setHasFormChanges(true);
  };

  // Function to clear compliance items for unselected laws
  const clearComplianceItemsForUnselectedLaws = (selectedLaws) => {
    const updatedComplianceItems = complianceItems.map((item) => {
      // If the compliance item's law is not selected
      if (!selectedLaws.includes(item.lawId)) {
        return {
          ...item,
          compliant: "",
          remarksOption: "",
          remarks: "",
        };
      }
      return item;
    });
    setComplianceItems(updatedComplianceItems);
    setHasFormChanges(true);
  };

  /* ======================
     Helper Functions
     ====================== */

  const generateViolationsSummary = () => {
    const violations = [];

    // Check compliance items for violations
    complianceItems.forEach((item) => {
      if (item.compliant === "No") {
        const itemName =
          item.complianceRequirement ||
          (item.conditionNumber ? `Condition ${item.conditionNumber}` : "") ||
          item.applicableLaw ||
          "Unnamed Item";
        violations.push(
          `• ${itemName}: ${item.remarksOption || "Non-compliant"}`
        );
      }
    });

    // Check systems for violations
    systems.forEach((system) => {
      if (system.nonCompliant) {
        const remarks =
          system.remarksOption === "Other"
            ? system.remarks
            : system.remarksOption;
        violations.push(`• ${system.system}: ${remarks || "Non-compliant"}`);
      }
    });

    return violations.length > 0
      ? violations.join("\n")
      : "No violations found";
  };

  const generateFindingsSummary = () => {
    const findings = [];

    // Add compliance items findings
    const compliantItems = complianceItems.filter(
      (item) => item.compliant === "Yes"
    );
    const nonCompliantItems = complianceItems.filter(
      (item) => item.compliant === "No"
    );

    if (compliantItems.length > 0) {
      findings.push(`Compliant Items (${compliantItems.length}):`);
      compliantItems.forEach((item) => {
        const itemName =
          item.complianceRequirement ||
          (item.conditionNumber ? `Condition ${item.conditionNumber}` : "") ||
          item.applicableLaw ||
          "Unnamed Item";
        findings.push(`• ${itemName}: Compliant`);
      });
    }

    if (nonCompliantItems.length > 0) {
      findings.push(`Non-Compliant Items (${nonCompliantItems.length}):`);
      nonCompliantItems.forEach((item) => {
        const itemName =
          item.complianceRequirement ||
          (item.conditionNumber ? `Condition ${item.conditionNumber}` : "") ||
          item.applicableLaw ||
          "Unnamed Item";
        findings.push(
          `• ${itemName}: ${item.remarksOption || "Non-compliant"}`
        );
      });
    }

    // Add systems findings
    const compliantSystems = systems.filter((system) => system.compliant);
    const nonCompliantSystems = systems.filter((system) => system.nonCompliant);

    if (compliantSystems.length > 0) {
      findings.push(`Compliant Systems (${compliantSystems.length}):`);
      compliantSystems.forEach((system) => {
        findings.push(`• ${system.system}: Compliant`);
      });
    }

    if (nonCompliantSystems.length > 0) {
      findings.push(`Non-Compliant Systems (${nonCompliantSystems.length}):`);
      nonCompliantSystems.forEach((system) => {
        const remarks =
          system.remarksOption === "Other"
            ? system.remarks
            : system.remarksOption;
        findings.push(`• ${system.system}: ${remarks || "Non-compliant"}`);
      });
    }

    return findings.length > 0 ? findings.join("\n") : "No findings recorded";
  };

  /* ======================
     Handlers
     ====================== */
  const handleSubmit = () => {
    if (!inspectionId) {
      notifications.error("No inspection ID found. Cannot submit.", {
        title: "Submit Failed",
      });
      return;
    }

    const isValid = validateForm();

    if (!isValid) {
      window.scrollTo({ top: 0, behavior: "smooth" });

      // Show detailed error summary
      const errorCount = Object.keys(errors).length;
      const errorSummary = Object.entries(errors)
        .map(([, message]) => `• ${message}`)
        .join("\n");

      notifications.warning(
        `Please fix ${errorCount} validation error(s) before submitting:\n\n${errorSummary}`,
        {
          title: "Validation Error",
          duration: 10000, // Show for 10 seconds
        }
      );
      return;
    }

    // Auto-save to localStorage before navigation
    try {
      const saveData = {
        general,
        purpose,
        permits,
        complianceItems,
        systems,
        recommendationState,
        findingImages,
        generalFindings,
        lastSaved: new Date().toISOString(),
        autoSavedOnSubmit: true,
      };

      localStorage.setItem(storageKey, JSON.stringify(saveData));

      // Show brief success notification
      notifications.success("Form auto-saved successfully", {
        title: "Auto-Save Complete",
        duration: 2000,
      });
    } catch (e) {
      console.error("Auto-save error on submit:", e);
      notifications.warning("Form submitted but auto-save failed", {
        title: "Auto-Save Warning",
        duration: 3000,
      });
    }

    // Navigate to preview page

    // Prepare form data for preview
    const formDataToPreview = {
      general,
      purpose,
      permits,
      complianceItems,
      systems,
      recommendationState,
      lawFilter,
      findingImages,
      generalFindings,
    };

    if (returnTo === "review") {
      // If editing from review, navigate to preview with reviewApproval=true
      const url = `/inspections/${inspectionId}/review?mode=preview&reviewApproval=true`;
      navigate(url, {
        state: {
          formData: formDataToPreview,
          inspectionData: fullInspectionData,
          compliance: determineComplianceStatus(),
        },
      });
    } else {
      // Regular submit from personnel
      const url = `/inspections/${inspectionId}/review?mode=preview`;
      navigate(url, {
        state: {
          formData: formDataToPreview,
          inspectionData: fullInspectionData,
          compliance: determineComplianceStatus(),
        },
      });
    }
  };

  const handleDraft = async () => {
    if (!inspectionId) {
      notifications.error("No inspection ID found. Cannot save draft.", {
        title: "Draft Save Failed",
      });
      return;
    }

    // Save as draft without validation
    const formDataToSave = {
      general,
      purpose,
      permits,
      complianceItems,
      systems,
      recommendationState,
      lawFilter,
      findingImages,
      generalFindings,
    };

    try {
      // Save draft to backend
      await saveInspectionDraft(inspectionId, { form_data: formDataToSave });

      // Update last save time
      const now = new Date().toISOString();
      setLastSaveTime(now);

      // Clear localStorage draft since it's saved to backend
      try {
        localStorage.removeItem(storageKey);
      } catch (e) {
        console.error("clear draft error", e);
      }

      // Show success message
      notifications.success("Draft saved successfully!", {
        title: "Draft Saved",
      });
    } catch (error) {
      console.error("Failed to save draft:", error);
      notifications.error(`Failed to save draft: ${error.message}`, {
        title: "Draft Save Failed",
      });
    }
  };

  const executeAction = async () => {
    const { inspection, action } = actionConfirmation;
    if (!inspection || !action) return;

    try {
      setLoading(true);

      // Show loading notification for long operations
      if (["send_nov", "send_noo", "mark_compliant"].includes(action)) {
        notifications.info("Processing your request...", {
          title: "Please Wait",
          duration: 2000,
        });
      }

      if (action === "send_nov") {
        await sendNOV(inspection.id, {
          violation_breakdown: generateViolationsSummary(),
          payment_deadline: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
            .toISOString()
            .split("T")[0], // 30 days from now
          penalty_fees: "To be determined based on violation severity",
        });

        setHasActionTaken(true);
        notifications.success("Notice of Violation sent successfully!", {
          title: "NOV Sent",
          duration: 6000,
        });
      } else if (action === "send_noo") {
        await sendNOO(inspection.id, {
          violation_breakdown: generateViolationsSummary(),
          payment_deadline: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000)
            .toISOString()
            .split("T")[0], // 60 days from now
          penalty_fees: "To be determined based on violation severity",
        });

        setHasActionTaken(true);
        notifications.success("Notice of Order sent successfully!", {
          title: "NOO Sent",
          duration: 6000,
        });
      } else if (action === "mark_compliant") {
        // Execute the onConfirm callback from actionConfirmation
        if (actionConfirmation.onConfirm) {
          await actionConfirmation.onConfirm();
        }
        // Close confirmation dialog
        setActionConfirmation({ open: false, inspection: null, action: null });
        return; // Don't navigate here, onConfirm handles it
      }

      // Close confirmation dialog
      setActionConfirmation({ open: false, inspection: null, action: null });

      // Navigate back to inspections list
      navigate("/inspections");
    } catch (error) {
      console.error(`Failed to ${action}:`, error);
      notifications.error(`Failed to ${action}: ${error.message}`, {
        title: `${action.charAt(0).toUpperCase() + action.slice(1)} Failed`,
      });
    } finally {
      setLoading(false);
    }
  };

  const executeComplete = async () => {
    const { compliance } = completeConfirmation;

    if (!compliance) {
      notifications.error(
        "Compliance decision is required to complete the inspection.",
        {
          title: "Missing Information",
        }
      );
      return;
    }

    // Automatically generate violations and findings based on collected data
    const autoViolations = generateViolationsSummary();
    const autoFindings = generateFindingsSummary();

    setLoading(true);
    const formData = {
      general,
      purpose,
      permits,
      complianceItems,
      systems,
      recommendationState,
      findingImages,
      generalFindings,
    };

    try {
      const userLevel = currentUser?.userlevel;
      const status = inspectionStatus;
      let remarks = "";
      let successMessage = "";

      // Determine the appropriate action based on user level and status
      if (
        userLevel === "Monitoring Personnel" &&
        status === "MONITORING_IN_PROGRESS"
      ) {
        // Check if inspection is for combined section or individual section
        const inspectionLaw = fullInspectionData?.law;
        const isCombinedSection = ["PD-1586", "RA-8749", "RA-9275"].includes(
          inspectionLaw
        );

        if (isCombinedSection) {
          remarks = "Inspection submitted for Unit Head review";
          successMessage =
            "Inspection submitted successfully! It has been sent to Unit Head for review.";
        } else {
          remarks = "Inspection submitted for Section Chief review";
          successMessage =
            "Inspection submitted successfully! It has been sent to Section Chief for review.";
        }
      } else if (
        userLevel === "Section Chief" &&
        status === "SECTION_IN_PROGRESS"
      ) {
        remarks = "Inspection submitted for Division Chief review";
        successMessage =
          "Inspection submitted successfully! It has been sent to Division Chief for review.";
      } else if (userLevel === "Unit Head" && status === "UNIT_IN_PROGRESS") {
        remarks = "Inspection submitted for Section Chief review";
        successMessage =
          "Inspection submitted successfully! It has been sent to Section Chief for review.";
      } else {
        remarks = "Inspection submitted for review";
        successMessage = "Inspection submitted successfully!";
      }

      // Complete the inspection
      await completeInspection(inspectionId, {
        form_data: formData,
        compliance_decision: compliance.toUpperCase(),
        violations_found: autoViolations
          ? autoViolations.split("\n").filter((line) => line.trim())
          : ["None"],
        findings_summary: autoFindings,
        remarks: remarks,
      });

      // Clear localStorage draft since it's completed
      try {
        localStorage.removeItem(storageKey);
      } catch (e) {
        console.error("clear draft error", e);
      }

      // Show success message
      notifications.success(successMessage, {
        title: "Inspection Submitted",
        duration: 6000,
      });

      // Close confirmation dialog
      setCompleteConfirmation({
        open: false,
        compliance: "",
        violations: "",
        findings: "",
      });

      // Navigate back to inspections list
      navigate("/inspections");
    } catch (error) {
      console.error("Failed to complete inspection:", error);
      notifications.error(`Failed to complete inspection: ${error.message}`, {
        title: "Completion Failed",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = async () => {
    const userLevel = currentUser?.userlevel;
    const status = inspectionStatus;

    // Section Chief closing from SECTION_REVIEWED
    if (userLevel === "Section Chief" && status === "SECTION_REVIEWED") {
      if (hasFormChanges) {
        // Show confirmation
        setActionConfirmation({
          open: true,
          inspection: fullInspectionData,
          action: "close_section_review",
          message:
            "You have unsaved changes. Do you want to close and send this inspection to Division Chief?",
          onConfirm: async () => {
            try {
              setLoading(true);
              await closeInspection(inspectionId, {
                remarks: "Reviewed and closed by Section Chief",
              });
              notifications.success(
                "Inspection sent to Division Chief successfully",
                { title: "Review Completed" }
              );
              navigate("/inspections");
            } catch (error) {
              notifications.error(`Failed to close: ${error.message}`, {
                title: "Close Failed",
              });
              setLoading(false);
            }
          },
        });
        return;
      } else {
        // No changes - auto-close
        try {
          setLoading(true);
          await closeInspection(inspectionId, {
            remarks: "Reviewed by Section Chief - no changes needed",
          });
          notifications.success("Inspection sent to Division Chief", {
            title: "Review Completed",
          });
          navigate("/inspections");
          return;
        } catch (error) {
          notifications.error(`Failed to close: ${error.message}`, {
            title: "Close Failed",
          });
          setLoading(false);
          return;
        }
      }
    }

    // Division Chief closing from DIVISION_REVIEWED
    if (userLevel === "Division Chief" && status === "DIVISION_REVIEWED") {
      const complianceStatus = determineComplianceStatus();

      if (hasFormChanges) {
        // Show confirmation
        setActionConfirmation({
          open: true,
          inspection: fullInspectionData,
          action: "close_division_review",
          message: `You have unsaved changes. Do you want to close this inspection as ${complianceStatus}?`,
          onConfirm: async () => {
            try {
              setLoading(true);
              const newStatus =
                complianceStatus === "COMPLIANT"
                  ? "CLOSED_COMPLIANT"
                  : "CLOSED_NON_COMPLIANT";
              await closeInspection(inspectionId, {
                remarks: "Closed by Division Chief",
                final_status: newStatus,
              });
              notifications.success(
                `Inspection closed successfully as ${complianceStatus}`,
                { title: "Inspection Closed" }
              );
              navigate("/inspections");
            } catch (error) {
              notifications.error(`Failed to close: ${error.message}`, {
                title: "Close Failed",
              });
              setLoading(false);
            }
          },
        });
        return;
      } else {
        // No changes - auto-finalize
        try {
          setLoading(true);
          const newStatus =
            complianceStatus === "COMPLIANT"
              ? "CLOSED_COMPLIANT"
              : "CLOSED_NON_COMPLIANT";
          await closeInspection(inspectionId, {
            remarks: "Reviewed by Division Chief - no changes needed",
            final_status: newStatus,
          });
          notifications.success(`Inspection closed as ${complianceStatus}`, {
            title: "Inspection Closed",
          });
          navigate("/inspections");
          return;
        } catch (error) {
          notifications.error(`Failed to close: ${error.message}`, {
            title: "Close Failed",
          });
          setLoading(false);
          return;
        }
      }
    }

    // Legal Unit closing from LEGAL_REVIEW
    if (userLevel === "Legal Unit" && status === "LEGAL_REVIEW") {
      if (hasActionTaken || hasFormChanges) {
        // Show confirmation if NOV/NOO was sent or changes made
        setActionConfirmation({
          open: true,
          inspection: fullInspectionData,
          action: "close_legal_review",
          message:
            "Do you want to close this legal review? The inspection will be marked as closed.",
          onConfirm: async () => {
            try {
              setLoading(true);
              await closeInspection(inspectionId, {
                remarks: "Legal review completed",
                final_status: "CLOSED_NON_COMPLIANT",
              });
              notifications.success("Legal review closed successfully", {
                title: "Review Closed",
              });
              navigate("/inspections");
            } catch (error) {
              notifications.error(`Failed to close: ${error.message}`, {
                title: "Close Failed",
              });
              setLoading(false);
            }
          },
        });
        return;
      } else {
        // No action taken - auto-close
        try {
          setLoading(true);
          await closeInspection(inspectionId, {
            remarks: "Legal review completed - no action needed",
            final_status: "CLOSED_NON_COMPLIANT",
          });
          notifications.success("Legal review closed", {
            title: "Review Closed",
          });
          navigate("/inspections");
          return;
        } catch (error) {
          notifications.error(`Failed to close: ${error.message}`, {
            title: "Close Failed",
          });
          setLoading(false);
          return;
        }
      }
    }

    // Default: show regular close confirmation for other cases
    setCloseConfirmation({ open: true });
  };

  const executeClose = (keepDraft) => {
    if (!keepDraft) {
      try {
        localStorage.removeItem(storageKey);
      } catch (e) {
        console.error("Error removing draft:", e);
      }
    }

    setCloseConfirmation({ open: false });

    // Navigate back to inspections list
    navigate("/inspections");
  };

  // Generate validation status for tabs - only show when user has interacted or saving
  const getValidationStatus = () => {
    const validationStatus = {};

    // Only show validation indicators if user has made changes or is saving
    const hasUserInteraction = hasFormChanges || Object.keys(errors).length > 0;

    if (!hasUserInteraction) {
      // Return empty status when no user interaction
      return {
        general: { hasErrors: false, isIncomplete: false },
        purpose: { hasErrors: false, isIncomplete: false },
        "compliance-status": { hasErrors: false, isIncomplete: false },
        "summary-compliance": { hasErrors: false, isIncomplete: false },
        findings: { hasErrors: false, isIncomplete: false },
        recommendations: { hasErrors: false, isIncomplete: false },
      };
    }

    // Check General Information - only show critical field errors
    const criticalGeneralErrors = [
      "establishment_name",
      "environmental_laws",
      "inspection_date_time",
    ].some((field) => errors[field]);
    validationStatus.general = {
      hasErrors: criticalGeneralErrors,
      isIncomplete:
        !general.establishment_name || !general.environmental_laws?.length,
    };

    // Check Purpose of Inspection - only show if no purpose selected
    const purposeErrors = [
      "verify_accuracy",
      "determine_compliance",
      "investigate_complaints",
      "check_commitment_status",
      "other_purpose",
    ].some((field) => errors[field]);
    validationStatus.purpose = {
      hasErrors: purposeErrors,
      isIncomplete:
        !purpose.verify_accuracy &&
        !purpose.determine_compliance &&
        !purpose.investigate_complaints &&
        !purpose.check_commitment_status &&
        !purpose.other_purpose,
    };

    // Check Compliance Status - only show permit errors when user has selected laws
    const complianceErrors = Object.keys(errors).some((key) =>
      key.startsWith("permits")
    );
    validationStatus["compliance-status"] = {
      hasErrors: complianceErrors && general.environmental_laws?.length > 0,
      isIncomplete: false,
    };

    // Check Summary of Compliance - only show when user has interacted with compliance items
    const summaryErrors = Object.keys(errors).some(
      (key) => key.startsWith("remarks-") || key === "compliance_items"
    );
    validationStatus["summary-compliance"] = {
      hasErrors: summaryErrors,
      isIncomplete: false,
    };

    // Check Summary of Findings - only show when user has made compliance decisions
    const findingsErrors = Object.keys(errors).some(
      (key) => key.startsWith("sysRemarks-") || key.startsWith("systemStatus-")
    );
    validationStatus.findings = {
      hasErrors: findingsErrors,
      isIncomplete: false,
    };

    // Check Recommendations - only show when non-compliant and user should add recommendations
    const recommendationsErrors = Object.keys(errors).some((key) =>
      key.startsWith("recommendation-")
    );
    const complianceStatus = determineOverallCompliance();
    validationStatus.recommendations = {
      hasErrors: recommendationsErrors,
      isIncomplete:
        complianceStatus.isNonCompliant &&
        !recommendationState.recommendations?.length &&
        (complianceItems.some((item) => item.compliant === "No") ||
          hasUserInteraction),
    };

    return validationStatus;
  };

  const handleBackToReview = () => {
    if (returnTo === "review") {
      // When returnTo=review (with or without reviewMode), go back to regular review page
      navigate(`/inspections/${inspectionId}/review`);
    } else {
      navigate(-1);
    }
  };

  /* ======================
     Render
     ====================== */
  return (
    <LayoutForm
      headerHeight="large"
      inspectionHeader={
        <UnifiedInspectionHeader
          onSave={handleSubmit}
          onDraft={handleDraft}
          onClose={handleClose}
          onBack={handleBackToReview}
          showBackButton={buttonVisibility.showBackButton}
          lastSaveTime={lastSaveTime}
          autoSaveStatus={autoSaveStatus}
          showDraftButton={buttonVisibility.showDraftButton}
          showSubmitButton={buttonVisibility.showSubmitButton}
          showCloseButton={buttonVisibility.showCloseButton}
          isDraft={fullInspectionData?.form?.checklist?.is_draft || false}
          activeSection={activeSection}
          onTabClick={scrollToSection}
          validationStatus={getValidationStatus()}
          isMapPanelOpen={isMapPanelOpen}
          hasMapData={!!fullInspectionData}
          showRecommendationsTab={determineOverallCompliance().isNonCompliant}
        />
      }
      rightSidebar={
        // Priority 1: Show validation errors (only when submit is attempted)
        hasFormChanges &&
        Object.keys(errors).length > 0 &&
        buttonVisibility.showSubmitButton ? (
          <ValidationSummary
            errors={errors}
            onScrollToSection={scrollToSection}
          />
        ) : // Priority 2: Show previous violations (when panel is open or reinspection detected)
        isPreviousViolationsOpen && fullInspectionData && inspectionId ? (
          <PreviousViolations
            inspectionId={inspectionId}
            inspectionData={fullInspectionData}
            onClose={() => setIsPreviousViolationsOpen(false)}
          />
        ) : // Priority 3: Show map (reference only)
        isMapPanelOpen && fullInspectionData ? (
          <InspectionPolygonMap
            inspectionData={fullInspectionData}
            currentUser={currentUser}
            onClose={() => setIsMapPanelOpen(false)}
          />
        ) : null
      }
    >
      <div className="w-full bg-gray-50">
        <GeneralInformation
          ref={sectionRefs.general}
          data={general}
          setData={(newData) => {
            setGeneral(newData);
            setHasFormChanges(true);
          }}
          systemUserEmails={systemUserEmails}
          onLawFilterChange={(selectedLaws) => {
            setLawFilter(selectedLaws);
            // Clear systems and compliance items for unselected laws
            clearSystemsForUnselectedLaws(selectedLaws);
            clearComplianceItemsForUnselectedLaws(selectedLaws);
          }}
          inspectionData={fullInspectionData}
          errors={errors}
          clearError={clearError}
          isReadOnly={buttonVisibility.isReadOnly}
        />
        <PurposeOfInspection
          ref={sectionRefs.purpose}
          state={purpose}
          setState={(newState) => {
            setPurpose(newState);
            setHasFormChanges(true);
          }}
          errors={errors}
          isReadOnly={buttonVisibility.isReadOnly}
        />

        {lawFilter.length > 0 && (
          <>
            <ComplianceStatus
              ref={sectionRefs["compliance-status"]}
              permits={permits}
              setPermits={setPermits}
              lawFilter={lawFilter}
              errors={errors}
              isReadOnly={buttonVisibility.isReadOnly}
            />
            <SummaryOfCompliance
              ref={sectionRefs["summary-compliance"]}
              items={complianceItems}
              setItems={(newItems) => {
                setComplianceItems(newItems);
                setHasFormChanges(true);
              }}
              lawFilter={lawFilter}
              errors={errors}
              isReadOnly={buttonVisibility.isReadOnly}
              systems={systems}
              setSystems={(newSystems) => {
                setSystems(newSystems);
                setHasFormChanges(true);
              }}
              onComplianceChange={(updatedComplianceItems) => {
                // Auto-sync compliance status to findings systems
                const updatedSystems = systems.map((system) => {
                  // Find corresponding compliance items for this system
                  const relatedComplianceItems = updatedComplianceItems.filter(
                    (item) => {
                      // Match by law ID or system name
                      return (
                        item.lawId === system.lawId ||
                        system.system.includes(item.lawId) ||
                        item.lawId?.includes(system.system)
                      );
                    }
                  );

                  if (relatedComplianceItems.length > 0) {
                    // PRIORITY: Check for non-compliant first (No takes priority over Yes)
                    const hasNonCompliant = relatedComplianceItems.some(
                      (item) => item.compliant === "No"
                    );
                    const hasCompliant = relatedComplianceItems.some(
                      (item) => item.compliant === "Yes"
                    );

                    // If ANY item is non-compliant, mark system as non-compliant
                    if (hasNonCompliant) {
                      return {
                        ...system,
                        compliant: "No",
                        nonCompliant: true,
                      };
                    }
                    // Only mark as compliant if ALL items are compliant (no non-compliant items)
                    else if (hasCompliant && !hasNonCompliant) {
                      return {
                        ...system,
                        compliant: "Yes",
                        nonCompliant: false,
                      };
                    }
                  }

                  return system;
                });

                setSystems(updatedSystems);
                setHasFormChanges(true);
              }}
            />
            <SummaryOfFindingsAndObservations
              ref={sectionRefs.findings}
              systems={systems}
              setSystems={(newSystems) => {
                setSystems(newSystems);
                setHasFormChanges(true);
              }}
              lawFilter={lawFilter}
              errors={errors}
              isReadOnly={buttonVisibility.isReadOnly}
              findingImages={findingImages}
              setFindingImages={(newImages) => {
                setFindingImages(newImages);
                setHasFormChanges(true);
              }}
              generalFindings={generalFindings}
              setGeneralFindings={(newGeneralFindings) => {
                setGeneralFindings(newGeneralFindings);
                setHasFormChanges(true);
              }}
              onUploadFinding={async (systemId, imagesToUpload) => {
                // Upload handler with actual API integration
                try {
                  for (const image of imagesToUpload) {
                    // Update progress to show uploading
                    const updateProgress = (progress) => {
                      if (systemId === "general") {
                        setGeneralFindings((prev) =>
                          prev.map((img) =>
                            img.id === image.id
                              ? { ...img, uploadProgress: progress }
                              : img
                          )
                        );
                      } else {
                        setFindingImages((prev) => ({
                          ...prev,
                          [systemId]: (prev[systemId] || []).map((img) =>
                            img.id === image.id
                              ? { ...img, uploadProgress: progress }
                              : img
                          ),
                        }));
                      }
                    };

                    updateProgress(30);

                    // Upload to backend
                    const findingType =
                      systemId === "general" ? "general" : "individual";
                    const response = await uploadFindingDocument(
                      inspectionId,
                      systemId,
                      image.file,
                      image.caption || "",
                      findingType
                    );

                    updateProgress(100);

                    // Update with backend URL and mark as uploaded
                    if (systemId === "general") {
                      setGeneralFindings((prev) =>
                        prev.map((img) =>
                          img.id === image.id
                            ? {
                                ...img,
                                uploaded: true,
                                uploadProgress: 100,
                                backendId: response.id,
                                url: response.file_url || img.url,
                              }
                            : img
                        )
                      );
                    } else {
                      setFindingImages((prev) => ({
                        ...prev,
                        [systemId]: (prev[systemId] || []).map((img) =>
                          img.id === image.id
                            ? {
                                ...img,
                                uploaded: true,
                                uploadProgress: 100,
                                backendId: response.id,
                                url: response.file_url || img.url,
                              }
                            : img
                        ),
                      }));
                    }
                  }

                  notifications.success("Documents uploaded successfully!", {
                    title: "Upload Complete",
                  });
                } catch (error) {
                  console.error("Upload failed:", error);

                  // Mark images as failed
                  imagesToUpload.forEach((image) => {
                    if (systemId === "general") {
                      setGeneralFindings((prev) =>
                        prev.map((img) =>
                          img.id === image.id
                            ? {
                                ...img,
                                error: error.message,
                                uploadProgress: 0,
                              }
                            : img
                        )
                      );
                    } else {
                      setFindingImages((prev) => ({
                        ...prev,
                        [systemId]: (prev[systemId] || []).map((img) =>
                          img.id === image.id
                            ? {
                                ...img,
                                error: error.message,
                                uploadProgress: 0,
                              }
                            : img
                        ),
                      }));
                    }
                  });

                  notifications.error(`Upload failed: ${error.message}`, {
                    title: "Upload Error",
                  });
                }
              }}
              onDeletePhoto={deletePhotoFromBackend}
              complianceItems={complianceItems}
            />
          </>
        )}

        {/* Conditionally display Recommendations based on compliance status */}
        {(() => {
          const complianceStatus = determineOverallCompliance();
          // Show recommendations only if non-compliant
          if (complianceStatus.isNonCompliant) {
            return (
              <Recommendations
                ref={sectionRefs.recommendations}
                recState={recommendationState}
                setRecState={(newState) => {
                  setRecommendationState(newState);
                  setHasFormChanges(true);
                }}
                errors={errors}
                isReadOnly={buttonVisibility.isReadOnly}
                canEditRecommendation={buttonVisibility.canEditRecommendation}
              />
            );
          }
          // If compliant, hide recommendations section
          return null;
        })()}
      </div>

      {/* Completion Confirmation Dialog */}
      <ConfirmationDialog
        open={completeConfirmation.open}
        title="Submit Inspection for Review"
        message={
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Based on the collected inspection data, the following compliance
              status has been determined. This inspection will be submitted to
              the Unit Head for review:
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Compliance Decision (Auto-determined)
              </label>
              <div
                className={`w-full p-3 border rounded-md ${
                  completeConfirmation.compliance === "COMPLIANT"
                    ? "bg-green-50 border-green-200 text-green-800"
                    : "bg-red-50 border-red-200 text-red-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">
                    {completeConfirmation.compliance === "COMPLIANT"
                      ? "✅"
                      : "❌"}
                  </span>
                  <span className="font-semibold">
                    {completeConfirmation.compliance === "COMPLIANT"
                      ? "COMPLIANT"
                      : "NON-COMPLIANT"}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Summary of Findings and Observations (Auto-generated)
              </label>
              <div className="w-full p-3 border border-gray-300 rounded-md bg-gray-50 text-sm text-gray-700 max-h-32 overflow-y-auto">
                {generateFindingsSummary()}
              </div>
            </div>

            {completeConfirmation.compliance === "NON_COMPLIANT" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Violations Found (Auto-generated)
                </label>
                <div className="w-full p-3 border border-red-200 rounded-md bg-red-50 text-sm text-red-700 max-h-32 overflow-y-auto">
                  {generateViolationsSummary()}
                </div>
              </div>
            )}

            <p className="text-sm text-gray-600">
              Click "Complete Inspection" to finalize the inspection with the
              above status.
            </p>
          </div>
        }
        confirmText="Complete Inspection"
        cancelText="Cancel"
        confirmColor="green"
        size="lg"
        loading={loading}
        onCancel={() =>
          setCompleteConfirmation({
            open: false,
            compliance: "",
            violations: "",
            findings: "",
          })
        }
        onConfirm={executeComplete}
      />

      {/* Close Confirmation Dialog */}
      <ConfirmationDialog
        open={closeConfirmation.open}
        title="Close Inspection Form"
        message={
          <div>
            <p className="mb-2">
              Are you sure you want to close the inspection form?
            </p>
            <p className="text-sm text-gray-600">
              Your current progress will be saved as a draft unless you choose
              to discard it.
            </p>
          </div>
        }
        confirmText="Keep Draft & Close"
        cancelText="Discard & Close"
        confirmColor="sky"
        size="md"
        onCancel={() => executeClose(false)}
        onConfirm={() => executeClose(true)}
      />

      {/* Action Confirmation Dialog */}
      <ConfirmationDialog
        open={actionConfirmation.open}
        title={
          actionConfirmation.action === "send_nov"
            ? "Send Notice of Violation"
            : actionConfirmation.action === "send_noo"
            ? "Send Notice of Order"
            : actionConfirmation.action === "mark_compliant"
            ? "Mark as Compliant"
            : "Confirm Action"
        }
        message={
          actionConfirmation.message || (
            <div>
              <p className="mb-2">
                {actionConfirmation.action === "send_nov"
                  ? `Are you sure you want to send Notice of Violation for inspection ${actionConfirmation.inspection?.code}?`
                  : actionConfirmation.action === "send_noo"
                  ? `Are you sure you want to send Notice of Order for inspection ${actionConfirmation.inspection?.code}?`
                  : "Are you sure you want to proceed with this action?"}
              </p>
              <p className="text-sm text-gray-600">
                {actionConfirmation.action === "send_nov"
                  ? "This will send a Notice of Violation to the establishment with a 30-day compliance deadline."
                  : actionConfirmation.action === "send_noo"
                  ? "This will send a Notice of Order to the establishment with a 60-day compliance deadline."
                  : ""}
              </p>
            </div>
          )
        }
        confirmText={
          actionConfirmation.action === "send_nov"
            ? "Send NOV"
            : actionConfirmation.action === "send_noo"
            ? "Send NOO"
            : "Confirm"
        }
        cancelText="Cancel"
        confirmColor="red"
        size="md"
        loading={loading}
        onCancel={() =>
          setActionConfirmation({ open: false, inspection: null, action: null })
        }
        onConfirm={executeAction}
      />
    </LayoutForm>
  );
}
