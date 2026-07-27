from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


# Grupos administrativos (admin / administrador) usam None = todas as permissões
# do banco no momento da execução. Com RegistroAuditoria append-only
# (somente view_registroauditoria), esses grupos passam a visualizar o histórico
# ao reexecutar este comando após migrate — sem conceder add/change/delete.
# Demais grupos (operador, consulta, etc.) NÃO recebem view_registroauditoria
# nesta fase, salvo decisão explícita futura.
#
# Liberação financeira de Proposta (AnaliseFinanceiraProposta):
# Codenames reais (app comercial):
#   - view_analisefinanceiraproposta
#   - solicitar_analisefinanceiraproposta
#   - decidir_analisefinanceiraproposta
#   - ver_detalhe_financeiro_analisefinanceiraproposta
#   - view_analisefinanceirapropostaevento (somente view; append-only)
# API exige essas permissões específicas — sem fallback para change_proposta
# ou change_titulofinanceiro.
# NÃO atribuídas automaticamente neste seed nesta fase — rollout manual:
# - comercial: view + solicitar
# - financeiro: view + decidir + ver_detalhe_financeiro
# - admin/administrador: cobrem via None após create_groups.
GROUPS_PERMISSIONS = {
    "admin": None,
    "administrador": None,
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
    "compras": [
        "add_pedidocompra",
        "change_pedidocompra",
        "add_fornecedor",
        "change_fornecedor",
        "add_nfeentrada",
        "change_nfeentrada",
    ],
    "financeiro": [
        "add_titulofinanceiro",
        "change_titulofinanceiro",
        "view_titulofinanceiro",
        "add_baixafinanceira",
        "change_baixafinanceira",
        "add_creditofinanceiro",
        "change_creditofinanceiro",
    ],
    "estoque": [
        "view_estoque",
        "change_estoque",
        "add_produto",
        "change_produto",
        "view_produto",
    ],
    "produtos": [
        "add_produto",
        "change_produto",
        "view_produto",
        "add_familiaproduto",
        "change_familiaproduto",
    ],
    "consulta": [
        "view_cliente",
        "view_fornecedor",
        "view_produto",
        "view_titulofinanceiro",
        "view_pedidovenda",
        "view_pedidocompra",
        "view_proposta",
        "view_nfesaida",
        "view_nfeentrada",
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
        "view_nfesaida",
        "change_nfesaida",
        "view_nfeentrada",
        "change_nfeentrada",
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
