from copy import deepcopy

from django.utils.text import capfirst

from .constants import AUDIT_ACTIONS, AUDIT_MODULES
from .models import ActivityLog


def log_activity(
    user,
    action,
    *,
    module=None,
    description=None,
    message="",
    metadata=None,
    before=None,
    after=None,
    request=None,
):
    """
    Create a standardized audit log entry.

    Args:
        user: Django user performing the action (optional for system events).
        action: Verb describing the change (use constants from AUDIT_ACTIONS).
        module: Logical module/section key or label.
        description: Human-readable summary; falls back to auto-generated text.
        message: Optional technical note (defaults to description).
        metadata: Dict with extra context (ids, filenames, status, etc.).
        before/after: Optional snapshots captured around updates.
        request: Django request for IP/user agent inference.
    """
    ip = None
    ua = ""

    if request:
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "") or ""

    user_to_log = resolve_user(user)

    module_label = resolve_module(module, request)
    normalized_action = normalize_action(action)

    payload = {}
    if metadata:
        payload.update(deepcopy(metadata))

    # Ensure a status is present for UI filtering (default to success)
    payload.setdefault("status", "success")

    if before is not None:
        payload.setdefault("before", before)
    if after is not None:
        payload.setdefault("after", after)

    if request:
        payload.setdefault("path", request.path)
        payload.setdefault("method", request.method)

    final_description = description or build_default_description(
        user_to_log,
        normalized_action,
        module_label,
        payload,
    )

    ActivityLog.objects.create(
        user=user_to_log,
        role=getattr(user_to_log, "userlevel", "") if user_to_log else "",
        action=normalized_action,
        module=module_label,
        description=final_description,
        message=message or final_description,
        metadata=payload,
        ip_address=ip,
        user_agent=ua or "",
    )


def resolve_user(user):
    if user and hasattr(user, "is_authenticated"):
        if user.is_authenticated:
            return user
        return None
    return user


def resolve_module(module, request):
    if module:
        if module in AUDIT_MODULES:
            return AUDIT_MODULES[module]
        return module

    inferred = infer_module_from_request(request)
    if inferred:
        return inferred

    return AUDIT_MODULES.get("SYSTEM", "System Operations")


def normalize_action(action):
    if not action:
        return AUDIT_ACTIONS["SYSTEM"]

    lower_action = str(action).lower()
    if lower_action in AUDIT_ACTIONS.values():
        return lower_action

    # Allow callers to pass constants such as AUDIT_ACTIONS["CREATE"]
    for value in AUDIT_ACTIONS.values():
        if value == lower_action:
            return value
    return lower_action


def build_default_description(user, action, module, data):
    actor = (
        getattr(user, "email", None)
        or getattr(user, "username", None)
        or getattr(user, "get_full_name", lambda: "")()
        or "System"
    )

    target = (
        data.get("entity_name")
        or data.get("resource_name")
        or data.get("file_name")
        or data.get("identifier")
    )

    action_text = action.replace("_", " ")
    module_text = module or AUDIT_MODULES.get("SYSTEM", "system")

    if target:
        identifier = data.get("entity_id") or data.get("resource_id")
        if identifier:
            return f"{actor} {action_text} {target} (ID {identifier}) in {module_text}"
        return f"{actor} {action_text} {target} in {module_text}"

    return f"{actor} {action_text} in {module_text}"


def infer_module_from_request(request):
    if not request:
        return ""

    match = getattr(request, "resolver_match", None)
    if match and match.app_names:
        for namespace in match.app_names:
            upper = namespace.upper()
            if upper in AUDIT_MODULES:
                return AUDIT_MODULES[upper]

    if match and match.view_name:
        view_name = match.view_name.split(":")[-1]
        view_name = view_name.replace("_", " ").replace("-", " ")
        return capfirst(view_name)

    segments = [segment for segment in request.path.strip("/").split("/") if segment]
    for segment in segments:
        key = segment.upper()
        if key in AUDIT_MODULES:
            return AUDIT_MODULES[key]
        if segment.lower() in {"api", "v1"}:
            continue
        return capfirst(segment.replace("-", " ").replace("_", " "))
    return ""


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
