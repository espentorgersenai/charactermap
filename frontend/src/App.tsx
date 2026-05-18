import { Routes, Route } from 'react-router-dom'
import Home from './routes/Home'
import JobView from './routes/JobView'
import Privacy from './routes/Privacy'
import Terms from './routes/Terms'
import AppHeader from './components/AppHeader'

export default function App() {
  return (
    <div className="flex flex-col h-screen award-spotlight text-award-cream">
      <AppHeader />
      {/* flex-1 + min-h-0: Home scrolls, JobView canvas fills height */}
      <div className="flex-1 min-h-0 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/job/:id" element={<JobView />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
        </Routes>
      </div>
    </div>
  )
}
