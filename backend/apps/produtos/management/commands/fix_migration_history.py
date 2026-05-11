from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Corrige histórico de migrations do app produtos para conflito 0013/0014."

    def handle(self, *args, **options):
        migration_0013 = "0013_familia_tipo_dimensional_produto_od_mm"
        migration_0014 = "0014_familia_tipo_dimensional_produto_od_mm"

        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.django_migrations')")
            if cursor.fetchone()[0] is None:
                self.stdout.write("fix_migration_history: django_migrations ainda não existe; ignorado.")
                return

            cursor.execute(
                "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s LIMIT 1",
                ["produtos", migration_0013],
            )
            has_0013 = cursor.fetchone() is not None

            cursor.execute(
                "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s LIMIT 1",
                ["produtos", migration_0014],
            )
            has_0014 = cursor.fetchone() is not None

            if has_0014 and not has_0013:
                cursor.execute(
                    """
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES (%s, %s, NOW())
                    """,
                    ["produtos", migration_0013],
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "fix_migration_history: inserida migration 0013 como aplicada (compatibilidade)."
                    )
                )
                return

        self.stdout.write("fix_migration_history: nenhum ajuste necessário.")
