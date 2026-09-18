import logging
import ollama
from config import settings

logger = logging.getLogger(__name__)

class LocalLLMManager:
    """Manager for local LLM operations using official Ollama Python SDK."""

    def __init__(self, host: str = None, model: str = None):
        self.host = host or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_MODEL
        self.client = ollama.Client(host=self.host)

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call local Ollama instance using official python SDK."""
        try:
            response = self.client.generate(
                model=self.model,
                system=system_prompt,
                prompt=user_prompt,
                keep_alive="10m",
                options={
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            )
            return response.get("response", "").strip()
        except Exception as e:
            logger.error(f"Error calling Ollama SDK: {e}")
            return f"[Ollama LLM Error: Ensure Ollama is running (`ollama serve`) and model '{self.model}' is pulled. Error details: {str(e)}]"

    def summarize_email(self, subject: str, sender: str, body: str) -> str:
        """Generate a concise summary of an incoming email."""
        system_prompt = (
            "You are an intelligent email executive assistant. "
            "Your task is to summarize the key points of the incoming email concisely in 2-3 clear bullet points."
        )
        user_prompt = f"Subject: {subject}\nFrom: {sender}\n\nEmail Body:\n{body}\n\nPlease summarize this email:"
        return self._call_ollama(system_prompt, user_prompt)

    def generate_draft(self, subject: str, sender: str, body: str, rag_context: str = "") -> str:
        """Generate a context-aware, personalized email reply draft."""
        system_prompt = (
            "You are acting as the personal assistant drafting email replies on behalf of the user. "
            "Write a natural, polite, and direct email reply. Match the user's personal style based on past interaction history. "
            "Do NOT include generic AI clichés like 'I hope this email finds you well'. Output ONLY the body of the proposed email reply."
        )
        user_prompt = f"Subject: {subject}\nFrom: {sender}\n\nIncoming Email:\n{body}\n\n"
        if rag_context:
            user_prompt += f"Relevant Past Emails & Context for this Contact:\n{rag_context}\n\n"
        user_prompt += "Draft a response on behalf of the user:"

        return self._call_ollama(system_prompt, user_prompt)

    def revise_draft(self, subject: str, sender: str, original_email: str, previous_draft: str, feedback: str) -> str:
        """Revise a draft response based on user's voice note / feedback instructions."""
        system_prompt = (
            "You are an assistant revising an email draft based on explicit user feedback instructions. "
            "Apply the requested changes to the previous draft accurately and maintain a clear, natural writing tone. "
            "Output ONLY the revised email reply."
        )
        user_prompt = (
            f"Subject: {subject}\nFrom: {sender}\n\n"
            f"Original Email:\n{original_email}\n\n"
            f"Previous Draft Reply:\n{previous_draft}\n\n"
            f"User Spoken Instructions / Feedback:\n\"{feedback}\"\n\n"
            "Generate the updated revised email reply:"
        )

        return self._call_ollama(system_prompt, user_prompt)

llm_manager = LocalLLMManager()
