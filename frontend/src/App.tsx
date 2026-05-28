import { Routes, Route, useLocation } from 'react-router-dom'
import Home from './routes/Home'
import JobView from './routes/JobView'
import GeographicJobView from './routes/GeographicJobView'
import Privacy from './routes/Privacy'
import Terms from './routes/Terms'
import AppHeader from './components/AppHeader'
import AttributionFooter from './components/AttributionFooter'
import CookieBanner from './components/CookieBanner'

function GlobalFooter() {
  const { pathname } = useLocation()
  // JobView fills the viewport with the canvas; a footer would push the
  // canvas below the fold. Attribution there lives in the markdown/PDF
  // footer and in the TMDB hover credits on character cards.
  if (pathname.startsWith('/job/') || pathname.startsWith('/geo/')) return null
  return <AttributionFooter />
}

export default function App() {
  return (
    <div className="flex flex-col h-screen award-spotlight text-award-cream">
      <AppHeader />
      {/* flex-1 + min-h-0: Home scrolls, JobView canvas fills height */}
      <div className="flex-1 min-h-0 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/job/:id" element={<JobView />} />
          <Route path="/geo/:id" element={<GeographicJobView />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
        </Routes>
        <GlobalFooter />
      </div>
      <CookieBanner />
    </div>
  )
}
