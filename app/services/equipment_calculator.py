"""Pure equipment snapshot cost calculation."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class EquipmentCalculationError(ValueError):
    pass


def calculate_equipment_total(usage_quantity, agreed_unit_rate):
    if agreed_unit_rate is None:
        return None
    try:
        quantity = Decimal(str(usage_quantity))
        rate = Decimal(str(agreed_unit_rate))
    except (InvalidOperation, ValueError) as exc:
        raise EquipmentCalculationError("invalid equipment calculation input") from exc
    if not quantity.is_finite() or not rate.is_finite() or quantity < 0 or rate < 0:
        raise EquipmentCalculationError("equipment values must be finite and non-negative")
    return (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
