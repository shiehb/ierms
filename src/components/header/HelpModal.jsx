// src/components/header/HelpModal.jsx
import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Search,
  HelpCircle,
  X,
  Clock,
  Zap,
  Target,
  ArrowLeft,
  BookOpen,
  Edit,
} from "lucide-react";
import { helpTopics as defaultHelpTopics } from "../../data/helpData";
import {
  filterTopicsByUserLevel,
  normalizeUserLevel,
} from "../../utils/helpUtils";
import { getHelpTopics } from "../../services/helpApi";
import { getProfile } from "../../services/api";
import { API_BASE_URL } from "../../config/api";
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

const RECENT_TOPICS_KEY = "recentHelpTopics";
const MAX_RECENT_TOPICS = 5;

const TABS = [
  { id: "quick-start", name: "Quick Start", icon: Zap },
  { id: "context", name: "For This Page", icon: Target },
  { id: "recent", name: "Recent", icon: Clock },
  { id: "all", name: "Search All", icon: Search },
];

export default function HelpModal({
  userLevel = "public",
  isOpen = false,
  onClose,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [helpSearchQuery, setHelpSearchQuery] = useState("");
  const [recentTopics, setRecentTopics] = useState([]);
  const [activeTab, setActiveTab] = useState("quick-start");
  const [viewMode, setViewMode] = useState("list"); // 'list' or 'detail'
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [helpTopics, setHelpTopics] = useState(defaultHelpTopics);
  const [profile, setProfile] = useState(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImageIndex, setLightboxImageIndex] = useState(0);
  const [lightboxImages, setLightboxImages] = useState([]);
  const modalRef = useRef(null);
  const closeButtonRef = useRef(null);
  const previousFocusRef = useRef(null);

  // Fetch user profile to check if admin
  useEffect(() => {
    getProfile()
      .then(setProfile)
      .catch(() => setProfile(null));
  }, []);

  // Fetch help data from API with fallback to static files
  useEffect(() => {
    const loadHelpData = async () => {
      try {
        const topicsData = await getHelpTopics();
        if (Array.isArray(topicsData) && topicsData.length > 0) {
          setHelpTopics(topicsData);
        }
      } catch (error) {
        console.warn(
          "Failed to load help data from API, using default data:",
          error
        );
        // Keep default data from static imports
      }
    };

    loadHelpData();
  }, []);

  // Load recent topics from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(RECENT_TOPICS_KEY);
    if (stored) {
      try {
        setRecentTopics(JSON.parse(stored));
      } catch (e) {
        console.error("Error loading recent topics:", e);
      }
    }
  }, []);

  // Focus management
  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement;
      // Small delay to ensure modal is rendered
      setTimeout(() => {
        if (modalRef.current) {
          const firstInput = modalRef.current.querySelector("input");
          if (firstInput) {
            firstInput.focus();
          }
        }
      }, 100);
    } else {
      // Return focus to previous element when modal closes
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    }
  }, [isOpen]);

  // ESC key to close modal
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Focus trap
  useEffect(() => {
    if (!isOpen) return;

    const handleTab = (e) => {
      if (e.key !== "Tab" || !modalRef.current) return;

      const focusableElements = modalRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener("keydown", handleTab);
    return () => document.removeEventListener("keydown", handleTab);
  }, [isOpen]);

  const handleHelpSearch = (e) => setHelpSearchQuery(e.target.value);

  const accessibleTopics = filterTopicsByUserLevel(
    helpTopics,
    normalizeUserLevel(userLevel)
  );

  const filteredHelpSuggestions = accessibleTopics.filter(
    (topic) =>
      topic.title.toLowerCase().includes(helpSearchQuery.toLowerCase()) ||
      topic.description.toLowerCase().includes(helpSearchQuery.toLowerCase())
  );

  // Get context-sensitive help based on current route with improved matching
  const getContextHelp = () => {
    const path = location.pathname;

    // Enhanced route mapping with keywords and tags
    const contextMap = {
      "/": {
        keywords: ["Dashboard"],
        tags: ["dashboard", "home", "overview"],
        priority: 1,
      },
      "/map": {
        keywords: ["Map"],
        tags: ["map", "location", "geography", "polygon"],
        priority: 1,
      },
      "/establishments": {
        keywords: ["Establishment"],
        tags: ["establishment", "business", "add", "edit"],
        priority: 1,
      },
      "/inspections": {
        keywords: ["Inspection"],
        tags: ["inspection", "inspect", "monitor", "create"],
        priority: 1,
      },
      "/inspection/new": {
        keywords: ["Inspection", "Create"],
        tags: ["inspection", "create", "new"],
        priority: 2,
      },
      "/inspection/": {
        keywords: ["Inspection"],
        tags: ["inspection", "view", "edit"],
        priority: 1,
      },
      "/users": {
        keywords: ["User Management", "User"],
        tags: ["user", "admin", "management", "role"],
        priority: 1,
      },
      "/billing": {
        keywords: ["Billing"],
        tags: ["billing", "payment", "legal", "records"],
        priority: 1,
      },
      "/database-backup": {
        keywords: ["Backup & Restore", "Database"],
        tags: ["database", "backup", "restore", "export", "admin"],
        priority: 1,
      },
      "/notifications": {
        keywords: ["Notification"],
        tags: ["notification", "alert", "message"],
        priority: 1,
      },
      "/help": {
        keywords: ["Help"],
        tags: ["help", "guide", "support"],
        priority: 1,
      },
      "/profile": {
        keywords: ["Profile"],
        tags: ["profile", "account", "user", "settings"],
        priority: 1,
      },
      "/change-password": {
        keywords: ["Password"],
        tags: ["password", "security", "change"],
        priority: 2,
      },
    };

    // Find matching route
    let matchedContext = null;
    let matchedPriority = 0;

    for (const [route, config] of Object.entries(contextMap)) {
      if (path.startsWith(route) && config.priority >= matchedPriority) {
        matchedContext = config;
        matchedPriority = config.priority;
      }
    }

    if (!matchedContext) return [];

    // Score and filter topics based on relevance
    const scoredTopics = accessibleTopics.map((topic) => {
      let score = 0;
      const topicText =
        `${topic.title} ${topic.description} ${topic.category}`.toLowerCase();
      const topicTags = (topic.tags || []).map((t) => t.toLowerCase());

      // Check keywords (highest weight)
      matchedContext.keywords.forEach((keyword) => {
        if (topic.title.toLowerCase().includes(keyword.toLowerCase()))
          score += 10;
        if (topic.description.toLowerCase().includes(keyword.toLowerCase()))
          score += 5;
        if (topic.category?.toLowerCase().includes(keyword.toLowerCase()))
          score += 7;
      });

      // Check tags (medium weight)
      matchedContext.tags.forEach((tag) => {
        if (topicTags.includes(tag)) score += 8;
        if (topicText.includes(tag)) score += 3;
      });

      return { topic, score };
    });

    // Filter topics with score > 0 and sort by score
    return scoredTopics
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((item) => item.topic);
  };

  const contextHelp = getContextHelp();

  // Add topic to recent topics
  const addToRecentTopics = (topic) => {
    const updated = [
      topic,
      ...recentTopics.filter((t) => t.id !== topic.id),
    ].slice(0, MAX_RECENT_TOPICS);

    setRecentTopics(updated);
    localStorage.setItem(RECENT_TOPICS_KEY, JSON.stringify(updated));
  };

  const handleHelpSuggestionClick = (topic) => {
    addToRecentTopics(topic);
    setSelectedTopic(topic);
    setViewMode("detail");
  };

  const handleBackToList = () => {
    setViewMode("list");
    setSelectedTopic(null);
  };

  // Highlight search terms in text
  const highlightText = (text, query) => {
    if (!query) return text;

    const parts = text.split(new RegExp(`(${query})`, "gi"));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-yellow-200 text-gray-900">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  // Get topics filtered by tab
  const getTopicsForTab = () => {
    if (activeTab === "quick-start") {
      return accessibleTopics.filter(
        (topic) => topic.category === "getting-started"
      );
    } else if (activeTab === "context") {
      return contextHelp;
    } else if (activeTab === "recent") {
      return recentTopics;
    } else {
      return filteredHelpSuggestions;
    }
  };

  const tabTopics = getTopicsForTab();

  if (!isOpen) return null;

  return (
    <>
      {/* Help Modal - Centered overlay with backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-lg bg-gray-100/50 transition-all duration-300 ease-out"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-labelledby="help-modal-title"
        >
          <div
            ref={modalRef}
            onClick={(e) => e.stopPropagation()}
            className="w-full h-full md:w-[90vw] md:max-w-3xl md:max-h-[80vh] md:min-h-[65vh] flex flex-col bg-white md:rounded-xl shadow-2xl border border-gray-200 transform transition-all duration-300 ease-out scale-100 opacity-100 animate-modalEntry"
          >
            {/* Header - Simple and Minimal */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
              <h2
                id="help-modal-title"
                className="flex items-center text-base font-semibold text-gray-800"
              >
                <HelpCircle className="w-4 h-4 mr-2" />
                Help Center
              </h2>
              <div className="flex items-center gap-2">
                {(profile?.userlevel === "Admin" ||
                  profile?.is_staff ||
                  profile?.is_superuser) && (
                  <button
                    onClick={() => {
                      onClose();
                      navigate("/help/editor");
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-sky-600 hover:text-sky-700 hover:bg-sky-50 rounded transition-colors"
                    title="Edit Help Content"
                  >
                    <Edit className="w-3.5 h-3.5" />
                    Edit Help
                  </button>
                )}
                <button
                  ref={closeButtonRef}
                  onClick={onClose}
                  className="p-1.5 transition-all duration-200 rounded hover:bg-gray-100"
                  aria-label="Close help center"
                >
                  <X className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Search bar - Only show in list view */}
            {viewMode === "list" && (
              <div className="px-4 py-3 bg-white border-b border-gray-200">
                <div className="relative">
                  <Search className="absolute w-4 h-4 text-gray-400 -translate-y-1/2 left-3 top-1/2" />
                  <input
                    type="text"
                    placeholder="Search help topics..."
                    value={helpSearchQuery}
                    onChange={handleHelpSearch}
                    className="w-full py-2 pl-10 pr-4 text-sm bg-white border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
                    aria-label="Search help topics"
                  />
                </div>
              </div>
            )}

            {/* Tab Navigation - Only show in list view */}
            {viewMode === "list" && (
              <div className="flex border-b border-gray-200 bg-white">
                {TABS.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id);
                        if (tab.id === "all") {
                          setHelpSearchQuery("");
                        }
                      }}
                      className={`flex items-center px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                        activeTab === tab.id
                          ? "border-sky-600 text-sky-600"
                          : "border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300"
                      }`}
                    >
                      <Icon className="w-4 h-4 mr-2" />
                      {tab.name}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Content Area - List or Detail View */}
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
              {viewMode === "list" ? (
                /* LIST VIEW */
                <div className="px-4 py-3 space-y-4">
                  {tabTopics.length > 0 ? (
                    <ul className="space-y-2">
                      {tabTopics.map((topic, index) => (
                        <li
                          key={topic.id}
                          onClick={() => handleHelpSuggestionClick(topic)}
                          className="p-3 transition-colors border border-gray-200 bg-white rounded cursor-pointer hover:bg-gray-50 hover:border-gray-300"
                          role="button"
                          tabIndex={0}
                          onKeyPress={(e) =>
                            e.key === "Enter" &&
                            handleHelpSuggestionClick(topic)
                          }
                        >
                          <div className="text-sm font-semibold text-gray-900">
                            {activeTab === "all" && helpSearchQuery
                              ? highlightText(topic.title, helpSearchQuery)
                              : topic.title}
                          </div>
                          <div className="mt-1 text-xs text-gray-600 line-clamp-2">
                            {activeTab === "all" && helpSearchQuery
                              ? highlightText(
                                  topic.description,
                                  helpSearchQuery
                                )
                              : topic.description}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="py-12 text-center text-gray-500">
                      <BookOpen className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                      <p className="text-sm font-medium">
                        {activeTab === "recent"
                          ? "No recent topics yet"
                          : activeTab === "context"
                          ? "No help available for this page"
                          : activeTab === "quick-start"
                          ? "No quick start guides found"
                          : "No topics found"}
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        {activeTab === "all" && "Try different keywords"}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                /* DETAIL VIEW */
                <div className="flex flex-col h-full">
                  {/* Breadcrumb & Back Button */}
                  <div className="flex items-center px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <button
                      onClick={handleBackToList}
                      className="flex items-center text-sm font-medium text-sky-600 hover:text-sky-700 transition-colors"
                    >
                      <ArrowLeft className="w-4 h-4 mr-1" />
                      Back to Topics
                    </button>
                    <span className="ml-3 text-xs text-gray-400">
                      {TABS.find((t) => t.id === activeTab)?.name} ›{" "}
                      {selectedTopic?.title}
                    </span>
                  </div>

                  {/* Topic Content */}
                  <div className="flex-1 overflow-y-auto px-5 py-4">
                    {selectedTopic && (
                      <div className="max-w-3xl">
                        {/* Topic Title */}
                        <h2 className="text-2xl font-bold text-gray-900 mb-3">
                          {selectedTopic.title}
                        </h2>

                        {/* Topic Description */}
                        <p className="text-base text-gray-700 mb-6 leading-relaxed">
                          {selectedTopic.description}
                        </p>

                        {/* Steps */}
                        {selectedTopic.steps &&
                          selectedTopic.steps.length > 0 && (
                            <div className="space-y-6">
                              {selectedTopic.steps.map((step, index) => (
                                <div
                                  key={index}
                                  className="border-l-2 border-sky-500 pl-4 pb-4"
                                >
                                  <h3 className="text-base font-semibold text-gray-800 mb-2">
                                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-sky-100 text-sky-700 text-xs font-bold mr-2">
                                      {index + 1}
                                    </span>
                                    {step.title}
                                  </h3>
                                  <p className="text-sm text-gray-700 leading-relaxed mb-3">
                                    {step.description}
                                  </p>
                                  {step.image && (
                                    <div
                                      className="rounded-lg border border-gray-200 overflow-hidden cursor-pointer group"
                                      onClick={() => {
                                        // Collect all images from all steps
                                        const allImages = (
                                          selectedTopic.steps || []
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
                                            return (
                                              getImageUrl(step.image) ===
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
                                        src={getImageUrl(step.image)}
                                        alt={step.title}
                                        className="w-full max-w-2xl shadow-sm transition-transform group-hover:scale-105"
                                        onError={(e) => {
                                          e.target.style.display = "none";
                                        }}
                                      />
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Image Lightbox */}
      {lightboxOpen && lightboxImages.length > 0 && (
        <ImageLightbox
          images={lightboxImages}
          currentIndex={lightboxImageIndex}
          onClose={() => setLightboxOpen(false)}
          onNavigate={setLightboxImageIndex}
        />
      )}
    </>
  );
}
