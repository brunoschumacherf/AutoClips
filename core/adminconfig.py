from django.contrib.admin.apps import AdminConfig


class CortaAdminConfig(AdminConfig):
    default_site = "core.adminsite.CortaAdminSite"
