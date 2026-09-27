"""Compatibility entry point for existing crawler jobs.

New deployments use ``manage.py sync_products`` directly.
"""
import os
import sys
from pathlib import Path

manage = Path(__file__).resolve().parents[1] / 'forge_backend_server' / 'manage.py'
os.execv(sys.executable, [sys.executable, str(manage), 'sync_products', *sys.argv[1:]])
