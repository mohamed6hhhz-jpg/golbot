import re

with open('Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    content = f.read()

patch_code = """
# =========================================================================
# AI Client Patch: Redirect all local Groq calls to the robust AI manager
# =========================================================================
try:
    from Goldbot.ai_client import generate_robust_ai_response, get_api_keys
except ImportError:
    from ai_client import generate_robust_ai_response, get_api_keys

class _RobustCompletions:
    def create(self, messages, model=None, temperature=0.1, max_tokens=700, **kwargs):
        system_prompt = messages[0]["content"] if len(messages) > 0 else ""
        user_prompt = messages[1]["content"] if len(messages) > 1 else ""
        
        # We rely on generate_robust_ai_response which handles 429, failovers, and OpenAI automatically.
        content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens, temperature)
        
        # Create a dummy response object to match the expected format: resp.choices[0].message.content
        class _Message:
            def __init__(self, content):
                self.content = content
        class _Choice:
            def __init__(self, content):
                self.message = _Message(content)
        class _Response:
            def __init__(self, content):
                self.choices = [_Choice(content)]
                
        return _Response(content)

class _RobustChat:
    def __init__(self):
        self.completions = _RobustCompletions()

class RobustAIClient:
    def __init__(self, api_key=None, **kwargs):
        self.chat = _RobustChat()

# Override Groq with our completely managed robust client
Groq = RobustAIClient
GROQ_MODELS = ["auto-managed"]  # Force loop to only run once per report
# =========================================================================
"""

# Replace the existing UniversalAIClient import with our patch
content = re.sub(
    r"try:\s*from Goldbot\.ai_client import UniversalAIClient as Groq, get_api_keys\s*except ImportError:\s*from ai_client import UniversalAIClient as Groq, get_api_keys",
    patch_code,
    content,
    flags=re.MULTILINE
)

# We also need to remove the old GROQ_MODELS definition if it exists
content = re.sub(r"GROQ_MODELS\s*=\s*\[.*?\]", "", content, flags=re.DOTALL, count=1)

with open('Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch applied to bot_spot.py")
