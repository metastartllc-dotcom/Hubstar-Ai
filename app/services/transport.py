import math
from decimal import Decimal

class TransportCalculator:
    @staticmethod
    def calculate_trips_and_cost(
        package_quantity: int,
        weight_per_package_kg: float,
        volume_per_package_m3: float,
        vehicle_payload_kg: float,
        vehicle_volume_m3: float,
        one_way_distance_km: float,
        distance_multiplier: float,
        base_tariff: Decimal,
        road_fee_per_trip: Decimal
    ) -> dict:
        
        total_weight_kg = package_quantity * weight_per_package_kg
        total_volume_m3 = package_quantity * volume_per_package_m3
        
        trips_by_weight = math.ceil(total_weight_kg / vehicle_payload_kg) if vehicle_payload_kg > 0 else 0
        trips_by_volume = math.ceil(total_volume_m3 / vehicle_volume_m3) if vehicle_volume_m3 > 0 else 0
        
        final_trip_count = max(trips_by_weight, trips_by_volume)
        limiting_factor = "weight" if trips_by_weight >= trips_by_volume else "volume"
        
        distance_cost = Decimal(str(one_way_distance_km)) * Decimal(str(distance_multiplier)) * base_tariff * Decimal(final_trip_count)
        total_road_fee = road_fee_per_trip * Decimal(final_trip_count)
        
        total_cost = distance_cost + total_road_fee
        
        return {
            "total_weight_kg": total_weight_kg,
            "total_volume_m3": total_volume_m3,
            "trips_by_weight": trips_by_weight,
            "trips_by_volume": trips_by_volume,
            "final_trip_count": final_trip_count,
            "limiting_factor": limiting_factor,
            "transport_cost": total_cost
        }
