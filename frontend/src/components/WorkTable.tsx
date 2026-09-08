import type { ProjectBudgetWork, ProjectWorkItem } from '../api'
import { formatMnt, formatQuantity } from '../utils/format'
import { StatusBadge } from './StatusBadge'

interface WorkTableProps {
  works: ProjectBudgetWork[]
  workItems: ProjectWorkItem[]
  selectedWorkId: string | null
  onSelectWork: (workId: string) => void
}

export function WorkTable({ works, workItems, selectedWorkId, onSelectWork }: WorkTableProps) {
  const workItemsById = new Map(workItems.map((work) => [work.work_id, work]))

  return (
    <section className="panel works-panel" aria-labelledby="works-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Төслийн задаргаа</p>
          <h2 id="works-title">Ажлын төсөв</h2>
        </div>
        <span className="count-pill">{works.length} ажил</span>
      </div>
      {works.length === 0 ? (
        <div className="empty-state">Ажил бүртгэгдээгүй байна</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Ажлын код</th><th scope="col">Ажлын нэр</th><th scope="col">Нэгж</th>
                <th scope="col" className="numeric">Тоо хэмжээ</th><th scope="col" className="numeric">Хөдөлмөр</th>
                <th scope="col" className="numeric">Материал</th><th scope="col" className="numeric">Машин механизм</th>
                <th scope="col" className="numeric">Нийт</th><th scope="col">Төлөв</th><th scope="col"><span className="sr-only">Үйлдэл</span></th>
              </tr>
            </thead>
            <tbody>
              {works.map((work) => {
                const detail = workItemsById.get(work.work_id)
                return (
                  <tr key={work.work_id} className={selectedWorkId === work.work_id ? 'selected-row' : undefined}>
                    <td><span className="work-code">{work.work_id}</span></td>
                    <td><strong>{work.name}</strong></td>
                    <td>{detail?.unit ?? work.unit ?? '—'}</td>
                    <td className="numeric">{formatQuantity(detail?.quantity ?? work.quantity)}</td>
                    <td className="numeric">{formatMnt(work.labor_total)}</td>
                    <td className="numeric">{formatMnt(work.material_subtotal_known)}</td>
                    <td className="numeric">{formatMnt(work.equipment_subtotal_known)}</td>
                    <td className="numeric total-cell">{formatMnt(work.subtotal_known_before_vat)}</td>
                    <td><StatusBadge status={work.pricing_status} /></td>
                    <td>
                      <button
                        className="detail-toggle"
                        type="button"
                        aria-expanded={selectedWorkId === work.work_id}
                        aria-controls={`work-details-${work.work_id}`}
                        onClick={() => onSelectWork(work.work_id)}
                      >
                        {selectedWorkId === work.work_id ? 'Хаах' : 'Дэлгэрэнгүй'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
