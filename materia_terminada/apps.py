from django.apps import AppConfig


class MateriaTerminadaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'materia_terminada'

    def ready(self):
        import materia_terminada.signals  # noqa: F401
