import { useState, useEffect, useRef, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import AgentDetail from './pages/AgentDetail'
import WorkView from './pages/WorkView'
import LearningView from './pages/LearningView'
import Leaderboard from './pages/Leaderboard'
import Artifacts from './pages/Artifacts'
import { useWebSocket } from './hooks/useWebSocket'
import { fetchAgents, fetchHiddenAgents, saveHiddenAgents, fetchDisplayNames } from './api'
import { DisplayNamesContext } from './DisplayNamesContext'

function App() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [selectionEpoch, setSelectionEpoch] = useState(0)
  const [hiddenAgents, setHiddenAgents] = useState(new Set())
  const [displayNames, setDisplayNames] = useState({})
  const { lastMessage, connectionStatus } = useWebSocket()
  const hasAutoSelected = useRef(false)

  // Auto-select first VISIBLE agent once both agents and hiddenAgents are loaded
  useEffect(() => {
    if (hasAutoSelected.current) return
    const firstVisible = agents.find(a => !hiddenAgents.has(a.signature))
    if (firstVisible) {
      setSelectedAgent(firstVisible.signature)
      hasAutoSelected.current = true
    }
  }, [agents, hiddenAgents])

  // Fetch hidden agents on mount
  useEffect(() => {
    fetchHiddenAgents()
      .then(data => setHiddenAgents(new Set(data.hidden || [])))
      .catch(err => console.error('Error fetching hidden agents:', err))
  }, [])

  // Fetch display names on mount
  useEffect(() => {
    fetchDisplayNames()
      .then(data => setDisplayNames(data || {}))
      .catch(() => {})
  }, [])

  // Fetch agents on mount
  useEffect(() => {
    fetchAgentsData()
    const interval = setInterval(fetchAgentsData, 5000)
    return () => clearInterval(interval)
  }, [])

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) handleWebSocketMessage(lastMessage)
  }, [lastMessage])

  const fetchAgentsData = async () => {
    try {
      const data = await fetchAgents()
      setAgents(data.agents || [])
    } catch (error) {
      console.error('Error fetching agents:', error)
    }
  }

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message)

    if (message.type === 'balance_update' || message.type === 'activity_update') {
      // Refresh agents when updates come in
      fetchAgentsData()
    }
  }

  const updateHiddenAgents = useCallback(async (newHiddenSet) => {
    setHiddenAgents(newHiddenSet)
    try {
      await saveHiddenAgents(Array.from(newHiddenSet))
    } catch (error) {
      console.error('Error saving hidden agents:', error)
    }
  }, [])

  const handleSelectAgent = useCallback((signature) => {
    setSelectionEpoch(prev => prev + 1)
    setSelectedAgent(signature)
  }, [])

  const visibleAgents = agents.filter(a => !hiddenAgents.has(a.signature))

  return (
    <DisplayNamesContext.Provider value={displayNames}>
    <Router basename={import.meta.env.BASE_URL}>
      <div className="flex h-screen bg-gray-50">
        <Sidebar
          agents={visibleAgents}
          allAgents={agents}
          hiddenAgents={hiddenAgents}
          onUpdateHiddenAgents={updateHiddenAgents}
          selectedAgent={selectedAgent}
          onSelectAgent={handleSelectAgent}
          connectionStatus={connectionStatus}
        />

        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={
              <Leaderboard hiddenAgents={hiddenAgents} />
            } />
            <Route path="/dashboard" element={
              <Dashboard
                key={`dashboard-${selectedAgent || 'none'}-${selectionEpoch}`}
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
            <Route path="/agent/:signature" element={
              <AgentDetail />
            } />
            <Route path="/artifacts" element={
              <Artifacts />
            } />
            <Route path="/work" element={
              <WorkView
                key={`work-${selectedAgent || 'none'}-${selectionEpoch}`}
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
            <Route path="/learning" element={
              <LearningView
                key={`learning-${selectedAgent || 'none'}-${selectionEpoch}`}
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
          </Routes>
        </main>
      </div>
    </Router>
    </DisplayNamesContext.Provider>
  )
}

export default App
