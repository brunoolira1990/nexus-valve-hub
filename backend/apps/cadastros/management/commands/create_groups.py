from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


GROUPS_PERMISSIONS = {
    "admin": None,  # todas as permissões
    "operador": [
        "add_empresa",
        "change_empresa",
        "add_cliente",
        "change_cliente",
        "add_fornecedor",
        "change_fornecedor",
        "add_transportadora",
        "change_transportadora",
        "add_nfeentrada",
        "change_nfeentrada",
        "add_nfesaida",
        "change_nfesaida",
        "view_estoque",
    ],
    "comercial": [
        "add_proposta",
        "change_proposta",
        "add_pedidovenda",
        "change_pedidovenda",
    ],
    "qualidade": [
        "view_certificado",
        "add_certificado",
        "change_certificado",
    ],
    "fiscal": [
        "view_regrafiscal",
        "add_regrafiscal",
        "change_regrafiscal",
    ],
}


class Command(BaseCommand):
    help = "Cria grupos base e associa permissões padrão."

    def handle(self, *args, **options):
        all_permissions = Permission.objects.all()
        created = 0

        for group_name, codenames in GROUPS_PERMISSIONS.items():
            group, was_created = Group.objects.get_or_create(name=group_name)
            if was_created:
                created += 1

            if codenames is None:
                group.permissions.set(all_permissions)
                self.stdout.write(self.style.SUCCESS(f"Grupo '{group_name}' com todas as permissões."))
                continue

            perms = Permission.objects.filter(codename__in=codenames)
            group.permissions.set(perms)
            missing = sorted(set(codenames) - set(perms.values_list("codename", flat=True)))
            msg = f"Grupo '{group_name}' atualizado com {perms.count()} permissões."
            if missing:
                msg += f" Ausentes: {', '.join(missing)}."
            self.stdout.write(self.style.WARNING(msg) if missing else self.style.SUCCESS(msg))

        self.stdout.write(self.style.SUCCESS(f"Concluído. Grupos novos: {created}."))
