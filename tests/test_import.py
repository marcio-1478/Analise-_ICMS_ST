"""
Testes para a importação de NF-e: data de emissão e impostos.
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para importar app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import xmltodict  # type: ignore

# Importa funções do app (sem carregar Streamlit)
from app import (
    extrair_data_emissao_ide,
    extrair_impostos_item,
)

# Fixture: XML mínimo de NF-e para testes (estrutura NFe: det com prod e imposto)
XML_NFE_MINIMO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc>
  <NFe>
    <infNFe>
      <ide>
        <nNF>123456</nNF>
        <dhEmi>2024-03-15T14:30:00-03:00</dhEmi>
      </ide>
      <dest>
        <CNPJ>12345678000199</CNPJ>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>001</cProd>
          <xProd>Produto Teste</xProd>
          <NCM>12345678</NCM>
          <CFOP>5401</CFOP>
          <vUnCom>10.00</vUnCom>
          <qCom>2</qCom>
          <vProd>20.00</vProd>
        </prod>
        <imposto>
          <ICMS>
            <ICMS00>
              <vBC>20.00</vBC>
              <pICMS>18.00</pICMS>
              <vICMS>3.60</vICMS>
            </ICMS00>
          </ICMS>
          <PIS>
            <PISAliq>
              <vBC>20.00</vBC>
              <pPIS>1.65</pPIS>
              <vPIS>0.33</vPIS>
            </PISAliq>
          </PIS>
          <COFINS>
            <COFINSAliq>
              <vBC>20.00</vBC>
              <pCOFINS>7.60</pCOFINS>
              <vCOFINS>1.52</vCOFINS>
            </COFINSAliq>
          </COFINS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vBC>20.00</vBC>
          <vICMS>3.60</vICMS>
          <vST>0.00</vST>
          <vPIS>0.33</vPIS>
          <vCOFINS>1.52</vCOFINS>
          <vNF>25.45</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
"""


XML_NFE_DEMI = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc>
  <NFe>
    <infNFe>
      <ide>
        <nNF>999999</nNF>
        <dEmi>2025-01-20</dEmi>
      </ide>
    </infNFe>
  </NFe>
</nfeProc>
"""


XML_NFE_DATA_BR = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc>
  <NFe>
    <infNFe>
      <ide>
        <nNF>555555</nNF>
        <dEmi>15/06/2024</dEmi>
      </ide>
    </infNFe>
  </NFe>
</nfeProc>
"""


class TestExtrairDataEmissao:
    """Testes para extrair_data_emissao_ide."""

    def test_dhemi_format(self):
        """dhEmi com datetime: 2024-03-15T14:30:00-03:00 -> 2024-03-15"""
        ide = {"dhEmi": "2024-03-15T14:30:00-03:00", "nNF": "123"}
        assert extrair_data_emissao_ide(ide) == "2024-03-15"

    def test_demi_format_iso(self):
        """dEmi com formato ISO: 2025-01-20"""
        ide = {"dEmi": "2025-01-20", "nNF": "123"}
        assert extrair_data_emissao_ide(ide) == "2025-01-20"

    def test_demi_format_br(self):
        """dEmi com formato BR: 15/06/2024 -> 2024-06-15"""
        ide = {"dEmi": "15/06/2024"}
        assert extrair_data_emissao_ide(ide) == "2024-06-15"

    def test_demi_format_br_single_digit(self):
        """dEmi com dia/mês de um dígito: 5/3/2024 -> 2024-03-05"""
        ide = {"dEmi": "5/3/2024"}
        assert extrair_data_emissao_ide(ide) == "2024-03-05"

    def test_dhemi_lowercase(self):
        """dhemi em lowercase (alguns parsers XML)"""
        ide = {"dhemi": "2024-07-01T10:00:00"}
        assert extrair_data_emissao_ide(ide) == "2024-07-01"

    def test_demi_lowercase(self):
        """demi em lowercase"""
        ide = {"demi": "2024-12-31"}
        assert extrair_data_emissao_ide(ide) == "2024-12-31"

    def test_ide_vazio(self):
        """ide vazio retorna None"""
        assert extrair_data_emissao_ide({}) is None

    def test_ide_none(self):
        """ide None retorna None"""
        assert extrair_data_emissao_ide(None) is None  # type: ignore

    def test_ide_sem_data(self):
        """ide sem dhEmi/dEmi retorna None"""
        ide = {"nNF": "123", "cUF": "41"}
        assert extrair_data_emissao_ide(ide) is None


class TestExtrairImpostosItem:
    """Testes para extrair_impostos_item."""

    def test_icms_icms00(self):
        """ICMS00 extrai vBC, pICMS, vICMS"""
        item = {
            "imposto": {
                "ICMS": {
                    "ICMS00": {
                        "vBC": "100.50",
                        "pICMS": "18.00",
                        "vICMS": "18.09",
                    }
                }
            }
        }
        r = extrair_impostos_item(item)
        assert r["icms_bc"] == 100.50
        assert r["icms_aliq"] == 18.0
        assert r["icms_valor"] == 18.09

    def test_icms_st(self):
        """ICMS com vBCST, vICMSST"""
        item = {
            "imposto": {
                "ICMS": {
                    "ICMS00": {
                        "vBC": "100.00",
                        "vBCST": "50.00",
                        "pICMSST": "18.00",
                        "vICMSST": "9.00",
                    }
                }
            }
        }
        r = extrair_impostos_item(item)
        assert r["icms_st_bc"] == 50.0
        assert r["icms_st_aliq"] == 18.0
        assert r["icms_st_valor"] == 9.0

    def test_pis_cofins(self):
        """PIS e COFINS extraídos"""
        item = {
            "imposto": {
                "PIS": {
                    "PISAliq": {"vBC": "100.00", "pPIS": "1.65", "vPIS": "1.65"}
                },
                "COFINS": {
                    "COFINSAliq": {"vBC": "100.00", "pCOFINS": "7.60", "vCOFINS": "7.60"}
                },
            }
        }
        r = extrair_impostos_item(item)
        assert r["pis_bc"] == 100.0
        assert r["pis_aliq"] == 1.65
        assert r["pis_valor"] == 1.65
        assert r["cofins_bc"] == 100.0
        assert r["cofins_aliq"] == 7.6
        assert r["cofins_valor"] == 7.6

    def test_item_sem_imposto(self):
        """Item sem imposto: valores numéricos são None ou 0 (safe_float)"""
        r = extrair_impostos_item({})
        # ICMS sem bloco fica None; PIS/COFINS com dict vazio podem devolver 0.0
        assert r["icms_bc"] is None or r["icms_bc"] == 0
        assert r["icms_valor"] is None or r["icms_valor"] == 0
        assert r["pis_valor"] is None or r["pis_valor"] == 0
        assert r["cofins_valor"] is None or r["cofins_valor"] == 0

    def test_imposto_vazio(self):
        """imposto vazio não quebra"""
        r = extrair_impostos_item({"imposto": {}})
        assert r["icms_bc"] is None
        assert r["icms_valor"] is None


class TestParseXMLCompleto:
    """Testes de parsing de XML completo com xmltodict."""

    def test_xml_nfe_dhemi_extrai_data(self):
        """XML com dhEmi: extrai data e estrutura correta"""
        d = xmltodict.parse(XML_NFE_MINIMO)
        inf = d["nfeProc"]["NFe"]["infNFe"]
        ide = inf["ide"]
        data = extrair_data_emissao_ide(ide)
        assert data == "2024-03-15"
        assert ide["nNF"] == "123456"

    def test_xml_nfe_demi_extrai_data(self):
        """XML com dEmi (ISO): extrai data"""
        d = xmltodict.parse(XML_NFE_DEMI)
        ide = d["nfeProc"]["NFe"]["infNFe"]["ide"]
        data = extrair_data_emissao_ide(ide)
        assert data == "2025-01-20"

    def test_xml_nfe_data_br_extrai_data(self):
        """XML com dEmi (15/06/2024): extrai data"""
        d = xmltodict.parse(XML_NFE_DATA_BR)
        ide = d["nfeProc"]["NFe"]["infNFe"]["ide"]
        data = extrair_data_emissao_ide(ide)
        assert data == "2024-06-15"

    def test_xml_nfe_det_extrai_impostos(self):
        """XML com det: extrai impostos do item"""
        d = xmltodict.parse(XML_NFE_MINIMO)
        inf = d["nfeProc"]["NFe"]["infNFe"]
        det = inf["det"]
        # xmltodict: 1 det -> dict com @nItem, prod, imposto; vários -> list
        item = det[0] if isinstance(det, list) else det
        imposto = item.get("imposto", {}) if isinstance(item, dict) else {}
        item_para_impostos = {"imposto": imposto}
        r = extrair_impostos_item(item_para_impostos)
        assert r["icms_bc"] == 20.0
        assert r["icms_valor"] == 3.6
        assert r["pis_valor"] == 0.33
        assert r["cofins_valor"] == 1.52


def run_tests():
    """Executa todos os testes manualmente (sem pytest)."""
    results = []
    for cls in [TestExtrairDataEmissao, TestExtrairImpostosItem, TestParseXMLCompleto]:
        for name in dir(cls):
            if name.startswith("test_"):
                meth = getattr(cls(), name)
                try:
                    meth()
                    results.append((name, True, None))
                except Exception as e:
                    results.append((name, False, str(e)))

    ok = sum(1 for _, passed, _ in results if passed)
    total = len(results)
    for name, passed, err in results:
        status = "OK" if passed else "FALHOU"
        extra = f" - {err}" if err else ""
        print(f"  {status}: {name}{extra}")
    print(f"\n{ok}/{total} testes passaram.")
    return ok == total


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
