"""Pure material-quantity and cost calculations."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


QUANTITY_PLACES = Decimal("0.001")
MONEY_PLACES = Decimal("0.01")


class MaterialCalculationError(ValueError):
    """Raised when calculation inputs are not finite non-negative numbers."""


@dataclass(frozen=True)
class MaterialCalculation:
    calculated_quantity: Decimal
    effective_quantity: Decimal
    material_total: Decimal | None


def _non_negative_decimal(value: object, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite() or decimal_value < 0:
        raise MaterialCalculationError(f"{field_name} must be finite and non-negative")
    return decimal_value


def calculate_material_requirement(
    *,
    work_quantity: object,
    consumption_rate: object,
    waste_percentage: object = 0,
    approved_quantity: object | None = None,
    unit_price: object | None = None,
) -> MaterialCalculation:
    """Calculate rounded required quantity, effective quantity, and total cost."""
    work = _non_negative_decimal(work_quantity, "work_quantity")
    rate = _non_negative_decimal(consumption_rate, "consumption_rate")
    waste = _non_negative_decimal(waste_percentage, "waste_percentage")

    calculated = (work * rate * (Decimal("1") + waste / Decimal("100"))).quantize(
        QUANTITY_PLACES,
        rounding=ROUND_HALF_UP,
    )
    effective = (
        _non_negative_decimal(approved_quantity, "approved_quantity").quantize(
            QUANTITY_PLACES,
            rounding=ROUND_HALF_UP,
        )
        if approved_quantity is not None
        else calculated
    )
    total = None
    if unit_price is not None:
        price = _non_negative_decimal(unit_price, "unit_price")
        total = (effective * price).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)

    return MaterialCalculation(
        calculated_quantity=calculated,
        effective_quantity=effective,
        material_total=total,
    )
