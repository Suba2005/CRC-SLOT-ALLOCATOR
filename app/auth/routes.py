# Auth routes removed — /login, /logout, and /register have all been stripped.
from flask import Blueprint

auth_bp = Blueprint("auth", __name__)
