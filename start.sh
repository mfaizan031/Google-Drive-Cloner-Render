#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Activate the virtual environment
source venv/bin/activate

# Run Gunicorn
exec gunicorn --bind 0.0.0.0:$PORT src.main:app


