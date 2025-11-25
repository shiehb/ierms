// src/components/header/RoleBasedSearch.jsx
import { useState, useRef, useEffect, useMemo } from "react";
import {
  Search,
  Users,
  Building,
  FileText,
  MapPin,
  Settings,
  Database,
  Clock,
  X,
  Bookmark,
  BookmarkPlus,
  Trash2,
  Info,
} from "lucide-react";
import { useSearch } from "../../contexts/SearchContext";
import { useNotifications } from "../../hooks/useNotifications";

export default function RoleBasedSearch({ userLevel = "public" }) {
  const {
    searchQuery,
    updateSearchQuery,
    searchSuggestions,
    searchHistory,
    savedSearches,
    showSuggestions,
    hideSuggestions,
    selectSuggestion,
    clearHistory,
    saveSearch,
    deleteSavedSearch,
    loadSavedSearch,
    loading,
  } = useSearch();

  const notifications = useNotifications();
  const [showHistory, setShowHistory] = useState(false);
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [showKeyboardHints, setShowKeyboardHints] = useState(false);
  const [activeFilter, setActiveFilter] = useState("all");
  const [sortBy, setSortBy] = useState("relevance");
  const [groupBy, setGroupBy] = useState("type");
  const [resultCount, setResultCount] = useState(0);
  const searchContainerRef = useRef(null);
  const searchInputRef = useRef(null);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);

  // Filter, sort and group suggestions
  const sortedSuggestions = useMemo(() => {
    let sorted = [...searchSuggestions];

    switch (sortBy) {
      case "name":
        sorted.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        break;
      case "recent":
        sorted.sort((a, b) => {
          const dateA = a.updated_at ? new Date(a.updated_at) : new Date(0);
          const dateB = b.updated_at ? new Date(b.updated_at) : new Date(0);
          return dateB - dateA;
        });
        break;
      case "relevance":
      default:
        // Keep original order from API
        break;
    }

    return sorted;
  }, [searchSuggestions, sortBy]);

  // Filter suggestions by active filter
  const filteredSuggestions = useMemo(() => {
    if (activeFilter === "all") {
      return sortedSuggestions;
    }
    return sortedSuggestions.filter((s) => s.type === activeFilter);
  }, [sortedSuggestions, activeFilter]);

  const groupedSuggestions = useMemo(() => {
    if (groupBy === "none") {
      return { all: filteredSuggestions };
    }

    return filteredSuggestions.reduce((groups, suggestion) => {
      const key = suggestion[groupBy] || "Other";
      if (!groups[key]) groups[key] = [];
      groups[key].push(suggestion);
      return groups;
    }, {});
  }, [filteredSuggestions, groupBy]);

  // Update result count when filtered suggestions change
  useEffect(() => {
    setResultCount(filteredSuggestions.length);
  }, [filteredSuggestions]);

  // Handle click outside to close suggestions and modals
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target)
      ) {
        hideSuggestions();
        setShowHistory(false);
        setShowSavedSearches(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [hideSuggestions]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Ctrl+K to focus search
      if (e.ctrlKey && e.key === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }

      // Escape to close dropdowns
      if (e.key === "Escape") {
        hideSuggestions();
        setShowHistory(false);
        setShowSavedSearches(false);
        searchInputRef.current?.blur();
      }

      // Arrow key navigation in suggestions
      if (showSuggestions && searchSuggestions.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedSuggestionIndex((prev) =>
            prev < searchSuggestions.length - 1 ? prev + 1 : 0
          );
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedSuggestionIndex((prev) =>
            prev > 0 ? prev - 1 : searchSuggestions.length - 1
          );
        } else if (e.key === "Enter" && selectedSuggestionIndex >= 0) {
          e.preventDefault();
          handleSuggestionClick(searchSuggestions[selectedSuggestionIndex]);
        }
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [
    showSuggestions,
    searchSuggestions,
    selectedSuggestionIndex,
    hideSuggestions,
  ]);

  const handleGlobalSearch = (e) => {
    updateSearchQuery(e.target.value, userLevel); // Pass userLevel
  };

  const handleInputFocus = () => {
    if (searchQuery.length >= 2 && searchSuggestions.length > 0) {
      // Suggestions will show automatically via the context
    }

    // Show history when focusing on empty input
    if (!searchQuery && searchHistory.length > 0) {
      setShowHistory(true);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    selectSuggestion(suggestion);
    setSelectedSuggestionIndex(-1);
  };

  const handleHistoryClick = (query) => {
    updateSearchQuery(query, userLevel);
    setShowHistory(false);
  };

  const getSuggestionIcon = (type) => {
    switch (type) {
      case "navigation":
        return <MapPin className="w-4 h-4" />;
      case "establishment":
        return <Building className="w-4 h-4" />;
      case "user":
        return <Users className="w-4 h-4" />;
      case "inspection":
        return <FileText className="w-4 h-4" />;
      case "system":
        return <Settings className="w-4 h-4" />;
      case "database":
        return <Database className="w-4 h-4" />;
      default:
        return <Search className="w-4 h-4" />;
    }
  };

  const getSuggestionColor = (type) => {
    switch (type) {
      case "navigation":
        return "text-indigo-600 bg-indigo-50";
      case "establishment":
        return "text-blue-600 bg-blue-50";
      case "user":
        return "text-green-600 bg-green-50";
      case "inspection":
        return "text-purple-600 bg-purple-50";
      case "system":
        return "text-red-600 bg-red-50";
      case "database":
        return "text-gray-600 bg-gray-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  const getRoleBasedPlaceholder = () => {
    const basePlaceholders = {
      Admin: "Search establishments, users, inspections, settings...",
      "Section Chief": "Search establishments, inspections, districts...",
      "Unit Head": "Search establishments, inspections, districts...",
      "Legal Unit": "Search billing records, legal documents...",
      Inspector: "Search establishments, inspections...",
      public: "Search establishments, inspections...",
    };

    return basePlaceholders[userLevel] || basePlaceholders["public"];
  };

  // Highlight matching text in search results
  const highlightMatch = (text, query) => {
    if (!query || !text) return text;

    const parts = text.split(new RegExp(`(${query})`, "gi"));
    return (
      <span>
        {parts.map((part, i) =>
          part.toLowerCase() === query.toLowerCase() ? (
            <mark key={i} className="bg-yellow-200 text-gray-900 font-semibold">
              {part}
            </mark>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
      </span>
    );
  };

  return (
    <div className="flex-1 max-w-xl relative" ref={searchContainerRef}>
      <div className="relative">
        {/* Keyboard hints button */}
        <button
          onMouseEnter={() => setShowKeyboardHints(true)}
          onMouseLeave={() => setShowKeyboardHints(false)}
          className="absolute translate-y-1 right-[-1.5rem] top-1 text-gray-400 hover:text-gray-600 transition-colors hidden sm:block"
          title="Keyboard shortcuts"
        >
          <Info className="w-3.5 h-3.5" />
        </button>

        <Search className="absolute w-3.5 h-3.5 text-gray-400 -translate-y-1/2 left-2.5 top-1/2" />
        <input
          ref={searchInputRef}
          type="text"
          placeholder={getRoleBasedPlaceholder()}
          value={searchQuery}
          onChange={handleGlobalSearch}
          onFocus={handleInputFocus}
          className="w-full py-1 pl-8 pr-16 text-sm transition bg-gray-100 border border-gray-300 rounded-full hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
          aria-label="Search"
          role="searchbox"
          aria-autocomplete="list"
          aria-controls="search-suggestions"
          aria-expanded={showSuggestions}
          aria-activedescendant={
            selectedSuggestionIndex >= 0
              ? `search-result-${selectedSuggestionIndex}`
              : undefined
          }
        />

        {/* Result count badge */}
        {searchQuery && !loading && (
          <div className="absolute -translate-y-1/2 right-10 top-1/2">
            <span className="text-xs bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded-full result-count-badge">
              {resultCount}
            </span>
          </div>
        )}

        {/* Loading spinner */}
        {loading && (
          <div className="absolute w-3.5 h-3.5 -translate-y-1/2 right-10 top-1/2">
            <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-sky-500"></div>
          </div>
        )}

        {/* Saved searches button */}
        <button
          onClick={() => setShowSavedSearches(!showSavedSearches)}
          className="absolute -translate-y-1/2 right-3 top-1/2 text-gray-400 hover:text-sky-600 transition-colors"
          title="Saved searches"
        >
          <Bookmark className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Screen reader announcements */}
      <div role="status" aria-live="polite" className="sr-only">
        {loading ? "Searching..." : `${resultCount} results found`}
      </div>

      {/* Keyboard shortcuts tooltip */}
      {showKeyboardHints && (
        <div className="absolute top-full right-0 mt-1 bg-gray-900 text-white rounded-lg shadow-lg p-3 z-50 text-xs w-64 keyboard-hints-tooltip">
          <h4 className="font-semibold mb-2">Keyboard Shortcuts</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-300">Focus search</span>
              <kbd className="bg-gray-800 px-1.5 py-0.5 rounded">Ctrl+K</kbd>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-300">Navigate results</span>
              <kbd className="bg-gray-800 px-1.5 py-0.5 rounded">↑ ↓</kbd>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-300">Select result</span>
              <kbd className="bg-gray-800 px-1.5 py-0.5 rounded">Enter</kbd>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-300">Close dropdown</span>
              <kbd className="bg-gray-800 px-1.5 py-0.5 rounded">Esc</kbd>
            </div>
          </div>
        </div>
      )}

      {/* Search History */}
      {showHistory && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto">
          <div className="p-2">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-gray-500">
                Recent ({searchHistory.length})
              </div>
              <button
                onClick={clearHistory}
                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-0.5"
                title="Clear history"
              >
                <X className="w-3 h-3" />
              </button>
            </div>

            {searchHistory.length > 0 ? (
              <div className="space-y-0.5">
                {searchHistory.map((query, index) => (
                  <button
                    key={index}
                    onClick={() => handleHistoryClick(query)}
                    className="flex items-center w-full p-1.5 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors text-left"
                  >
                    <Clock className="w-3.5 h-3.5 text-gray-400 mr-2" />
                    <span className="text-xs text-gray-700 truncate">
                      {query}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-center py-3 text-gray-500">
                <Clock className="w-5 h-5 mx-auto mb-1 text-gray-300" />
                <p className="text-xs">No recent searches</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Saved Searches */}
      {showSavedSearches && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-50 max-w-md">
          <div className="p-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-gray-700">Saved</h3>
              <button
                onClick={() => setShowSavedSearches(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Save current search */}
            {searchQuery && (
              <button
                onClick={() => {
                  saveSearch(searchQuery);
                  notifications.success("Search saved!");
                }}
                className="w-full flex items-center gap-2 p-2 mb-2 border-2 border-dashed border-gray-300 rounded-lg hover:border-sky-400 hover:bg-sky-50 transition-colors"
              >
                <BookmarkPlus className="w-3.5 h-3.5 text-sky-600" />
                <span className="text-xs text-gray-700 truncate">
                  Save "{searchQuery}"
                </span>
              </button>
            )}

            {/* Saved searches list */}
            {savedSearches.length > 0 ? (
              <div className="space-y-0.5 max-h-48 overflow-y-auto">
                {savedSearches.map((search) => (
                  <div
                    key={search.id}
                    className="flex items-center gap-1.5 p-1.5 rounded-lg hover:bg-gray-50 group"
                  >
                    <button
                      onClick={() => {
                        loadSavedSearch(search);
                        setShowSavedSearches(false);
                      }}
                      className="flex-1 text-left"
                    >
                      <div className="text-xs text-gray-900 truncate">
                        {search.name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(search.timestamp).toLocaleDateString()}
                      </div>
                    </button>
                    <button
                      onClick={() => deleteSavedSearch(search.id)}
                      className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-4 text-gray-500">
                <Bookmark className="w-6 h-6 mx-auto mb-1 text-gray-300" />
                <p className="text-xs">No saved searches</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Search Suggestions Dropdown - Compact */}
      {showSuggestions && searchSuggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl z-50 max-h-80 overflow-hidden">
          {/* Header with filters and controls */}
          <div className="sticky top-0 bg-white border-b border-gray-100 p-2 z-10">
            {/* Filter buttons */}
            <div className="flex gap-1 mb-2 overflow-x-auto pb-1">
              <button
                onClick={() => setActiveFilter("all")}
                className={`px-2 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                  activeFilter === "all"
                    ? "bg-sky-100 text-sky-700 font-medium"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                All ({searchSuggestions.length})
              </button>
              {searchSuggestions.some((s) => s.type === "establishment") && (
                <button
                  onClick={() => setActiveFilter("establishment")}
                  className={`px-2 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                    activeFilter === "establishment"
                      ? "bg-blue-100 text-blue-700 font-medium"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  Establishments (
                  {
                    searchSuggestions.filter((s) => s.type === "establishment")
                      .length
                  }
                  )
                </button>
              )}
              {searchSuggestions.some((s) => s.type === "user") && (
                <button
                  onClick={() => setActiveFilter("user")}
                  className={`px-2 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                    activeFilter === "user"
                      ? "bg-green-100 text-green-700 font-medium"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  Users (
                  {searchSuggestions.filter((s) => s.type === "user").length})
                </button>
              )}
              {searchSuggestions.some((s) => s.type === "inspection") && (
                <button
                  onClick={() => setActiveFilter("inspection")}
                  className={`px-2 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                    activeFilter === "inspection"
                      ? "bg-purple-100 text-purple-700 font-medium"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  Inspections (
                  {
                    searchSuggestions.filter((s) => s.type === "inspection")
                      .length
                  }
                  )
                </button>
              )}
              {searchSuggestions.some((s) => s.type === "navigation") && (
                <button
                  onClick={() => setActiveFilter("navigation")}
                  className={`px-2 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                    activeFilter === "navigation"
                      ? "bg-indigo-100 text-indigo-700 font-medium"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  Pages (
                  {
                    searchSuggestions.filter((s) => s.type === "navigation")
                      .length
                  }
                  )
                </button>
              )}
            </div>

            {/* Sort and group controls */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-500">
                Results ({resultCount})
              </span>
              <div className="flex gap-1.5">
                {/* Sort dropdown */}
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="text-xs border border-gray-200 rounded px-1.5 py-0.5"
                >
                  <option value="relevance">Relevance</option>
                  <option value="name">A-Z</option>
                  <option value="recent">Recent</option>
                </select>

                {/* Group dropdown */}
                <select
                  value={groupBy}
                  onChange={(e) => setGroupBy(e.target.value)}
                  className="text-xs border border-gray-200 rounded px-1.5 py-0.5"
                >
                  <option value="type">By Type</option>
                  <option value="category">By Category</option>
                  <option value="none">No Group</option>
                </select>
              </div>
            </div>
          </div>

          {/* Scrollable results */}
          <div
            id="search-suggestions"
            role="listbox"
            aria-label="Search suggestions"
            className="overflow-y-auto max-h-64 scrollbar-thin"
          >
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-sky-600"></div>
                <span className="ml-2 text-sm text-gray-600">Searching...</span>
              </div>
            ) : (
              Object.entries(groupedSuggestions).map(([group, items]) => (
                <div key={group} className="mb-1">
                  {/* Group header */}
                  {groupBy !== "none" && (
                    <div className="sticky top-0 bg-gradient-to-r from-gray-50 to-white px-3 py-1 border-b border-gray-100 search-group-header">
                      <span className="text-xs font-semibold text-gray-700 uppercase">
                        {group} ({items.length})
                      </span>
                    </div>
                  )}

                  {/* Results */}
                  <div className="p-1.5">
                    {items.map((suggestion, index) => (
                      <button
                        key={index}
                        id={`search-result-${index}`}
                        role="option"
                        aria-selected={index === selectedSuggestionIndex}
                        onClick={() => handleSuggestionClick(suggestion)}
                        onMouseEnter={() => setSelectedSuggestionIndex(index)}
                        className={`flex items-start w-full p-2 rounded-lg transition-all mb-0.5 text-left ${
                          index === selectedSuggestionIndex
                            ? "bg-sky-50 border border-sky-200 shadow-sm"
                            : "hover:bg-gray-50 border border-transparent"
                        }`}
                        onMouseDown={(e) => e.preventDefault()}
                      >
                        {/* Icon */}
                        <div
                          className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${getSuggestionColor(
                            suggestion.type
                          )} mr-2`}
                        >
                          {getSuggestionIcon(suggestion.type)}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 truncate">
                            {highlightMatch(
                              suggestion.name || suggestion.text,
                              searchQuery
                            )}
                          </div>
                          {suggestion.description && (
                            <div className="text-xs text-gray-500 truncate leading-tight">
                              {suggestion.description}
                            </div>
                          )}
                        </div>

                        {/* Arrow indicator for selected */}
                        {index === selectedSuggestionIndex && (
                          <div className="flex-shrink-0 ml-1">
                            <div className="text-sky-500 text-sm">→</div>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer with quick actions */}
          <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 p-1.5 text-xs text-gray-500">
            <div className="flex items-center justify-between px-1.5">
              <span className="text-xs">↑↓ navigate • Enter select</span>
              <button
                onClick={() => {
                  saveSearch(searchQuery);
                  notifications.success("Saved!");
                }}
                className="text-sky-600 hover:text-sky-700 flex items-center gap-0.5"
              >
                <BookmarkPlus className="w-3 h-3" />
                <span className="text-xs">Save</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* No Results State */}
      {showSuggestions &&
        searchQuery.length >= 2 &&
        searchSuggestions.length === 0 &&
        !loading && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-50 p-4">
            <div className="text-center">
              <Search className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              <h3 className="text-xs font-medium text-gray-900 mb-1">
                No results
              </h3>
              <p className="text-xs text-gray-500 mb-2">
                No matches for "{searchQuery}"
              </p>
              <div className="text-xs text-gray-600">
                <p className="mb-1">Try:</p>
                <ul className="list-none text-left inline-block space-y-0.5">
                  <li>• Different keywords</li>
                  <li>• Check spelling</li>
                </ul>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
