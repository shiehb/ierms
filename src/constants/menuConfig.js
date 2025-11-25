// src/constants/menuConfig.js
import {
  LayoutDashboard,
  Users,
  Building,
  MapPin,
  InspectIcon,
  FileText,
  Settings,
  Database,
  Map as MapIcon,
  BookOpen,
  Scale,
  History,
  Bell,
  BarChart3,
} from "lucide-react";

// Menu configuration with role-based access control
export const MENU_CONFIG = [
  {
    id: "dashboard",
    name: "Dashboard",
    path: "/",
    icon: LayoutDashboard,
    roles: [
      "Admin",
      "Section Chief",
      "Unit Head",
      "Legal Unit",
      "Inspector",
      "public",
    ],
  },
  {
    id: "users",
    name: "Users",
    path: "/users",
    icon: Users,
    roles: ["Admin"],
    category: "Administration",
  },
  {
    id: "laws",
    name: "Law Management",
    path: "/laws",
    icon: Scale,
    roles: ["Admin"],
    category: "Administration",
  },
  {
    id: "map",
    name: "Map",
    path: "/map",
    icon: MapPin,
    roles: [
      "Admin",
      "Section Chief",
      "Unit Head",
      "Legal Unit",
      "Inspector",
      "public",
    ],
  },
  {
    id: "establishments",
    name: "Establishments",
    path: "/establishments",
    icon: Building,
    roles: [
      "Admin",
      "Section Chief",
      "Unit Head",
      "Legal Unit",
      "Inspector",
      "public",
    ],
    category: "Management",
  },
  {
    id: "inspections",
    name: "Inspections",
    path: "/inspections",
    icon: InspectIcon,
    roles: [
      "Admin",
      "Section Chief",
      "Unit Head",
      "Legal Unit",
      "Inspector",
      "public",
    ],
    category: "Management",
  },
  {
    id: "reports",
    name: "Reports",
    path: "/reports",
    icon: BarChart3,
    roles: [
      "Admin",
      "Section Chief",
      "Unit Head",
      "Legal Unit",
      "Inspector",
      "Division Chief",
      "Monitoring Personnel",
    ],
    category: "Management",
  },
  {
    id: "billing",
    name: "Billing Records",
    path: "/billing",
    icon: FileText,
    roles: ["Legal Unit"],
    category: "Legal",
  },
  {
    id: "reinspection-reminders",
    name: "Reinspection Reminders",
    path: "/reinspection-reminders",
    icon: Bell,
    roles: ["Division Chief"],
    category: "Management",
  },
  {
    id: "database-backup",
    name: "Backup & Restore",
    path: "/database-backup",
    icon: Database,
    roles: ["Admin"],
    category: "Administration",
  },
  {
    id: "audit-logs",
    name: "Audit Trails",
    path: "/audit-logs",
    icon: History,
    roles: ["Admin"],
    category: "Administration",
  },
  {
    id: "help-editor",
    name: "Help Editor",
    path: "/help/editor",
    icon: BookOpen,
    roles: ["Admin"],
    category: "Administration",
  },
];

// Helper function to filter menu items by user role
export const filterMenuByRole = (userLevel) => {
  return MENU_CONFIG.filter(
    (item) => item.roles.includes(userLevel) || item.roles.includes("public")
  );
};

// Helper function to group menu items by category
export const groupMenuByCategory = (menuItems) => {
  const grouped = {};
  const uncategorized = [];

  menuItems.forEach((item) => {
    if (item.category) {
      if (!grouped[item.category]) {
        grouped[item.category] = [];
      }
      grouped[item.category].push(item);
    } else {
      uncategorized.push(item);
    }
  });

  // Define the order of categories (Administration at the bottom)
  const categoryOrder = ["Management", "Legal", "Administration"];

  // Create ordered grouped object
  const orderedGrouped = {};
  categoryOrder.forEach((category) => {
    if (grouped[category]) {
      orderedGrouped[category] = grouped[category];
    }
  });

  return { grouped: orderedGrouped, uncategorized };
};
