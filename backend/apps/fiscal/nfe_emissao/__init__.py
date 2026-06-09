"""NF-e 4.0.2 — emissão SEFAZ (homologação).

Evitar imports eager de ``servico`` / ``xml_oficial`` aqui — quebram cadeia
``nfe_xml_higienizacao`` → ``nfe_emissao.xml_serializacao`` → ``__init__`` → ``servico``.
Importe submódulos diretamente: ``from apps.fiscal.nfe_emissao.servico import ...``.
"""
