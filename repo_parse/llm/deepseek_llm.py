from openai import OpenAI
from dotenv import load_dotenv
import os

from repo_parse.llm.llm import LLM

load_dotenv()

api_base = os.getenv("API_BASE")
api_key = os.getenv("API_KEY")
model_name = os.getenv("MODEL_NAME")

class DeepSeekLLM(LLM):
    def __init__(self, api_key=api_key, api_base=api_base, model_name=model_name):
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        self.model_name = model_name
    
    def __str__(self) -> str:
        return "DeepSeek"

    def chat(self, system_prompt, user_input, model=None, max_tokens=4096, temperature=0, stream=True):
        history_openai_format = [{"role": "system", "content": system_prompt}]
        history_openai_format.append({"role": "user", "content": user_input})
        
        if model is None:
            model = self.model_name
        
        response_stream = self.client.chat.completions.create(
            model=model,
            messages=history_openai_format,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )
        
        return self._process_stream(response_stream)

    def _process_stream(self, stream):
        full_response = ""
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            full_response += content
        print("\n")
        return full_response
    
if __name__ == "__main__":
    # Example usage
    deepseek_llm = DeepSeekLLM()
    response = deepseek_llm.chat(
        system_prompt="You are a helpful assistant",
        user_input="Hello"
    )
    print("Final Response:", response)