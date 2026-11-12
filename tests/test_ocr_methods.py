import io
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from Text_function.ocr_methods import executar_gemini, executar_tesseract


def test_tesseract_converte_caixas_para_coordenadas_da_imagem_original():
    pytesseract_fake = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        image_to_data=lambda imagem, lang, output_type: {
            "text": ["Serial"],
            "conf": ["90"],
            "left": ["20"],
            "top": ["40"],
            "width": ["60"],
            "height": ["20"],
        },
    )
    imagem = SimpleNamespace(shape=(200, 400, 3))

    with patch.dict(sys.modules, {"pytesseract": pytesseract_fake}):
        texto, resultados = executar_tesseract(imagem, 200, 100)

    assert texto == "Serial"
    assert resultados == [
        ([[10, 20], [40, 20], [40, 30], [10, 30]], "Serial", 0.9)
    ]


def test_gemini_converte_caixa_normalizada_para_pixels():
    resposta = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "detections": [{
                            "text": "Serial 123456",
                            "box": [0.1, 0.2, 0.9, 0.8],
                            "confidence": 0.95,
                        }]
                    })
                }]
            }
        }]
    }

    class OpenCVFake:
        @staticmethod
        def imencode(extensao, imagem):
            return True, b"imagem-de-teste"

    imagem = SimpleNamespace(shape=(100, 200, 3))
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with patch(
            "urllib.request.urlopen",
            return_value=io.BytesIO(json.dumps(resposta).encode("utf-8")),
        ):
            texto, resultados = executar_gemini(imagem, OpenCVFake)

    assert texto == "Serial 123456"
    assert resultados == [
        ([[20, 20], [180, 20], [180, 80], [20, 80]], "Serial 123456", 0.95)
    ]
