#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --no-input --skip-checks
