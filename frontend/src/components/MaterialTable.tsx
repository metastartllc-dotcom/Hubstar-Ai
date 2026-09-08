import type { WorkMaterialLink } from '../api'
import { formatMnt, formatQuantity } from '../utils/format'
import { RecordStatusBadge } from './StatusBadge'

export function MaterialTable({ materials }: { materials: WorkMaterialLink[] }) {
  if (materials.length === 0) {
    return <div className="empty-state">Материал холбогдоогүй байна</div>
  }

  return (
    <div className="table-scroll detail-table-scroll">
      <table className="detail-table">
        <thead>
          <tr>
            <th scope="col">Material ID</th><th scope="col">Материалын нэр</th><th scope="col">Нэгж</th>
            <th scope="col" className="numeric">Орцын норм</th><th scope="col" className="numeric">Хаягдлын хувь</th>
            <th scope="col" className="numeric">Тооцоолсон хэмжээ</th><th scope="col" className="numeric">Баталсан хэмжээ</th>
            <th scope="col" className="numeric">Төсөвт ашигласан хэмжээ</th><th scope="col" className="numeric">Нэгж үнэ</th>
            <th scope="col" className="numeric">Нийт</th><th scope="col">Төлөв</th>
          </tr>
        </thead>
        <tbody>
          {materials.map((material) => (
            <tr key={material.material_id}>
              <td><span className="work-code">{material.material_id}</span></td>
              <td><strong>{material.name}</strong></td>
              <td>{material.normalized_unit ?? '—'}</td>
              <td className="numeric">{formatQuantity(material.consumption_rate)}</td>
              <td className="numeric">{formatQuantity(material.waste_percentage)}%</td>
              <td className="numeric">{formatQuantity(material.calculated_quantity)}</td>
              <td className="numeric">{formatQuantity(material.approved_quantity)}</td>
              <td className="numeric">{formatQuantity(material.effective_quantity)}</td>
              <td className="numeric">{formatMnt(material.unit_price)}</td>
              <td className="numeric total-cell">{formatMnt(material.material_total)}</td>
              <td><RecordStatusBadge status={material.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
