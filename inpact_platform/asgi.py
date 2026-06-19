"""ASGI entrypoint (optional; WSGI is the default used by Vercel here)."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inpact_platform.settings")

application = get_asgi_application()
