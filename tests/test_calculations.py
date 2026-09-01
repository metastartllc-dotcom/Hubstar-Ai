import pytest
from app.validators.units import UnitNormalizer
from app.validators.double_count import DoubleCountValidator
from app.services.cost_engine import CostEngine
from app.services.transport import TransportCalculator
from decimal import Decimal

def test_unit_conversion():
    assert UnitNormalizer.normalize("тн") == "тн"
    assert UnitNormalizer.normalize("тонн") == "тн"
    assert UnitNormalizer.normalize("м2") == "м²"
    
    val = UnitNormalizer.convert(1.5, "тн", "кг")
    assert val == 1500.0

def test_cost_engine():
    result = CostEngine.calculate_work_cost(
        quantity=Decimal('5100.0'),
        labor_unit_rate=Decimal('209.526'), # arbitrary test value
        material_cost=Decimal('45900000') + Decimal('25245000') + Decimal('4462500'),
        equipment_cost=Decimal('0')
    )
    # Direct Cost = Labor(5100 * 209.526) + Materials
    assert result["material_cost"] == Decimal('75607500')

def test_transport_trips():
    result = TransportCalculator.calculate_trips_and_cost(
        package_quantity=113,
        weight_per_package_kg=10.0, # 1130 total
        volume_per_package_m3=0.06, # 6.78 total
        vehicle_payload_kg=500.0,
        vehicle_volume_m3=2.0,
        one_way_distance_km=15.0,
        distance_multiplier=1.0,
        base_tariff=Decimal('1000'),
        road_fee_per_trip=Decimal('10000')
    )
    
    assert result["total_weight_kg"] == 1130.0
    assert round(result["total_volume_m3"], 2) == 6.78
    assert result["trips_by_weight"] == 3  # 1130 / 500 = 2.26 -> 3
    assert result["trips_by_volume"] == 4  # 6.78 / 2 = 3.39 -> 4
    assert result["final_trip_count"] == 4
    assert result["limiting_factor"] == "volume"

class DummyEquipment:
    def __init__(self, op, fuel, deliv):
        self.operator_included = op
        self.fuel_included = fuel
        self.delivery_included = deliv

def test_machinery_double_count():
    eq = DummyEquipment(True, True, True)
    warnings = DoubleCountValidator.check_equipment(eq, work_item_includes_operator=True, work_item_includes_fuel=True)
    assert len(warnings) == 2
    assert "Operator cost is included" in warnings[0]
    
def test_facade_calculation():
    # Test based on the issue description for "Гадна фасадны нийт ажил"
    qty = Decimal('5100')
    
    # confirmed items
    mech_anchor_total = Decimal('30600') * Decimal('1500') # 45,900,000
    mesh_total = Decimal('5610') * Decimal('4500') # 25,245,000
    paint_total = Decimal('1275') * Decimal('3500') # 4,462,500
    primer_total = Decimal('765') * Decimal('3500') # 2,677,500
    
    total_materials = mech_anchor_total + mesh_total + paint_total + primer_total
    
    result = CostEngine.calculate_work_cost(
        quantity=qty,
        labor_unit_rate=Decimal('0'), # Testing materials only for this assert
        material_cost=total_materials
    )
    
    assert result["material_cost"] == Decimal('78285000')
