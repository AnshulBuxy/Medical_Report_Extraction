#!/bin/bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 app:app
