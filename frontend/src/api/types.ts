export type Status =
  | 'VALID'
  | 'ACTIVE'
  | 'ACTIVE_WITH_WARNINGS'
  | 'NEEDS_REVIEW'
  | 'REJECTED'
  | 'SUPERSEDED'

export type PricingStatus =
  | 'NO_WORK_ITEMS'
  | 'NO_MATERIALS'
  | 'COMPLETE'
  | 'INCOMPLETE'
  | 'NEEDS_REVIEW'

export interface HealthResponse {
  status: string
}

export interface ProjectDetail {
  project_id: string | null
  name: string
  location: string | null
  project_type: string | null
  gross_floor_area: number | null
  start_date: string | null
  end_date: string | null
  status: Status
}

export interface ProjectWorkItem {
  work_id: string
  name: string
  wbs_code: string | null
  unit: string | null
  quantity: number | null
  labor_unit_rate: number | null
  labor_total: number | null
  status: Status
}

export interface MaterialWarningPair {
  work_id: string
  material_id: string
}

export interface EquipmentWarningPair {
  work_id: string
  equipment_id: string
}

export interface ProjectBudgetWork {
  work_id: string
  name: string
  unit: string | null
  quantity: number | null
  labor_total: number | null
  material_subtotal_known: number
  equipment_subtotal_known: number
  subtotal_known_before_vat: number
  missing_price_count: number
  needs_review_count: number
  pricing_status: Exclude<PricingStatus, 'NO_WORK_ITEMS'>
  equipment_link_count: number
  priced_equipment_link_count: number
  missing_equipment_rate_link_count: number
  needs_review_equipment_link_count: number
  excluded_equipment_link_count: number
}

export interface ProjectBudgetSummary {
  project_id: string
  name: string
  work_item_count: number
  complete_work_count: number
  incomplete_work_count: number
  needs_review_work_count: number
  missing_labor_work_count: number
  no_materials_work_count: number
  no_materials_work_ids: string[]
  material_link_count: number
  priced_material_link_count: number
  missing_price_link_count: number
  needs_review_link_count: number
  labor_subtotal_known: number
  material_subtotal_known: number
  equipment_subtotal_known: number
  subtotal_known_before_vat: number
  is_pricing_complete: boolean
  has_review_warnings: boolean
  pricing_status: Exclude<PricingStatus, 'NO_MATERIALS'>
  missing_labor_work_ids: string[]
  missing_price_links: MaterialWarningPair[]
  needs_review_links: MaterialWarningPair[]
  equipment_link_count: number
  priced_equipment_link_count: number
  missing_equipment_rate_link_count: number
  needs_review_equipment_link_count: number
  excluded_equipment_link_count: number
  missing_equipment_rate_pairs: EquipmentWarningPair[]
  needs_review_equipment_pairs: EquipmentWarningPair[]
  excluded_equipment_pairs: EquipmentWarningPair[]
  warnings: string[]
  works: ProjectBudgetWork[]
}

export interface WorkBudgetSummary {
  project_id: string
  work_id: string
  name: string
  unit: string | null
  quantity: number | null
  labor_unit_rate: number | null
  labor_total: number | null
  material_link_count: number
  priced_material_count: number
  missing_price_count: number
  needs_review_count: number
  material_subtotal_known: number
  equipment_subtotal_known: number
  subtotal_known_before_vat: number
  is_pricing_complete: boolean
  has_review_warnings: boolean
  pricing_status: Exclude<PricingStatus, 'NO_WORK_ITEMS'>
  missing_price_material_ids: string[]
  needs_review_material_ids: string[]
  warnings: string[]
  equipment_link_count: number
  priced_equipment_link_count: number
  missing_equipment_rate_link_count: number
  needs_review_equipment_link_count: number
  excluded_equipment_link_count: number
  missing_equipment_rate_ids: string[]
  needs_review_equipment_ids: string[]
  excluded_equipment_ids: string[]
}

export interface WorkMaterialLink {
  material_id: string
  name: string
  specification: string | null
  normalized_unit: string | null
  unit_price: number | null
  consumption_rate: number
  waste_percentage: number
  calculated_quantity: number | null
  approved_quantity: number | null
  effective_quantity: number | null
  material_total: number | null
  status: Status
}

export interface WorkEquipmentLink {
  equipment_id: string
  type: string | null
  capacity: string | null
  usage_quantity: number
  agreed_unit_rate: number | null
  tariff_type: string | null
  operator_included: boolean | null
  fuel_included: boolean | null
  delivery_included: boolean | null
  included_delivery_one_way_distance_km: number | null
  equipment_total: number | null
  status: Status
}
