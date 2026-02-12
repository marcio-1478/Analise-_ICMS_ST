#!/usr/bin/env python3
"""Validação do app antes de subir atualizações."""
import sys

def main():
    errors = []
    try:
        import app
    except Exception as e:
        errors.append(f"Falha ao importar app: {e}")
        return errors

    for name in ["extrair_impostos_item", "_extrair_cst_icms", "cfop_inicia_54_ou_64",
                 "salvar_nota_e_itens", "processar_xml", "_exibir_resultados_auditoria"]:
        if not hasattr(app, name):
            errors.append(f"Função ausente: {name}")

    try:
        r = app.extrair_impostos_item({"imposto": {"ICMS": {"ICMS00": {"CST": "00"}}}})
        if r.get("cst") != "00":
            errors.append(f"CST esperado '00', obtido {r.get('cst')!r}")
    except Exception as e:
        errors.append(f"extrair_impostos_item: {e}")

    try:
        assert app.cfop_inicia_54_ou_64("5401") and app.cfop_inicia_61("6102") and app.cfop_inicia_51("5102")
    except AssertionError:
        errors.append("CFOP helpers falharam")

    return errors

if __name__ == "__main__":
    errs = main()
    if errs:
        print("ERROS:", *errs, sep="\n  - ")
        sys.exit(1)
    print("Validação OK.")
