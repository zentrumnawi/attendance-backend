from .base import *  # noqa


DEBUG = False
SECRET_KEY = "g2evp6ktpj)kctnme#j$nye*_^gdwbaqs-ji4fbq_ld78$g8^d"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast password hashing in tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Use in-memory email backend for tests.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Prefer sqlite for tests unless DATABASE_URL is explicitly provided.
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite://:memory:"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
