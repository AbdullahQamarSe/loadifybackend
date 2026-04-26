from django.apps import AppConfig


class LoadifyApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loadify_api'

    def ready(self):
        import loadify_api.signals  # noqa: F401
