from django.db import models


class Certificado(models.Model):
    nf_saida = models.OneToOneField(
        'fiscal.NFeSaida',
        on_delete=models.CASCADE,
        related_name='certificado',
    )
    arquivo = models.FileField(upload_to='certificados/%Y/%m/')
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-gerado_em']
