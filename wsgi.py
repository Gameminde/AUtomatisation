"""Gunicorn entry point for production serving."""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()
