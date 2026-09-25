import time
from optimum.intel.openvino import OVModelForFeatureExtraction
from transformers import AutoTokenizer

print("Checking available OpenVINO devices...")
import openvino as ov
core = ov.Core()
print("Available devices:", core.available_devices)

print("\nLoading embedding model on iGPU...")
try:
    start = time.time()
    model = OVModelForFeatureExtraction.from_pretrained(
        "OpenVINO/qwen3-embedding-0.6b-int8-ov",
        device="GPU"
    )
    print(f"SUCCESS: Loaded on iGPU in {time.time()-start:.2f}s")
except Exception as e:
    print(f"iGPU failed: {e}")
