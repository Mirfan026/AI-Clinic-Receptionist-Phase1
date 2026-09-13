from .doctors import get_doctors
from .services import get_services
from .availability import check_availability
from .booking import book_appointment


TOOL_REGISTRY = {
    "get_doctors": get_doctors,
    "get_services": get_services,
    "check_availability": check_availability,
    "book_appointment": book_appointment,
}