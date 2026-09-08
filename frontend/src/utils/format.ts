const moneyFormatter = new Intl.NumberFormat('mn-MN', {
  maximumFractionDigits: 0,
})

const quantityFormatter = new Intl.NumberFormat('mn-MN', {
  maximumFractionDigits: 3,
})

function isDisplayable(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function formatMnt(value: number | null | undefined): string {
  return isDisplayable(value) ? `${moneyFormatter.format(value)} ₮` : '—'
}

export function formatQuantity(value: number | null | undefined): string {
  return isDisplayable(value) ? quantityFormatter.format(value) : '—'
}

export function safePercentage(value: number, total: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(total) || total <= 0) {
    return 0
  }

  return Math.min(100, Math.max(0, (Math.max(0, value) / total) * 100))
}
