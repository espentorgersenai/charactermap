import { Routes, Route } from 'react-router-dom'
import Home from './routes/Home'
import JobView from './routes/JobView'
import Privacy from './routes/Privacy'
import Terms from './routes/Terms'

export default function App() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/job/:id" element={<JobView />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
      </Routes>
    </div>
  )
}
