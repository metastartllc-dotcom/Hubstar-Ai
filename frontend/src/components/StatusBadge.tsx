import type { PricingStatus, Status } from '../api'

const labels: Record<PricingStatus, string> = {
  COMPLETE: 'Бүрэн',
  INCOMPLETE: 'Дутуу',
  NEEDS_REVIEW: 'Хянах шаардлагатай',
  NO_MATERIALS: 'Материалгүй',
  NO_WORK_ITEMS: 'Ажилгүй',
}

export function StatusBadge({ status }: { status: PricingStatus }) {
  return (
    <span className={`status-badge status-${status.toLowerCase()}`} title={status}>
      <span aria-hidden="true">●</span>
      {labels[status]}
      <small>{status}</small>
    </span>
  )
}

const recordLabels: Record<Status, string> = {
  VALID: 'Баталгаатай',
  ACTIVE: 'Идэвхтэй',
  ACTIVE_WITH_WARNINGS: 'Анхааруулгатай',
  NEEDS_REVIEW: 'Хянах шаардлагатай',
  REJECTED: 'Татгалзсан',
  SUPERSEDED: 'Хүчингүй болсон',
}

export function RecordStatusBadge({ status }: { status: Status }) {
  return (
    <span className={`record-status record-${status.toLowerCase()}`} title={status}>
      {recordLabels[status]} · {status}
    </span>
  )
}
