interface Props {
  acknowledged: boolean
  onAcknowledgeChange: (v: boolean) => void
}

export default function SpoilerWarningBanner({ acknowledged, onAcknowledgeChange }: Props) {
  return (
    <div
      className="rounded-xl px-4 py-3.5"
      style={{
        background: 'linear-gradient(135deg, rgba(26,8,8,0.95) 0%, rgba(20,10,6,0.9) 100%)',
        borderLeft: '3px solid rgba(224,82,82,0.6)',
        border: '1px solid rgba(224,82,82,0.18)',
        borderLeftWidth: '3px',
      }}
    >
      <p className="text-xs text-award-cream-muted mb-2.5 leading-relaxed">
        <span className="font-semibold" style={{ color: '#E05252' }}>⚠ Spoiler warning —</span>{' '}
        full character maps revealed. Don't use for works you haven't finished.
        A spoiler-free mode is coming — drop your email below to be notified.
      </p>
      <label className="flex items-center gap-2.5 cursor-pointer group">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(e) => onAcknowledgeChange(e.target.checked)}
          className="rounded"
          style={{ accentColor: '#D4AF37', width: '14px', height: '14px' }}
        />
        <span className="text-xs text-award-cream-dim group-hover:text-award-cream-muted transition-colors">
          I understand this map will contain spoilers
        </span>
      </label>
    </div>
  )
}
