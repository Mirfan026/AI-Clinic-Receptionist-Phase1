"""Optional live smoke test: python scripts/test_groq_connection.py.

Reads exported environment variables (including GROQ_API_KEY); does not load
.env automatically. Importing this script or running pytest makes no API call.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import get_settings
from app.llm.base import LLMError
from app.llm.groq_client import GroqLLMClient


def main() -> int:
    settings = get_settings()
    key = settings.groq_api_key

    def safe_print(text):
        print(text.replace(key, "[redacted]") if key else text)

    safe_print(f"Model: {settings.groq_model}")
    if not key:
        safe_print("FAILURE: Set GROQ_API_KEY in your environment first.")
        return 1

    client = GroqLLMClient(settings)
    try:
        response = client.generate([
            {"role": "user", "content": "Reply with a short greeting only."},
        ])
    except LLMError as exc:
        safe_print(f"FAILURE: {exc}")
        return 1
    finally:
        try:
            client.close()
        except LLMError:
            safe_print("Client cleanup failed.")

    safe_print("SUCCESS")
    safe_print(f"Response: {response}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
