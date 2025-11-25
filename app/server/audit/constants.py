"""
Shared constants for audit logging.
"""

# High-level modules/sections we want to appear in the audit trail.
AUDIT_MODULES = {
    "AUTH": "Authentication",
    "USERS": "User Management",
    "ESTABLISHMENTS": "Establishment Registry",
    "INSPECTIONS": "Inspection Workflow",
    "REPORTS": "Reports & Analytics",
    "NOTIFICATIONS": "Notifications",
    "SYSTEM_CONFIG": "System Configuration",
    "BACKUP": "Backup & Restore",
    "HELP": "Help Center",
    "LAWS": "Law Management",
    "FILES": "File Storage",
    "SYSTEM": "System Operations",
    "BILLING": "Billing & Payments",
}

# Canonical action labels to keep analytics consistent.
AUDIT_ACTIONS = {
    "CREATE": "create",
    "UPDATE": "update",
    "DELETE": "delete",
    "LOGIN": "login",
    "LOGOUT": "logout",
    "BACKUP": "backup",
    "RESTORE": "restore",
    "EXPORT": "export",
    "IMPORT": "import",
    "ASSIGN": "assign",
    "APPROVE": "approve",
    "REJECT": "reject",
    "SYSTEM": "system",
}

