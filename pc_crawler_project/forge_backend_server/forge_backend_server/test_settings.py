"""Tests use a separate in-memory database and dummy credentials."""
import os
os.environ.update(SECRET_KEY='test-only-key-never-used-for-deployment', DB_USER='test', DB_PASSWORD='test')
from .settings import *  # noqa: F403
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
ALLOWED_HOSTS = ['testserver', 'localhost']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
