from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

from django.core.management.base import BaseCommand

from apps.produtos.models import Polegada
from apps.produtos.polegadas import aliases_for_polegada


def _fmt_inches(value: Fraction) -> str:
    inteiro = value.numerator // value.denominator
    resto = value - inteiro
    if resto == 0:
        return f'{inteiro}"'
    frac = Fraction(resto).limit_denominator()
    if inteiro == 0:
        return f'{frac.numerator}/{frac.denominator}"'
    return f'{inteiro}.{frac.numerator}/{frac.denominator}"'


class Command(BaseCommand):
    help = 'Gera base de medidas OD (polegada real) validada até 21".'

    def handle(self, *args, **options):
        faixas = [
            (Fraction(1, 8), Fraction(2, 1), Fraction(1, 32)),
            (Fraction(2, 1), Fraction(3, 1), Fraction(1, 16)),
            (Fraction(3, 1), Fraction(4, 1), Fraction(1, 8)),
            (Fraction(4, 1), Fraction(7, 1), Fraction(1, 4)),
            (Fraction(7, 1), Fraction(21, 1), Fraction(1, 2)),
        ]
        created = 0
        current_code = (
            Polegada.objects.filter(tipo_medida=Polegada.TipoMedida.OD)
            .exclude(codigo_oficial='')
            .order_by('-codigo_oficial')
            .values_list('codigo_oficial', flat=True)
            .first()
            or '00'
        )
        seq = int(''.join(ch for ch in current_code if ch.isdigit()) or '0')
        for ini, fim, passo in faixas:
            v = ini
            while v <= fim:
                dec = Decimal(v.numerator) / Decimal(v.denominator)
                if dec > Decimal('100'):
                    break
                mm = (dec * Decimal('25.4')).quantize(Decimal('0.001'))
                descricao = _fmt_inches(v)
                obj = Polegada.objects.filter(tipo_medida=Polegada.TipoMedida.OD, valor_decimal=dec).first()
                if not obj:
                    seq += 1
                    codigo = str(seq).zfill(2)
                    Polegada.objects.create(
                        tipo_medida=Polegada.TipoMedida.OD,
                        codigo=codigo,
                        codigo_oficial=codigo,
                        descricao=descricao,
                        valor_decimal=dec,
                        valor_mm=mm,
                        aliases=aliases_for_polegada(descricao, dec, mm),
                        origem='SEED_OD_BASE_21',
                        ativo=True,
                    )
                    created += 1
                v += passo
        self.stdout.write(self.style.SUCCESS(f'Medidas OD base até 21": {created} novos registros.'))
