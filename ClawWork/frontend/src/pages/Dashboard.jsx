import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Activity, AlertCircle, Briefcase, Brain, Wallet } from 'lucide-react'
import { fetchAgentDetail, fetchAgentEconomic, fetchAgentTasks, fetchLatestFyersScreener } from '../api'
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
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (selectedAgent) {
      fetchAgentDetails()
      fetchEconomicData()
      fetchAgentTasks(selectedAgent).then(d => setTasksData(d)).catch(() => {})
      fetchLatestFyersScreener().then(d => setFyersScreener(d)).catch(() => setFyersScreener(null))
    }
  }, [selectedAgent])

  useEffect(() => {
    if (!selectedAgent) return

    const id = setInterval(() => {
      fetchLatestFyersScreener().then(d => setFyersScreener(d)).catch(() => {})
    }, 15000)

    return () => clearInterval(id)
  }, [selectedAgent])

  const fetchAgentDetails = async () => {
    if (!selectedAgent) return
    try {
      setLoading(true)
      setAgentDetails(await fetchAgentDetail(selectedAgent))
    } catch (error) {
      console.error('Error fetching agent details:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchEconomicData = async () => {
    if (!selectedAgent) return
    try {
      setEconomicData(await fetchAgentEconomic(selectedAgent))
    } catch (error) {
      console.error('Error fetching economic data:', error)
    }
  }

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
          {fyersScreener?.available && (
            <span className="text-xs text-gray-500">{fyersScreener.file}</span>
          )}
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

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-gray-500">
                    <th className="text-left py-2 pr-3 font-medium">Symbol</th>
                    <th className="text-left py-2 pr-3 font-medium">Signal</th>
                    <th className="text-right py-2 pr-3 font-medium">LTP</th>
                    <th className="text-right py-2 pr-3 font-medium">Change %</th>
                    <th className="text-left py-2 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {(fyersScreener.data?.results || []).slice(0, 8).map((row, idx) => (
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
                </tbody>
              </table>
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
