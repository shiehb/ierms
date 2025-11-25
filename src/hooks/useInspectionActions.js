import { useState } from "react";
import { useNotifications } from "./useNotifications";
import {
  inspectInspection,
  startInspection,
  continueInspection,
  completeInspection,
  forwardInspection,
  reviewInspection,
  forwardToLegal,
  returnInspection,
  returnToMonitoring,
  returnToUnit,
  returnToSection,
  sendToDivision,
  sendNOV,
  sendNOO,
  closeInspection,
} from "../services/api";

export const useInspectionActions = (refreshInspections) => {
  const notifications = useNotifications();
  const [loadingActions, setLoadingActions] = useState({});

  const handleAction = async (
    action,
    inspectionId,
    data = {},
    overrides = {}
  ) => {
    setLoadingActions((prev) => ({ ...prev, [inspectionId]: action }));

    try {
      // Show loading notification for long operations
      const longOperations = [
        "complete",
        "forward",
        "return_to_previous",
        "return_to_monitoring",
        "return_to_unit",
        "return_to_section",
        "send_nov",
        "send_noo",
        "close",
      ];
      if (longOperations.includes(action)) {
        notifications.info("Processing your request...", {
          title: "Please Wait",
          duration: 2000,
        });
      }

      let result;
      let successMessage = "";
      let successTitle = "";

      switch (action) {
        case "inspect":
          result = await inspectInspection(inspectionId, data);
          successMessage = "Inspection started successfully!";
          successTitle = "Inspection Started";
          break;
        case "start":
          result = await startInspection(inspectionId, data);
          successMessage = "Inspection started successfully!";
          successTitle = "Inspection Started";
          break;
        case "continue":
          result = await continueInspection(inspectionId, data);
          successMessage = "Inspection continued successfully!";
          successTitle = "Inspection Continued";
          break;
        case "complete":
          result = await completeInspection(inspectionId, data);
          successMessage = "Inspection completed successfully!";
          successTitle = "Inspection Completed";
          break;
        case "forward":
          result = await forwardInspection(inspectionId, data);
          successMessage = "Inspection forwarded successfully!";
          successTitle = "Inspection Forwarded";
          break;
        case "review":
          result = await reviewInspection(inspectionId, data);
          successMessage = "Review access granted successfully!";
          successTitle = "Review Access Granted";
          break;
        case "return_to_previous":
          result = await returnInspection(inspectionId, data);
          successMessage = "Inspection returned successfully!";
          successTitle = "Inspection Returned";
          break;
        case "return_to_monitoring":
          result = await returnToMonitoring(inspectionId, data);
          successMessage = "Inspection returned to monitoring successfully!";
          successTitle = "Returned to Monitoring";
          break;
        case "return_to_unit":
          result = await returnToUnit(inspectionId, data);
          successMessage = "Inspection returned to unit successfully!";
          successTitle = "Returned to Unit";
          break;
        case "return_to_section":
          result = await returnToSection(inspectionId, data);
          successMessage = "Inspection returned to section successfully!";
          successTitle = "Returned to Section";
          break;
        case "forward_to_legal":
          result = await forwardToLegal(inspectionId, data);
          successMessage = "Inspection forwarded to Legal Unit successfully!";
          successTitle = "Forwarded to Legal";
          break;
        case "send_to_division":
          result = await sendToDivision(inspectionId, data);
          successMessage = "Inspection sent to Division successfully!";
          successTitle = "Sent to Division";
          break;
        case "send_nov":
          result = await sendNOV(inspectionId, data);
          successMessage = "Notice of Violation sent successfully!";
          successTitle = "NOV Sent";
          break;
        case "send_noo":
          result = await sendNOO(inspectionId, data);
          successMessage = "Notice of Order sent successfully!";
          successTitle = "NOO Sent";
          break;
        case "close":
          result = await closeInspection(inspectionId, data);
          successMessage = "Inspection closed successfully!";
          successTitle = "Inspection Closed";
          break;
        default:
          throw new Error(`Unknown action: ${action}`);
      }

      // Show success notification
      const {
        successMessage: overrideMessage,
        successTitle: overrideTitle,
        successDuration: overrideDuration,
      } = overrides || {};

      const finalMessage =
        overrideMessage !== undefined ? overrideMessage : successMessage;
      const finalTitle =
        overrideTitle !== undefined ? overrideTitle : successTitle;
      const finalDuration =
        overrideDuration !== undefined ? overrideDuration : 4000;

      if (finalMessage) {
        notifications.success(finalMessage, {
          title: finalTitle,
          duration: finalDuration,
        });
      }

      if (typeof refreshInspections === "function") {
        await refreshInspections({ force: true });
      }
      return result;
    } catch (error) {
      console.error(`Action ${action} failed:`, error);
      notifications.error(
        error.message || `Failed to perform action. Please try again.`,
        { title: "Error" }
      );
      throw error;
    } finally {
      setLoadingActions((prev) => {
        const newState = { ...prev };
        delete newState[inspectionId];
        return newState;
      });
    }
  };

  const isActionLoading = (inspectionId) => {
    return loadingActions[inspectionId] || false;
  };

  return {
    handleAction,
    isActionLoading,
    loadingActions,
  };
};
