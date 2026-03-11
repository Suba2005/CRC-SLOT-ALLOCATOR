"""
Auth blueprint — login, register, logout.
Sends email notifications on successful login and logout.
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session,
)
from ..models import db, User
from ..services.email_service import send_login_email, send_logout_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login and send login alert email."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # Set session variables
            session["user_id"] = user.id
            session["username"] = user.username
            session["email"] = user.email
            session["role"] = user.role

            flash(f"Welcome back, {user.username}!", "success")

            # Send login notification email (non-blocking; failure won't stop login)
            send_login_email(user.username, user.email)

            return redirect(url_for("allocator.upload"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "student")

        # Validation
        errors = []
        if not username or not email or not password:
            errors.append("All fields are required.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("Username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email is already registered.")
        if role not in ("student", "leader", "staff", "crc_head"):
            errors.append("Invalid role selected.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/register.html")

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    """Clear session, send logout email, and redirect to login."""
    # Capture user info before clearing session
    username = session.get("username", "")
    email = session.get("email", "")

    # Send logout notification email (non-blocking)
    if username and email:
        send_logout_email(username, email)

    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
