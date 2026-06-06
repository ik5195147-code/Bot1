"""WSGI entry point for Gunicorn"""
from app import app

# Railway uses this directly - no if __name__ == "__main__" needed
