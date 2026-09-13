from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class ConversationState:
    session_id: str
    clinic_id: str
    language: str = "english"
    history: list[dict[str, str]] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    last_intent: str | None = None

    def add_turn(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self.history = self.history[-20:]

    def update(self, **values: Any) -> None:
        self.slots.update({k: v for k, v in values.items() if v is not None})

    def snapshot(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "clinic_id": self.clinic_id,
                "language": self.language, "last_intent": self.last_intent,
                "slots": dict(self.slots), "turns": len(self.history)}
