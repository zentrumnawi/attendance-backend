from .base import *  # noqa


DEBUG = env.bool("DJANGO_DEBUG", default=True)

SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="django-insecure-4o4n-$s^y356xob(g15=_z&_%tuy36p7_ejnrp8xb-x=i11cu$"
)

ALLOWED_HOSTS = ["*"]