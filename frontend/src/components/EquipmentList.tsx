import type { WorkEquipmentLink } from '../api'
import { formatMnt, formatQuantity } from '../utils/format'
import { RecordStatusBadge } from './StatusBadge'

function inclusionLabel(value: boolean | null): string {
  if (value === null) return '—'
  return value ? 'Багтсан' : 'Багтаагүй'
}

function tariffUnit(tariffType: string | null): string | null {
  if (!tariffType) return null
  const parts = tariffType.split('/')
  return parts.length > 1 ? parts.at(-1) ?? null : tariffType
}

function formatQuantityWithUnit(value: number | null, unit: string): string {
  return value === null ? '—' : `${formatQuantity(value)} ${unit}`
}

function formatRateWithUnit(value: number | null, unit: string | null): string {
  if (value === null) return '—'
  return `${formatMnt(value)}${unit ? `/${unit}` : ''}`
}

function includedCostNote(equipment: WorkEquipmentLink): string | null {
  const included = [
    equipment.operator_included ? 'Оператор' : null,
    equipment.fuel_included ? 'түлш' : null,
    equipment.delivery_included ? 'хүргэлт' : null,
  ].filter((label): label is string => label !== null)

  return included.length > 0
    ? `${included.join(', ')} тарифт багтсан тул төсөвт дахин нэмэхгүй.`
    : null
}

export function EquipmentList({ equipment }: { equipment: WorkEquipmentLink[] }) {
  if (equipment.length === 0) {
    return <div className="empty-state">Машин механизм холбогдоогүй байна</div>
  }

  return (
    <div className="equipment-grid">
      {equipment.map((item) => {
        const unit = tariffUnit(item.tariff_type)
        const note = includedCostNote(item)
        return (
          <article className="equipment-card" key={item.equipment_id}>
            <div className="equipment-card-header">
              <div>
                <span className="work-code">{item.equipment_id}</span>
                <h4>{item.type ?? 'Машин механизм'}</h4>
              </div>
              <RecordStatusBadge status={item.status} />
            </div>
            <dl className="equipment-facts">
              <div><dt>Даац</dt><dd>{item.capacity ?? '—'}</dd></div>
              <div><dt>Ашиглалт</dt><dd>{formatQuantity(item.usage_quantity)}{unit ? ` ${unit}` : ''}</dd></div>
              <div><dt>Тохиролцсон тариф</dt><dd>{formatRateWithUnit(item.agreed_unit_rate, unit)}</dd></div>
              <div><dt>Нийт</dt><dd className="total-cell">{formatMnt(item.equipment_total)}</dd></div>
              <div><dt>Оператор</dt><dd>{inclusionLabel(item.operator_included)}</dd></div>
              <div><dt>Түлш</dt><dd>{inclusionLabel(item.fuel_included)}</dd></div>
              <div><dt>Хүргэлт</dt><dd>{inclusionLabel(item.delivery_included)}</dd></div>
              <div><dt>Нэг талын багтсан зай</dt><dd>{formatQuantityWithUnit(item.included_delivery_one_way_distance_km, 'км')}</dd></div>
            </dl>
            {note && <p className="inclusion-note"><span aria-hidden="true">ⓘ</span>{note}</p>}
          </article>
        )
      })}
    </div>
  )
}
