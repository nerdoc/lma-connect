from django.apps import AppConfig


class GamificationConfig(AppConfig):
    name = "lma_connect.plugins.gamification"
    label = "lma_gamification"
    verbose_name = "Gamification"

    def ready(self):
        # Register signal receivers that award points / check achievements.
        from . import signals  # noqa: F401
