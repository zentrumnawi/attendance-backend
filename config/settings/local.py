from .base import *  # noqa


DEBUG = env.bool("DJANGO_DEBUG", default=True)

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-4o4n-$s^y356xob(g15=_z&_%tuy36p7_ejnrp8xb-x=i11cu$",
)

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# relevant if usingdjango-cors-headers
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173",
# ]
CORS_ALLOW_CREDENTIALS = True
