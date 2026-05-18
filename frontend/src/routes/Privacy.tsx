import { Link } from 'react-router-dom'

export default function Privacy() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6 inline-block">
        ← Back to home
      </Link>
      <h1 className="text-2xl font-bold mb-6">Privacy Policy</h1>
      <div className="prose dark:prose-invert space-y-6 text-sm text-gray-700 dark:text-gray-300">
        <section>
          <h2 className="text-base font-semibold mb-2">What we collect</h2>
          <p>When you use Character Map Generator, we collect:</p>
          <ul className="list-disc list-inside space-y-1 mt-2">
            <li>The title you searched for</li>
            <li>Your model and format selections</li>
            <li>Your email address, if you provide one</li>
            <li>Your IP address (for rate-limiting and abuse prevention)</li>
            <li>Your browser's user agent string</li>
          </ul>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">Why we collect it</h2>
          <p>
            To generate and deliver the character map you requested, prevent abuse, and improve the
            service. IP addresses are used only for rate-limiting — they are never shared or sold.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">Where it's stored</h2>
          <p>All data is stored on servers in Germany (EU).</p>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">How long we keep it</h2>
          <ul className="list-disc list-inside space-y-1">
            <li>Generated files: deleted 30 days after creation</li>
            <li>Job records (including your query, email, and IP): soft-deleted after 90 days, permanently erased after 180 days</li>
            <li>Anonymous usage statistics: retained indefinitely (no PII)</li>
          </ul>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">Third parties</h2>
          <p>
            Your title query is sent to the AI provider you chose (Anthropic, OpenAI, or Google)
            to generate the map. Title metadata is fetched from Open Library and TMDb. Email
            delivery uses Resend. Bot-prevention uses Cloudflare Turnstile.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">Your rights (GDPR)</h2>
          <p>
            You have the right to access, correct, or erase your data. To exercise these rights,
            email <a href="mailto:privacy@torgersen.ai" className="text-blue-600 dark:text-blue-400 hover:underline">privacy@torgersen.ai</a> with
            your job ID(s). We will process requests within 30 days.
          </p>
        </section>
        <section>
          <h2 className="text-base font-semibold mb-2">Cookies</h2>
          <p>
            We don't use tracking or marketing cookies. Cloudflare Turnstile sets a cookie for
            bot-prevention purposes. No other cookies are used.
          </p>
        </section>
      </div>
    </main>
  )
}
