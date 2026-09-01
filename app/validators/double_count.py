class DoubleCountValidator:
    
    @staticmethod
    def check_equipment(equipment, work_item_includes_operator: bool, work_item_includes_fuel: bool):
        warnings = []
        if equipment.operator_included and work_item_includes_operator:
            warnings.append("Operator cost is included in both equipment tariff and work item labor.")
        
        if equipment.fuel_included and work_item_includes_fuel:
            warnings.append("Fuel cost is included in both equipment tariff and work item materials.")
            
        return warnings

    @staticmethod
    def check_transport_crane(is_crane_equipment: bool, is_crane_transport: bool):
        if is_crane_equipment and is_crane_transport:
            return ["Crane cost is entered as lifting equipment and also under transport."]
        return []
        
    @staticmethod
    def check_duplicate_material_links(links: list):
        seen_materials = set()
        warnings = []
        for link in links:
            if link.material_id in seen_materials:
                warnings.append(f"Material ID {link.material_id} is linked multiple times to the same work item.")
            seen_materials.add(link.material_id)
        return warnings
