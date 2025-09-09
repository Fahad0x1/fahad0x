#!/bin/bash

# قم بتحديث متغيرات البيئة ببيانات Home Assistant
export HA_URL="http://homeassistant.local:8123/api"
export HA_TOKEN=$(</data/options.json jq -r '.ha_token')

# تشغيل تطبيق Flask
python3 /app/app.py