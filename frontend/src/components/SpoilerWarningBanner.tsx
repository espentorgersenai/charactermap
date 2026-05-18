interface Props {
  acknowledged: boolean
  onAcknowledgeChange: (v: boolean) => void
}

export default function SpoilerWarningBanner({ acknowledged, onAcknowledgeChange }: Props) {
  return (
    <div className="rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 p-4 text-sm">
      <p className="font-medium text-amber-900 dark:text-amber-200 mb-1">
        ⚠ This app generates full-spoiler maps
      </p>
      <p className="text-amber-800 dark:text-amber-300">
        Don&apos;t use it for books or films you haven&apos;t finished yet. A spoiler-free mode is
        in development —{' '}
        <a href="#" className="underline hover:no-underline">
          sign up for the mailing list
        </a>{' '}
        to know when it ships.
      </p>
      <label className="flex items-center gap-2 mt-3 cursor-pointer">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(e) => onAcknowledgeChange(e.target.checked)}
          className="rounded"
        />
        <span className="text-amber-900 dark:text-amber-200 font-medium">
          I understand this map will contain spoilers
        </span>
      </label>
    </div>
  )
}
