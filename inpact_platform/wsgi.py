"""WSGI entrypoint. Vercel reads `application` from here (WSGI_APPLICATION)."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inpact_platform.settings")

application = get_wsgi_application()

# Some platforms look for `app`; expose an alias for convenience.
app = application
