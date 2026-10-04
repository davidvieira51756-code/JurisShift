import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'

import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileSearch,
  Landmark,
  MessageSquareText,
  Scale,
  Send,
  X,
} from 'lucide-react'

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import './App.css'


const API_BASE =
  import.meta.env.VITE_API_BASE
  ?? (
    import.meta.env.DEV
      ? 'http://127.0.0.1:8000'
      : ''
  )


const POSITION_COLORS = [
  '#2563eb',
  '#c2410c',
  '#7c3aed',
  '#059669',
]


type IssueSummary = {
  slug: string
  title: string
  question: string
  source: string
  analyzed_cases: number
  deciding_cases: number
  review_cases: number
}


type Position = {
  id: string
  label: string
  description: string
  case_count: number
}


type PositionRange = {
  position_id: string
  label: string
  first_date: string
  last_date: string
  total: number
}


type PositionOverlap = {
  position_a: string
  position_b: string
  start_date: string
  end_date: string
}


type Issue = {
  slug: string
  title: string
  question: string
  source: string

  landmark: {
    label: string | null
    year: number | null
  }

  stats: {
    analyzed_cases: number
    deciding_cases: number
    non_deciding_cases: number
    auto_cases: number
    review_cases: number
    verified_evidence_cases: number
    represented_positions: number
    validated_deciding_cases: number
    divergence_detected: boolean
  }

  positions: Position[]

  divergence_analysis: {
    detected: boolean
    validated_decisions: number
    position_ranges: PositionRange[]
    overlaps: PositionOverlap[]
    scope_note: string
  }
}


type Timeline = {
  landmark: {
    label: string | null
    year: number | null
  }

  years: Array<{
    year: number
    total_decisions: number
    positions: Record<string, number>
  }>
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


type CaseDetail = {
  id: number
  ecli: string | null
  process_number: string
  court: string | null
  section: string | null
  area: string | null
  decision_date: string | null
  rapporteur: string | null
  procedural_type: string | null
  decision: string | null
  voting: string | null
  source_url: string

  issue: {
    slug: string
    title: string
    question: string
    source: string
  } | null

  position: {
    id: string
    label: string
    description: string
  } | null

  decides_issue: boolean
  status: string | null
  model: string | null
  prompt_version: string | null

  evidence: {
    id: number
    quote: string
    role: string
    verified: boolean

    context: {
      source: string
      before: string
      quote: string
      after: string
    } | null
  } | null
}


type CasesResponse = {
  total: number
  cases: CaseItem[]
}


type CourtTimePoint = {
  caseId: number
  processNumber: string
  court: string
  decisionDate: string
  timestamp: number
  courtIndex: number
  positionId: string
  positionLabel: string
  status: string
}


type ChatCitation = {
  case_id: number
  process_number: string
  court: string | null
  decision_date: string | null
  position_id: string
  position_label: string
  quote: string
}


type ChatResponse = {
  answer: string
  citation_case_ids: number[]
  citations: ChatCitation[]
  insufficient_evidence: boolean
  model: string | null
  retrieved_cases: number
  from_cache: boolean
}


type Filter =
  | 'all'
  | 'review'
  | string


function App() {
  const [
    availableIssues,
    setAvailableIssues,
  ] = useState<IssueSummary[]>([])

  const [
    selectedIssueSlug,
    setSelectedIssueSlug,
  ] = useState<string | null>(
    null,
  )

  const [
    issue,
    setIssue,
  ] = useState<Issue | null>(
    null,
  )

  const [
    timeline,
    setTimeline,
  ] = useState<Timeline | null>(
    null,
  )

  const [
    cases,
    setCases,
  ] = useState<CaseItem[]>(
    [],
  )

  const [
    filter,
    setFilter,
  ] = useState<Filter>(
    'all',
  )

  const [
    selectedCaseId,
    setSelectedCaseId,
  ] = useState<number | null>(
    null,
  )

  const [
    caseDetail,
    setCaseDetail,
  ] = useState<CaseDetail | null>(
    null,
  )

  const [
    detailLoading,
    setDetailLoading,
  ] = useState(false)

  const [
    detailError,
    setDetailError,
  ] = useState<string | null>(
    null,
  )

  const [
    loadingIssues,
    setLoadingIssues,
  ] = useState(true)

  const [
    loading,
    setLoading,
  ] = useState(false)

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )

  const [
    chatQuestion,
    setChatQuestion,
  ] = useState('')

  const [
    chatResponse,
    setChatResponse,
  ] = useState<ChatResponse | null>(
    null,
  )

  const [
    chatLoading,
    setChatLoading,
  ] = useState(false)

  const [
    chatError,
    setChatError,
  ] = useState<string | null>(
    null,
  )


  useEffect(
    () => {
      async function loadIssues() {
        try {
          setLoadingIssues(
            true,
          )

          setError(
            null,
          )

          const response =
            await fetch(
              `${API_BASE}/api/issues`,
            )

          if (
            !response.ok
          ) {
            throw new Error(
              'Não foi possível carregar as questões jurídicas.',
            )
          }

          const data:
            IssueSummary[] =
            await response.json()

          setAvailableIssues(
            data,
          )
        } catch (
        err
        ) {
          setError(
            err instanceof Error
              ? err.message
              : 'Erro inesperado.',
          )
        } finally {
          setLoadingIssues(
            false,
          )
        }
      }

      void loadIssues()
    },
    [],
  )


  useEffect(
    () => {
      if (
        !selectedIssueSlug
      ) {
        setIssue(
          null,
        )

        setTimeline(
          null,
        )

        setCases(
          [],
        )

        return
      }

      async function loadDashboard() {
        try {
          setLoading(
            true,
          )

          setError(
            null,
          )

          setFilter(
            'all',
          )

          const [
            issueResponse,
            timelineResponse,
            casesResponse,
          ] = await Promise.all(
            [
              fetch(
                `${API_BASE}/api/issues/${selectedIssueSlug}`,
              ),

              fetch(
                `${API_BASE}/api/issues/${selectedIssueSlug}/timeline`,
              ),

              fetch(
                `${API_BASE}/api/issues/${selectedIssueSlug}/cases`,
              ),
            ],
          )

          if (
            !issueResponse.ok
            || !timelineResponse.ok
            || !casesResponse.ok
          ) {
            throw new Error(
              'Não foi possível carregar a análise desta questão.',
            )
          }

          const issueData:
            Issue =
            await issueResponse.json()

          const timelineData:
            Timeline =
            await timelineResponse.json()

          const casesData:
            CasesResponse =
            await casesResponse.json()

          setIssue(
            issueData,
          )

          setTimeline(
            timelineData,
          )

          setCases(
            casesData.cases,
          )
        } catch (
        err
        ) {
          setError(
            err instanceof Error
              ? err.message
              : 'Erro inesperado.',
          )
        } finally {
          setLoading(
            false,
          )
        }
      }

      void loadDashboard()
    },
    [
      selectedIssueSlug,
    ],
  )


  useEffect(
    () => {
      if (
        selectedCaseId === null
        || !selectedIssueSlug
      ) {
        return
      }

      async function loadCaseDetail() {
        try {
          setDetailLoading(
            true,
          )

          setDetailError(
            null,
          )

          const response =
            await fetch(
              `${API_BASE}/api/issues/${selectedIssueSlug}/cases/${selectedCaseId}`,
            )

          if (
            !response.ok
          ) {
            throw new Error(
              'Não foi possível carregar o acórdão.',
            )
          }

          const data:
            CaseDetail =
            await response.json()

          setCaseDetail(
            data,
          )
        } catch (
        err
        ) {
          setCaseDetail(
            null,
          )

          setDetailError(
            err instanceof Error
              ? err.message
              : 'Erro inesperado.',
          )
        } finally {
          setDetailLoading(
            false,
          )
        }
      }

      void loadCaseDetail()
    },
    [
      selectedCaseId,
      selectedIssueSlug,
    ],
  )


  useEffect(
    () => {
      function closeOnEscape(
        event: KeyboardEvent,
      ) {
        if (
          event.key
          === 'Escape'
        ) {
          closeCaseDetail()
        }
      }

      if (
        selectedCaseId
        !== null
      ) {
        window.addEventListener(
          'keydown',
          closeOnEscape,
        )
      }

      return () =>
        window.removeEventListener(
          'keydown',
          closeOnEscape,
        )
    },
    [
      selectedCaseId,
    ],
  )


  function resetChat() {
    setChatQuestion(
      '',
    )

    setChatResponse(
      null,
    )

    setChatError(
      null,
    )
  }


  function selectIssue(
    slug: string,
  ) {
    setSelectedCaseId(
      null,
    )

    setCaseDetail(
      null,
    )

    resetChat()

    setSelectedIssueSlug(
      slug,
    )

    window.scrollTo(
      {
        top: 0,
        behavior: 'smooth',
      },
    )
  }


  function goHome() {
    setSelectedCaseId(
      null,
    )

    setCaseDetail(
      null,
    )

    resetChat()

    setSelectedIssueSlug(
      null,
    )

    setError(
      null,
    )

    window.scrollTo(
      {
        top: 0,
        behavior: 'smooth',
      },
    )
  }


  function openCaseDetail(
    caseId: number,
  ) {
    setCaseDetail(
      null,
    )

    setDetailError(
      null,
    )

    setSelectedCaseId(
      caseId,
    )
  }


  function closeCaseDetail() {
    setSelectedCaseId(
      null,
    )

    setCaseDetail(
      null,
    )

    setDetailError(
      null,
    )
  }


  async function askCorpus(
    questionOverride?: string,
  ) {
    if (
      !selectedIssueSlug
      || chatLoading
    ) {
      return
    }

    const question = (
      questionOverride
      ?? chatQuestion
    ).trim()

    if (
      !question
    ) {
      setChatError(
        'Escreve uma pergunta sobre esta questão jurídica.',
      )

      return
    }

    try {
      setChatQuestion('')

      setChatLoading(
        true,
      )

      setChatError(
        null,
      )

      setChatResponse(
        null,
      )

      const response =
        await fetch(
          `${API_BASE}/api/issues/${selectedIssueSlug}/chat`,
          {
            method:
              'POST',

            headers: {
              'Content-Type':
                'application/json',
            },

            body:
              JSON.stringify(
                {
                  question,
                },
              ),
          },
        )

      if (
        !response.ok
      ) {
        let message =
          'Não foi possível obter uma resposta do JurisShift.'

        try {
          const payload =
            await response.json()

          if (
            typeof payload
              ?.detail
            === 'string'
          ) {
            message =
              payload.detail
          }
        } catch {
          // Mantém a mensagem genérica.
        }

        throw new Error(
          message,
        )
      }

      const data:
        ChatResponse =
        await response.json()

      setChatResponse(
        data,
      )
    } catch (
    err
    ) {
      setChatError(
        err instanceof Error
          ? err.message
          : 'Erro inesperado ao consultar o corpus.',
      )
    } finally {
      setChatLoading(
        false,
      )
    }
  }


  const chartData =
    useMemo(
      () => {
        if (
          !timeline
          || !issue
        ) {
          return []
        }

        return (
          timeline.years.map(
            item => {
              const row:
                Record<
                  string,
                  string | number
                > = {
                year:
                  item.year,
              }

              for (
                const position
                of issue.positions
              ) {
                row[
                  position.id
                ] =
                  item.positions[
                  position.id
                  ]
                  ?? 0
              }

              return row
            },
          )
        )
      },
      [
        timeline,
        issue,
      ],
    )


  const courtTime =
    useMemo(
      () => {
        const relevant =
          cases.filter(
            item =>
              item
                .stance
                .decides_issue
              && item
                .decision_date
              && item
                .stance
                .position_id,
          )

        const courts =
          Array.from(
            new Set(
              relevant.map(
                item =>
                  item.court
                  ?? 'Tribunal não identificado',
              ),
            ),
          ).sort(
            (
              a,
              b,
            ) => {
              if (
                a === 'STJ'
              ) {
                return -1
              }

              if (
                b === 'STJ'
              ) {
                return 1
              }

              return (
                a.localeCompare(
                  b,
                  'pt',
                )
              )
            },
          )

        const points:
          CourtTimePoint[] =
          relevant.map(
            item => {
              const court =
                item.court
                ?? 'Tribunal não identificado'

              const decisionDate =
                item.decision_date!

              const courtPosition =
                courts.indexOf(
                  court,
                )

              return {
                caseId:
                  item.id,

                processNumber:
                  item.process_number,

                court,

                decisionDate,

                timestamp:
                  new Date(
                    `${decisionDate}T00:00:00Z`,
                  ).getTime(),

                courtIndex:
                  courts.length
                  - 1
                  - courtPosition,

                positionId:
                  item
                    .stance
                    .position_id!,

                positionLabel:
                  item
                    .stance
                    .position_label
                  ?? 'Sem posição',

                status:
                  item
                    .stance
                    .status,
              }
            },
          )

        return {
          courts,
          points,
        }
      },
      [
        cases,
      ],
    )


  const visibleCases =
    useMemo(
      () => {
        const relevant =
          cases.filter(
            item =>
              item
                .stance
                .decides_issue,
          )

        if (
          filter === 'review'
        ) {
          return (
            cases.filter(
              item =>
                item
                  .stance
                  .status
                === 'REVIEW',
            )
          )
        }

        if (
          filter !== 'all'
        ) {
          return (
            relevant.filter(
              item =>
                item
                  .stance
                  .position_id
                === filter,
            )
          )
        }

        return relevant
      },
      [
        cases,
        filter,
      ],
    )


  if (
    loadingIssues
  ) {
    return (
      <StateScreen
        text="A carregar jurisprudência..."
      />
    )
  }


  if (
    !selectedIssueSlug
  ) {
    return (
      <HomePage
        issues={
          availableIssues
        }
        error={
          error
        }
        onSelect={
          selectIssue
        }
      />
    )
  }


  if (
    loading
  ) {
    return (
      <StateScreen
        text="A analisar jurisprudência..."
      />
    )
  }


  if (
    error
    || !issue
    || !timeline
  ) {
    return (
      <main
        className="state-screen"
      >
        <strong>
          Não foi possível carregar esta análise.
        </strong>

        <p>
          {
            error
            ?? 'Confirma que a API está disponível na porta 8000.'
          }
        </p>

        <button
          className="filter-button"
          onClick={
            goHome
          }
        >
          Voltar às questões
        </button>
      </main>
    )
  }


  const insight =
    buildCorpusInsight(
      issue,
    )


  return (
    <div
      className="app-shell"
    >
      <Topbar />


      <main>
        <div
          className="back-row"
        >
          <button
            className="filter-button"
            onClick={
              goHome
            }
          >
            <ArrowLeft
              size={15}
            />

            Todas as questões
          </button>
        </div>


        <section
          className="hero issue-hero"
        >
          <div
            className="hero-copy"
          >
            <div
              className="eyebrow"
            >
              <FileSearch
                size={15}
              />

              Análise de divergência jurisprudencial
            </div>

            <h1>
              {
                issue.title
              }
            </h1>

            <p
              className="question"
            >
              {
                issue.question
              }
            </p>

            <div
              className="hero-meta"
            >
              {
                issue
                  .landmark
                  .label
                && (
                  <span>
                    <Landmark
                      size={15}
                    />

                    Marco: {
                      issue
                        .landmark
                        .label
                    }
                  </span>
                )
              }

              {
                issue
                  .stats
                  .divergence_detected
                && (
                  <span
                    className="divergence-pill"
                  >
                    Divergência identificada
                  </span>
                )
              }
            </div>
          </div>

        </section>


        <section
          className="stats-grid"
        >
          <StatCard
            value={
              issue
                .stats
                .analyzed_cases
            }
            label="Acórdãos analisados"
            icon={
              <FileSearch
                size={18}
              />
            }
          />

          <StatCard
            value={
              issue
                .stats
                .validated_deciding_cases
            }
            label="Decisões com evidência verificada"
            icon={
              <CheckCircle2
                size={18}
              />
            }
          />

          <StatCard
            value={
              issue
                .stats
                .represented_positions
            }
            label="Posições identificadas"
            icon={
              <Scale
                size={18}
              />
            }
          />

          <StatCard
            value={
              issue
                .stats
                .review_cases
            }
            label="Em revisão"
            icon={
              <Clock3
                size={18}
              />
            }
          />
        </section>


        {
          issue
            .divergence_analysis
            .detected
          && (
            <section
              className="panel divergence-panel"
            >
              <div
                className="timeline-insight"
              >
                <Scale
                  size={20}
                />

                <div>
                  <strong>
                    Divergência confirmada no corpus
                  </strong>

                  <p>
                    Foram identificadas {
                      issue
                        .stats
                        .represented_positions
                    } posições jurisprudenciais distintas através de {
                      issue
                        .divergence_analysis
                        .validated_decisions
                    } decisões AUTO com evidência textual verificada.
                  </p>

                  {
                    issue
                      .divergence_analysis
                      .overlaps
                      .length
                    > 0
                    && (
                      <p>
                        Coexistência observada: {
                          formatDate(
                            issue
                              .divergence_analysis
                              .overlaps[0]
                              .start_date,
                          )
                        } – {
                          formatDate(
                            issue
                              .divergence_analysis
                              .overlaps[0]
                              .end_date,
                          )
                        }.
                      </p>
                    )
                  }

                  <p>
                    {
                      issue
                        .divergence_analysis
                        .scope_note
                    }
                  </p>
                </div>
              </div>
            </section>
          )
        }




        <section
          className="positions-grid"
        >
          {
            issue
              .positions
              .map(
                (
                  position,
                  index,
                ) => (
                  <PositionCard
                    key={
                      position.id
                    }
                    position={
                      position
                    }
                    variant={
                      index % 2 === 0
                        ? 'primary'
                        : 'secondary'
                    }
                  />
                ),
              )
          }
        </section>


        <section
          className="panel timeline-panel"
        >
          <div
            className="section-heading"
          >
            <div>
              <span
                className="section-kicker"
              >
                Evolução
              </span>

              <h2>
                Evolução jurisprudencial
              </h2>
            </div>

            <p>
              Número de decisões com evidência verificada que adotam cada posição no corpus analisado.
            </p>
          </div>


          <div
            className="chart-wrapper"
          >
            <ResponsiveContainer
              width="100%"
              height={380}
            >
              <LineChart
                data={
                  chartData
                }
                margin={{
                  top: 22,
                  right: 28,
                  left: 0,
                  bottom: 8,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={
                    false
                  }
                />

                <XAxis
                  dataKey="year"
                  tickLine={
                    false
                  }
                  axisLine={
                    false
                  }
                />

                <YAxis
                  allowDecimals={
                    false
                  }
                  tickLine={
                    false
                  }
                  axisLine={
                    false
                  }
                />

                <Tooltip />

                <Legend />


                {
                  timeline
                    .landmark
                    .year
                  && (
                    <ReferenceLine
                      x={
                        timeline
                          .landmark
                          .year
                      }
                      strokeDasharray="5 5"
                      label={{
                        value:
                          timeline
                            .landmark
                            .label
                          ?? 'Marco',

                        position:
                          'insideTopRight',
                      }}
                    />
                  )
                }


                {
                  issue
                    .positions
                    .map(
                      (
                        position,
                        index,
                      ) => (
                        <Line
                          key={
                            position.id
                          }
                          type="monotone"
                          dataKey={
                            position.id
                          }
                          name={
                            position.label
                          }
                          stroke={
                            POSITION_COLORS[
                            index
                            % POSITION_COLORS.length
                            ]
                          }
                          strokeWidth={
                            index === 0
                              ? 3
                              : 2
                          }
                          strokeDasharray={
                            index === 0
                              ? undefined
                              : '7 5'
                          }
                          dot={{
                            r: 5,
                          }}
                          activeDot={{
                            r: 7,
                          }}
                        />
                      ),
                    )
                }
              </LineChart>
            </ResponsiveContainer>
          </div>


          <div
            className="timeline-insight"
          >
            <CheckCircle2
              size={18}
            />

            <div>
              <strong>
                Padrão observado no corpus
              </strong>

              <p>
                {
                  insight
                }
              </p>
            </div>
          </div>
        </section>


        <section
          className="panel timeline-panel"
        >
          <div
            className="section-heading"
          >
            <div>
              <span
                className="section-kicker"
              >
                Onde e quando
              </span>

              <h2>
                Tribunal × tempo
              </h2>
            </div>

            <p>
              Cada ponto representa uma decisão que resolve diretamente a questão jurídica.
            </p>
          </div>


          <div
            className="chart-wrapper"
          >
            <ResponsiveContainer
              width="100%"
              height={
                Math.max(
                  380,
                  courtTime
                    .courts
                    .length
                  * 75,
                )
              }
            >
              <ScatterChart
                margin={{
                  top: 24,
                  right: 28,
                  bottom: 34,
                  left: 20,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  type="number"
                  dataKey="timestamp"
                  domain={[
                    'dataMin',
                    'dataMax',
                  ]}
                  scale="time"
                  tickFormatter={
                    value =>
                      new Date(
                        value,
                      ).getUTCFullYear()
                        .toString()
                  }
                  name="Data"
                />

                <YAxis
                  type="number"
                  dataKey="courtIndex"
                  domain={[
                    -0.5,
                    Math.max(
                      0.5,
                      courtTime
                        .courts
                        .length
                      - 0.5,
                    ),
                  ]}
                  ticks={
                    courtTime
                      .courts
                      .map(
                        (
                          _,
                          index,
                        ) =>
                          index,
                      )
                  }
                  tickFormatter={
                    value => {
                      const index =
                        courtTime
                          .courts
                          .length
                        - 1
                        - Number(
                          value,
                        )

                      return (
                        courtTime
                          .courts[
                        index
                        ]
                        ?? ''
                      )
                    }
                  }
                  allowDecimals={
                    false
                  }
                  width={120}
                />

                <Tooltip
                  content={
                    <CourtTimeTooltip />
                  }
                />

                <Legend />


                {
                  issue
                    .positions
                    .map(
                      (
                        position,
                        index,
                      ) => (
                        <Scatter
                          key={
                            position.id
                          }
                          name={
                            position.label
                          }
                          data={
                            courtTime
                              .points
                              .filter(
                                point =>
                                  point
                                    .positionId
                                  === position.id
                                  && point
                                    .status
                                  !== 'REVIEW',
                              )
                          }
                          fill={
                            POSITION_COLORS[
                            index
                            % POSITION_COLORS.length
                            ]
                          }
                          cursor="pointer"
                          onClick={
                            (
                              entry:
                                unknown,
                            ) => {
                              const point =
                                (
                                  entry as {
                                    payload?:
                                    CourtTimePoint
                                  }
                                )
                                  .payload

                              if (
                                point
                              ) {
                                openCaseDetail(
                                  point.caseId,
                                )
                              }
                            }
                          }
                        />
                      ),
                    )
                }


                <Scatter
                  name="Em revisão"
                  data={
                    courtTime
                      .points
                      .filter(
                        point =>
                          point
                            .status
                          === 'REVIEW',
                      )
                  }
                  fill="#64748b"
                  fillOpacity={0.4}
                  stroke="#334155"
                  strokeWidth={2}
                  cursor="pointer"
                  onClick={
                    (
                      entry:
                        unknown,
                    ) => {
                      const point =
                        (
                          entry as {
                            payload?:
                            CourtTimePoint
                          }
                        )
                          .payload

                      if (
                        point
                      ) {
                        openCaseDetail(
                          point.caseId,
                        )
                      }
                    }
                  }
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>


          <div
            className="timeline-insight"
          >
            <Landmark
              size={18}
            />

            <div>
              <strong>
                Visualização baseada no corpus analisado
              </strong>

              <p>
                A posição vertical identifica o tribunal e a posição horizontal a data da decisão. Os casos em revisão não são tratados como evidência confirmada da divergência.
              </p>
            </div>
          </div>
        </section>


        <CorpusChat
          issue={
            issue
          }
          question={
            chatQuestion
          }
          response={
            chatResponse
          }
          loading={
            chatLoading
          }
          error={
            chatError
          }
          onQuestionChange={
            setChatQuestion
          }
          onAsk={
            askCorpus
          }
          onOpenCitation={
            openCaseDetail
          }
        />


        <section
          className="panel cases-panel"
        >
          <div
            className="section-heading cases-heading"
          >
            <div>
              <span
                className="section-kicker"
              >
                Evidência
              </span>

              <h2>
                Acórdãos analisados
              </h2>
            </div>

            <span
              className="case-total"
            >
              {
                visibleCases
                  .length
              } resultados
            </span>
          </div>


          <div
            className="filters"
          >
            <FilterButton
              active={
                filter === 'all'
              }
              onClick={
                () =>
                  setFilter(
                    'all',
                  )
              }
            >
              Todos os relevantes
            </FilterButton>


            {
              issue
                .positions
                .map(
                  position => (
                    <FilterButton
                      key={
                        position.id
                      }
                      active={
                        filter
                        === position.id
                      }
                      onClick={
                        () =>
                          setFilter(
                            position.id,
                          )
                      }
                    >
                      {
                        position.label
                      }
                    </FilterButton>
                  ),
                )
            }


            {
              issue
                .stats
                .review_cases
              > 0
              && (
                <FilterButton
                  active={
                    filter
                    === 'review'
                  }
                  onClick={
                    () =>
                      setFilter(
                        'review',
                      )
                  }
                >
                  Em revisão
                </FilterButton>
              )
            }
          </div>


          <div
            className="case-list"
          >
            {
              visibleCases.map(
                item => (
                  <CaseCard
                    key={
                      item.id
                    }
                    item={
                      item
                    }
                    positions={
                      issue.positions
                    }
                    onOpen={
                      () =>
                        openCaseDetail(
                          item.id,
                        )
                    }
                  />
                ),
              )
            }
          </div>
        </section>


        <section
          className="methodology"
        >
          <div>
            <strong>
              Como ler estes resultados
            </strong>

            <p>
              O JurisShift identifica posições jurisprudenciais no corpus analisado e associa cada conclusão a evidência textual verificável. Os resultados não pretendem medir a prevalência de uma orientação em toda a jurisprudência portuguesa.
            </p>
          </div>
        </section>
      </main>


      {
        selectedCaseId
        !== null
        && (
          <CaseDetailModal
            detail={
              caseDetail
            }
            positions={
              issue.positions
            }
            error={
              detailError
            }
            loading={
              detailLoading
            }
            onClose={
              closeCaseDetail
            }
          />
        )
      }
    </div>
  )
}


function Topbar() {
  return (
    <header
      className="topbar"
    >
      <div
        className="brand"
      >
        <div
          className="brand-mark"
        >
          <Scale
            size={19}
          />
        </div>

        <span>
          JurisShift
        </span>
      </div>

      <div
        className="topbar-meta"
      >
        <span
          className="live-dot"
        />

        Jurisprudência portuguesa
      </div>
    </header>
  )
}


function HomePage({
  issues,
  error,
  onSelect,
}: {
  issues: IssueSummary[]
  error: string | null
  onSelect: (
    slug: string,
  ) => void
}) {
  return (
    <div
      className="app-shell"
    >
      <Topbar />

      <main>
        <section
          className="hero home-hero"
        >
          <div
            className="hero-copy"
          >
            <div
              className="eyebrow"
            >
              <Scale
                size={15}
              />

              Exploração de jurisprudência
            </div>

            <h1>
              Onde a jurisprudência diverge — e quando muda.
            </h1>

            <p
              className="question"
            >
              Explore questões jurídicas concretas, compare posições jurisprudenciais e consulte a evidência textual que sustenta cada classificação.
            </p>
          </div>


          <aside
            className="hero-summary"
          >
            <span>
              Questões disponíveis
            </span>

            <strong>
              {
                issues.length
              }
            </strong>

            <p>
              Protótipo baseado num corpus delimitado e auditável.
            </p>
          </aside>
        </section>


        {
          error
          && (
            <section
              className="panel error-panel"
            >
              <strong>
                {
                  error
                }
              </strong>
            </section>
          )
        }


        <section
          className="panel issue-picker"
        >
          <div
            className="section-heading"
          >
            <div>
              <span
                className="section-kicker"
              >
                Questões jurídicas
              </span>

              <h2>
                Escolha uma análise
              </h2>
            </div>

            <p>
              Cada questão contém posições, evolução temporal, acórdãos e evidência verificável.
            </p>
          </div>


          <div
            className="positions-grid issue-grid"
          >
            {
              issues.map(
                (
                  currentIssue,
                  index,
                ) => (
                  <article
                    key={
                      currentIssue.slug
                    }
                    className={
                      `position-card ${index % 2 === 0
                        ? 'primary'
                        : 'secondary'
                      }`
                    }
                    role="button"
                    tabIndex={0}
                    onClick={
                      () =>
                        onSelect(
                          currentIssue.slug,
                        )
                    }
                    onKeyDown={
                      event => {
                        if (
                          event.key
                          === 'Enter'
                          || event.key
                          === ' '
                        ) {
                          event.preventDefault()

                          onSelect(
                            currentIssue.slug,
                          )
                        }
                      }
                    }
                  >
                    <div
                      className="position-top"
                    >
                      <span
                        className="position-label"
                      >
                        {
                          currentIssue.source
                        }
                      </span>

                      <strong
                        className="position-count"
                      >
                        {
                          currentIssue
                            .analyzed_cases
                        }
                      </strong>
                    </div>


                    <h3>
                      {
                        currentIssue.title
                      }
                    </h3>

                    <p>
                      {
                        currentIssue.question
                      }
                    </p>


                    <div
                      className="position-footer"
                    >
                      {
                        currentIssue
                          .deciding_cases
                      } decisões relevantes · {
                        currentIssue
                          .review_cases
                      } em revisão

                      <span
                        className="issue-open"
                      >
                        Abrir análise →
                      </span>
                    </div>
                  </article>
                ),
              )
            }
          </div>
        </section>


        <section
          className="methodology"
        >
          <div>
            <strong>
              Corpus delimitado
            </strong>

            <p>
              O protótipo não pretende cobrir toda a jurisprudência portuguesa. Cada questão apresenta apenas conclusões suportadas pelo corpus analisado e distingue evidência verificada de casos que exigem revisão.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}


function CorpusChat({
  issue,
  question,
  response,
  loading,
  error,
  onQuestionChange,
  onAsk,
  onOpenCitation,
}: {
  issue: Issue
  question: string
  response: ChatResponse | null
  loading: boolean
  error: string | null
  onQuestionChange: (
    value: string,
  ) => void
  onAsk: (
    questionOverride?: string,
  ) => Promise<void>
  onOpenCitation: (
    caseId: number,
  ) => void
}) {
  const suggestions =
    getChatSuggestions(
      issue,
    )


  function submit(
    event:
      FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    void onAsk()
  }


  return (
    <section
      className="panel chat-panel"
    >
      <div
        className="section-heading chat-heading"
      >
        <div>
          <span
            className="section-kicker"
          >
            Assistente com RAG
          </span>

          <h2>
            Pergunte ao corpus
          </h2>
        </div>

        <p>
          As respostas são geradas apenas a partir dos acórdãos com evidência verificada desta questão e incluem fontes clicáveis.
        </p>
      </div>


      <div
        className="chat-layout"
      >
        <div
          className="chat-compose"
        >
          <div
            className="chat-compose-label"
          >
            <MessageSquareText
              size={18}
            />

            <div>
              <strong>
                Faça uma pergunta jurídica
              </strong>

              <span>
                O JurisShift não usa conhecimento externo para preencher lacunas do corpus.
              </span>
            </div>
          </div>


          <form
            className="chat-form"
            onSubmit={
              submit
            }
          >
            <textarea
              value={
                question
              }
              onChange={
                event =>
                  onQuestionChange(
                    event.target.value,
                  )
              }
              placeholder="Ex.: Havia divergência antes da uniformização?"
              rows={4}
              maxLength={1500}
              disabled={
                loading
              }
            />


            <div
              className="chat-form-footer"
            >
              <span>
                {
                  question.length
                } / 1500
              </span>

              <button
                type="submit"
                className="chat-submit"
                disabled={
                  loading
                  || !question
                    .trim()
                }
              >
                {
                  loading
                    ? (
                      <>
                        <span
                          className="chat-button-spinner"
                        />

                        A consultar
                      </>
                    )
                    : (
                      <>
                        <Send
                          size={16}
                        />

                        Perguntar
                      </>
                    )
                }
              </button>
            </div>
          </form>


          <div
            className="chat-suggestions"
          >
            <span>
              Experimente
            </span>

            <div>
              {
                suggestions.map(
                  suggestion => (
                    <button
                      key={
                        suggestion
                      }
                      type="button"
                      disabled={
                        loading
                      }
                      onClick={
                        () => {
                          onQuestionChange(
                            suggestion,
                          )

                          void onAsk(
                            suggestion,
                          )
                        }
                      }
                    >
                      {
                        suggestion
                      }
                    </button>
                  ),
                )
              }
            </div>
          </div>
        </div>


        <div
          className="chat-output"
        >
          {
            !response
            && !loading
            && !error
            && (
              <div
                className="chat-empty"
              >
                <MessageSquareText
                  size={24}
                />

                <strong>
                  Resposta fundamentada no corpus
                </strong>

                <p>
                  Faça uma pergunta para obter uma síntese acompanhada dos acórdãos que a sustentam.
                </p>
              </div>
            )
          }


          {
            loading
            && (
              <div
                className="chat-empty"
              >
                <div
                  className="spinner"
                />

                <strong>
                  A consultar os acórdãos...
                </strong>

                <p>
                  O sistema está a recuperar evidência e a preparar uma resposta com fontes verificáveis.
                </p>
              </div>
            )
          }


          {
            error
            && !loading
            && (
              <div
                className="chat-error"
              >
                <strong>
                  Não foi possível responder.
                </strong>

                <p>
                  {
                    error
                  }
                </p>
              </div>
            )
          }


          {
            response
            && !loading
            && (
              <div
                className={
                  `chat-response ${response
                    .insufficient_evidence
                    ? 'insufficient'
                    : ''
                  }`
                }
              >
                <div
                  className="chat-response-head"
                >
                  <div
                    className="chat-response-icon"
                  >
                    <Scale
                      size={17}
                    />
                  </div>

                  <div>
                    <strong>
                      JurisShift
                    </strong>

                    <span>
                      Resposta limitada ao corpus analisado
                    </span>
                  </div>
                </div>


                <div
                  className="chat-answer"
                >
                  {
                    splitChatAnswer(
                      response.answer,
                    ).map(
                      (
                        paragraph,
                        index,
                      ) => (
                        <p
                          key={
                            `${index}-${paragraph.slice(0, 24)}`
                          }
                        >
                          {
                            paragraph
                          }
                        </p>
                      ),
                    )
                  }
                </div>


                {
                  response
                    .citations
                    .length
                  > 0
                  && (
                    <div
                      className="chat-citations"
                    >
                      <span
                        className="chat-citations-label"
                      >
                        Fontes usadas na resposta
                      </span>

                      <div
                        className="chat-citation-list"
                      >
                        {
                          response
                            .citations
                            .map(
                              citation => (
                                <button
                                  key={
                                    citation
                                      .case_id
                                  }
                                  type="button"
                                  className="chat-citation"
                                  onClick={
                                    () =>
                                      onOpenCitation(
                                        citation
                                          .case_id,
                                      )
                                  }
                                >
                                  <div>
                                    <strong>
                                      Processo {
                                        citation
                                          .process_number
                                      }
                                    </strong>

                                    <span>
                                      {
                                        citation
                                          .court
                                        ?? 'Tribunal não identificado'
                                      } · {
                                        formatDate(
                                          citation
                                            .decision_date,
                                        )
                                      }
                                    </span>
                                  </div>

                                  <ArrowUpRight
                                    size={15}
                                  />
                                </button>
                              ),
                            )
                        }
                      </div>
                    </div>
                  )
                }
              </div>
            )
          }
        </div>
      </div>


      <p
        className="chat-disclaimer"
      >
        Ferramenta de exploração jurisprudencial. A resposta não constitui aconselhamento jurídico e não deve ser generalizada para além do corpus apresentado.
      </p>
    </section>
  )
}


function StateScreen({
  text,
}: {
  text: string
}) {
  return (
    <main
      className="state-screen"
    >
      <div
        className="spinner"
      />

      <p>
        {
          text
        }
      </p>
    </main>
  )
}


function StatCard({
  value,
  label,
  icon,
}: {
  value: number
  label: string
  icon: ReactNode
}) {
  return (
    <div
      className="stat-card"
    >
      <div
        className="stat-icon"
      >
        {
          icon
        }
      </div>

      <strong>
        {
          value
        }
      </strong>

      <span>
        {
          label
        }
      </span>
    </div>
  )
}


function PositionCard({
  position,
  variant,
}: {
  position: Position
  variant:
  | 'primary'
  | 'secondary'
}) {
  return (
    <article
      className={
        `position-card ${variant}`
      }
    >
      <div
        className="position-top"
      >
        <span
          className="position-label"
        >
          Posição jurisprudencial
        </span>

        <strong
          className="position-count"
        >
          {
            position
              .case_count
          }
        </strong>
      </div>

      <h3>
        {
          position.label
        }
      </h3>

      <p>
        {
          position.description
        }
      </p>

      <div
        className="position-footer"
      >
        {
          position
            .case_count
        } {
          position
            .case_count
            === 1
            ? 'decisão com evidência verificada'
            : 'decisões com evidência verificada'
        }
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
  children: ReactNode
}) {
  return (
    <button
      className={
        `filter-button ${active
          ? 'active'
          : ''
        }`
      }
      onClick={
        onClick
      }
    >
      {
        children
      }
    </button>
  )
}


function getPositionVariant(
  positionId: string | null,
  positions: Position[],
) {
  if (
    !positionId
  ) {
    return 'five'
  }

  const index =
    positions.findIndex(
      position =>
        position.id
        === positionId,
    )

  return (
    index === 1
      ? 'twenty'
      : 'five'
  )
}


function CaseCard({
  item,
  positions,
  onOpen,
}: {
  item: CaseItem
  positions: Position[]
  onOpen: () => void
}) {
  const isReview =
    item
      .stance
      .status
    === 'REVIEW'

  const positionText =
    isReview
      ? 'Em revisão'
      : item
        .stance
        .position_label
      ?? 'Sem posição'

  const variant =
    getPositionVariant(
      item
        .stance
        .position_id,
      positions,
    )

  return (
    <article
      className={
        `case-card ${isReview
          ? 'case-card-review'
          : ''
        }`
      }
      onClick={
        onOpen
      }
      onKeyDown={
        event => {
          if (
            event.key
            === 'Enter'
            || event.key
            === ' '
          ) {
            event.preventDefault()

            onOpen()
          }
        }
      }
      role="button"
      tabIndex={0}
    >
      <div
        className="case-header"
      >
        <div>
          <div
            className="case-meta"
          >
            <span>
              {
                item.court
                ?? 'Tribunal não identificado'
              }
            </span>

            <span>
              ·
            </span>

            <span>
              {
                formatDate(
                  item
                    .decision_date,
                )
              }
            </span>
          </div>

          <h3>
            Processo {
              item
                .process_number
            }
          </h3>
        </div>

        <div
          className="case-badges"
        >
          <span
            className={
              `position-badge ${isReview
                ? 'review'
                : variant
              }`
            }
          >
            {
              positionText
            }
          </span>
        </div>
      </div>


      {
        item.evidence
          && !isReview
          ? (
            <blockquote>
              “{
                item
                  .evidence
                  .quote
              }”
            </blockquote>
          )
          : (
            <p
              className="no-evidence"
            >
              {
                isReview
                  ? 'Classificação assinalada para revisão: não é apresentada como evidência confirmada da divergência.'
                  : 'Não existe evidência textual verificada associada.'
              }
            </p>
          )
      }


      <div
        className="case-footer"
      >
        <div>
          {
            item
              .rapporteur
            && (
              <span>
                Relator: {
                  item
                    .rapporteur
                }
              </span>
            )
          }
        </div>

        <span
          className="case-open"
        >
          Ver detalhe

          <ArrowUpRight
            size={15}
          />
        </span>
      </div>
    </article>
  )
}


function CaseDetailModal({
  detail,
  positions,
  error,
  loading,
  onClose,
}: {
  detail:
  CaseDetail | null
  positions:
  Position[]
  error:
  string | null
  loading:
  boolean
  onClose:
  () => void
}) {
  const isReview =
    detail?.status
    === 'REVIEW'

  const context =
    detail
      ?.evidence
      ?.context

  const variant =
    getPositionVariant(
      detail
        ?.position
        ?.id
      ?? null,
      positions,
    )


  return (
    <div
      className="detail-overlay"
      onClick={
        onClose
      }
    >
      <section
        className="detail-modal"
        onClick={
          event =>
            event.stopPropagation()
        }
        role="dialog"
        aria-modal="true"
        aria-label="Detalhe do acórdão"
      >
        <button
          className="detail-close"
          onClick={
            onClose
          }
          aria-label="Fechar detalhe"
        >
          <X
            size={18}
          />
        </button>


        {
          loading
          && (
            <div
              className="detail-state"
            >
              <div
                className="spinner"
              />

              <p>
                A carregar acórdão...
              </p>
            </div>
          )
        }


        {
          !loading
          && error
          && (
            <div
              className="detail-state"
            >
              <strong>
                Não foi possível carregar o detalhe.
              </strong>

              <p>
                {
                  error
                }
              </p>
            </div>
          )
        }


        {
          !loading
          && !error
          && detail
          && (
            <>
              <div
                className="detail-header"
              >
                <div>
                  <div
                    className="case-meta"
                  >
                    <span>
                      {
                        detail.court
                        ?? 'Tribunal não identificado'
                      }
                    </span>

                    <span>
                      ·
                    </span>

                    <span>
                      {
                        formatDate(
                          detail
                            .decision_date,
                        )
                      }
                    </span>
                  </div>

                  <h2>
                    Processo {
                      detail
                        .process_number
                    }
                  </h2>
                </div>


                <div
                  className="case-badges"
                >
                  <span
                    className={
                      `position-badge ${isReview
                        ? 'review'
                        : variant
                      }`
                    }
                  >
                    {
                      isReview
                        ? 'Em revisão'
                        : detail
                          .position
                          ?.label
                        ?? 'Sem posição'
                    }
                  </span>
                </div>
              </div>


              <dl
                className="detail-meta-grid"
              >
                <div>
                  <dt>
                    Tribunal
                  </dt>

                  <dd>
                    {
                      detail.court
                      ?? 'Não identificado'
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    Relator
                  </dt>

                  <dd>
                    {
                      detail
                        .rapporteur
                      ?? 'Não identificado'
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    Questão
                  </dt>

                  <dd>
                    {
                      detail
                        .issue
                        ?.title
                      ?? 'Não associada'
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    Estado
                  </dt>

                  <dd>
                    {
                      detail.status === 'AUTO'
                        ? 'Evidência verificada'
                        : detail.status === 'REVIEW'
                          ? 'Em revisão'
                          : '-'
                    }
                  </dd>
                </div>
              </dl>


              {
                detail
                  .position
                && (
                  <section
                    className="detail-section"
                  >
                    <span
                      className="section-kicker"
                    >
                      Posição
                    </span>

                    <h3>
                      {
                        detail
                          .position
                          .label
                      }
                    </h3>

                    <p>
                      {
                        detail
                          .position
                          .description
                      }
                    </p>
                  </section>
                )
              }


              <section
                className="detail-section"
              >
                <span
                  className="section-kicker"
                >
                  Evidência
                </span>

                {
                  detail
                    .evidence
                    && !isReview
                    ? (
                      <>
                        {
                          context
                          && (
                            <p>
                              {
                                context.before
                              }
                            </p>
                          )
                        }

                        <blockquote>
                          “{
                            detail
                              .evidence
                              .quote
                          }”
                        </blockquote>

                        {
                          context
                          && (
                            <p>
                              {
                                context.after
                              }
                            </p>
                          )
                        }
                      </>
                    )
                    : (
                      <p
                        className="no-evidence"
                      >
                        {
                          isReview
                            ? 'Este caso está assinalado para revisão e não é usado como evidência verificada da divergência.'
                            : 'Não existe evidência textual verificada associada.'
                        }
                      </p>
                    )
                }
              </section>


              {
                detail
                  .source_url
                && (
                  <a
                    className="case-open detail-source-link"
                    href={
                      detail
                        .source_url
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    Abrir fonte original

                    <ArrowUpRight
                      size={15}
                    />
                  </a>
                )
              }
            </>
          )
        }
      </section>
    </div>
  )
}


function CourtTimeTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{
    payload:
    CourtTimePoint
  }>
}) {
  if (
    !active
    || !payload
    || payload.length === 0
  ) {
    return null
  }

  const point =
    payload[0].payload

  return (
    <div
      className="chart-tooltip"
    >
      <strong>
        Processo {
          point
            .processNumber
        }
      </strong>

      <span>
        {
          point.court
        }
      </span>

      <span>
        {
          formatDate(
            point
              .decisionDate,
          )
        }
      </span>

      <span>
        {
          point
            .positionLabel
        }
      </span>
    </div>
  )
}


function getChatSuggestions(
  issue: Issue,
) {
  if (
    issue.slug
    === 'loan-prescription-acceleration'
  ) {
    return [
      'Havia divergência jurisprudencial antes do AUJ 6/2022?',
      'Que decisões defenderam o prazo de vinte anos após o vencimento antecipado?',
      'Que decisões mantiveram o prazo de cinco anos antes do AUJ 6/2022?',
    ]
  }

  if (
    issue.slug
    === 'family-home-own-land'
  ) {
    return [
      'Que decisão defendeu a aplicação do artigo 1726.º?',
      'Que decisões entenderam que o imóvel permanecia bem próprio?',
      'Havia orientações divergentes antes do AUJ 9/2025?',
    ]
  }

  return [
    'Que posições jurisprudenciais foram identificadas?',
    'Que decisões sustentam cada posição?',
    'O corpus mostra divergência antes da uniformização?',
  ]
}


function splitChatAnswer(
  value: string,
) {
  const normalized =
    value
      .replace(
        /\\n/g,
        '\n',
      )
      .replace(
        /\s*\(CASE_IDs?[^)]*\)/gi,
        '',
      )
      .trim()

  if (
    !normalized
  ) {
    return []
  }

  const paragraphs =
    normalized
      .split(
        /\n{2,}/,
      )
      .map(
        paragraph =>
          paragraph.trim(),
      )
      .filter(
        Boolean,
      )

  return (
    paragraphs.length
      ? paragraphs
      : [
        normalized,
      ]
  )
}


function buildCorpusInsight(
  issue: Issue,
) {
  const positions =
    issue
      .divergence_analysis
      .position_ranges

  const overlap =
    issue
      .divergence_analysis
      .overlaps[0]

  if (
    issue
      .divergence_analysis
      .detected
  ) {
    if (
      overlap
    ) {
      return (
        `No corpus analisado foram observadas ${issue.stats.represented_positions} posições jurisprudenciais distintas. `
        + `Existem decisões com evidência verificada de ambas as orientações no intervalo ${formatDate(overlap.start_date)} – ${formatDate(overlap.end_date)}. `
        + 'A visualização descreve apenas o corpus analisado e não mede a prevalência geral na jurisprudência portuguesa.'
      )
    }

    return (
      `No corpus analisado foram identificadas ${issue.stats.represented_positions} posições jurisprudenciais distintas, `
      + `sustentadas por ${issue.stats.validated_deciding_cases} decisões com evidência verificada. `
      + 'O resultado não deve ser interpretado como uma medição da prevalência geral na jurisprudência portuguesa.'
    )
  }

  if (
    positions.length === 1
  ) {
    return (
      'O corpus com evidência verificada representa apenas uma posição jurisprudencial. '
      + 'Não existe evidência suficiente neste subset para afirmar divergência.'
    )
  }

  return (
    'O corpus analisado não contém evidência verificada suficiente para caracterizar uma divergência jurisprudencial.'
  )
}


function formatDate(
  value:
    string | null,
) {
  return (
    value
      ? new Intl.DateTimeFormat(
        'pt-PT',
        {
          day:
            '2-digit',

          month:
            '2-digit',

          year:
            'numeric',
        },
      ).format(
        new Date(
          `${value}T00:00:00Z`,
        ),
      )
      : 'Data não disponível'
  )
}


export default App