from app.tools.doctors import get_doctors
from app.tools.services import get_services
from app.tools.availability import check_availability
from app.tools.booking import book_appointment

TOOL_REGISTRY = {
    "get_doctors": get_doctors,
    "get_services": get_services,
    "check_availability": check_availability,
    "book_appointment": book_appointment,
}

FORBIDDEN_DB_ACCESS = "The agent has no direct database interface; all operational data access is through validated tools."
