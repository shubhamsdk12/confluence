from abc import ABC, abstractmethod
from app.config import settings
from app.utils.logger import rag_logger


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        """Generate LLM response given a system and user prompt."""
        pass


class GroqProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI

        if not settings.groq_api_key:
            rag_logger.warning("GROQ_API_KEY is not set in environment variables.")

        self.client = OpenAI(
            api_key=settings.groq_api_key or "DUMMY_KEY",
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = "llama-3.3-70b-versatile"
        rag_logger.info(f"Initialized GroqProvider with model: {self.model}")

    def generate(self, system: str, user: str) -> str:
        if not settings.groq_api_key or settings.groq_api_key == "your_key_here":
            return (
                '{"explanation": "LLM key is missing. Please configure GROQ_API_KEY in the environment.", '
                '"regulation_cited": "N/A", '
                '"fix_action": "Add GROQ_API_KEY to your .env file."}'
            )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            rag_logger.error(f"Groq API call failed: {e}")
            # Fallback mock explanation
            return (
                f'{{"explanation": "Failed to call Groq API. Error: {str(e)}", '
                f'"regulation_cited": "N/A", '
                f'"fix_action": "Verify your API key and connection."}}'
            )


class OpenAIProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI

        if not settings.openai_api_key:
            rag_logger.warning(
                "OPENAI_API_KEY is not set in environment variables."
            )

        self.client = OpenAI(api_key=settings.openai_api_key or "DUMMY_KEY")
        self.model = "gpt-4o-mini"
        rag_logger.info(f"Initialized OpenAIProvider with model: {self.model}")

    def generate(self, system: str, user: str) -> str:
        if not settings.openai_api_key or settings.openai_api_key == "your_key_here":
            return (
                '{"explanation": "LLM key is missing. Please configure OPENAI_API_KEY in the environment.", '
                '"regulation_cited": "N/A", '
                '"fix_action": "Add OPENAI_API_KEY to your .env file."}'
            )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            rag_logger.error(f"OpenAI API call failed: {e}")
            # Fallback mock explanation
            return (
                f'{{"explanation": "Failed to call OpenAI API. Error: {str(e)}", '
                f'"regulation_cited": "N/A", '
                f'"fix_action": "Verify your API key and connection."}}'
            )


_provider_instance = None


def get_provider() -> LLMProvider:
    global _provider_instance
    if _provider_instance is None:
        provider_name = settings.llm_provider.lower()
        if provider_name == "groq":
            _provider_instance = GroqProvider()
        elif provider_name == "openai":
            _provider_instance = OpenAIProvider()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Supported: groq, openai"
            )
    return _provider_instance
