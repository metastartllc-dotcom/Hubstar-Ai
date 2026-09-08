import { useCallback, useEffect, useState } from 'react'
import {
  getHealth,
  getProject,
  getProjectBudgetSummary,
  getProjectWorkItems,
  type ProjectBudgetSummary,
  type ProjectDetail,
  type ProjectWorkItem,
} from './api'
import { BudgetOverview } from './components/BudgetOverview'
import { Sidebar } from './components/Sidebar'
import { StatusBadge } from './components/StatusBadge'
import { WorkDetailsPanel } from './components/WorkDetailsPanel'
import { WorkTable } from './components/WorkTable'
import { projectId } from './config'
import { formatMnt } from './utils/format'
import './App.css'

interface DashboardData {
  project: ProjectDetail
  summary: ProjectBudgetSummary
  workItems: ProjectWorkItem[]
}

type DashboardState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: DashboardData }

function DashboardSkeleton() {
  return (
    <main className="content" aria-busy="true" aria-label="Өгөгдөл ачаалж байна">
      <div className="skeleton skeleton-header" />
      <div className="summary-grid">
        {[0, 1, 2, 3].map((item) => <div className="skeleton skeleton-card" key={item} />)}
      </div>
      <div className="skeleton skeleton-panel" />
      <span className="sr-only">Төслийн мэдээлэл ачаалж байна</span>
    </main>
  )
}

function App() {
  const [state, setState] = useState<DashboardState>({ status: 'loading' })
  const [retryCount, setRetryCount] = useState(0)
  const [selectedWorkId, setSelectedWorkId] = useState<string | null>(null)

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setRetryCount((count) => count + 1)
  }, [])

  useEffect(() => {
    let active = true

    async function loadDashboard() {
      try {
        const [, project, summary, workItems] = await Promise.all([
          getHealth(),
          getProject(projectId),
          getProjectBudgetSummary(projectId),
          getProjectWorkItems(projectId),
        ])

        if (active) {
          setState({ status: 'success', data: { project, summary, workItems } })
        }
      } catch {
        if (active) {
          setState({ status: 'error' })
        }
      }
    }

    void loadDashboard()
    return () => {
      active = false
    }
  }, [retryCount])

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="workspace">
        {state.status === 'loading' && <DashboardSkeleton />}
        {state.status === 'error' && (
          <main className="content centered-state">
            <div className="error-state" role="alert">
              <span className="state-icon" aria-hidden="true">!</span>
              <h1>Өгөгдөл ачаалж чадсангүй</h1>
              <p>Backend серверийн холболтыг шалгаад дахин оролдоно уу.</p>
              <button type="button" onClick={retry}>Дахин оролдох</button>
            </div>
          </main>
        )}
        {state.status === 'success' && (
          <main className="content" id="dashboard">
            <header className="page-header">
              <div>
                <p className="eyebrow">Hubstar AI · Project controls</p>
                <h1>Төслийн төсвийн хяналтын самбар</h1>
                <div className="project-identity">
                  <strong>{state.data.project.name}</strong>
                  <span>{state.data.project.project_id ?? projectId}</span>
                </div>
              </div>
              <div className="header-statuses">
                <StatusBadge status={state.data.summary.pricing_status} />
                <span className="connection-status"><span aria-hidden="true">●</span>API холбогдсон</span>
              </div>
            </header>

            <section className="summary-grid" aria-label="Төсвийн хураангуй">
              <article className="summary-card total-card">
                <p>Баталгаажсан нийт</p>
                <strong>{formatMnt(state.data.summary.subtotal_known_before_vat)}</strong>
                <small>Одоогоор бүртгэгдсэн хөдөлмөр, материал, машин механизмын нийлбэр</small>
              </article>
              <article className="summary-card labor-card">
                <p><span aria-hidden="true">●</span> Хөдөлмөр</p>
                <strong>{formatMnt(state.data.summary.labor_subtotal_known)}</strong>
                <small>Бүртгэгдсэн хөдөлмөрийн зардал</small>
              </article>
              <article className="summary-card material-card">
                <p><span aria-hidden="true">●</span> Материал</p>
                <strong>{formatMnt(state.data.summary.material_subtotal_known)}</strong>
                <small>{state.data.summary.priced_material_link_count} үнэлэгдсэн материал</small>
              </article>
              <article className="summary-card equipment-card">
                <p><span aria-hidden="true">●</span> Машин механизм</p>
                <strong>{formatMnt(state.data.summary.equipment_subtotal_known)}</strong>
                <small>{state.data.summary.priced_equipment_link_count} үнэлэгдсэн холбоос</small>
              </article>
            </section>

            <BudgetOverview summary={state.data.summary} />
            <WorkTable
              works={state.data.summary.works}
              workItems={state.data.workItems}
              selectedWorkId={selectedWorkId}
              onSelectWork={(workId) => setSelectedWorkId((selected) => selected === workId ? null : workId)}
            />
            {selectedWorkId && (
              <WorkDetailsPanel key={selectedWorkId} projectId={projectId} workId={selectedWorkId} />
            )}
          </main>
        )}
      </div>
    </div>
  )
}

export default App
