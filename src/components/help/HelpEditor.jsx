import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Save,
  Plus,
  Trash2,
  Edit,
  ChevronUp,
  ChevronDown,
  X,
  Search,
  Download,
  Upload,
  AlertCircle,
  CheckCircle,
  FileText,
  Tag,
  Users,
  Info,
  Image as ImageIcon,
  ChevronDown as ChevronDownIcon,
} from "lucide-react";
import {
  getHelpTopics,
  getHelpCategories,
  saveHelpTopics,
  saveHelpCategories,
  exportHelpData,
  importHelpData,
  uploadHelpImage,
} from "../../services/helpApi";
import { API_BASE_URL } from "../../config/api";
import { helpCategories as defaultCategories } from "../../data/helpCategories";
import { USER_LEVELS } from "../../constants/helpConstants";
import ConfirmationDialog from "../common/ConfirmationDialog";
import { useNotifications } from "../../hooks/useNotifications";
import ImageLightbox from "../inspection-form/ImageLightbox";

// Helper function to convert relative media URLs to absolute URLs
const getImageUrl = (url) => {
  if (!url) return "";
  // If already an absolute URL (starts with http:// or https://), return as is
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  // If it's a relative URL starting with /media/, construct full URL
  if (url.startsWith("/media/")) {
    // Extract base URL from API_BASE_URL (remove /api/ if present)
    const baseUrl = API_BASE_URL.replace(/\/api\/?$/, "").replace(/\/$/, "");
    return `${baseUrl}${url}`;
  }
  // Return as is for other cases
  return url;
};

/**
 * Generate a new topic ID in format "topic-XXX"
 * @param {Array} existingTopics - Array of existing topics
 * @returns {string} - New topic ID
 */
const generateTopicId = (existingTopics) => {
  // Get all existing topic IDs (filter out null/undefined)
  const existingIds = existingTopics
    .map((t) => t.id)
    .filter(
      (id) => id != null && typeof id === "string" && id.startsWith("topic-")
    )
    .map((id) => {
      // Extract numeric part from "topic-XXX"
      const match = id.match(/topic-(\d+)/);
      return match ? parseInt(match[1], 10) : 0;
    });

  // Find the highest number and increment, start from 100 if no existing topics
  const maxNum = existingIds.length > 0 ? Math.max(...existingIds) : 99;
  return `topic-${maxNum + 1}`;
};

/**
 * Clean and fix topic IDs - generates IDs for topics with null/undefined IDs and fixes duplicates
 * @param {Array} topics - Array of topics to clean
 * @returns {Array} - Topics with valid, unique IDs
 */
const cleanTopicIds = (topics) => {
  if (!Array.isArray(topics)) return [];

  // First pass: fix null/invalid IDs
  let cleanedTopics = topics.map((topic) => {
    // If topic has null, undefined, or invalid ID, generate a new one
    if (
      !topic.id ||
      topic.id === null ||
      (typeof topic.id === "string" && !topic.id.startsWith("topic-"))
    ) {
      // Generate ID based on existing valid topics
      const validTopics = topics.filter(
        (t) => t.id && typeof t.id === "string" && t.id.startsWith("topic-")
      );
      const newId = generateTopicId(validTopics);
      return { ...topic, id: newId };
    }
    return topic;
  });

  // Second pass: fix duplicate IDs
  const seenIds = new Set();
  const idCounts = new Map();

  // Count occurrences of each ID
  cleanedTopics.forEach((topic) => {
    if (topic.id) {
      idCounts.set(topic.id, (idCounts.get(topic.id) || 0) + 1);
    }
  });

  // Fix duplicates - keep first occurrence, regenerate IDs for duplicates
  cleanedTopics = cleanedTopics.map((topic) => {
    if (!topic.id) return topic;

    // If this ID appears more than once and we've seen it before, generate a new unique ID
    if (idCounts.get(topic.id) > 1 && seenIds.has(topic.id)) {
      // Get all existing valid IDs to generate a new unique one
      const allValidIds = Array.from(seenIds).filter(
        (id) => typeof id === "string" && id.startsWith("topic-")
      );
      const existingTopics = cleanedTopics.filter(
        (t) => t.id && allValidIds.includes(t.id)
      );
      const newId = generateTopicId(existingTopics);
      idCounts.set(topic.id, idCounts.get(topic.id) - 1); // Decrement count for old ID
      idCounts.set(newId, 1); // Add new ID
      seenIds.add(newId);
      return { ...topic, id: newId };
    }

    seenIds.add(topic.id);
    return topic;
  });

  return cleanedTopics;
};

/**
 * Create a shallow copy of an object (more efficient than deep clone for simple objects)
 * @param {Object} obj - Object to copy
 * @returns {Object} - Shallow copy
 */
const shallowCopy = (obj) => {
  if (obj === null || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return [...obj];
  return { ...obj };
};

/**
 * Check if an image value is a File object (pending upload) or URL string (already uploaded)
 * @param {File|string} image - Image value to check
 * @returns {boolean} - True if File object, false if URL string
 */
const isFileObject = (image) => {
  return image instanceof File;
};

/**
 * Get preview URL for an image (File object or URL string)
 * @param {File|string} image - Image value (File object or URL string)
 * @param {Map} filePreviewCache - Map to cache File -> object URL mappings
 * @returns {string} - Preview URL
 */
const getImagePreviewUrl = (image, filePreviewCache) => {
  if (!image) return "";
  if (isFileObject(image)) {
    // Check if we already have a cached preview URL for this File
    if (filePreviewCache && filePreviewCache.has(image)) {
      return filePreviewCache.get(image);
    }
    // Create new object URL and cache it
    const objectUrl = URL.createObjectURL(image);
    if (filePreviewCache) {
      filePreviewCache.set(image, objectUrl);
    }
    return objectUrl;
  }
  // For URL strings, use existing helper
  return getImageUrl(image);
};

export default function HelpEditor() {
  const [topics, setTopics] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("topics");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImageIndex, setLightboxImageIndex] = useState(0);
  const [lightboxImages, setLightboxImages] = useState([]);
  const notifications = useNotifications();
  const searchTimeoutRef = useRef(null);

  // Cache File objects to their preview URLs (for cleanup)
  const filePreviewCacheRef = useRef(new Map());

  // Topic inline editing state
  const [isEditingTopic, setIsEditingTopic] = useState(false);
  const [editingTopicData, setEditingTopicData] = useState(null); // Topic being edited inline
  const [isNewTopic, setIsNewTopic] = useState(false); // Track if adding new vs editing existing
  const [topicInlineErrors, setTopicInlineErrors] = useState({});

  // Category inline editing state
  const [selectedCategoryKey, setSelectedCategoryKey] = useState(null);
  const [isEditingCategory, setIsEditingCategory] = useState(false);
  const [editingCategoryData, setEditingCategoryData] = useState(null); // Store category being edited inline
  const [editingCategoryOriginalKey, setEditingCategoryOriginalKey] =
    useState(null); // Track original key for editing
  const [categoryInlineErrors, setCategoryInlineErrors] = useState({});

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    type: null, // 'deleteTopic', 'deleteCategory', 'import', 'export', 'cancelTopic', 'cancelCategory', 'saveTopic', 'saveCategory'
    title: "",
    message: "",
    onConfirm: null,
    data: null,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [topicsData, categoriesData] = await Promise.all([
        getHelpTopics(),
        getHelpCategories(),
      ]);

      // Clean up topics with null/invalid IDs and fix duplicates
      const cleanedTopics = cleanTopicIds(topicsData || []);

      // Filter out empty/untitled topics (topics with no title or only whitespace)
      const validTopics = cleanedTopics.filter(
        (topic) => topic.title && topic.title.trim().length > 0
      );

      // Validate and fix category references
      const validCategoryKeys = new Set(
        (categoriesData || []).map((c) => c.key)
      );
      const fixedTopics = validTopics.map((topic) => {
        // If category doesn't exist, set to empty string (will be validated on save)
        if (topic.category && !validCategoryKeys.has(topic.category)) {
          return { ...topic, category: "" };
        }
        return topic;
      });

      // Check if data was cleaned (duplicates fixed or untitled topics removed)
      const wasCleaned =
        cleanedTopics.length !== (topicsData || []).length ||
        validTopics.length !== cleanedTopics.length ||
        JSON.stringify(fixedTopics) !== JSON.stringify(topicsData || []);

      // If data was cleaned, save it back to the server
      if (wasCleaned) {
        try {
          await saveHelpTopics(fixedTopics);
          notifications.success(
            "Help data cleaned: duplicate IDs fixed and untitled topics removed."
          );
        } catch (saveError) {
          console.error("Error saving cleaned data:", saveError);
          notifications.warning(
            "Data was cleaned but couldn't be saved. Please save manually."
          );
        }
      }

      setTopics(fixedTopics);
      setCategories(categoriesData || []);
    } catch (err) {
      console.error("Error loading help data:", err);
      notifications.error("Failed to load help data. Using defaults.");
      // Fallback to default data
      setCategories(defaultCategories || []);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // notifications is stable and doesn't need to be in deps

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      // Revoke all object URLs when component unmounts
      filePreviewCacheRef.current.forEach((url) => {
        try {
          URL.revokeObjectURL(url);
        } catch (e) {
          console.warn("Error revoking object URL:", e);
        }
      });
      filePreviewCacheRef.current.clear();
    };
  }, []);

  // Clear edit state when switching tabs
  useEffect(() => {
    if (activeTab !== "categories") {
      setIsEditingCategory(false);
      setEditingCategoryData(null);
      setEditingCategoryOriginalKey(null);
      setCategoryInlineErrors({});
    }
    if (activeTab !== "topics") {
      // Cleanup object URLs when switching away from topics tab
      filePreviewCacheRef.current.forEach((url) => {
        try {
          URL.revokeObjectURL(url);
        } catch (e) {
          console.warn("Error revoking object URL:", e);
        }
      });
      filePreviewCacheRef.current.clear();

      setIsEditingTopic(false);
      setEditingTopicData(null);
      setIsNewTopic(false);
      setTopicInlineErrors({});
    }
  }, [activeTab]);

  const handleExport = async () => {
    const filename = `help_backup_${
      new Date().toISOString().split("T")[0]
    }.zip`;

    // Show confirmation dialog
    setConfirmDialog({
      open: true,
      type: "export",
      title: "Export Help Data",
      message: (
        <div>
          <p>
            Export all help topics, categories, and images to a backup file?
          </p>
          <p className="mt-2 text-sm text-gray-600">
            You will be able to choose where to save the file.
          </p>
        </div>
      ),
      onConfirm: async () => {
        try {
          const blob = await exportHelpData(); // Returns ZIP blob

          // Try to use File System Access API (modern browsers)
          if ("showSaveFilePicker" in window) {
            try {
              const fileHandle = await window.showSaveFilePicker({
                suggestedName: filename,
                types: [
                  {
                    description: "ZIP files",
                    accept: {
                      "application/zip": [".zip"],
                    },
                  },
                ],
              });

              const writable = await fileHandle.createWritable();
              await writable.write(blob);
              await writable.close();

              notifications.success(
                `Help data exported successfully! File saved.`
              );
              setConfirmDialog({ ...confirmDialog, open: false });
              return;
            } catch (error) {
              // User cancelled or error occurred, fall back to download method
              if (error.name !== "AbortError") {
                console.warn(
                  "File System Access API failed, falling back to download:",
                  error
                );
              } else {
                // User cancelled
                setConfirmDialog({ ...confirmDialog, open: false });
                return;
              }
            }
          }

          // Fallback: Use download method (will save to default download location)
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          // Trigger click which should show save dialog in most browsers
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);

          notifications.success(
            `Help data exported successfully! File: ${filename}`
          );
          setConfirmDialog({ ...confirmDialog, open: false });
        } catch (error) {
          notifications.error(error.message || "Failed to export help data.");
          setConfirmDialog({ ...confirmDialog, open: false });
        }
      },
      data: null,
    });
  };

  const handleImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const fileInput = event.target; // Store reference for reset

    try {
      // Check if it's a ZIP file
      if (file.name.endsWith(".zip")) {
        // Import ZIP file (with images)
        try {
          const result = await importHelpData(file);

          setConfirmDialog({
            open: true,
            type: "import",
            title: "Import Help Data",
            message: (
              <div>
                <p>
                  This will replace all current help topics, categories, and
                  images with the imported data.
                </p>
                <p className="mt-2 text-sm text-amber-600 font-medium">
                  ⚠️ This action cannot be undone. Make sure you have a backup
                  before proceeding.
                </p>
                <div className="mt-3 p-2 bg-gray-50 rounded text-sm">
                  <p>
                    <strong>Topics:</strong> {result.topics_imported || 0}
                  </p>
                  <p>
                    <strong>Categories:</strong>{" "}
                    {result.categories_imported || 0}
                  </p>
                  <p>
                    <strong>Images:</strong> {result.images_imported || 0}
                  </p>
                </div>
              </div>
            ),
            onConfirm: async () => {
              try {
                // Reload data from server
                await loadData();
                setSelectedTopicId(null);
                setConfirmDialog({ ...confirmDialog, open: false });
                notifications.success(
                  `Help data imported successfully! ${result.topics_imported} topics, ${result.categories_imported} categories, ${result.images_imported} images.`
                );
                // Reset file input
                fileInput.value = "";
              } catch (error) {
                notifications.error("Failed to reload data after import.");
                console.error("Reload error:", error);
              }
            },
            data: result,
          });
        } catch (error) {
          notifications.error(
            error.message || "Failed to import help data. Invalid ZIP file."
          );
          console.error("Import error:", error);
          // Reset file input
          fileInput.value = "";
        }
      } else {
        // Import JSON file (backward compatibility)
        const text = await file.text();
        const data = JSON.parse(text);

        if (!data.topics || !data.categories) {
          throw new Error("Invalid backup file format");
        }

        setConfirmDialog({
          open: true,
          type: "import",
          title: "Import Help Data",
          message: (
            <div>
              <p>
                This will replace all current help topics and categories with
                the imported data.
              </p>
              <p className="mt-2 text-sm text-amber-600 font-medium">
                ⚠️ This action cannot be undone. Make sure you have a backup
                before proceeding.
              </p>
              <p className="mt-2 text-sm text-amber-600">
                Note: Images are not included in JSON files. Use ZIP format to
                import with images.
              </p>
              <div className="mt-3 p-2 bg-gray-50 rounded text-sm">
                <p>
                  <strong>Topics:</strong> {data.topics?.length || 0}
                </p>
                <p>
                  <strong>Categories:</strong> {data.categories?.length || 0}
                </p>
              </div>
            </div>
          ),
          onConfirm: async () => {
            try {
              await importHelpData(data);
              // Reload data from server
              await loadData();
              setSelectedTopicId(null);
              setConfirmDialog({ ...confirmDialog, open: false });
              notifications.success("Help data imported successfully!");
              // Reset file input
              fileInput.value = "";
            } catch (error) {
              notifications.error(
                error.message || "Failed to import help data."
              );
              console.error("Import error:", error);
            }
          },
          data: data,
        });
      }
    } catch (err) {
      notifications.error("Failed to import help data. Invalid file format.");
      console.error("Import error:", err);
      // Reset file input
      fileInput.value = "";
    }
  };

  // Constants
  const MAX_TITLE_LENGTH = 200;
  const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB
  const ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
  ];

  // Debounce search query
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery]);

  // Track unsaved changes
  useEffect(() => {
    if (isEditingTopic && editingTopicData) {
      setHasUnsavedChanges(true);
    } else if (isEditingCategory && editingCategoryData) {
      setHasUnsavedChanges(true);
    } else {
      setHasUnsavedChanges(false);
    }
  }, [
    isEditingTopic,
    editingTopicData,
    isEditingCategory,
    editingCategoryData,
  ]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+S or Cmd+S to save
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (isEditingTopic && editingTopicData) {
          handleSaveTopicInline();
        } else if (isEditingCategory && editingCategoryData) {
          handleSaveCategoryInline();
        }
      }
      // Escape to cancel
      if (e.key === "Escape") {
        if (isEditingTopic) {
          handleCancelTopicInline();
        } else if (isEditingCategory) {
          handleCancelCategoryInline();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isEditingTopic,
    editingTopicData,
    isEditingCategory,
    editingCategoryData,
  ]);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [hasUnsavedChanges]);

  // Topic management
  const addTopic = () => {
    // Generate proper topic ID
    const newId = generateTopicId(topics);

    // Get default category (first available or empty string)
    const defaultCategory = categories.length > 0 ? categories[0].key : "";

    const newTopic = {
      id: newId,
      title: "",
      description: "",
      category: defaultCategory,
      tags: [],
      access: [],
      steps: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // Add to topics list first
    const updatedTopics = [...topics, newTopic];
    setTopics(updatedTopics);
    // Select it and enter edit mode
    setSelectedTopicId(newTopic.id);
    // Use shallow copy for better performance (topic structure is simple)
    setEditingTopicData(shallowCopy(newTopic));
    setIsNewTopic(true);
    setIsEditingTopic(true);
    setTopicInlineErrors({});
  };

  // Open edit for existing topic
  const openEditTopic = (topic) => {
    setSelectedTopicId(topic.id);
    // Use structured clone for nested objects (steps array contains objects)
    // structuredClone is available in modern browsers, fallback to JSON method
    if (typeof structuredClone !== "undefined") {
      setEditingTopicData(structuredClone(topic));
    } else {
      setEditingTopicData(JSON.parse(JSON.stringify(topic)));
    }
    setIsNewTopic(false);
    setIsEditingTopic(true);
    setTopicInlineErrors({});
  };

  // Validate topic form
  const validateTopic = (topicData) => {
    const errors = {};

    if (!topicData.title || !topicData.title.trim()) {
      errors.title = "Topic title is required";
    } else if (topicData.title.length > MAX_TITLE_LENGTH) {
      errors.title = `Title must be less than ${MAX_TITLE_LENGTH} characters`;
    }

    // Category is required and must be valid
    if (!topicData.category || !topicData.category.trim()) {
      errors.category = "Please select a category";
    } else if (!categories.find((c) => c.key === topicData.category)) {
      errors.category = "Please select a valid category";
    }

    // Validate steps
    if (topicData.steps && Array.isArray(topicData.steps)) {
      topicData.steps.forEach((step, index) => {
        if (step.title && step.title.length > MAX_TITLE_LENGTH) {
          errors[
            `step_${index}_title`
          ] = `Step title must be less than ${MAX_TITLE_LENGTH} characters`;
        }
      });
    }

    return errors;
  };

  // Handle topic inline save
  const handleSaveTopicInline = async () => {
    if (!editingTopicData) return;

    const errors = validateTopic(editingTopicData);
    if (Object.keys(errors).length > 0) {
      setTopicInlineErrors(errors);
      return;
    }

    // Count pending image uploads (File objects)
    const pendingImages =
      editingTopicData?.steps?.filter((step) => isFileObject(step.image))
        .length || 0;

    // Show confirmation dialog before saving
    setConfirmDialog({
      open: true,
      type: "saveTopic",
      title: isNewTopic ? "Create Topic?" : "Save Changes?",
      message: (
        <div>
          <p>
            {isNewTopic
              ? "Are you sure you want to create this new topic?"
              : "Are you sure you want to save changes to this topic?"}
          </p>
          <p className="mt-2 text-sm text-gray-600">
            Topic:{" "}
            <span className="font-semibold">
              "{editingTopicData.title || "Untitled"}"
            </span>
          </p>
          {pendingImages > 0 && (
            <p className="mt-2 text-sm text-sky-600">
              📤 {pendingImages} image{pendingImages !== 1 ? "s" : ""} will be
              uploaded.
            </p>
          )}
        </div>
      ),
      onConfirm: async () => {
        try {
          setSaving(true);

          // Step 1: Upload all File objects first
          const stepsWithFiles = (editingTopicData.steps || [])
            .map((step, index) => ({
              step,
              index,
              isFile: isFileObject(step.image),
            }))
            .filter((item) => item.isFile);

          if (stepsWithFiles.length > 0) {
            notifications.info(
              `Uploading ${stepsWithFiles.length} image${
                stepsWithFiles.length !== 1 ? "s" : ""
              }...`
            );

            // Upload all images in parallel
            const uploadResults = await Promise.all(
              stepsWithFiles.map(async ({ step, index }) => {
                try {
                  const result = await uploadHelpImage(step.image);
                  return { index, url: result.url, file: step.image };
                } catch (error) {
                  console.error(
                    `Failed to upload image for step ${index + 1}:`,
                    error
                  );
                  throw new Error(
                    `Failed to upload image for step ${index + 1}: ${
                      error.message
                    }`
                  );
                }
              })
            );

            // Step 2: Replace File objects with uploaded URLs
            const updatedSteps = [...(editingTopicData.steps || [])];
            uploadResults.forEach(({ index, url, file }) => {
              updatedSteps[index] = { ...updatedSteps[index], image: url };

              // Clean up object URL after successful upload
              const previewUrl = filePreviewCacheRef.current.get(file);
              if (previewUrl) {
                try {
                  URL.revokeObjectURL(previewUrl);
                } catch (e) {
                  console.warn("Error revoking object URL:", e);
                }
                filePreviewCacheRef.current.delete(file);
              }
            });

            // Update editingTopicData with uploaded URLs
            editingTopicData.steps = updatedSteps;
          }

          // Step 3: Prepare the topic data with updated timestamp
          const topicToSave = {
            ...editingTopicData,
            updated_at: new Date().toISOString(),
          };

          // Step 4: Save the updated topics list
          let updatedTopicsList;
          if (isNewTopic) {
            // Add new topic to the list
            updatedTopicsList = [...topics, topicToSave];
          } else {
            // Update existing topic
            updatedTopicsList = topics.map((t) =>
              t.id === editingTopicData.id ? topicToSave : t
            );
          }

          await Promise.all([
            saveHelpTopics(updatedTopicsList),
            saveHelpCategories(categories),
          ]);

          // Reload data from server to get renamed image URLs (server auto-renames images)
          // This ensures we have the correct URLs after server-side renaming
          await loadData();

          // Update selection to the saved topic (after reload to ensure topic exists)
          setSelectedTopicId(topicToSave.id);

          // Exit edit mode and go to Topic Viewer
          setIsEditingTopic(false);
          setEditingTopicData(null);
          setIsNewTopic(false);
          setTopicInlineErrors({});
          setHasUnsavedChanges(false);

          setConfirmDialog({ ...confirmDialog, open: false });
          notifications.success(
            isNewTopic
              ? "Topic created successfully!"
              : "Topic updated successfully!"
          );
        } catch (error) {
          notifications.error(error.message || "Failed to save topic.");
        } finally {
          setSaving(false);
        }
      },
      data: null,
    });
  };

  // Handle topic inline cancel
  const handleCancelTopicInline = () => {
    // Helper to clean up File objects and their object URLs
    const cleanupFileObjects = () => {
      if (!editingTopicData || !editingTopicData.steps) return;

      // Find all File objects in steps
      const fileObjects = editingTopicData.steps
        .map((step) => step.image)
        .filter((img) => isFileObject(img));

      // Revoke object URLs for all File objects
      fileObjects.forEach((file) => {
        const previewUrl = filePreviewCacheRef.current.get(file);
        if (previewUrl) {
          try {
            URL.revokeObjectURL(previewUrl);
          } catch (e) {
            console.warn("Error revoking object URL:", e);
          }
          filePreviewCacheRef.current.delete(file);
        }
      });
    };

    // Count pending image uploads (File objects)
    const pendingImages =
      editingTopicData?.steps?.filter((step) => isFileObject(step.image))
        .length || 0;

    // If it's a new topic, always remove it (even if empty)
    if (isNewTopic && selectedTopicId) {
      // Clean up File objects
      cleanupFileObjects();

      const updatedTopics = topics.filter((t) => t.id !== selectedTopicId);
      setTopics(updatedTopics);
      setSelectedTopicId(null);
      setIsEditingTopic(false);
      setEditingTopicData(null);
      setIsNewTopic(false);
      setTopicInlineErrors({});
      setHasUnsavedChanges(false);
      return;
    }

    // For existing topics, check for unsaved changes
    if (hasUnsavedChanges && editingTopicData) {
      const hasChanges =
        editingTopicData.title ||
        editingTopicData.description ||
        (editingTopicData.steps && editingTopicData.steps.length > 0);
      if (hasChanges) {
        // Use ConfirmationDialog instead of window.confirm
        setConfirmDialog({
          open: true,
          type: "cancelTopic",
          title: "Discard Changes?",
          message: (
            <div>
              <p>You have unsaved changes to this topic.</p>
              <p className="mt-2 text-sm text-amber-600">
                Are you sure you want to cancel? All unsaved changes will be
                lost.
              </p>
              {pendingImages > 0 && (
                <p className="mt-2 text-sm text-amber-600">
                  ⚠️ {pendingImages} selected image
                  {pendingImages !== 1 ? "s" : ""} will be discarded (not
                  uploaded).
                </p>
              )}
            </div>
          ),
          onConfirm: () => {
            // Clean up File objects
            cleanupFileObjects();

            setIsEditingTopic(false);
            setEditingTopicData(null);
            setIsNewTopic(false);
            setTopicInlineErrors({});
            setHasUnsavedChanges(false);
            setConfirmDialog({ ...confirmDialog, open: false });
          },
          data: null,
        });
        return;
      }
    }

    // No changes, just cleanup and exit
    cleanupFileObjects();
    setIsEditingTopic(false);
    setEditingTopicData(null);
    setIsNewTopic(false);
    setTopicInlineErrors({});
    setHasUnsavedChanges(false);
  };

  // Update editingTopicData when topic changes inline
  const updateEditingTopicData = (updates) => {
    setEditingTopicData((prev) => ({
      ...prev,
      ...updates,
    }));
    // Clear errors when user types
    if (topicInlineErrors.title && updates.title) {
      setTopicInlineErrors((prev) => ({ ...prev, title: "" }));
    }
    if (topicInlineErrors.category && updates.category) {
      setTopicInlineErrors((prev) => ({ ...prev, category: "" }));
    }
    // Mark as having unsaved changes
    setHasUnsavedChanges(true);
  };

  const deleteTopic = (id) => {
    const topic = topics.find((t) => t.id === id);
    setConfirmDialog({
      open: true,
      type: "deleteTopic",
      title: "Delete Topic",
      message: (
        <div>
          Are you sure you want to delete the topic{" "}
          <span className="font-semibold">"{topic?.title || "Untitled"}"</span>?
          <p className="mt-2 text-sm text-amber-600">
            This action cannot be undone. All steps and images associated with
            this topic will be lost.
          </p>
        </div>
      ),
      onConfirm: async () => {
        try {
          setSaving(true);
          const updatedTopics = topics.filter((topic) => topic.id !== id);

          // Save to backend
          await saveHelpTopics(updatedTopics);

          // Reload data from server to ensure consistency
          await loadData();

          // Clear selection if deleted topic was selected
          if (selectedTopicId === id) {
            setSelectedTopicId(null);
            setIsEditingTopic(false);
            setEditingTopicData(null);
            setIsNewTopic(false);
            setTopicInlineErrors({});
          }

          setConfirmDialog({ ...confirmDialog, open: false });
          notifications.success("Topic deleted successfully");
        } catch (error) {
          notifications.error(error.message || "Failed to delete topic.");
        } finally {
          setSaving(false);
        }
      },
      data: { id },
    });
  };

  const moveTopic = (index, direction) => {
    if (
      (direction === "up" && index === 0) ||
      (direction === "down" && index === topics.length - 1)
    )
      return;

    const newTopics = [...topics];
    const newIndex = direction === "up" ? index - 1 : index + 1;
    [newTopics[index], newTopics[newIndex]] = [
      newTopics[newIndex],
      newTopics[index],
    ];
    setTopics(newTopics);
  };

  // Category management
  const addCategory = () => {
    const tempKey = `temp-${Date.now()}`;
    const newCategory = {
      key: tempKey,
      name: "",
    };
    // Add to categories list first
    const updatedCategories = [...categories, newCategory];
    setCategories(updatedCategories);
    // Select it and enter edit mode
    setSelectedCategoryKey(tempKey);
    setEditingCategoryData({ ...newCategory });
    setEditingCategoryOriginalKey(null); // New category, no original key
    setIsEditingCategory(true);
    setCategoryInlineErrors({});
  };

  // Generate category key from name
  const generateCategoryKey = (name) => {
    return name
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
  };

  // Validate category data
  const validateCategory = (categoryData) => {
    const errors = {};

    if (!categoryData.name || !categoryData.name.trim()) {
      errors.name = "Category name is required";
    }

    if (!categoryData.key || !categoryData.key.trim()) {
      errors.key = "Category key is required";
    } else {
      // Validate key format
      if (!/^[a-z0-9-]+$/.test(categoryData.key)) {
        errors.key =
          "Key must contain only lowercase letters, numbers, and hyphens";
      }

      // Check for duplicate key (excluding current category if editing)
      const existingCategory = categories.find(
        (c) => c.key === categoryData.key
      );
      if (
        existingCategory &&
        (!editingCategoryOriginalKey ||
          categoryData.key !== editingCategoryOriginalKey)
      ) {
        errors.key = "This key is already in use";
      }
    }

    return errors;
  };

  // Handle category inline save
  const handleSaveCategoryInline = async () => {
    if (!editingCategoryData) return;

    const errors = validateCategory(editingCategoryData);
    if (Object.keys(errors).length > 0) {
      setCategoryInlineErrors(errors);
      return;
    }

    // Show confirmation dialog before saving
    const isNewCategory = !editingCategoryOriginalKey;
    const oldKey = editingCategoryOriginalKey;
    const newKey = editingCategoryData.key;
    const keyChanged = oldKey && oldKey !== newKey;
    // Calculate topic count directly (function defined before memoization, but performance impact is minimal)
    const topicCount = oldKey
      ? topics.filter((t) => t.category === oldKey).length
      : 0;

    setConfirmDialog({
      open: true,
      type: "saveCategory",
      title: isNewCategory ? "Create Category?" : "Save Changes?",
      message: (
        <div>
          <p>
            {isNewCategory
              ? "Are you sure you want to create this new category?"
              : "Are you sure you want to save changes to this category?"}
          </p>
          <p className="mt-2 text-sm text-gray-600">
            Category:{" "}
            <span className="font-semibold">
              "{editingCategoryData.name || "Unnamed"}"
            </span>
          </p>
          {keyChanged && topicCount > 0 && (
            <p className="mt-2 text-sm text-amber-600">
              ⚠️ This category key is changing from "{oldKey}" to "{newKey}".
              {topicCount} topic{topicCount !== 1 ? "s" : ""} will be updated.
            </p>
          )}
        </div>
      ),
      onConfirm: async () => {
        try {
          setSaving(true);

          // Check if editing existing category (has original key)
          if (editingCategoryOriginalKey) {
            // Update existing category
            const oldKey = editingCategoryOriginalKey;
            const newKey = editingCategoryData.key;

            if (oldKey !== newKey) {
              // Update key in all topics that use this category
              const updatedTopics = topics.map((topic) =>
                topic.category === oldKey
                  ? { ...topic, category: newKey }
                  : topic
              );
              setTopics(updatedTopics);
            }

            const updatedCategories = categories.map((cat) =>
              cat.key === oldKey ? { ...editingCategoryData } : cat
            );
            setCategories(updatedCategories);
            setSelectedCategoryKey(newKey); // Update selected key if it changed

            // Save to backend
            await Promise.all([
              saveHelpTopics(topics),
              saveHelpCategories(updatedCategories),
            ]);
          } else {
            // This is a new category - find it by the selected key and replace it
            const updatedCategories = categories.map((cat) => {
              if (cat.key === selectedCategoryKey) {
                return { ...editingCategoryData };
              }
              return cat;
            });
            setCategories(updatedCategories);
            setSelectedCategoryKey(editingCategoryData.key);

            // Save to backend
            await Promise.all([
              saveHelpTopics(topics),
              saveHelpCategories(updatedCategories),
            ]);
          }

          // Reload data from server to ensure consistency
          await loadData();

          // Update selection to the saved category
          setSelectedCategoryKey(editingCategoryData.key);

          // Exit edit mode and go to Category Viewer
          setIsEditingCategory(false);
          setEditingCategoryData(null);
          setEditingCategoryOriginalKey(null);
          setCategoryInlineErrors({});
          setHasUnsavedChanges(false);

          setConfirmDialog({ ...confirmDialog, open: false });
          notifications.success("Category saved successfully!");
        } catch (error) {
          notifications.error(error.message || "Failed to save category.");
        } finally {
          setSaving(false);
        }
      },
      data: null,
    });
  };

  // Handle category inline cancel
  const handleCancelCategoryInline = () => {
    // If it's a new category, always remove it
    if (!editingCategoryOriginalKey && selectedCategoryKey) {
      const updatedCategories = categories.filter(
        (cat) => cat.key !== selectedCategoryKey
      );
      setCategories(updatedCategories);
      setSelectedCategoryKey(null);
      setIsEditingCategory(false);
      setEditingCategoryData(null);
      setEditingCategoryOriginalKey(null);
      setCategoryInlineErrors({});
      setHasUnsavedChanges(false);
      return;
    }

    // For existing categories, check for unsaved changes
    if (hasUnsavedChanges && editingCategoryData) {
      const hasChanges = editingCategoryData.name || editingCategoryData.key;
      if (hasChanges) {
        // Use ConfirmationDialog instead of window.confirm
        setConfirmDialog({
          open: true,
          type: "cancelCategory",
          title: "Discard Changes?",
          message: (
            <div>
              <p>You have unsaved changes to this category.</p>
              <p className="mt-2 text-sm text-amber-600">
                Are you sure you want to cancel? All unsaved changes will be
                lost.
              </p>
            </div>
          ),
          onConfirm: () => {
            setIsEditingCategory(false);
            setEditingCategoryData(null);
            setEditingCategoryOriginalKey(null);
            setCategoryInlineErrors({});
            setHasUnsavedChanges(false);
            setConfirmDialog({ ...confirmDialog, open: false });
          },
          data: null,
        });
        return;
      }
    }

    setIsEditingCategory(false);
    setEditingCategoryData(null);
    setEditingCategoryOriginalKey(null);
    setCategoryInlineErrors({});
    setHasUnsavedChanges(false);
  };

  const deleteCategory = (key) => {
    const category = categories.find((c) => c.key === key);
    // Calculate topic count directly (function defined before memoization, but performance impact is minimal)
    const topicCount = topics.filter((t) => t.category === key).length;

    setConfirmDialog({
      open: true,
      type: "deleteCategory",
      title: "Delete Category",
      message: (
        <div>
          Are you sure you want to delete the category{" "}
          <span className="font-semibold">"{category?.name || key}"</span>?
          {topicCount > 0 && (
            <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-sm">
              <p className="text-amber-800 font-medium">
                ⚠️ This category is used by {topicCount} topic
                {topicCount !== 1 ? "s" : ""}
              </p>
              <p className="text-amber-700 mt-1">
                Deleting it will remove the category from those topics.
              </p>
            </div>
          )}
        </div>
      ),
      onConfirm: async () => {
        try {
          setSaving(true);
          let updatedTopics = topics;

          // Remove category from topics if needed
          if (topicCount > 0) {
            updatedTopics = topics.map((topic) =>
              topic.category === key ? { ...topic, category: "" } : topic
            );
          }

          const updatedCategories = categories.filter((cat) => cat.key !== key);

          // Save to backend
          await Promise.all([
            saveHelpTopics(updatedTopics),
            saveHelpCategories(updatedCategories),
          ]);

          // Reload data from server to ensure consistency
          await loadData();

          // Clear selection if deleted category was selected
          if (selectedCategoryKey === key) {
            setSelectedCategoryKey(null);
            setIsEditingCategory(false);
            setEditingCategoryData(null);
            setEditingCategoryOriginalKey(null);
          }

          setConfirmDialog({ ...confirmDialog, open: false });
          notifications.success("Category deleted successfully");
        } catch (error) {
          notifications.error(error.message || "Failed to delete category.");
        } finally {
          setSaving(false);
        }
      },
      data: { key },
    });
  };

  // Memoize filtered topics for performance
  const filteredTopics = useMemo(() => {
    if (!debouncedSearchQuery.trim()) {
      return topics;
    }
    const query = debouncedSearchQuery.toLowerCase();
    return topics.filter(
      (topic) =>
        topic.title?.toLowerCase().includes(query) ||
        topic.description?.toLowerCase().includes(query) ||
        topic.tags?.some((tag) => tag.toLowerCase().includes(query))
    );
  }, [topics, debouncedSearchQuery]);

  // Memoize category name lookup map for performance
  const categoryNameMap = useMemo(() => {
    const map = new Map();
    categories.forEach((cat) => {
      map.set(cat.key, cat.name);
    });
    return map;
  }, [categories]);

  // Memoize topic counts per category for performance
  const topicCountsByCategory = useMemo(() => {
    const counts = new Map();
    topics.forEach((topic) => {
      if (topic.category) {
        counts.set(topic.category, (counts.get(topic.category) || 0) + 1);
      }
    });
    return counts;
  }, [topics]);

  // Memoize filtered categories for performance
  const filteredCategories = useMemo(() => {
    if (!debouncedSearchQuery.trim()) {
      return categories;
    }
    const query = debouncedSearchQuery.toLowerCase();
    return categories.filter(
      (category) =>
        category.name?.toLowerCase().includes(query) ||
        category.key?.toLowerCase().includes(query)
    );
  }, [categories, debouncedSearchQuery]);

  // Memoize selected topic lookup for performance
  const selectedTopic = useMemo(() => {
    if (!selectedTopicId) return null;
    return topics.find((t) => t.id === selectedTopicId) || null;
  }, [topics, selectedTopicId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-600"></div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white overflow-y-auto">
      {/* Header with Title, Tabs, and Actions (Option B) */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-2">
        <h1 className="text-2xl font-bold text-sky-600">Help Editor</h1>

        <div className="flex items-center gap-3">
          {/* Tabs */}
          <div className="flex  border-b border-gray-200">
            <button
              onClick={() => setActiveTab("topics")}
              className={`relative px-3 py-1 text-sm font-semibold transition-all duration-200 ${
                activeTab === "topics"
                  ? "text-sky-600"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <span className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Topics
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                    activeTab === "topics"
                      ? "bg-sky-100 text-sky-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {topics.length}
                </span>
              </span>
              {activeTab === "topics" && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-600 rounded-t-full" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("categories")}
              className={`relative px-4 py-2 text-sm font-semibold transition-all duration-200 ${
                activeTab === "categories"
                  ? "text-sky-600"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <span className="flex items-center gap-2">
                <Tag className="w-4 h-4" />
                Categories
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                    activeTab === "categories"
                      ? "bg-sky-100 text-sky-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {categories.length}
                </span>
              </span>
              {activeTab === "categories" && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-600 rounded-t-full" />
              )}
            </button>
          </div>

          {/* Action Buttons - Import, Export */}
          <div className="flex items-center gap-2">
            <label className="group bg-white border border-gray-300 hover:border-sky-400 hover:bg-sky-50 text-gray-700 hover:text-sky-700 px-3 py-2 rounded text-sm font-semibold cursor-pointer flex items-center gap-2 transition-all duration-200 shadow-sm hover:shadow-md">
              <Upload className="w-4 h-4 group-hover:scale-110 transition-transform" />
              <span>Import</span>
              <input
                type="file"
                accept=".zip,.json"
                onChange={handleImport}
                className="hidden"
              />
            </label>
            <button
              onClick={handleExport}
              className="group bg-white border border-gray-300 hover:border-sky-400 hover:bg-sky-50 text-gray-700 hover:text-sky-700 px-3 py-2 rounded text-sm font-semibold flex items-center gap-2 transition-all duration-200 shadow-sm hover:shadow-md"
            >
              <Download className="w-4 h-4 group-hover:scale-110 transition-transform" />
              <span>Export</span>
            </button>
          </div>
        </div>
      </div>

      {/* Topics Tab */}
      {activeTab === "topics" && (
        <div className="grid grid-cols-1 lg:grid-cols-[30%_70%] gap-1">
          {/* Left Column (30%) - Topics List */}
          <div className="bg-white border border-gray-200">
            {/* Search and Actions Bar */}
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                    <input
                      type="text"
                      placeholder="Search topics..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all"
                    />
                  </div>
                </div>
              </div>
              <button
                onClick={addTopic}
                className="w-full bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add New Topic
              </button>
            </div>

            {/* Topics List */}
            <div
              className="overflow-y-auto"
              style={{ maxHeight: "calc(100vh - 350px)" }}
            >
              {filteredTopics.length === 0 ? (
                <div className="p-12 text-center text-gray-500">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p className="text-sm">
                    {searchQuery ? "No topics found" : "No topics yet"}
                  </p>
                  {!searchQuery && (
                    <button
                      onClick={addTopic}
                      className="mt-4 bg-sky-600 text-white px-4 py-2 rounded text-sm font-medium"
                    >
                      Create First Topic
                    </button>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {filteredTopics.map((topic) => (
                    <div
                      key={topic.id}
                      onClick={() => setSelectedTopicId(topic.id)}
                      className={`p-4 cursor-pointer transition-all ${
                        selectedTopicId === topic.id
                          ? "bg-sky-50 border-l-4 border-l-sky-500 shadow-sm"
                          : "hover:bg-gray-50 border-l-4 border-l-transparent"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <h3
                            className={`font-semibold text-sm mb-1.5 truncate ${
                              selectedTopicId === topic.id
                                ? "text-sky-900"
                                : "text-gray-900"
                            }`}
                          >
                            {topic.title || "Untitled Topic"}
                          </h3>
                          <p className="text-xs text-gray-600 line-clamp-2 mb-2.5 leading-relaxed">
                            {topic.description || "No description"}
                          </p>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-md">
                              {categoryNameMap.get(topic.category) ||
                                topic.category ||
                                "Uncategorized"}
                            </span>
                            {topic.steps?.length > 0 && (
                              <span className="inline-flex items-center text-xs text-gray-500">
                                <FileText className="w-3 h-3 mr-1" />
                                {topic.steps.length} step
                                {topic.steps.length !== 1 ? "s" : ""}
                              </span>
                            )}
                            {topic.access && topic.access.length > 0 && (
                              <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-sky-100 text-sky-700 rounded-md">
                                🔒 Restricted
                              </span>
                            )}
                          </div>
                        </div>
                        <div
                          className="flex items-center gap-0.5 flex-shrink-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              moveTopic(
                                topics.findIndex((t) => t.id === topic.id),
                                "up"
                              );
                            }}
                            disabled={
                              topics.findIndex((t) => t.id === topic.id) === 0
                            }
                            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title="Move up"
                          >
                            <ChevronUp className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              moveTopic(
                                topics.findIndex((t) => t.id === topic.id),
                                "down"
                              );
                            }}
                            disabled={
                              topics.findIndex((t) => t.id === topic.id) ===
                              topics.length - 1
                            }
                            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title="Move down"
                          >
                            <ChevronDown className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteTopic(topic.id);
                            }}
                            className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                            title="Delete topic"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column (70%) - Topic Viewer/Editor */}
          <div className="bg-white border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  {isEditingTopic ? (
                    <span className="flex items-center gap-2">
                      Edit Topic
                      {hasUnsavedChanges && (
                        <span className="text-xs text-amber-600 font-normal flex items-center gap-1">
                          <span className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></span>
                          Unsaved changes
                        </span>
                      )}
                    </span>
                  ) : (
                    "Topic Viewer"
                  )}
                </h3>
              </div>
            </div>
            {selectedTopicId || (isEditingTopic && editingTopicData) ? (
              (() => {
                // If in edit mode with editingTopicData, use it directly (handles new topics)
                if (isEditingTopic && editingTopicData) {
                  return (
                    <div
                      className="p-5 overflow-y-auto"
                      style={{ maxHeight: "calc(100vh - 300px)" }}
                    >
                      {/* Edit Mode */}
                      <div className="space-y-5">
                        {/* Title */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Topic Title <span className="text-red-500">*</span>
                          </label>
                          <input
                            type="text"
                            value={editingTopicData?.title || ""}
                            onChange={(e) =>
                              updateEditingTopicData({ title: e.target.value })
                            }
                            placeholder="Enter topic title..."
                            className={`w-full text-sm border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all ${
                              topicInlineErrors.title
                                ? "border-red-300 bg-red-50"
                                : "border-gray-300"
                            }`}
                            autoFocus
                          />
                          {topicInlineErrors.title && (
                            <p className="mt-1 text-xs text-red-600">
                              {topicInlineErrors.title}
                            </p>
                          )}
                        </div>

                        {/* Description */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Description
                          </label>
                          <textarea
                            value={editingTopicData.description || ""}
                            onChange={(e) =>
                              updateEditingTopicData({
                                description: e.target.value,
                              })
                            }
                            placeholder="Enter a brief description of this help topic..."
                            className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all resize-none"
                            rows={3}
                          />
                        </div>

                        {/* Category and Tags */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                              Category
                            </label>
                            <select
                              value={editingTopicData.category || ""}
                              onChange={(e) =>
                                updateEditingTopicData({
                                  category: e.target.value,
                                })
                              }
                              className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all bg-white ${
                                topicInlineErrors.category
                                  ? "border-red-300 bg-red-50"
                                  : "border-gray-300"
                              }`}
                            >
                              {categories.map((cat) => (
                                <option key={cat.key} value={cat.key}>
                                  {cat.name}
                                </option>
                              ))}
                            </select>
                            {topicInlineErrors.category && (
                              <p className="mt-1 text-xs text-red-600">
                                {topicInlineErrors.category}
                              </p>
                            )}
                          </div>
                          <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                              Tags
                            </label>
                            <input
                              type="text"
                              value={(editingTopicData.tags || []).join(", ")}
                              onChange={(e) =>
                                updateEditingTopicData({
                                  tags: e.target.value
                                    .split(",")
                                    .map((t) => t.trim())
                                    .filter(Boolean),
                                })
                              }
                              placeholder="tag1, tag2, tag3"
                              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all"
                            />
                          </div>
                        </div>

                        {/* Access Control */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Access Control
                          </label>
                          <div className="flex flex-wrap gap-2 mb-3 min-h-[44px] p-3 border border-gray-300 rounded-lg bg-gray-50">
                            {editingTopicData.access &&
                            editingTopicData.access.length > 0 ? (
                              editingTopicData.access.map((accessRole, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium shadow-sm"
                                >
                                  {accessRole}
                                  <button
                                    type="button"
                                    onClick={() => {
                                      const newAccess =
                                        editingTopicData.access.filter(
                                          (_, i) => i !== idx
                                        );
                                      updateEditingTopicData({
                                        access: newAccess,
                                      });
                                    }}
                                    className="hover:bg-sky-200 rounded-full p-0.5 transition-colors"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                </span>
                              ))
                            ) : (
                              <span className="text-sm text-gray-500 italic flex items-center">
                                <Users className="w-4 h-4 mr-2" />
                                No restrictions (visible to all users)
                              </span>
                            )}
                          </div>
                          <select
                            value=""
                            onChange={(e) => {
                              if (e.target.value) {
                                const currentAccess =
                                  editingTopicData.access || [];
                                if (!currentAccess.includes(e.target.value)) {
                                  updateEditingTopicData({
                                    access: [...currentAccess, e.target.value],
                                  });
                                }
                                e.target.value = "";
                              }
                            }}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all bg-white"
                          >
                            <option value="">
                              + Add role to restrict access...
                            </option>
                            {USER_LEVELS.filter(
                              (level) =>
                                !(editingTopicData.access || []).includes(level)
                            ).map((level) => (
                              <option key={level} value={level}>
                                {level}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Steps */}
                        <div className="border-t border-gray-200 pt-4">
                          <div className="flex justify-between items-center mb-3">
                            <label className="block text-sm font-semibold text-gray-700">
                              Steps ({(editingTopicData.steps || []).length})
                            </label>
                            <button
                              type="button"
                              onClick={() => {
                                const newSteps = [
                                  ...(editingTopicData.steps || []),
                                  { title: "", description: "", image: "" },
                                ];
                                updateEditingTopicData({ steps: newSteps });
                              }}
                              className="text-sm text-sky-600 hover:text-sky-700 flex items-center gap-1.5 font-medium transition-colors"
                            >
                              <Plus className="w-4 h-4" />
                              Add Step
                            </button>
                          </div>
                          <div className="space-y-3 max-h-[400px] overflow-y-auto">
                            {(editingTopicData.steps || []).length === 0 ? (
                              <div className="text-center py-8 border-2 border-dashed border-gray-200 rounded-lg bg-gray-50">
                                <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                                <p className="text-sm text-gray-400">
                                  No steps added yet
                                </p>
                                <p className="text-xs text-gray-400 mt-1">
                                  Click "Add Step" to create instructions
                                </p>
                              </div>
                            ) : (
                              (editingTopicData.steps || []).map(
                                (step, stepIndex) => (
                                  <div
                                    key={stepIndex}
                                    className="border border-gray-200 rounded-lg p-4 bg-gray-50"
                                  >
                                    <div className="flex items-start gap-3 mb-3">
                                      <span className="w-8 h-8 bg-sky-100 text-sky-700 rounded-lg text-sm font-bold flex items-center justify-center flex-shrink-0 shadow-sm">
                                        {stepIndex + 1}
                                      </span>
                                      <div className="flex-1 min-w-0">
                                        <input
                                          type="text"
                                          value={step.title || ""}
                                          onChange={(e) => {
                                            const newSteps = [
                                              ...(editingTopicData.steps || []),
                                            ];
                                            newSteps[stepIndex] = {
                                              ...newSteps[stepIndex],
                                              title: e.target.value,
                                            };
                                            updateEditingTopicData({
                                              steps: newSteps,
                                            });
                                          }}
                                          placeholder="Step title..."
                                          className="w-full font-semibold border border-gray-300 rounded-lg px-3 py-2 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all"
                                        />
                                        <textarea
                                          value={step.description || ""}
                                          onChange={(e) => {
                                            const newSteps = [
                                              ...(editingTopicData.steps || []),
                                            ];
                                            newSteps[stepIndex] = {
                                              ...newSteps[stepIndex],
                                              description: e.target.value,
                                            };
                                            updateEditingTopicData({
                                              steps: newSteps,
                                            });
                                          }}
                                          placeholder="Step description..."
                                          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all resize-none"
                                          rows={3}
                                        />
                                        <div>
                                          {step.image ? (
                                            <div
                                              className="relative group rounded-lg overflow-hidden border border-gray-300 cursor-pointer"
                                              onClick={() => {
                                                // Collect all images from all steps
                                                const allImages = (
                                                  editingTopicData.steps || []
                                                )
                                                  .filter((s) => s.image)
                                                  .map((s, idx) => {
                                                    const previewUrl =
                                                      getImagePreviewUrl(
                                                        s.image,
                                                        filePreviewCacheRef.current
                                                      );
                                                    return {
                                                      url: previewUrl,
                                                      caption:
                                                        s.title ||
                                                        `Step ${idx + 1}`,
                                                      name: isFileObject(
                                                        s.image
                                                      )
                                                        ? s.image.name
                                                        : s.image
                                                            .split("/")
                                                            .pop() || "image",
                                                    };
                                                  });
                                                const currentImageIndex =
                                                  allImages.findIndex((img) => {
                                                    const stepWithImage = (
                                                      editingTopicData.steps ||
                                                      []
                                                    ).find(
                                                      (s, i) =>
                                                        s.image &&
                                                        i === stepIndex
                                                    );
                                                    if (!stepWithImage)
                                                      return false;
                                                    const currentPreviewUrl =
                                                      getImagePreviewUrl(
                                                        stepWithImage.image,
                                                        filePreviewCacheRef.current
                                                      );
                                                    return (
                                                      currentPreviewUrl ===
                                                      img.url
                                                    );
                                                  });
                                                setLightboxImages(allImages);
                                                setLightboxImageIndex(
                                                  currentImageIndex >= 0
                                                    ? currentImageIndex
                                                    : 0
                                                );
                                                setLightboxOpen(true);
                                              }}
                                            >
                                              <img
                                                src={getImagePreviewUrl(
                                                  step.image,
                                                  filePreviewCacheRef.current
                                                )}
                                                alt={step.title || "Step image"}
                                                className="w-full h-40 object-cover transition-transform group-hover:scale-105"
                                                onError={(e) => {
                                                  const img = e.target;
                                                  img.style.display = "none";
                                                  // Show error placeholder
                                                  const errorDiv =
                                                    document.createElement(
                                                      "div"
                                                    );
                                                  errorDiv.className =
                                                    "w-full h-40 bg-red-50 border border-red-200 rounded-lg flex flex-col items-center justify-center text-red-600 text-sm p-4";
                                                  const imageName =
                                                    isFileObject(step.image)
                                                      ? step.image.name
                                                      : step.image;
                                                  errorDiv.innerHTML = `
                                                    <svg class="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                    </svg>
                                                    <p class="font-medium">Failed to load image</p>
                                                    <p class="text-xs mt-1 text-center">${imageName}</p>
                                                  `;
                                                  img.parentNode.appendChild(
                                                    errorDiv
                                                  );
                                                }}
                                              />
                                              {/* Show indicator if image is pending upload */}
                                              {isFileObject(step.image) && (
                                                <div className="absolute top-2 left-2 px-2 py-1 bg-amber-500 text-white text-xs font-medium rounded shadow-sm">
                                                  Pending Upload
                                                </div>
                                              )}
                                              <div className="absolute top-2 right-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <label
                                                  className="cursor-pointer bg-white hover:bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-300 text-xs font-medium text-gray-700 shadow-sm"
                                                  onClick={(e) =>
                                                    e.stopPropagation()
                                                  }
                                                >
                                                  <input
                                                    type="file"
                                                    accept="image/*"
                                                    className="hidden"
                                                    onChange={(e) => {
                                                      const file =
                                                        e.target.files[0];
                                                      if (file) {
                                                        if (
                                                          file.size >
                                                          MAX_IMAGE_SIZE
                                                        ) {
                                                          notifications.error(
                                                            `Image size must be less than ${(
                                                              MAX_IMAGE_SIZE /
                                                              1024 /
                                                              1024
                                                            ).toFixed(0)}MB`
                                                          );
                                                          return;
                                                        }
                                                        if (
                                                          !ALLOWED_IMAGE_TYPES.includes(
                                                            file.type
                                                          )
                                                        ) {
                                                          notifications.error(
                                                            `Please select a valid image file (${ALLOWED_IMAGE_TYPES.map(
                                                              (t) =>
                                                                t
                                                                  .split("/")[1]
                                                                  .toUpperCase()
                                                            ).join(", ")})`
                                                          );
                                                          return;
                                                        }

                                                        // Store File object instead of uploading immediately
                                                        // Create preview URL and cache it
                                                        const previewUrl =
                                                          URL.createObjectURL(
                                                            file
                                                          );
                                                        filePreviewCacheRef.current.set(
                                                          file,
                                                          previewUrl
                                                        );

                                                        // Update step with File object
                                                        setEditingTopicData(
                                                          (prev) => {
                                                            const updatedSteps =
                                                              [
                                                                ...(prev?.steps ||
                                                                  []),
                                                              ];
                                                            updatedSteps[
                                                              stepIndex
                                                            ] = {
                                                              ...updatedSteps[
                                                                stepIndex
                                                              ],
                                                              image: file,
                                                            };
                                                            return {
                                                              ...prev,
                                                              steps:
                                                                updatedSteps,
                                                            };
                                                          }
                                                        );

                                                        notifications.success(
                                                          "Image selected. It will be uploaded when you save the topic."
                                                        );
                                                      }
                                                      e.target.value = "";
                                                    }}
                                                  />
                                                  Change
                                                </label>
                                                <button
                                                  type="button"
                                                  onClick={(e) => {
                                                    e.stopPropagation(); // Prevent opening lightbox

                                                    // Clean up object URL if it's a File object
                                                    if (
                                                      isFileObject(step.image)
                                                    ) {
                                                      const previewUrl =
                                                        filePreviewCacheRef.current.get(
                                                          step.image
                                                        );
                                                      if (previewUrl) {
                                                        try {
                                                          URL.revokeObjectURL(
                                                            previewUrl
                                                          );
                                                        } catch (e) {
                                                          console.warn(
                                                            "Error revoking object URL:",
                                                            e
                                                          );
                                                        }
                                                        filePreviewCacheRef.current.delete(
                                                          step.image
                                                        );
                                                      }
                                                    }

                                                    const newSteps = [
                                                      ...(editingTopicData.steps ||
                                                        []),
                                                    ];
                                                    newSteps[stepIndex] = {
                                                      ...newSteps[stepIndex],
                                                      image: "",
                                                    };
                                                    updateEditingTopicData({
                                                      steps: newSteps,
                                                    });
                                                  }}
                                                  className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium shadow-sm transition-colors"
                                                >
                                                  Remove
                                                </button>
                                              </div>
                                            </div>
                                          ) : (
                                            <label className="block cursor-pointer">
                                              <div className="border-2 border-dashed rounded-lg p-6 text-center transition-all border-gray-300 bg-white hover:border-sky-400 hover:bg-sky-50">
                                                <ImageIcon className="w-10 h-10 text-gray-400 mx-auto mb-2" />
                                                <p className="text-sm text-gray-600 font-medium">
                                                  Select Image
                                                </p>
                                                <p className="text-xs text-gray-400 mt-1">
                                                  Click to browse
                                                </p>
                                                <p className="text-xs text-gray-400 mt-0.5">
                                                  Max size: 5MB
                                                </p>
                                                <p className="text-xs text-amber-600 mt-1 font-medium">
                                                  Will upload on save
                                                </p>
                                              </div>
                                              <input
                                                type="file"
                                                accept="image/*"
                                                className="hidden"
                                                onChange={(e) => {
                                                  const file =
                                                    e.target.files[0];
                                                  if (file) {
                                                    if (
                                                      file.size >
                                                      5 * 1024 * 1024
                                                    ) {
                                                      notifications.error(
                                                        "Image size must be less than 5MB"
                                                      );
                                                      return;
                                                    }
                                                    if (
                                                      !file.type.startsWith(
                                                        "image/"
                                                      )
                                                    ) {
                                                      notifications.error(
                                                        "Please select an image file"
                                                      );
                                                      return;
                                                    }

                                                    // Store File object instead of uploading immediately
                                                    // Create preview URL and cache it
                                                    const previewUrl =
                                                      URL.createObjectURL(file);
                                                    filePreviewCacheRef.current.set(
                                                      file,
                                                      previewUrl
                                                    );

                                                    // Update step with File object
                                                    setEditingTopicData(
                                                      (prev) => {
                                                        const updatedSteps = [
                                                          ...(prev?.steps ||
                                                            []),
                                                        ];
                                                        updatedSteps[
                                                          stepIndex
                                                        ] = {
                                                          ...updatedSteps[
                                                            stepIndex
                                                          ],
                                                          image: file,
                                                        };
                                                        return {
                                                          ...prev,
                                                          steps: updatedSteps,
                                                        };
                                                      }
                                                    );

                                                    notifications.success(
                                                      "Image selected. It will be uploaded when you save the topic."
                                                    );
                                                  }
                                                  e.target.value = "";
                                                }}
                                              />
                                            </label>
                                          )}
                                        </div>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          // Clean up object URL if step has a File object
                                          if (
                                            step.image &&
                                            isFileObject(step.image)
                                          ) {
                                            const previewUrl =
                                              filePreviewCacheRef.current.get(
                                                step.image
                                              );
                                            if (previewUrl) {
                                              try {
                                                URL.revokeObjectURL(previewUrl);
                                              } catch (e) {
                                                console.warn(
                                                  "Error revoking object URL:",
                                                  e
                                                );
                                              }
                                              filePreviewCacheRef.current.delete(
                                                step.image
                                              );
                                            }
                                          }

                                          const newSteps = (
                                            editingTopicData.steps || []
                                          ).filter((_, i) => i !== stepIndex);
                                          updateEditingTopicData({
                                            steps: newSteps,
                                          });
                                        }}
                                        className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg flex-shrink-0 transition-colors"
                                        title="Delete step"
                                      >
                                        <X className="w-4 h-4" />
                                      </button>
                                    </div>
                                  </div>
                                )
                              )
                            )}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                          <button
                            onClick={handleCancelTopicInline}
                            className="px-6 py-2.5 text-gray-700 transition-colors bg-gray-200 rounded-lg hover:bg-gray-300 font-medium"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveTopicInline}
                            disabled={saving}
                            className="px-6 py-2.5 text-white rounded-lg transition-colors bg-sky-600 hover:bg-sky-700 font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Save className="w-4 h-4" />
                            {saving ? "Saving..." : "Save"}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                }

                // View Mode - use memoized selected topic
                const topic = selectedTopic;
                if (!topic) {
                  return null;
                }

                return (
                  <div
                    className="p-5 overflow-y-auto"
                    style={{ maxHeight: "calc(100vh - 300px)" }}
                  >
                    {/* View Mode */}
                    <div className="space-y-4">
                      {/* Topic Header */}
                      <div className="mb-4 pb-2 border-b border-gray-200">
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="flex-1 min-w-0">
                            <h2 className="font-semibold text-lg text-gray-900 mb-2">
                              {topic.title || "Untitled Topic"}
                            </h2>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="inline-flex items-center px-2.5 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-md">
                                {categoryNameMap.get(topic.category) ||
                                  topic.category ||
                                  "Uncategorized"}
                              </span>
                              {topic.steps?.length > 0 && (
                                <span className="inline-flex items-center text-xs text-gray-600">
                                  <FileText className="w-3.5 h-3.5 mr-1" />
                                  {topic.steps.length} step
                                  {topic.steps.length !== 1 ? "s" : ""}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <button
                              onClick={() =>
                                moveTopic(
                                  topics.findIndex((t) => t.id === topic.id),
                                  "up"
                                )
                              }
                              disabled={
                                topics.findIndex((t) => t.id === topic.id) === 0
                              }
                              className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                              title="Move up"
                            >
                              <ChevronUp className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() =>
                                moveTopic(
                                  topics.findIndex((t) => t.id === topic.id),
                                  "down"
                                )
                              }
                              disabled={
                                topics.findIndex((t) => t.id === topic.id) ===
                                topics.length - 1
                              }
                              className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                              title="Move down"
                            >
                              <ChevronDown className="w-4 h-4" />
                            </button>
                            <div className="h-6 w-px bg-gray-300"></div>
                            <button
                              onClick={() => openEditTopic(topic)}
                              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
                              title="Edit topic"
                            >
                              <Edit className="w-4 h-4" />
                              Edit
                            </button>
                            <div className="h-6 w-px bg-gray-300"></div>
                            <button
                              onClick={() => {
                                deleteTopic(topic.id);
                              }}
                              className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                              title="Delete topic"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Topic Content - Read-only Viewer */}
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Description
                          </label>
                          <div className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-50 text-gray-700 min-h-[80px]">
                            {topic.description || (
                              <span className="text-gray-400 italic">
                                No description provided
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                              Category
                            </label>
                            <div className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-50 text-gray-700">
                              {categoryNameMap.get(topic.category) ||
                                topic.category ||
                                "Uncategorized"}
                            </div>
                          </div>
                          <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                              Tags
                            </label>
                            <div className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-50 text-gray-700">
                              {topic.tags && topic.tags.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                  {topic.tags.map((tag, idx) => (
                                    <span
                                      key={idx}
                                      className="inline-flex items-center px-2 py-0.5 bg-gray-200 text-gray-700 rounded text-xs"
                                    >
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-gray-400 italic">
                                  No tags
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Access Control
                          </label>
                          <div className="flex flex-wrap gap-2 p-3 border border-gray-200 rounded-lg bg-gray-50 min-h-[44px]">
                            {topic.access && topic.access.length > 0 ? (
                              topic.access.map((accessRole, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium shadow-sm"
                                >
                                  {accessRole}
                                </span>
                              ))
                            ) : (
                              <span className="text-sm text-gray-500 italic flex items-center">
                                <Users className="w-4 h-4 mr-2" />
                                No restrictions (visible to all users)
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="border-t border-gray-200 pt-4">
                          <div className="flex justify-between items-center mb-3">
                            <label className="block text-sm font-semibold text-gray-700">
                              Steps ({topic.steps?.length || 0})
                            </label>
                          </div>
                          <div className="space-y-3">
                            {(topic.steps || []).length === 0 ? (
                              <div className="text-center py-8 border-2 border-dashed border-gray-200 rounded-lg bg-gray-50">
                                <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                                <p className="text-sm text-gray-400">
                                  No steps added yet
                                </p>
                              </div>
                            ) : (
                              (topic.steps || []).map((step, stepIndex) => (
                                <div
                                  key={stepIndex}
                                  className="border border-gray-200 rounded-lg p-4 bg-gray-50"
                                >
                                  <div className="flex items-start gap-3">
                                    <span className="w-8 h-8 bg-sky-100 text-sky-700 rounded-lg text-sm font-bold flex items-center justify-center flex-shrink-0 shadow-sm">
                                      {stepIndex + 1}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                      <h4 className="font-semibold text-sm text-gray-900 mb-2">
                                        {step.title || (
                                          <span className="text-gray-400 italic">
                                            Untitled step
                                          </span>
                                        )}
                                      </h4>
                                      <p className="text-sm text-gray-700 mb-3 whitespace-pre-wrap">
                                        {step.description || (
                                          <span className="text-gray-400 italic">
                                            No description
                                          </span>
                                        )}
                                      </p>
                                      {step.image && (
                                        <div
                                          className="rounded-lg overflow-hidden border border-gray-300 relative cursor-pointer group"
                                          onClick={() => {
                                            // Collect all images from all steps
                                            const allImages = (
                                              topic.steps || []
                                            )
                                              .filter((s) => s.image)
                                              .map((s, idx) => ({
                                                url: getImageUrl(s.image),
                                                caption:
                                                  s.title || `Step ${idx + 1}`,
                                                name:
                                                  s.image.split("/").pop() ||
                                                  "image",
                                              }));
                                            const currentImageIndex =
                                              allImages.findIndex((img) => {
                                                const stepWithImage = (
                                                  topic.steps || []
                                                ).find(
                                                  (s, i) =>
                                                    s.image && i === stepIndex
                                                );
                                                return (
                                                  stepWithImage &&
                                                  getImageUrl(
                                                    stepWithImage.image
                                                  ) === img.url
                                                );
                                              });
                                            setLightboxImages(allImages);
                                            setLightboxImageIndex(
                                              currentImageIndex >= 0
                                                ? currentImageIndex
                                                : 0
                                            );
                                            setLightboxOpen(true);
                                          }}
                                        >
                                          <img
                                            src={getImageUrl(step.image)}
                                            alt={step.title || "Step image"}
                                            className="w-full h-40 object-cover transition-transform group-hover:scale-105"
                                            onError={(e) => {
                                              const img = e.target;
                                              img.style.display = "none";
                                              // Show error placeholder
                                              const errorDiv =
                                                document.createElement("div");
                                              errorDiv.className =
                                                "w-full h-40 bg-red-50 border border-red-200 rounded-lg flex flex-col items-center justify-center text-red-600 text-sm p-4";
                                              errorDiv.innerHTML = `
                                                <svg class="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                </svg>
                                                <p class="font-medium">Failed to load image</p>
                                                <p class="text-xs mt-1 text-center break-all">${step.image}</p>
                                              `;
                                              img.parentNode.appendChild(
                                                errorDiv
                                              );
                                            }}
                                          />
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()
            ) : (
              <div className="p-12 text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
                  <Edit className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-base font-semibold text-gray-700 mb-2">
                  No Topic Selected
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Select a topic from the list on the left to view details
                </p>
                <button
                  onClick={addTopic}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Create New Topic
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Categories Tab */}
      {activeTab === "categories" && (
        <div className="grid grid-cols-1 lg:grid-cols-[30%_70%] gap-1">
          {/* Left Column (30%) - Categories List */}
          <div className="bg-white border border-gray-200">
            {/* Search and Actions Bar */}
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                    <input
                      type="text"
                      placeholder="Search categories..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all"
                    />
                  </div>
                </div>
              </div>
              <button
                onClick={addCategory}
                className="w-full bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add New Category
              </button>
            </div>

            {/* Categories List */}
            <div
              className="overflow-y-auto"
              style={{ maxHeight: "calc(100vh - 350px)" }}
            >
              {filteredCategories.length === 0 ? (
                <div className="p-12 text-center text-gray-500">
                  <Tag className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p className="text-sm">
                    {searchQuery ? "No categories found" : "No categories yet"}
                  </p>
                  {!searchQuery && (
                    <button
                      onClick={addCategory}
                      className="mt-4 bg-sky-600 text-white px-4 py-2 rounded text-sm font-medium"
                    >
                      Create First Category
                    </button>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {filteredCategories.map((category) => {
                    const topicCount =
                      topicCountsByCategory.get(category.key) || 0;
                    const isSelected = selectedCategoryKey === category.key;
                    return (
                      <div
                        key={category.key}
                        onClick={() => {
                          setSelectedCategoryKey(category.key);
                          setIsEditingCategory(false);
                          setEditingCategoryData(null);
                          setEditingCategoryOriginalKey(null);
                        }}
                        className={`p-4 cursor-pointer transition-all ${
                          isSelected
                            ? "bg-sky-50 border-l-4 border-l-sky-500 shadow-sm"
                            : "hover:bg-gray-50 border-l-4 border-l-transparent"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <h3
                              className={`font-semibold text-sm mb-1.5 truncate ${
                                isSelected ? "text-sky-900" : "text-gray-900"
                              }`}
                            >
                              {category.name || "Unnamed Category"}
                            </h3>
                            <p className="text-xs text-gray-600 line-clamp-2 mb-2.5 leading-relaxed">
                              {category.key && !category.key.startsWith("temp-")
                                ? category.key
                                : "New category"}
                            </p>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-md">
                                {topicCount} topic{topicCount !== 1 ? "s" : ""}
                              </span>
                              {topicCount > 0 && (
                                <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-sky-100 text-sky-700 rounded-md">
                                  In Use
                                </span>
                              )}
                            </div>
                          </div>
                          <div
                            className="flex items-center gap-0.5 flex-shrink-0"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedCategoryKey(category.key);
                                setEditingCategoryData({ ...category });
                                setEditingCategoryOriginalKey(category.key);
                                setIsEditingCategory(true);
                                setCategoryInlineErrors({});
                              }}
                              className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                              title="Edit category"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteCategory(category.key);
                              }}
                              className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                              title="Delete category"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column (70%) - Category Viewer/Editor */}
          <div className="bg-white border border-gray-200 rounded shadow">
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                  <Tag className="w-4 h-4" />
                  {isEditingCategory ? "Edit Category" : "Category Viewer"}
                </h3>
              </div>
            </div>
            {selectedCategoryKey ? (
              (() => {
                const category = categories.find(
                  (c) => c.key === selectedCategoryKey
                );
                if (!category) {
                  setSelectedCategoryKey(null);
                  return null;
                }
                const topicCount = topics.filter(
                  (t) => t.category === category.key
                ).length;

                return (
                  <div
                    className="p-5 overflow-y-auto"
                    style={{ maxHeight: "calc(100vh - 300px)" }}
                  >
                    {isEditingCategory && editingCategoryData ? (
                      /* Edit Mode */
                      <div className="space-y-5">
                        {/* Category Name */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Category Name{" "}
                            <span className="text-red-500">*</span>
                          </label>
                          <input
                            type="text"
                            value={editingCategoryData.name || ""}
                            onChange={(e) => {
                              const newName = e.target.value;
                              const newKey =
                                editingCategoryData.key ||
                                generateCategoryKey(newName);
                              setEditingCategoryData({
                                ...editingCategoryData,
                                name: newName,
                                key: editingCategoryData.key || newKey,
                              });
                              // Clear name error when typing
                              if (categoryInlineErrors.name) {
                                setCategoryInlineErrors({
                                  ...categoryInlineErrors,
                                  name: "",
                                });
                              }
                              // Mark as having unsaved changes
                              setHasUnsavedChanges(true);
                            }}
                            placeholder="Enter category name..."
                            className={`w-full text-sm border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all ${
                              categoryInlineErrors.name
                                ? "border-red-300 bg-red-50"
                                : "border-gray-300"
                            }`}
                            autoFocus
                          />
                          {categoryInlineErrors.name && (
                            <p className="mt-1 text-xs text-red-600">
                              {categoryInlineErrors.name}
                            </p>
                          )}
                        </div>

                        {/* Category Key */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Category Key <span className="text-red-500">*</span>
                          </label>
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editingCategoryData.key || ""}
                              onChange={(e) => {
                                const newKey = e.target.value
                                  .toLowerCase()
                                  .replace(/\s+/g, "-")
                                  .replace(/[^a-z0-9-]/g, "");
                                setEditingCategoryData({
                                  ...editingCategoryData,
                                  key: newKey,
                                });
                                // Clear key error when typing
                                if (categoryInlineErrors.key) {
                                  setCategoryInlineErrors({
                                    ...categoryInlineErrors,
                                    key: "",
                                  });
                                }
                                // Mark as having unsaved changes
                                setHasUnsavedChanges(true);
                              }}
                              placeholder="category-key"
                              className={`w-full text-xs font-mono border rounded-lg px-3 py-2.5 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all ${
                                categoryInlineErrors.key
                                  ? "border-red-300 bg-red-50"
                                  : "border-gray-300"
                              }`}
                            />
                            {!editingCategoryData.key &&
                              editingCategoryData.name && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const autoKey = generateCategoryKey(
                                      editingCategoryData.name
                                    );
                                    setEditingCategoryData({
                                      ...editingCategoryData,
                                      key: autoKey,
                                    });
                                  }}
                                  className="px-3 py-2.5 text-xs font-medium text-sky-600 hover:text-sky-700 hover:bg-sky-50 rounded-lg border border-sky-200 transition-colors whitespace-nowrap"
                                  title="Auto-generate key from name"
                                >
                                  Auto
                                </button>
                              )}
                          </div>
                          {categoryInlineErrors.key && (
                            <p className="mt-1 text-xs text-red-600">
                              {categoryInlineErrors.key}
                            </p>
                          )}
                          <p className="mt-1 text-xs text-gray-500">
                            Key must be lowercase, alphanumeric, and use hyphens
                            for spaces
                          </p>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                          <button
                            onClick={handleCancelCategoryInline}
                            className="px-6 py-2.5 text-gray-700 transition-colors bg-gray-200 rounded-lg hover:bg-gray-300 font-medium"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveCategoryInline}
                            disabled={saving}
                            className="px-6 py-2.5 text-white rounded-lg transition-colors bg-sky-600 hover:bg-sky-700 font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Save className="w-4 h-4" />
                            {saving ? "Saving..." : "Save"}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* View Mode */
                      <div className="space-y-4">
                        {/* Category Header */}
                        <div className="mb-5 pb-4 border-b border-gray-200">
                          <div className="flex items-start justify-between gap-3 mb-3">
                            <div className="flex-1 min-w-0">
                              <h2 className="font-semibold text-lg text-gray-900 mb-2">
                                {category.name || "Unnamed Category"}
                              </h2>
                              <div className="flex items-center gap-2 mt-2">
                                <code className="text-xs font-mono text-gray-700 bg-gray-100 px-2.5 py-1 rounded-md">
                                  {category.key || "No key"}
                                </code>
                                <span className="inline-flex items-center text-xs text-gray-600">
                                  <FileText className="w-3.5 h-3.5 mr-1" />
                                  {topicCount} topic
                                  {topicCount !== 1 ? "s" : ""}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <button
                                onClick={() => {
                                  setEditingCategoryData({ ...category });
                                  setEditingCategoryOriginalKey(category.key);
                                  setIsEditingCategory(true);
                                  setCategoryInlineErrors({});
                                }}
                                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
                                title="Edit category"
                              >
                                <Edit className="w-4 h-4" />
                                Edit
                              </button>
                              <div className="h-6 w-px bg-gray-300"></div>
                              <button
                                onClick={() => {
                                  deleteCategory(category.key);
                                }}
                                className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                                title="Delete category"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Category Details */}
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Category Key
                          </label>
                          <div className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-50 text-gray-700 font-mono">
                            {category.key || "No key"}
                          </div>
                        </div>

                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Usage
                          </label>
                          <div className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-50 text-gray-700 min-h-[44px]">
                            {topicCount === 0 ? (
                              <span className="text-gray-400 italic">
                                No topics use this category
                              </span>
                            ) : (
                              <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-gray-500" />
                                <span>
                                  Used by {topicCount} topic
                                  {topicCount !== 1 ? "s" : ""}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()
            ) : (
              <div className="p-12 text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
                  <Tag className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-base font-semibold text-gray-700 mb-2">
                  No Category Selected
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Select a category from the list on the left to view details
                </p>
                <button
                  onClick={addCategory}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Create New Category
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        open={confirmDialog.open}
        title={confirmDialog.title}
        message={confirmDialog.message}
        onCancel={() => setConfirmDialog({ ...confirmDialog, open: false })}
        onConfirm={() => {
          if (confirmDialog.onConfirm) {
            confirmDialog.onConfirm();
          }
        }}
        confirmText="Confirm"
        cancelText="Cancel"
        confirmColor={
          confirmDialog.type === "deleteTopic" ||
          confirmDialog.type === "deleteCategory"
            ? "red"
            : confirmDialog.type === "cancelTopic" ||
              confirmDialog.type === "cancelCategory"
            ? "amber"
            : confirmDialog.type === "saveTopic" ||
              confirmDialog.type === "saveCategory"
            ? "green"
            : "sky"
        }
        icon={
          confirmDialog.type === "import" ? (
            <AlertCircle className="w-6 h-6 text-sky-600" />
          ) : confirmDialog.type === "export" ? (
            <Download className="w-6 h-6 text-sky-600" />
          ) : confirmDialog.type === "cancelTopic" ||
            confirmDialog.type === "cancelCategory" ? (
            <AlertCircle className="w-6 h-6 text-amber-600" />
          ) : confirmDialog.type === "saveTopic" ||
            confirmDialog.type === "saveCategory" ? (
            <CheckCircle className="w-6 h-6 text-green-600" />
          ) : (
            <Trash2 className="w-6 h-6 text-red-600" />
          )
        }
        headerColor={
          confirmDialog.type === "deleteTopic" ||
          confirmDialog.type === "deleteCategory"
            ? "red"
            : confirmDialog.type === "cancelTopic" ||
              confirmDialog.type === "cancelCategory"
            ? "amber"
            : confirmDialog.type === "saveTopic" ||
              confirmDialog.type === "saveCategory"
            ? "green"
            : "sky"
        }
      />

      {/* Image Lightbox */}
      {lightboxOpen && lightboxImages.length > 0 && (
        <ImageLightbox
          images={lightboxImages}
          currentIndex={lightboxImageIndex}
          onClose={() => setLightboxOpen(false)}
          onNavigate={setLightboxImageIndex}
        />
      )}
    </div>
  );
}
