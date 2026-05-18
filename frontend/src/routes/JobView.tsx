import { useParams, Link } from 'react-router-dom'

export default function JobView() {
  const { id } = useParams()

  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6 inline-block">
        ← Back to home
      </Link>
      <div className="text-center py-16 space-y-4">
        <div className="text-4xl">🗺</div>
        <h1 className="text-2xl font-bold">Generating your character map</h1>
        <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
          Generation pipeline coming in Phase 2. For now this is a placeholder.
          Job ID: <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">{id}</code>
        </p>
        <p className="text-sm text-gray-400">
          Once Phase 2 is complete, this page will show a live progress bar and the finished
          interactive map when generation completes.
        </p>
      </div>
    </main>
  )
}
