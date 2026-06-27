import os
import sys
import time

def run_verification():
    print("===============================")
    print("GPU Verification Report")
    print("===============================\n")

    # 1. Python Version
    print(f"Python Version: {sys.version.split()[0]}")

    # 2. PyTorch Version & Build
    import torch
    print(f"PyTorch Version: {torch.__version__}")
    # torch build
    torch_build = getattr(torch, "__config__", None)
    if torch_build:
        # Get brief build string
        build_str = "CUDA " + torch.version.cuda if torch.version.cuda else "CPU"
    else:
        build_str = "Unknown"
    print(f"Torch Build: {build_str}")

    # 3. CUDA Status
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")

    if cuda_available:
        # CUDA Runtime Version
        cuda_ver = torch.version.cuda
        print(f"CUDA Runtime Version: {cuda_ver}")
        # cuDNN Version
        cudnn_ver = torch.backends.cudnn.version()
        print(f"cuDNN Version: {cudnn_ver}")
        # GPU Name
        gpu_name = torch.cuda.get_device_name(0)
        print(f"GPU Name: {gpu_name}")
        # Compute Capability
        cc = torch.cuda.get_device_capability(0)
        cc_str = f"{cc[0]}.{cc[1]}"
        print(f"Compute Capability: {cc_str}")
    else:
        print("CUDA Runtime Version: N/A")
        print("cuDNN Version: N/A")
        print("GPU Name: N/A")
        print("Compute Capability: N/A")

    print("\nModel:\nBAAI/bge-m3")

    model = None
    model_device = "N/A"
    forward_pass_status = "N/A"
    embedding_test_status = "N/A"
    chunks_embedded = 0
    embedding_speed = "N/A"
    peak_gpu_mem = "N/A"
    result = "FAIL"

    try:
        from app.embeddings.vector_store import VectorStoreManager
        from app.config import Config

        print("Loading model BAAI/bge-m3...")
        start_load = time.time()
        model = VectorStoreManager.get_model()
        load_time = time.time() - start_load
        print(f"Model loaded in {load_time:.2f}s")

        model_device = str(next(model.parameters()).device)
        print(f"Model Device: {model_device}")

        # Forward Pass
        print("Performing forward pass test...")
        dummy_inputs = ["This is a test prompt to verify the GPU environment forward pass."]
        # Get tokenized inputs
        features = model.tokenize(dummy_inputs)
        # Move features to model device
        device = next(model.parameters()).device
        for k, v in features.items():
            if isinstance(v, torch.Tensor):
                features[k] = v.to(device)

        with torch.no_grad():
            out = model.forward(features)
        forward_pass_status = "SUCCESS"
        print(f"Forward Pass: {forward_pass_status}")

        # Embedding test
        print("Performing embedding test...")
        test_chunks = [
            f"Groundwater monitoring data row {i} shows normal water level fluctuations."
            for i in range(10)
        ]
        
        # Track memory and speed
        if cuda_available:
            torch.cuda.reset_peak_memory_stats()
            
        start_time = time.time()
        with torch.inference_mode():
            # If using GPU, try mixed precision
            if "cuda" in str(device):
                with torch.amp.autocast("cuda"):
                    embeddings = model.encode(test_chunks, batch_size=4, convert_to_numpy=True)
            else:
                embeddings = model.encode(test_chunks, batch_size=4, convert_to_numpy=True)
                
        elapsed = time.time() - start_time
        chunks_embedded = len(test_chunks)
        speed = chunks_embedded / elapsed if elapsed > 0 else 0
        embedding_speed = f"{speed:.2f} chunks/sec"
        embedding_test_status = "SUCCESS"
        
        if cuda_available:
            peak_gpu_mem = f"{torch.cuda.max_memory_allocated() / (1024 * 1024):.2f} MB"
        else:
            peak_gpu_mem = "N/A"
            
        print(f"Embedding Test: {embedding_test_status}")
        print(f"Chunks Embedded: {chunks_embedded}")
        print(f"Embedding Speed: {embedding_speed}")
        print(f"Peak GPU Memory: {peak_gpu_mem}")

        # If we got here and device is cuda, it's a pass
        if cuda_available and "cuda" in model_device:
            result = "PASS"
        else:
            result = "FAIL (Model not on CUDA or CUDA not available)"

    except Exception as e:
        print(f"Verification encountered error: {e}")
        import traceback
        traceback.print_exc()
        result = "FAIL"

    print("\nResult:")
    print(result)
    print("===============================")

if __name__ == "__main__":
    run_verification()
