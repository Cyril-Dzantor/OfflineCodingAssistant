import time
from llama_cpp import Llama

from assistant.config import settings
from assistant.utils.logger import app_logger

class ModelInterface:
    def __init__(self):
        self.llm = None
        self.load_model()

    def load_model(self):
        """Initializes the Llama model with settings from the config file."""
        app_logger.info(f"Loading model from {settings.MODEL_PATH}...")
        start_time = time.time()
        
        try:
            self.llm = Llama(
                model_path=settings.MODEL_PATH,
                n_gpu_layers=settings.N_GPU_LAYERS,
                n_ctx=settings.CONTEXT_WINDOW,
                verbose=False
            )
            elapsed = time.time() - start_time
            app_logger.info(f"Model loaded successfully in {elapsed:.2f} seconds.")
        except Exception as e:
            app_logger.error(f"Failed to load model: {e}")
            raise e

    def generate_stream(self, messages: list):
        """
        Takes a list of conversation messages and yields the response token-by-token.
        """
        if not self.llm:
            raise RuntimeError("Model is not loaded.")

        # create_chat_completion automatically applies the ChatML format (like <|im_start|>)
        # because the formatting rules are embedded inside the Qwen GGUF file!
        response_generator = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=settings.MAX_TOKENS,
            temperature=settings.TEMPERATURE,
            stream=True
        )

        for chunk in response_generator:
            # Extract the text token from the chunk
            delta = chunk['choices'][0].get('delta', {})
            if 'content' in delta:
                yield delta['content']
