"""Quantize the Typhoon ASR ONNX model to int8 (dynamic, weights only).

    venv\\Scripts\\python.exe scripts\\quantize_typhoon.py

Writes *-int8.onnx next to the fp32 files in models/typhoon-asr-realtime/.
Dev-only: needs `pip install onnx`; the app itself only needs onnxruntime.
Check accuracy afterwards: scripts\\stt_bench.py bench --models typhoon,typhoon-int8
"""
import os
import time

from onnxruntime.quantization import QuantType, quantize_dynamic

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "typhoon-asr-realtime")
FILES = ["encoder-fastconformer-quran-ar.onnx", "decoder_joint-fastconformer-quran-ar.onnx"]


def main():
    for name in FILES:
        src = os.path.join(MODEL_DIR, name)
        dst = src.replace(".onnx", "-int8.onnx")
        t0 = time.perf_counter()
        quantize_dynamic(src, dst, weight_type=QuantType.QInt8)
        print(f"{name}: {os.path.getsize(src) / 1e6:.0f} MB -> {os.path.getsize(dst) / 1e6:.0f} MB"
              f" ({time.perf_counter() - t0:.0f}s)")


if __name__ == "__main__":
    main()
