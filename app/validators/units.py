class UnitNormalizer:
    UNIT_MAPPINGS = {
        "тн": "тн", "тонн": "тн", "ton": "тн",
        "кг": "кг", "килограмм": "кг", "kg": "кг",
        "м": "м", "метр": "м", "m": "м",
        "м2": "м²", "мкв": "м²", "м.кв": "м²", "m2": "м²", "м²": "м²",
        "м3": "м³", "мкуб": "м³", "м.куб": "м³", "m3": "м³", "м³": "м³",
        "л": "л", "литр": "л", "l": "л",
        "ш": "ш", "ширхэг": "ш", "ш/х": "ш", "pcs": "ш",
        "цаг": "цаг", "ц": "цаг", "h": "цаг", "hour": "цаг",
        "рейс": "рейс",
        "багц": "багц"
    }

    CONVERSIONS = {
        ("тн", "кг"): 1000.0,
        ("кг", "тн"): 0.001
    }

    @classmethod
    def normalize(cls, unit_str: str) -> str:
        if not unit_str:
            return None
        normalized = unit_str.strip().lower()
        return cls.UNIT_MAPPINGS.get(normalized, unit_str.strip())
    
    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        if from_unit == to_unit:
            return value
        
        factor = cls.CONVERSIONS.get((from_unit, to_unit))
        if factor is not None:
            return value * factor
        
        raise ValueError(f"Unknown or incompatible units: {from_unit} to {to_unit}")
