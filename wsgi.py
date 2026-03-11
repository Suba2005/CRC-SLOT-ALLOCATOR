"""
PythonAnywhere WSGI entry point.
Point your WSGI config file to this module's `application` object.
"""
from app import create_app

application = create_app()
