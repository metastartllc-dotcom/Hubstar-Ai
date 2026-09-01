from decimal import Decimal

class CostEngine:
    @staticmethod
    def calculate_work_cost(
        quantity: Decimal,
        labor_unit_rate: Decimal,
        material_cost: Decimal = Decimal('0'),
        equipment_cost: Decimal = Decimal('0'),
        transport_cost: Decimal = Decimal('0'),
        subcontract_cost: Decimal = Decimal('0'),
        other_cost: Decimal = Decimal('0')
    ) -> dict:
        
        labor_cost = quantity * labor_unit_rate
        direct_cost = labor_cost + material_cost + equipment_cost + transport_cost + subcontract_cost + other_cost
        vat = direct_cost * Decimal('0.10') # Assuming 10% VAT
        grand_total = direct_cost + vat
        
        unit_cost = grand_total / quantity if quantity > 0 else Decimal('0')
        
        return {
            "quantity": quantity,
            "labor_cost": labor_cost,
            "material_cost": material_cost,
            "equipment_cost": equipment_cost,
            "transport_cost": transport_cost,
            "subcontract_cost": subcontract_cost,
            "other_cost": other_cost,
            "direct_cost": direct_cost,
            "vat": vat,
            "grand_total": grand_total,
            "unit_cost": unit_cost
        }
