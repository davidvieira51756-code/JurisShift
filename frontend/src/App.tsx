import { useEffect, useMemo, useState } from 'react'
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileSearch,
  Landmark,
  Scale,
} from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

const ISSUE_SLUG = 'loan-prescription-acceleration'

const FIVE_YEAR = 'loan-prescription-five-year'
const TWENTY_YEAR = 'loan-prescription-twenty-year'

type Position = {
  id: string
  label: string
  description: string
  case_count: number
}

type Issue = {
  slug: string
  title: string
  question: string
  source: string
  landmark: {
    label: string
    year: number
  }
  stats: {
    analyzed_cases: number
    deciding_cases: number
    non_deciding_cases: number
    auto_cases: number
    review_cases: number
    verified_evidence_cases: number
    represented_positions: number
    divergence_detected: boolean
  }
  positions: Position[]
}

type TimelineYear = {
  year: number
  total_decisions: number
  positions: Record<string, number>
}

type Timeline = {
  landmark: {
    label: string
    year: number
  }
  years: TimelineYear[]
}

type CaseItem = {
  id: number
  ecli: string | null
  process_number: string
  court: string | null
  decision_date: string | null
  rapporteur: string | null
  source_url: string
  summary: string | null
  stance: {
    decides_issue: boolean
    position_id: string | null
    position_label: string | null
    status: string
    model: string | null
    prompt_version: string | null
  }
  evidence: {
    quote: string
    role: string
    verified: boolean
  } | null
}

type CasesResponse = {
  total: number
  cases: CaseItem[]
}

type Filter = 'all' | 'five' | 'twenty' | 'review'

function App() {
  const [issue, setIssue] = useState<Issue | null>(null)
  const [timeline, setTimeline] = useState<Timeline | null>(null)
  const [cases, setCases] = useState<CaseItem[]>([])
  const [filter, setFilter] = useState<Filter>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true)

        const [issueResponse, timelineResponse, casesResponse] =
          await Promise.all([
            fetch(`${API_BASE}/api/issues/${ISSUE_SLUG}`),
            fetch(`${API_BASE}/api/issues/${ISSUE_SLUG}/timeline`),
            fetch(`${API_BASE}/api/issues/${ISSUE_SLUG}/cases`),
          ])

        if (
          !issueResponse.ok ||
          !timelineResponse.ok ||
          !casesResponse.ok
        ) {
          throw new Error('Não foi possível carregar os dados.')
        }

        const issueData: Issue = await issueResponse.json()
        const timelineData: Timeline = await timelineResponse.json()
        const casesData: CasesResponse = await casesResponse.json()

        setIssue(issueData)
        setTimeline(timelineData)
        setCases(casesData.cases)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Erro inesperado.',
        )
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  const chartData = useMemo(() => {
    if (!timeline) {
      return []
    }

    return timeline.years.map((item) => ({
      year: item.year,
      fiveYear: item.positions[FIVE_YEAR] ?? 0,
      twentyYear: item.positions[TWENTY_YEAR] ?? 0,
    }))
  }, [timeline])

  const visibleCases = useMemo(() => {
    const relevant = cases.filter(
      (item) => item.stance.decides_issue,
    )

    if (filter === 'five') {
      return relevant.filter(
        (item) => item.stance.position_id === FIVE_YEAR,
      )
    }

    if (filter === 'twenty') {
      return relevant.filter(
        (item) => item.stance.position_id === TWENTY_YEAR,
      )
    }

    if (filter === 'review') {
      return cases.filter((item) => item.stance.status === 'REVIEW')
    }

    return relevant
  }, [cases, filter])

  if (loading) {
    return (
      <main className="state-screen">
        <div className="spinner" />
        <p>A analisar jurisprudência...</p>
      </main>
    )
  }

  if (error || !issue || !timeline) {
    return (
      <main className="state-screen">
        <strong>Não foi possível carregar o JurisShift.</strong>
        <p>
          {error ??
            'Confirma que a API está disponível na porta 8000.'}
        </p>
      </main>
    )
  }

  const fiveYear = issue.positions.find(
    (position) => position.id === FIVE_YEAR,
  )

  const twentyYear = issue.positions.find(
    (position) => position.id === TWENTY_YEAR,
  )

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Scale size={19} />
          </div>

          <span>JurisShift</span>
        </div>

        <div className="topbar-meta">
          <span className="live-dot" />
          Jurisprudência portuguesa
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <FileSearch size={15} />
              Análise de divergência jurisprudencial
            </div>

            <h1>{issue.title}</h1>

            <p className="question">{issue.question}</p>

            <div className="hero-meta">
              <span>
                <Landmark size={15} />
                Marco: {issue.landmark.label}
              </span>

              {issue.stats.divergence_detected && (
                <span className="divergence-pill">
                  Divergência identificada
                </span>
              )}
            </div>
          </div>

          <aside className="hero-summary">
            <span>Corpus analisado</span>
            <strong>{issue.stats.analyzed_cases}</strong>
            <p>
              {issue.stats.deciding_cases} decisões sobre a questão,
              com {issue.stats.verified_evidence_cases} evidências
              verificadas.
            </p>
          </aside>
        </section>

        <section className="stats-grid">
          <StatCard
            value={issue.stats.analyzed_cases}
            label="Acórdãos analisados"
            icon={<FileSearch size={18} />}
          />

          <StatCard
            value={issue.stats.deciding_cases}
            label="Decidem a questão"
            icon={<Scale size={18} />}
          />

          <StatCard
            value={issue.stats.represented_positions}
            label="Posições identificadas"
            icon={<Landmark size={18} />}
          />

          <StatCard
            value={issue.stats.review_cases}
            label="Revisão necessária"
            icon={<Clock3 size={18} />}
          />
        </section>

        <section className="panel timeline-panel">
          <div className="section-heading">
            <div>
              <span className="section-kicker">Evolução</span>
              <h2>Evolução jurisprudencial</h2>
            </div>

            <p>
              Número de decisões que adotam cada posição no corpus
              analisado.
            </p>
          </div>

          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={380}>
              <LineChart
                data={chartData}
                margin={{
                  top: 22,
                  right: 28,
                  left: 0,
                  bottom: 8,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                />

                <XAxis
                  dataKey="year"
                  tickLine={false}
                  axisLine={false}
                />

                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                />

                <Tooltip content={<ChartTooltip />} />

                <Legend />

                <ReferenceLine
                  x={2022}
                  strokeDasharray="5 5"
                  label={{
                    value: 'AUJ 6/2022',
                    position: 'insideTopRight',
                  }}
                />

                <Line
                  type="monotone"
                  dataKey="fiveYear"
                  name="Prazo de 5 anos"
                  stroke="currentColor"
                  strokeWidth={3}
                  dot={{ r: 5 }}
                  activeDot={{ r: 7 }}
                />

                <Line
                  type="monotone"
                  dataKey="twentyYear"
                  name="Prazo ordinário / 20 anos"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeDasharray="7 5"
                  dot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="timeline-insight">
            <CheckCircle2 size={18} />

            <div>
              <strong>Mudança visível no corpus</strong>
              <p>
                As decisões selecionadas revelam a posição dos 20 anos
                entre 2016 e 2021. Em 2021 coexistem as duas
                orientações. A partir de 2022, os acórdãos
                classificados no corpus adotam a posição dos cinco anos.
              </p>
            </div>
          </div>
        </section>

        <section className="positions-grid">
          <PositionCard position={fiveYear} variant="primary" />

          <PositionCard position={twentyYear} variant="secondary" />
        </section>

        <section className="panel cases-panel">
          <div className="section-heading cases-heading">
            <div>
              <span className="section-kicker">Evidência</span>

              <h2>Acórdãos analisados</h2>
            </div>

            <span className="case-total">
              {visibleCases.length} resultados
            </span>
          </div>

          <div className="filters">
            <FilterButton
              active={filter === 'all'}
              onClick={() => setFilter('all')}
            >
              Todos os relevantes
            </FilterButton>

            <FilterButton
              active={filter === 'five'}
              onClick={() => setFilter('five')}
            >
              5 anos
            </FilterButton>

            <FilterButton
              active={filter === 'twenty'}
              onClick={() => setFilter('twenty')}
            >
              20 anos
            </FilterButton>

            <FilterButton
              active={filter === 'review'}
              onClick={() => setFilter('review')}
            >
              Em revisão
            </FilterButton>
          </div>

          <div className="case-list">
            {visibleCases.map((item) => (
              <CaseCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="methodology">
          <div>
            <strong>Como ler estes resultados</strong>

            <p>
              O JurisShift classifica a posição jurídica adotada pelo
              tribunal e liga cada classificação a evidência textual
              verificável. Casos sem evidência suficiente são
              assinalados para revisão, em vez de serem apresentados
              como conclusões automáticas.
            </p>
          </div>

          <div className="methodology-stat">
            <strong>{issue.stats.verified_evidence_cases}</strong>
            <span>decisões com evidência verificada</span>
          </div>
        </section>
      </main>

      <footer>JurisShift · Protótipo de análise jurisprudencial</footer>
    </div>
  )
}

function StatCard({
  value,
  label,
  icon,
}: {
  value: number
  label: string
  icon: React.ReactNode
}) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>

      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function PositionCard({
  position,
  variant,
}: {
  position: Position | undefined
  variant: 'primary' | 'secondary'
}) {
  if (!position) {
    return null
  }

  return (
    <article className={`position-card ${variant}`}>
      <div className="position-top">
        <span className="position-label">Posição jurisprudencial</span>

        <strong className="position-count">{position.case_count}</strong>
      </div>

      <h3>{position.label}</h3>

      <p>{position.description}</p>

      <div className="position-footer">
        {position.case_count}{' '}
        {position.case_count === 1
          ? 'decisão identificada'
          : 'decisões identificadas'}
      </div>
    </article>
  )
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      className={`filter-button ${active ? 'active' : ''}`}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function CaseCard({ item }: { item: CaseItem }) {
  const isTwenty = item.stance.position_id === TWENTY_YEAR

  const positionText = isTwenty
    ? '20 anos'
    : item.stance.position_id === FIVE_YEAR
      ? '5 anos'
      : 'Sem posição'

  const date = item.decision_date
    ? new Intl.DateTimeFormat('pt-PT', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }).format(new Date(`${item.decision_date}T00:00:00`))
    : 'Data não disponível'

  return (
    <article className="case-card">
      <div className="case-header">
        <div>
          <div className="case-meta">
            <span>{item.court ?? 'Tribunal não identificado'}</span>
            <span>·</span>
            <span>{date}</span>
          </div>

          <h3>Processo {item.process_number}</h3>
        </div>

        <div className="case-badges">
          {item.stance.status === 'REVIEW' && (
            <span className="review-badge">Rever</span>
          )}

          <span
            className={`position-badge ${isTwenty ? 'twenty' : 'five'}`}
          >
            {positionText}
          </span>
        </div>
      </div>

      {item.evidence ? (
        <blockquote>“{item.evidence.quote}”</blockquote>
      ) : (
        <p className="no-evidence">
          Classificação assinalada para revisão: não existe evidência
          textual validada associada.
        </p>
      )}

      <div className="case-footer">
        <div>
          {item.rapporteur && <span>Relator: {item.rapporteur}</span>}
        </div>

        <a href={item.source_url} target="_blank" rel="noreferrer">
          Ver fonte
          <ArrowUpRight size={15} />
        </a>
      </div>
    </article>
  )
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{
    name?: string
    value?: number
  }>
  label?: number
}) {
  if (!active || !payload || payload.length === 0) {
    return null
  }

  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>

      {payload.map((entry) => (
        <div key={entry.name}>
          <span>{entry.name}</span>
          <strong>{entry.value}</strong>
        </div>
      ))}
    </div>
  )
}

export default App
