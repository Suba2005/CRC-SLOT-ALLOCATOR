"""
Authentication decorators — session-based access control.
"""
from functools import wraps
from flask import session, redirect, url_for, flash, abort


def login_required(f):
    """Redirect to login page if the user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*allowed_roles):
    """
    Restrict access to users with one of the specified roles.
    Usage: @role_required("staff", "crc_head")
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            user_role = session.get("role", "")
            if user_role not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
