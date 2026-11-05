import time
from llama_cpp import Llama
from datetime import datetime 

# Path to the Q8 GGUF model
MODEL_PATH = "../Qwen 2.5/Q8/qwen2.5-coder-1.5b-instruct-q8_0.gguf"


def main():
    print(f"Loading model from {MODEL_PATH}...")
    
    
    # Initialize the model
    # n_gpu_layers=-1 offloads all layers to the GPU
    # n_ctx=2048 sets the context window size
    llm = Llama(
        model_path=MODEL_PATH,
        n_gpu_layers=-1, 
        n_ctx=4096,
        verbose=False
    )
    print(datetime.now().strftime("%H:%M:%S"))
    print("\nModel loaded successfully! GPU should be fully utilized.")
    print(datetime.now().strftime("%H:%M:%S"))
    
    # Prepare a simple coding prompt
    prompt = "<|im_start|>system\nYou are a helpful AI coding assistant.<|im_end|>\n<|im_start|>user\nWrite a Python function to calculate the Fibonacci sequence up to n.<|im_end|>\n<|im_start|>assistant\n"
    
    print("\nGenerating response...\n" + "-"*40)
    print(datetime.now().strftime("%H:%M:%S"))
    start_time = time.time()
    
    # Run inference
    response = llm(
        prompt,
        max_tokens=256,
        stop=["<|im_end|>"],
        echo=False
    )
    
    end_time = time.time()
    
    generated_text = response["choices"][0]["text"]
    total_tokens = response["usage"]["completion_tokens"]
    generation_time = end_time - start_time
    tokens_per_second = total_tokens / generation_time
    
    print(generated_text.strip())
    print(datetime.now().strftime("%H:%M:%S"))
    print("-" * 40)
    
    print("\n=== Performance Benchmark ===")
    print(f"Total Tokens Generated : {total_tokens}")
    print(f"Time Taken             : {generation_time:.2f} seconds")
    print(f"Speed                  : {tokens_per_second:.2f} tokens/second")

    print(datetime.now().strftime("%H:%M:%S"))

if __name__ == "__main__":
    main()
