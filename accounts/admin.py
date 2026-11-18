from django.apps import apps
from django.contrib import admin

for app_label in ("accounts", "videos", "streams", "transcriptions", "ai_engine", "clips", "rendering",
                  "subscriptions", "notifications"):
    for model in apps.get_app_config(app_label).get_models():
        admin.site.register(model)
