interface Props {
  onClose: () => void
}

export default function HowThisWorksModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-md w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">How this works</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
          <p>
            You type a title and click Search. The app looks it up in Open Library (for books) or
            TMDb (for films and TV) to confirm which work you mean and pull basic metadata — author,
            year, cover image. If the match is unambiguous it skips straight to generation; if
            there are multiple plausible results it shows you a small picker.
          </p>
          <p>
            Once you confirm the work, the request goes to the AI model you chose. The model reads
            everything it knows about the work and returns a structured list of characters,
            relationships, and factions. That JSON is rendered as an interactive diagram you can
            pan, zoom, drag, and download as PNG, SVG, PDF, or Markdown. Nothing is saved to a
            database longer than 90 days; no account is needed.
          </p>
        </div>
        <button
          onClick={onClose}
          className="mt-5 w-full py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          Got it
        </button>
      </div>
    </div>
  )
}
