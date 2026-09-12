"""Central NEXORA identity policy and reply safety checks."""

import re

NEXORA_INTRODUCTION = (
    "I am NEXORA, your personal AI workspace. I can help you discuss ideas, plan tasks, "
    "organize work, answer questions, and complete approved actions."
)
NEXORA_PROJECT_DESCRIPTION = (
    "A goal-based personal AI workspace that helps users plan, organize, research, create, and verify tasks."
)
SAFE_IDENTITY_FALLBACK = "I am NEXORA, your personal AI workspace. Please ask your question again."

NEXORA_IDENTITY_POLICY = """You are NEXORA, a goal-based personal AI workspace.

Always identify yourself only as NEXORA.

Never introduce yourself as an external AI provider, model, chatbot, language model, or company product.

Never say phrases such as:
- “I am Gemini”
- “I am built by Google”
- “I am ChatGPT”
- “I am an AI language model”
- “As an AI model”
- “I am powered by…”

When a user asks, “What are you?”, reply:

“I am NEXORA, your personal AI workspace. I can help you discuss ideas, plan tasks, organize work, answer
questions, and complete approved actions.”

When the user asks about the NEXORA project, explain NEXORA as:
“A goal-based personal AI workspace that helps users plan, organize, research, create, and verify tasks.”

Use clear, confident and simple English."""

IDENTITY_REWRITE_REQUEST = (
    "Rewrite your previous answer so it follows the NEXORA Identity Policy exactly. Keep the useful answer, "
    "identify yourself only as NEXORA, and remove any claim that NEXORA is an external provider, model, "
    "chatbot, language model, or company product. Return only the rewritten answer."
)

_SERVICE_TERMS = re.compile(
    r"\b(gemini|openai|chatgpt|google|claude|anthropic|copilot|ollama|llama|language model|chatbot|ai model|"
    r"external ai provider|artificial intelligence|large language model|powered by)\b",
    re.IGNORECASE,
)
_FALSE_SELF_IDENTIFICATION = re.compile(
    r"\b(?:i\s*(?:am|'m)|as)\s+(?:an?\s+|google(?:'s)?\s+)?"
    r"(?:gemini|chatgpt|claude|copilot|llama|an?\s+ai|ai(?:\s+language)?\s+model|ai assistant|"
    r"artificial intelligence|(?:large\s+)?language model|chatbot)\b|"
    r"\bi\s*(?:am|'m)\s+(?:built|created|developed|made|powered)\s+by\b|"
    r"\bnexora\s+is\s+(?:an?\s+)?(?:gemini|chatgpt|claude|copilot|language model|chatbot|ai model)\b|"
    r"\bnexora\s+is\s+(?:built|created|developed|made|powered)\s+by\b",
    re.IGNORECASE,
)
_PROVIDER_QUESTION = re.compile(
    r"\b(gemini|openai|chatgpt|google|claude|anthropic|copilot|ollama|llama|ai service|ai provider|"
    r"backend service|language model|chatbot|what model|which model|artificial intelligence|ai)\b",
    re.IGNORECASE,
)


def allows_service_discussion(user_text: str) -> bool:
    """Return whether the user explicitly asked about AI services or models."""
    return bool(_PROVIDER_QUESTION.search(user_text))


def is_identity_question(user_text: str) -> bool:
    """Return whether the prompt asks directly for NEXORA's identity or product description."""
    normalized = re.sub(r"[^a-z0-9 ]+", "", user_text.lower()).strip()
    return normalized in {
        "who are you",
        "what are you",
        "what is nexora",
        "tell me about nexora",
        "tell me about this platform",
    }


def violates_identity(reply: str, user_text: str) -> bool:
    """Reject false self-identification and unsolicited provider disclosure."""
    if _FALSE_SELF_IDENTIFICATION.search(reply):
        return True
    return not allows_service_discussion(user_text) and bool(_SERVICE_TERMS.search(reply))
