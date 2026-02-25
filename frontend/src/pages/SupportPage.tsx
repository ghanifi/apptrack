import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Rocket, ArrowLeft, Mail, MessageSquare, BookOpen, Send, Check } from 'lucide-react'

export default function SupportPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSent(true)
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Rocket size={20} className="text-primary-500" />
            <span className="font-bold">AppTrack</span>
          </Link>
          <Link to="/" className="text-sm text-gray-400 hover:text-white flex items-center gap-1">
            <ArrowLeft size={14} /> Back
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold mb-2">Help & Support</h1>
        <p className="text-gray-400 text-sm mb-12">We're here to help. Choose a support option below.</p>

        <div className="grid md:grid-cols-3 gap-6 mb-16">
          <a
            href="mailto:support@apptrack.io"
            className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors text-center"
          >
            <Mail size={28} className="mx-auto mb-3 text-primary-400" />
            <h3 className="font-semibold mb-1">Email Support</h3>
            <p className="text-sm text-gray-400">support@apptrack.io</p>
          </a>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
            <MessageSquare size={28} className="mx-auto mb-3 text-primary-400" />
            <h3 className="font-semibold mb-1">Community</h3>
            <p className="text-sm text-gray-400">Join our Discord server</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
            <BookOpen size={28} className="mx-auto mb-3 text-primary-400" />
            <h3 className="font-semibold mb-1">Documentation</h3>
            <p className="text-sm text-gray-400">Guides, API docs, FAQs</p>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 mb-12">
          <h2 className="text-xl font-semibold mb-6">Common Questions</h2>
          <div className="space-y-4">
            {[
              { q: 'How do I connect my GitHub account?', a: 'Go to Settings and click "Connect GitHub". You will be redirected to authorize AppTrack.' },
              { q: 'My build failed. What should I do?', a: 'Check the build logs on the project detail page. Common issues: missing dependencies, wrong framework config, or expired credentials.' },
              { q: 'How do I add App Store credentials?', a: 'Go to Settings > Credentials tab. Add your App Store Connect API Key (Key ID, Issuer ID, and private key .p8 file).' },
              { q: 'What is the difference between Free and Pro?', a: 'Free: 3 projects, 10 builds/month. Pro: 20 projects, 100 builds/month, 5 concurrent builds, priority support.' },
              { q: 'Can I downgrade my plan?', a: 'Yes. Go to Usage & Billing page and click Downgrade. The change takes effect immediately. Excess projects will become read-only.' },
              { q: 'How long are build artifacts stored?', a: 'Artifacts are retained for 90 days. After that, you need to rebuild to deploy again.' },
            ].map(({ q, a }) => (
              <details key={q} className="group">
                <summary className="flex items-center justify-between cursor-pointer text-sm font-medium text-gray-300 hover:text-white py-3 border-b border-gray-800">
                  {q}
                  <span className="text-gray-600 group-open:rotate-45 transition-transform text-lg">+</span>
                </summary>
                <p className="text-sm text-gray-400 py-3 pl-4">{a}</p>
              </details>
            ))}
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
          <h2 className="text-xl font-semibold mb-6">Contact Us</h2>
          {sent ? (
            <div className="text-center py-8">
              <Check size={48} className="mx-auto mb-4 text-green-400" />
              <h3 className="text-lg font-semibold mb-2">Message Sent</h3>
              <p className="text-gray-400 text-sm">We'll get back to you within 24 hours.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Name</label>
                  <input
                    value={name} onChange={(e) => setName(e.target.value)} required
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Email</label>
                  <input
                    type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Subject</label>
                <input
                  value={subject} onChange={(e) => setSubject(e.target.value)} required
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Message</label>
                <textarea
                  value={message} onChange={(e) => setMessage(e.target.value)} rows={5} required
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 resize-none"
                />
              </div>
              <button
                type="submit"
                className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
              >
                <Send size={14} /> Send Message
              </button>
            </form>
          )}
        </div>

        <div className="mt-12 text-center text-sm text-gray-600">
          <p>Response times: Free (48h) | Pro (12h) | Enterprise (2h)</p>
          <p className="mt-1">See our <Link to="/sla" className="text-primary-400 hover:underline">SLA</Link> for details.</p>
        </div>
      </main>
    </div>
  )
}
