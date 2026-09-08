import { useEffect, useState } from 'react'
import {
  getWorkBudgetSummary,
  getWorkEquipment,
  getWorkMaterials,
  type WorkBudgetSummary,
  type WorkEquipmentLink,
  type WorkMaterialLink,
} from '../api'
import { formatMnt, formatQuantity } from '../utils/format'
import { EquipmentList } from './EquipmentList'
import { MaterialTable } from './MaterialTable'
import { StatusBadge } from './StatusBadge'

interface WorkDetailData {
  summary: WorkBudgetSummary
  materials: WorkMaterialLink[]
  equipment: WorkEquipmentLink[]
}

type DetailState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: WorkDetailData }

function buildWarnings(summary: WorkBudgetSummary): string[] {
  return [
    ...summary.warnings,
    ...summary.missing_price_material_ids.map((id) => `Үнэ дутуу материал: ${id}`),
    ...summary.needs_review_material_ids.map((id) => `Хянах шаардлагатай материал: ${id}`),
    ...summary.missing_equipment_rate_ids.map((id) => `Тариф дутуу машин механизм: ${id}`),
    ...summary.needs_review_equipment_ids.map((id) => `Хянах шаардлагатай машин механизм: ${id}`),
    ...summary.excluded_equipment_ids.map((id) => `Төсвөөс хассан машин механизм: ${id}`),
  ]
}

export function WorkDetailsPanel({ projectId, workId }: { projectId: string; workId: string }) {
  const [state, setState] = useState<DetailState>({ status: 'loading' })
  const [retryCount, setRetryCount] = useState(0)
  const panelId = `work-details-${workId}`

  useEffect(() => {
    let active = true

    async function loadDetails() {
      try {
        const [summary, materials, equipment] = await Promise.all([
          getWorkBudgetSummary(projectId, workId),
          getWorkMaterials(projectId, workId),
          getWorkEquipment(projectId, workId),
        ])
        if (active) {
          setState({ status: 'success', data: { summary, materials, equipment } })
        }
      } catch {
        if (active) setState({ status: 'error' })
      }
    }

    void loadDetails()
    return () => {
      active = false
    }
  }, [projectId, retryCount, workId])

  if (state.status === 'loading') {
    return (
      <section className="panel detail-panel" id={panelId} aria-busy="true" aria-label="Ажлын дэлгэрэнгүй ачаалж байна">
        <div className="skeleton detail-skeleton" />
        <span className="sr-only">Ажлын дэлгэрэнгүй ачаалж байна</span>
      </section>
    )
  }

  if (state.status === 'error') {
    return (
      <section className="panel detail-panel detail-error" id={panelId} role="alert">
        <h2>Дэлгэрэнгүй мэдээлэл ачаалж чадсангүй</h2>
        <p>Холболтыг шалгаад дахин оролдоно уу.</p>
        <button type="button" onClick={() => {
          setState({ status: 'loading' })
          setRetryCount((count) => count + 1)
        }}>Дахин оролдох</button>
      </section>
    )
  }

  const { summary, materials, equipment } = state.data
  const warnings = buildWarnings(summary)

  return (
    <section className="panel detail-panel" id={panelId} aria-labelledby={`${panelId}-title`}>
      <div className="detail-header">
        <div>
          <p className="eyebrow">Сонгосон ажлын дэлгэрэнгүй</p>
          <h2 id={`${panelId}-title`}>{summary.name}</h2>
          <span className="work-code">{summary.work_id}</span>
        </div>
        <StatusBadge status={summary.pricing_status} />
      </div>

      <div className="detail-metrics">
        <div><span>Нэгж</span><strong>{summary.unit ?? '—'}</strong></div>
        <div><span>Тоо хэмжээ</span><strong>{formatQuantity(summary.quantity)}</strong></div>
        <div><span>Хөдөлмөр</span><strong>{formatMnt(summary.labor_total)}</strong></div>
        <div><span>Материал</span><strong>{formatMnt(summary.material_subtotal_known)}</strong></div>
        <div><span>Машин механизм</span><strong>{formatMnt(summary.equipment_subtotal_known)}</strong></div>
        <div><span>Нийт</span><strong>{formatMnt(summary.subtotal_known_before_vat)}</strong></div>
      </div>

      <div className={warnings.length === 0 ? 'warning-box success-box' : 'warning-box'}>
        {warnings.length === 0 ? (
          <p><span aria-hidden="true">✓</span> Үнэ болон тооцооны анхааруулга байхгүй</p>
        ) : (
          <><h3>Анхаарах зүйлс</h3><ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></>
        )}
      </div>

      <section className="detail-section" aria-labelledby={`${panelId}-materials`}>
        <div className="detail-section-title">
          <h3 id={`${panelId}-materials`}>Материалын хэрэгцээ</h3>
          <span className="count-pill">{materials.length} материал</span>
        </div>
        <MaterialTable materials={materials} />
      </section>

      <section className="detail-section" aria-labelledby={`${panelId}-equipment`}>
        <div className="detail-section-title">
          <h3 id={`${panelId}-equipment`}>Машин механизм</h3>
          <span className="count-pill">{equipment.length} холбоос</span>
        </div>
        <EquipmentList equipment={equipment} />
      </section>
    </section>
  )
}
