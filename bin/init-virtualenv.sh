#!/usr/bin/env bash -evx

mkvirtualenv "boto3-retry"
workon "boto3-retry"

pip install -e .
pip install -r requirements_dev.txt
