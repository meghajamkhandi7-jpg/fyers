import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Activity, AlertCircle, Briefcase, Brain, Wallet } from 'lucide-react'
import { fetchAgentDetail, fetchAgentEconomic, fetchAgentTasks, fetchLatestFyersScreener, fetchLatestInstitutionalShadow } from '../api'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { motion } from 'framer-motion'
import { useDisplayName } from '../DisplayNamesContext'

const formatINR = (value, digits = 2) =>
  `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`

const Dashboard = ({ agents, selectedAgent }) => {
  const dn = useDisplayName()
  const [agentDetails, setAgentDetails] = useState(null)
  const [economicData, setEconomicData] = useState(null)
  const [tasksData, setTasksData] = useState(null)
  const [fyersScreener, setFyersScreener] = useState(null)
  const [institutionalShadow, setInstitutionalShadow] = useState(null)
  const [loading, setLoading] = useState(true)
  const [resultsView, setResultsView] = useState('few')
  const [basketFilter, setBasketFilter] = useState('ALL')
  const [signalFilter, setSignalFilter] = useState('ALL')
  const [signalSort, setSignalSort] = useState('default')

  useEffect(() => {
    let cancelled = false

    if (!selectedAgent) {
      setAgentDetails(null)
      setEconomicData(null)
      setTasksData(null)
      setFyersScreener(null)
      setInstitutionalShadow(null)
      setLoading(false)
      return () => { cancelled = true }
    }

    const loadSelectedAgent = async () => {
      try {
        setLoading(true)
        setAgentDetails(null)
        setEconomicData(null)
        setTasksData(null)
        setInstitutionalShadow(null)

        const [details, economic, tasks, screener, shadow] = await Promise.allSettled([
          fetchAgentDetail(selectedAgent),
          fetchAgentEconomic(selectedAgent),
          fetchAgentTasks(selectedAgent),
          fetchLatestFyersScreener(),
          fetchLatestInstitutionalShadow(selectedAgent),
        ])

        if (cancelled) return

        setAgentDetails(details.status === 'fulfilled' ? details.value : null)
        setEconomicData(economic.status === 'fulfilled' ? economic.value : null)
        setTasksData(tasks.status === 'fulfilled' ? tasks.value : null)
        setFyersScreener(screener.status === 'fulfilled' ? screener.value : null)
        setInstitutionalShadow(shadow.status === 'fulfilled' ? shadow.value : null)
      } catch (error) {
        if (!cancelled) {
          console.error('Error loading selected agent:', error)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadSelectedAgent()

    return () => {
      cancelled = true
    }
  }, [selectedAgent])

  useEffect(() => {
    if (!selectedAgent) return

    const id = setInterval(() => {
      fetchLatestFyersScreener().then(d => setFyersScreener(d)).catch(() => {})
      fetchLatestInstitutionalShadow(selectedAgent).then(d => setInstitutionalShadow(d)).catch(() => {})
    }, 15000)

    return () => clearInterval(id)
  }, [selectedAgent])

  if (!selectedAgent) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-600">No Agent Selected</h2>
          <p className="text-gray-500 mt-2">Select an agent from the sidebar to view details</p>
        </div>
      </div>
    )
  }

  if (loading || !agentDetails) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const { current_status, balance_history, decisions } = agentDetails

  const getStatusColor = (status) => {
    switch (status) {
      case 'thriving':
        return 'text-green-600 bg-green-50 border-green-200'
      case 'stable':
        return 'text-blue-600 bg-blue-50 border-blue-200'
      case 'struggling':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      case 'bankrupt':
        return 'text-red-600 bg-red-50 border-red-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const getStatusEmoji = (status) => {
    switch (status) {
      case 'thriving':
        return '💪'
      case 'stable':
        return '👍'
      case 'struggling':
        return '⚠️'
      case 'bankrupt':
        return '💀'
      default:
        return '❓'
    }
  }

  const getActivityIcon = (activity) => {
    switch (activity) {
      case 'work':
        return <Briefcase className="w-5 h-5" />
      case 'learn':
        return <Brain className="w-5 h-5" />
      default:
        return <Activity className="w-5 h-5" />
    }
  }

  // Prepare chart data
  const balanceChartData = balance_history?.filter(item => item.date !== 'initialization').map(item => ({
    date: item.date,
    balance: item.balance,
    tokenCost: item.daily_token_cost || 0,
    workIncome: item.work_income_delta || 0,
  })) || []

  const QUALITY_CLIFF = 0.6

  // Domain earnings breakdown per occupation:
  //   earned  (green) — payment from tasks with score >= QUALITY_CLIFF
  //   failed  (red)   — task_value_usd of tasks that were completed but scored < QUALITY_CLIFF
  //                     (agent burned tokens, got almost nothing — a real loss)
  //   untapped (blue) — task_value_usd of tasks never completed
  const domainChartData = (() => {
    const tasks = tasksData?.tasks || []
    const byDomain = {}
    for (const t of tasks) {
      const domain = t.occupation || t.sector || 'Unknown'
      if (!byDomain[domain]) byDomain[domain] = { earned: 0, failed: 0, untapped: 0, totalTasks: 0 }
      byDomain[domain].totalTasks += 1
      const score = t.evaluation_score
      if (t.completed) {
        if (score === null || score === undefined || score >= QUALITY_CLIFF) {
          byDomain[domain].earned += (t.payment || 0)
        } else {
          // Worked but failed quality gate — show full task value as "loss"
          byDomain[domain].failed += (t.task_value_usd || 0)
        }
      } else {
        byDomain[domain].untapped += (t.task_value_usd || 0)
      }
    }
    return Object.entries(byDomain)
      .map(([domain, v]) => ({
        domain,
        earned:   parseFloat(v.earned.toFixed(2)),
        failed:   parseFloat(v.failed.toFixed(2)),
        untapped: parseFloat(v.untapped.toFixed(2)),
        totalTasks: v.totalTasks,
      }))
      .sort((a, b) => b.earned - a.earned)
  })()

  const screenerResults = fyersScreener?.data?.results || []
  const watchlistBaskets = fyersScreener?.data?.watchlist_baskets || {}
  const basketOptions = ['SENSEX', 'NIFTY50', 'BANKNIFTY']
  const basketFilteredResults = basketFilter === 'ALL'
    ? screenerResults
    : screenerResults.filter((row) => (watchlistBaskets[basketFilter] || []).includes(row.symbol))

  const signalCounts = basketFilteredResults.reduce((acc, row) => {
    if (!row?.signal) return acc
    acc[row.signal] = (acc[row.signal] || 0) + 1
    return acc
  }, {})
  const availableSignals = Object.keys(signalCounts)
  const effectiveSignalFilter = signalFilter !== 'ALL' && !availableSignals.includes(signalFilter)
    ? 'ALL'
    : signalFilter
  const filteredResults = effectiveSignalFilter === 'ALL'
    ? basketFilteredResults
    : basketFilteredResults.filter((row) => row.signal === effectiveSignalFilter)
  const sortedResults = [...filteredResults]

  const basketCounts = basketOptions.reduce((acc, basket) => {
    acc[basket] = (watchlistBaskets[basket] || []).length
    return acc
  }, { ALL: screenerResults.length })

  if (signalSort === 'signal') {
    const signalPriority = { BUY_CANDIDATE: 0, WATCH: 1, AVOID: 2 }
    sortedResults.sort((a, b) => {
      const priorityA = signalPriority[a.signal] ?? 99
      const priorityB = signalPriority[b.signal] ?? 99
      if (priorityA !== priorityB) return priorityA - priorityB
      return (a.symbol || '').localeCompare(b.symbol || '')
    })
  }

  const visibleCount = resultsView === 'few'
    ? 8
    : resultsView === 'more'
      ? 20
      : sortedResults.length
  const visibleResults = sortedResults.slice(0, visibleCount)

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{dn(selectedAgent)}</h1>
          <p className="text-gray-500 mt-1">Agent Dashboard - Live Monitoring</p>
        </div>
        <div className={`px-6 py-3 rounded-xl border-2 font-semibold uppercase tracking-wide ${getStatusColor(current_status.survival_status)}`}>
          {getStatusEmoji(current_status.survival_status)} {current_status.survival_status}
        </div>
      </motion.div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-6">
        <MetricCard
          title="Starter Asset"
          value={formatINR(balance_history?.[0]?.balance || 0)}
          icon={<Wallet className="w-6 h-6" />}
          color="gray"
        />
        <MetricCard
          title="Balance"
          value={formatINR(current_status.balance || 0)}
          icon={<DollarSign className="w-6 h-6" />}
          color="blue"
          trend={balance_history?.length > 1 ?
            ((balance_history[balance_history.length - 1].balance - balance_history[0].balance) / balance_history[0].balance * 100).toFixed(1) :
            '0'
          }
        />
        <MetricCard
          title="Net Worth"
          value={formatINR(current_status.net_worth || 0)}
          icon={<TrendingUp className="w-6 h-6" />}
          color="green"
        />
        <MetricCard
          title="Total Token Cost"
          value={formatINR(current_status.total_token_cost || 0)}
          icon={<Activity className="w-6 h-6" />}
          color="red"
        />
        <MetricCard
          title="Work Income"
          value={formatINR(current_status.total_work_income || 0)}
          icon={<Briefcase className="w-6 h-6" />}
          color="purple"
        />
        <MetricCard
          title="Avg Quality Score"
          value={current_status.avg_evaluation_score !== null && current_status.avg_evaluation_score !== undefined
            ? `${(current_status.avg_evaluation_score * 100).toFixed(1)}%`
            : 'N/A'}
          icon={<Activity className="w-6 h-6" />}
          color="orange"
          subtitle={current_status.num_evaluations > 0 ? `${current_status.num_evaluations} tasks` : ''}
        />
      </div>

      {/* Current Activity */}
      {current_status.current_activity && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-gradient-to-r from-primary-500 to-purple-600 rounded-2xl p-6 text-white shadow-lg"
        >
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center animate-pulse-slow">
              {getActivityIcon(current_status.current_activity)}
            </div>
            <div>
              <p className="text-sm font-medium opacity-90">Currently Active</p>
              <p className="text-2xl font-bold capitalize">{current_status.current_activity}</p>
            </div>
            <div className="flex-1"></div>
            <div className="text-right">
              <p className="text-sm opacity-90">Date</p>
              <p className="font-semibold">{current_status.current_date}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Balance History Chart */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200"
        >
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Balance History</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={balanceChartData}>
              <defs>
                <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                interval={Math.max(0, Math.floor(balanceChartData.length / 8) - 1)}
                angle={-45}
                textAnchor="end"
                height={60}
                tickFormatter={(d) => { const p = d.split('-'); return p.length === 3 ? `${p[1]}/${p[2]}` : d }}
              />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => formatINR(v, 0)} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
                labelFormatter={(d) => `Date: ${d}`}
                formatter={(value) => [formatINR(value), 'Balance']}
              />
              <Area
                type="monotone"
                dataKey="balance"
                stroke="#0ea5e9"
                strokeWidth={2}
                fill="url(#colorBalance)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Domain Earnings Distribution */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200"
        >
          <h3 className="text-lg font-semibold text-gray-900 mb-1">Domain Earnings</h3>
          <p className="text-xs text-gray-400 mb-4">
            <span className="inline-block w-2 h-2 rounded-sm bg-green-500 mr-1" />Earned (score ≥ 0.6)
            <span className="inline-block w-2 h-2 rounded-sm bg-red-400 mx-1 ml-3" />Failed &amp; wasted (score &lt; 0.6)
            <span className="inline-block w-2 h-2 rounded-sm bg-slate-300 mx-1 ml-3" />Untapped potential
          </p>
          {domainChartData.length === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">No task data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(300, domainChartData.length * 38)}>
              <BarChart
                data={domainChartData}
                layout="vertical"
                margin={{ left: 8, right: 48, top: 4, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11 }}
                  tickFormatter={v => formatINR(v, 0)}
                />
                <YAxis
                  type="category"
                  dataKey="domain"
                  tick={{ fontSize: 11 }}
                  width={160}
                  tickFormatter={s => s.length > 24 ? s.slice(0, 22) + '…' : s}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                    fontSize: 12,
                  }}
                  formatter={(value, name) => {
                    const labels = { earned: 'Earned', failed: 'Failed & wasted', untapped: 'Untapped potential' }
                    return [formatINR(value), labels[name] || name]
                  }}
                  labelFormatter={(label, payload) => {
                    const d = payload?.[0]?.payload
                    return d ? `${label} (${d.totalTasks} task${d.totalTasks !== 1 ? 's' : ''})` : label
                  }}
                />
                <Legend formatter={n => ({ earned: 'Earned', failed: 'Failed & wasted', untapped: 'Untapped potential' }[n] || n)} />
                <Bar dataKey="earned"   stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} />
                <Bar dataKey="failed"   stackId="a" fill="#f87171" radius={[0, 0, 0, 0]} />
                <Bar dataKey="untapped" stackId="a" fill="#94a3b8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </motion.div>
      </div>

      {/* FYERS Screener */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Latest FYERS Screener</h3>
          <div className="flex items-center gap-2">
            {fyersScreener?.available && (fyersScreener.data?.missing_quote_symbols || []).length > 0 && (
              <span className="text-[11px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium">
                {(fyersScreener.data?.missing_quote_symbols || []).length} missing quotes
              </span>
            )}
            {fyersScreener?.available && (
              <span className="text-xs text-gray-500">{fyersScreener.file}</span>
            )}
          </div>
        </div>

        {!fyersScreener?.available ? (
          <div className="text-sm text-gray-500">
            No screener run found yet. Run <span className="font-mono">./scripts/fyers_screener.sh</span> and refresh.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="rounded-lg bg-gray-50 p-3 border border-gray-100">
                <p className="text-xs text-gray-500">Total</p>
                <p className="text-lg font-semibold text-gray-900">{fyersScreener.data?.summary?.total ?? 0}</p>
              </div>
              <div className="rounded-lg bg-green-50 p-3 border border-green-100">
                <p className="text-xs text-green-700">Buy Candidates</p>
                <p className="text-lg font-semibold text-green-700">{fyersScreener.data?.summary?.buy_candidates ?? 0}</p>
              </div>
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-100">
                <p className="text-xs text-blue-700">Watch</p>
                <p className="text-lg font-semibold text-blue-700">{fyersScreener.data?.summary?.watch ?? 0}</p>
              </div>
              <div className="rounded-lg bg-red-50 p-3 border border-red-100">
                <p className="text-xs text-red-700">Avoid</p>
                <p className="text-lg font-semibold text-red-700">{fyersScreener.data?.summary?.avoid ?? 0}</p>
              </div>
            </div>

            {(fyersScreener.data?.basket_summaries || []).length > 0 && (
              <div className="mb-3 overflow-x-auto">
                <table className="min-w-full text-[13px] table-fixed">
                  <colgroup>
                    <col className="w-[26%]" />
                    <col className="w-[13%]" />
                    <col className="w-[15%]" />
                    <col className="w-[13%]" />
                    <col className="w-[13%]" />
                    <col className="w-[20%]" />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="text-left py-1.5 pr-2 font-semibold text-gray-800 bg-gray-100">Basket</th>
                      <th className="text-center py-1.5 px-1 font-semibold text-gray-800 bg-gray-100">Total</th>
                      <th className="text-center py-1.5 px-1 font-semibold text-green-800 bg-green-100 whitespace-nowrap">Buy Condition</th>
                      <th className="text-center py-1.5 px-1 font-semibold text-blue-800 bg-blue-100">Watch</th>
                      <th className="text-center py-1.5 px-1 font-semibold text-red-800 bg-red-100">Avoid</th>
                      <th className="text-center py-1.5 px-1 font-semibold text-amber-800 bg-amber-100 whitespace-nowrap">Missing Quotes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(fyersScreener.data?.basket_summaries || []).map((row, idx) => (
                      <tr key={`${row.basket}-${idx}`} className="border-b border-gray-50">
                        <td className="py-1.5 pr-2 text-gray-900 font-semibold tracking-wide">{row.basket}</td>
                        <td className="py-1.5 px-2 text-center bg-gray-50 text-gray-800 font-semibold">{row.total ?? 0}</td>
                        <td className="py-1.5 px-2 text-center bg-green-50 text-green-700 font-semibold">{row.buy_candidates ?? 0}</td>
                        <td className="py-1.5 px-2 text-center bg-blue-50 text-blue-700 font-semibold">{row.watch ?? 0}</td>
                        <td className="py-1.5 px-2 text-center bg-red-50 text-red-700 font-semibold">{row.avoid ?? 0}</td>
                        <td className="py-1.5 px-2 text-center bg-amber-50 text-amber-700 font-semibold">{row.missing_quotes ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {((fyersScreener.data?.warnings || []).length > 0 || (fyersScreener.data?.missing_quote_symbols || []).length > 0) && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-2 mb-4">
                {(fyersScreener.data?.warnings || []).map((warning, idx) => (
                  <p key={`fyers-warning-${idx}`}>{warning}</p>
                ))}
                {(fyersScreener.data?.missing_quote_symbols || []).length > 0 && (
                  <p>
                    Missing symbols: {(fyersScreener.data?.missing_quote_symbols || []).join(', ')}
                  </p>
                )}
              </div>
            )}

            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Index + Strike Recommender</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                <div className="rounded-lg bg-gray-50 p-3 border border-gray-100">
                  <p className="text-xs text-gray-500">Tracked</p>
                  <p className="text-base font-semibold text-gray-900">{fyersScreener.data?.index_summary?.tracked ?? 0}</p>
                </div>
                <div className="rounded-lg bg-green-50 p-3 border border-green-100">
                  <p className="text-xs text-green-700">Bullish</p>
                  <p className="text-base font-semibold text-green-700">{fyersScreener.data?.index_summary?.bullish ?? 0}</p>
                </div>
                <div className="rounded-lg bg-red-50 p-3 border border-red-100">
                  <p className="text-xs text-red-700">Bearish</p>
                  <p className="text-base font-semibold text-red-700">{fyersScreener.data?.index_summary?.bearish ?? 0}</p>
                </div>
                <div className="rounded-lg bg-blue-50 p-3 border border-blue-100">
                  <p className="text-xs text-blue-700">Neutral</p>
                  <p className="text-base font-semibold text-blue-700">{fyersScreener.data?.index_summary?.neutral ?? 0}</p>
                </div>
              </div>

              {fyersScreener.data?.index_error && (
                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-2 mb-2">
                  Index recommendation unavailable: {fyersScreener.data?.index_error}
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-gray-500">
                      <th className="text-left py-2 pr-3 font-medium">Index</th>
                      <th className="text-left py-2 pr-3 font-medium">Bias</th>
                      <th className="text-left py-2 pr-3 font-medium">Side</th>
                      <th className="text-right py-2 pr-3 font-medium">LTP</th>
                      <th className="text-right py-2 pr-3 font-medium">Change %</th>
                      <th className="text-right py-2 pr-3 font-medium">Preferred Strike</th>
                      <th className="text-right py-2 pr-3 font-medium">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(fyersScreener.data?.index_recommendations || []).map((row, idx) => (
                      <tr key={`${row.index}-${idx}`} className="border-b border-gray-50">
                        <td className="py-2 pr-3 text-gray-900 font-medium">{row.index}</td>
                        <td className="py-2 pr-3">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            row.signal === 'BULLISH'
                              ? 'bg-green-100 text-green-700'
                              : row.signal === 'BEARISH'
                                ? 'bg-red-100 text-red-700'
                                : 'bg-blue-100 text-blue-700'
                          }`}>
                            {row.signal}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-gray-700">{row.option_side}</td>
                        <td className="py-2 pr-3 text-right text-gray-700">
                          {typeof row.ltp === 'number' ? row.ltp.toFixed(2) : 'NA'}
                        </td>
                        <td className="py-2 pr-3 text-right text-gray-700">
                          {typeof row.change_pct === 'number' ? `${row.change_pct.toFixed(2)}%` : 'NA'}
                        </td>
                        <td className="py-2 pr-3 text-right text-gray-700">
                          {row.preferred_strike || 'WAIT'}
                        </td>
                        <td className="py-2 pr-3 text-right text-gray-700">{row.confidence ?? 0}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="sticky top-0 z-10 mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 bg-white/95 px-2 py-2 backdrop-blur">
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <span className="font-medium">View:</span>
                <button
                  type="button"
                  onClick={() => setResultsView('few')}
                  className={`px-2.5 py-1 rounded border ${resultsView === 'few' ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                >
                  Few
                </button>
                <button
                  type="button"
                  onClick={() => setResultsView('more')}
                  className={`px-2.5 py-1 rounded border ${resultsView === 'more' ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                >
                  Little More
                </button>
                <button
                  type="button"
                  onClick={() => setResultsView('full')}
                  className={`px-2.5 py-1 rounded border ${resultsView === 'full' ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                >
                  Full
                </button>
              </div>

              <div className="flex items-center gap-2 text-xs text-gray-600">
                <label className="font-medium" htmlFor="basket-filter">Basket:</label>
                <select
                  id="basket-filter"
                  value={basketFilter}
                  onChange={(e) => setBasketFilter(e.target.value)}
                  className="px-2 py-1 rounded border border-gray-200 bg-white text-gray-700"
                >
                  <option value="ALL">All ({basketCounts.ALL || 0})</option>
                  {basketOptions.map((basket) => (
                    <option key={basket} value={basket}>{basket} ({basketCounts[basket] || 0})</option>
                  ))}
                </select>

                <label className="font-medium" htmlFor="signal-filter">Filter Signal:</label>
                <select
                  id="signal-filter"
                  value={effectiveSignalFilter}
                  onChange={(e) => setSignalFilter(e.target.value)}
                  className="px-2 py-1 rounded border border-gray-200 bg-white text-gray-700"
                >
                  <option value="ALL">All ({basketFilteredResults.length})</option>
                  {availableSignals.map((signal) => (
                    <option key={signal} value={signal}>{signal} ({signalCounts[signal] || 0})</option>
                  ))}
                </select>

                <label className="font-medium" htmlFor="signal-sort">Sort:</label>
                <select
                  id="signal-sort"
                  value={signalSort}
                  onChange={(e) => setSignalSort(e.target.value)}
                  className="px-2 py-1 rounded border border-gray-200 bg-white text-gray-700"
                >
                  <option value="default">Default</option>
                  <option value="signal">By Signal</option>
                </select>

                <span className="text-gray-500">Showing {visibleResults.length} of {sortedResults.length}</span>
              </div>

              <div className="w-full flex flex-wrap items-center gap-1 text-xs">
                <button
                  type="button"
                  onClick={() => setBasketFilter('ALL')}
                  className={`px-2 py-1 rounded border ${basketFilter === 'ALL' ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                >
                  All Baskets ({basketCounts.ALL || 0})
                </button>
                {basketOptions.map((basket) => (
                  <button
                    type="button"
                    key={`basket-chip-${basket}`}
                    onClick={() => setBasketFilter(basket)}
                    className={`px-2 py-1 rounded border ${basketFilter === basket ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                  >
                    {basket} ({basketCounts[basket] || 0})
                  </button>
                ))}

                <button
                  type="button"
                  onClick={() => setSignalFilter('ALL')}
                  className={`px-2 py-1 rounded border ${effectiveSignalFilter === 'ALL' ? 'bg-gray-100 border-gray-300 text-gray-900' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                >
                  All Signals ({basketFilteredResults.length})
                </button>
                {availableSignals.map((signal) => {
                  const chipClass = signal === 'BUY_CANDIDATE'
                    ? 'border-green-200 text-green-700 bg-green-50'
                    : signal === 'AVOID'
                      ? 'border-red-200 text-red-700 bg-red-50'
                      : 'border-blue-200 text-blue-700 bg-blue-50'

                  const activeClass = signalFilter === signal ? 'ring-1 ring-gray-300' : ''
                  const activeSignalClass = effectiveSignalFilter === signal ? 'ring-1 ring-gray-300' : ''

                  return (
                    <button
                      type="button"
                      key={`signal-chip-${signal}`}
                      onClick={() => setSignalFilter(signal)}
                      className={`px-2 py-1 rounded border ${chipClass} ${activeSignalClass}`}
                    >
                      {signal} ({signalCounts[signal] || 0})
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="max-h-[420px] overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="sticky top-0 z-[1] border-b border-gray-100 text-gray-500 bg-white">
                    <th className="text-left py-2 pr-3 font-medium">Symbol</th>
                    <th className="text-left py-2 pr-3 font-medium">Signal</th>
                    <th className="text-right py-2 pr-3 font-medium">LTP</th>
                    <th className="text-right py-2 pr-3 font-medium">Change %</th>
                    <th className="text-left py-2 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleResults.map((row, idx) => (
                    <tr key={`${row.symbol}-${idx}`} className="border-b border-gray-50">
                      <td className="py-2 pr-3 text-gray-900 font-medium">{row.symbol}</td>
                      <td className="py-2 pr-3">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          row.signal === 'BUY_CANDIDATE'
                            ? 'bg-green-100 text-green-700'
                            : row.signal === 'AVOID'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-blue-100 text-blue-700'
                        }`}>
                          {row.signal}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right text-gray-700">
                        {typeof row.last_price === 'number' ? row.last_price.toFixed(2) : 'NA'}
                      </td>
                      <td className="py-2 pr-3 text-right text-gray-700">
                        {typeof row.change_pct === 'number' ? `${row.change_pct.toFixed(2)}%` : 'NA'}
                      </td>
                      <td className="py-2 text-gray-600">{row.reason}</td>
                    </tr>
                  ))}
                  {visibleResults.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-3 text-center text-gray-500">No stocks match selected signal filter.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </motion.div>

      {/* Institutional Shadow */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.38 }}
        className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Institutional Shadow (Latest)</h3>
          {institutionalShadow?.available && (
            <span className="text-xs text-gray-500">{institutionalShadow.date || institutionalShadow.timestamp}</span>
          )}
        </div>

        {!institutionalShadow?.available ? (
          <div className="text-sm text-gray-500">
            No institutional shadow audit found yet for this agent.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
              <div className="rounded-lg bg-gray-50 p-3 border border-gray-100">
                <p className="text-xs text-gray-500">Status</p>
                <p className="text-base font-semibold text-gray-900">{institutionalShadow.institutional_shadow?.status || 'NA'}</p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 border border-gray-100">
                <p className="text-xs text-gray-500">Records</p>
                <p className="text-base font-semibold text-gray-900">{institutionalShadow.institutional_shadow?.record_count ?? 0}</p>
              </div>
              <div className="rounded-lg bg-green-50 p-3 border border-green-100">
                <p className="text-xs text-green-700">Agree</p>
                <p className="text-base font-semibold text-green-700">{institutionalShadow.institutional_shadow?.agree_count ?? 0}</p>
              </div>
              <div className="rounded-lg bg-red-50 p-3 border border-red-100">
                <p className="text-xs text-red-700">Disagree</p>
                <p className="text-base font-semibold text-red-700">{institutionalShadow.institutional_shadow?.disagree_count ?? 0}</p>
              </div>
              <div className="rounded-lg bg-blue-50 p-3 border border-blue-100">
                <p className="text-xs text-blue-700">Screener OK</p>
                <p className="text-base font-semibold text-blue-700">{institutionalShadow.success ? 'YES' : 'NO'}</p>
              </div>
            </div>
          </>
        )}
      </motion.div>

      {/* Recent Decisions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200"
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Decisions</h3>
        <div className="space-y-3">
          {decisions?.slice(-5).reverse().map((decision, index) => (
            <div
              key={index}
              className="flex items-center space-x-4 p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                {getActivityIcon(decision.activity)}
              </div>
              <div className="flex-1">
                <p className="font-medium text-gray-900 capitalize">{decision.activity}</p>
                <p className="text-sm text-gray-500">{decision.reasoning}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{decision.date}</p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

const MetricCard = ({ title, value, icon, color, trend, subtitle }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
    gray: 'bg-gray-100 text-gray-500',
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
    >
      <div className="flex items-center justify-between mb-3">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${colorClasses[color]}`}>
          {icon}
        </div>
        {trend && (
          <span className={`text-sm font-medium ${parseFloat(trend) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {parseFloat(trend) >= 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {subtitle && (
        <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
      )}
    </motion.div>
  )
}

export default Dashboard
