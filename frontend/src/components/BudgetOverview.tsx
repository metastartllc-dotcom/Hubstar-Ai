import type { ProjectBudgetSummary } from '../api'
import { formatMnt, safePercentage } from '../utils/format'

export function BudgetOverview({ summary }: { summary: ProjectBudgetSummary }) {
  const total = Math.max(0, summary.subtotal_known_before_vat)
  const parts = [
    { key: 'labor', label: 'Хөдөлмөр', value: summary.labor_subtotal_known },
    { key: 'material', label: 'Материал', value: summary.material_subtotal_known },
    { key: 'equipment', label: 'Машин механизм', value: summary.equipment_subtotal_known },
  ]

  return (
    <section className="panel budget-panel" aria-labelledby="budget-structure-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Зардлын харьцаа</p>
          <h2 id="budget-structure-title">Төсвийн бүтэц</h2>
        </div>
        <span className="section-total">Нийт {formatMnt(total)}</span>
      </div>
      <div className="budget-bars">
        {parts.map((part) => {
          const percentage = safePercentage(part.value, total)
          return (
            <div className="budget-row" key={part.key}>
              <div className="budget-label">
                <strong>{part.label}</strong>
                <span>{formatMnt(part.value)} · {percentage.toFixed(1)}%</span>
              </div>
              <div className="bar-track" role="progressbar" aria-label={`${part.label} төсөвт эзлэх хувь`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percentage)}>
                <span className={`bar-fill ${part.key}`} style={{ width: `${percentage}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
