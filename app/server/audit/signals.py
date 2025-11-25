from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .utils import log_activity

# ❌ REMOVE or COMMENT OUT these duplicate handlers
# They're already handled in users/signals.py

# @receiver(user_logged_in)
# def log_user_login(sender, request, user, **kwargs):
#     log_activity(user, "login", "User logged in", request)

# @receiver(user_logged_out)
# def log_user_logout(sender, request, user, **kwargs):
#     log_activity(user, "logout", "User logged out", request)