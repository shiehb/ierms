// src/services/reportsApi.js
import api from "./api";

// ===============================================
// Centralized Report Dashboard API functions
// ===============================================

export const getAllowedReports = async () => {
  const res = await api.get("reports/access/");
  return res.data;
};

export const generateCentralizedReport = async (data) => {
  const res = await api.post("reports/generate/", data);
  return res.data;
};

export const getFilterOptions = async (reportType) => {
  const res = await api.get("reports/filter-options/", {
    params: { report_type: reportType },
  });
  return res.data;
};
