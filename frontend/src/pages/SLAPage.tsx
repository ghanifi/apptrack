import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import logoImg from '@/assets/logo.png'

export default function SLAPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src={logoImg} alt="AppTrack" className="w-6 h-6 object-contain" />
            <span className="font-bold">AppTrack</span>
          </Link>
          <Link to="/" className="text-sm text-gray-400 hover:text-white flex items-center gap-1">
            <ArrowLeft size={14} /> Back
          </Link>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-6 py-16 prose prose-invert prose-sm max-w-none">
        <h1 className="text-3xl font-bold mb-8">Service Level Agreement</h1>
        <p className="text-gray-400 text-sm mb-8">Effective: February 25, 2026</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">1. Platform Availability</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-6">
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800 text-sm font-semibold text-gray-400">
            <span>Plan</span><span>Uptime Target</span><span>Monthly Downtime</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800/50 text-sm text-gray-300">
            <span>Free</span><span>99.0%</span><span>~7.3 hours</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800/50 text-sm text-gray-300">
            <span>Pro</span><span>99.5%</span><span>~3.6 hours</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 text-sm text-gray-300">
            <span>Enterprise</span><span>99.9%</span><span>~43 minutes</span>
          </div>
        </div>

        <h2 className="text-xl font-semibold mt-8 mb-4">2. Support Response Times</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-6">
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800 text-sm font-semibold text-gray-400">
            <span>Plan</span><span>First Response</span><span>Resolution</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800/50 text-sm text-gray-300">
            <span>Free</span><span>48 hours</span><span>Best effort</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800/50 text-sm text-gray-300">
            <span>Pro</span><span>12 hours</span><span>48 hours</span>
          </div>
          <div className="grid grid-cols-3 gap-4 px-6 py-3 text-sm text-gray-300">
            <span>Enterprise</span><span>2 hours</span><span>24 hours</span>
          </div>
        </div>

        <h2 className="text-xl font-semibold mt-8 mb-4">3. Build Service</h2>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Build queue time target: under 5 minutes</li>
          <li>Build provider availability depends on third-party SLAs (Expo, Codemagic, GitHub)</li>
          <li>Failed builds are automatically retried once</li>
          <li>Build results are preserved for 90 days</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">4. Data Durability</h2>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Database: daily backups with 30-day retention</li>
          <li>Artifacts: replicated storage with 99.99% durability</li>
          <li>Credentials: encrypted with per-tenant keys, rotation support</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">5. Exclusions</h2>
        <p className="text-gray-300 mb-4">This SLA does not apply during scheduled maintenance (announced 48 hours in advance), force majeure events, or outages caused by third-party providers (GitHub, Apple, Google).</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">6. Service Credits</h2>
        <p className="text-gray-300 mb-4">If we fail to meet the uptime target for Pro or Enterprise plans, we will issue service credits equal to 10% of monthly fees per 0.1% below target, up to 30% maximum.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">7. Contact</h2>
        <p className="text-gray-300">For SLA inquiries: <a href="mailto:support@apptrack.io" className="text-primary-400 hover:underline">support@apptrack.io</a></p>
      </main>
    </div>
  )
}
