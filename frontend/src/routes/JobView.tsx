import { useParams } from 'react-router-dom'

export default function JobView() {
  const { id } = useParams()
  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-4">Job {id}</h1>
      <p className="text-gray-500">Generation coming in Phase 2 — your map is being prepared.</p>
      <a href="/" className="text-blue-600 hover:underline text-sm">← Back to home</a>
    </main>
  )
}
