import json
import httpx
from app.config import Config
from app.logging_config import logger

class LLMService:
    MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen/qwen3.6-27b",
        "qwen/qwen3-32b",
        "allam-2-7b"
    ]
    
    @classmethod
    def call(cls, prompt: str, system_prompt: str = None, json_mode: bool = False) -> str:
        """Sends a request to the Groq Chat Completions API with fallback logic and backoff retries."""
        if not Config.GROQ_API_KEY:
            logger.error("Groq API key not found in configuration.")
            return "Error: GROQ_API_KEY is not set in the configuration environment."

        headers = {
            "Authorization": f"Bearer {Config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        if json_mode:
            data["response_format"] = {"type": "json_object"}

        import time

        # Try models in priority sequence
        for model in cls.MODELS:
            data["model"] = model
            
            max_retries = 3
            backoff_base = 2.0
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Invoking Groq model: {model} (JSON mode: {json_mode}, attempt: {attempt + 1})...")
                    response = httpx.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        resp_json = response.json()
                        content = resp_json["choices"][0]["message"]["content"]
                        logger.info(f"Groq invocation successful using {model}.")
                        return content
                    elif response.status_code == 429:
                        sleep_time = backoff_base ** attempt
                        logger.warning(f"Groq model {model} rate limited (429). Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.warning(f"Groq API returned status {response.status_code} for model {model}: {response.text}")
                        break
                except Exception as e:
                    logger.error(f"Error calling Groq API with model {model}: {e}")
                    sleep_time = backoff_base ** attempt
                    if attempt < max_retries - 1:
                        time.sleep(sleep_time)
                        continue
                    break
                
        # If all models fail
        logger.critical("All configured Groq models failed to return a response.")
        return "Error: Unable to contact LLM provider. Please check connections or API keys."
        
    @classmethod
    def call_stream(cls, prompt: str, system_prompt: str = None):
        """Sends a request to the Groq Chat Completions API and streams chunks of tokens with fallback retries."""
        if not Config.GROQ_API_KEY:
            logger.error("Groq API key not found in configuration.")
            yield "Error: GROQ_API_KEY is not set."
            return

        headers = {
            "Authorization": f"Bearer {Config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
            "stream": True
        }

        import time

        # Try models in priority sequence
        for model in cls.MODELS:
            data["model"] = model
            
            max_retries = 3
            backoff_base = 2.0
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Invoking Groq model stream: {model} (attempt: {attempt + 1})...")
                    with httpx.stream(
                        "POST",
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30.0
                    ) as response:
                        if response.status_code == 200:
                            for line in response.iter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(data_str)
                                        delta = chunk["choices"][0]["delta"]
                                        if "content" in delta:
                                            yield delta["content"]
                                    except Exception:
                                        pass
                            return # Successful stream complete
                        elif response.status_code == 429:
                            sleep_time = backoff_base ** attempt
                            logger.warning(f"Groq stream model {model} rate limited (429). Retrying in {sleep_time:.2f}s...")
                            time.sleep(sleep_time)
                            continue
                        else:
                            logger.warning(f"Groq stream returned status {response.status_code} for {model}")
                            break
                except Exception as e:
                    logger.error(f"Error calling Groq stream API with model {model}: {e}")
                    sleep_time = backoff_base ** attempt
                    if attempt < max_retries - 1:
                        time.sleep(sleep_time)
                        continue
                    break
        yield "Error: All stream calls failed."

    @classmethod
    def call_json(cls, prompt: str, system_prompt: str = None) -> dict:
        """Helper to invoke LLM in JSON mode and parse the output immediately."""
        raw = cls.call(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Failed to parse JSON response from LLM: {e}. Raw content: {raw}")
            try:
                cleaned = raw.strip()
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                return json.loads(cleaned)
            except Exception:
                return {}
