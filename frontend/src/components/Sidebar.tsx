const futureItems = [
  'Төслүүд',
  'Ажлууд',
  'Материал',
  'Машин механизм',
  'Тээвэр',
  'Тайлан',
]

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand" aria-label="Hubstar AI">
        <span className="brand-mark" aria-hidden="true">H</span>
        <span>
          <strong>Hubstar</strong>
          <small>AI төсвийн систем</small>
        </span>
      </div>
      <nav aria-label="Үндсэн цэс">
        <ul className="nav-list">
          <li>
            <a className="nav-item active" href="#dashboard" aria-current="page">
              <span className="nav-icon" aria-hidden="true">▦</span>
              Хяналтын самбар
            </a>
          </li>
          {futureItems.map((item) => (
            <li key={item}>
              <span className="nav-item disabled" aria-disabled="true">
                <span className="nav-icon" aria-hidden="true">·</span>
                <span>{item}</span>
                <small>Тун удахгүй</small>
              </span>
            </li>
          ))}
        </ul>
      </nav>
      <p className="sidebar-note">Read-only хяналтын орчин</p>
    </aside>
  )
}
