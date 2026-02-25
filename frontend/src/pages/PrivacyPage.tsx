import { Link } from 'react-router-dom'
import { Rocket, ArrowLeft } from 'lucide-react'

export default function PrivacyPage() {
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
      <main className="max-w-4xl mx-auto px-6 py-16 prose prose-invert prose-sm max-w-none">
        <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-gray-400 text-sm mb-8">Last updated: February 25, 2026</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">1. Information We Collect</h2>
        <p className="text-gray-300 mb-2">We collect:</p>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li><strong>Account info</strong>: name, email, GitHub profile (via OAuth)</li>
          <li><strong>Repository data</strong>: repo metadata, code (temporarily for build)</li>
          <li><strong>Credentials</strong>: app store API keys (encrypted at rest with AES-256)</li>
          <li><strong>Usage data</strong>: build counts, deploy history, feature usage</li>
          <li><strong>Technical data</strong>: IP address, browser type, device fingerprint (for security)</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">2. How We Use Your Data</h2>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Provide the CI/CD and deployment service</li>
          <li>Detect frameworks, build apps, deploy to stores</li>
          <li>Monitor usage for billing and quota enforcement</li>
          <li>Improve the platform and fix issues</li>
          <li>Send service notifications (build status, deploy results)</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">3. Credential Security</h2>
        <p className="text-gray-300 mb-4">All credentials (App Store private keys, Google Play service account JSON, build provider tokens) are encrypted using AES-256 (Fernet) with per-tenant key derivation. Credentials are never stored in plaintext, never logged, and are decrypted only at the moment of use.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">4. Data Sharing</h2>
        <p className="text-gray-300 mb-2">We share data only with:</p>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li><strong>Build providers</strong> (Expo, Codemagic, GitHub Actions) — only build-related data</li>
          <li><strong>App stores</strong> (Apple, Google) — only during deploy, using your credentials</li>
          <li><strong>Payment processor</strong> (Stripe) — billing information only</li>
        </ul>
        <p className="text-gray-300 mb-4">We never sell your data. We do not share your code with any third party beyond what is necessary for builds.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">5. Data Retention</h2>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Source code: cloned temporarily, deleted after build</li>
          <li>Build artifacts (APK/IPA): retained for 90 days</li>
          <li>Audit logs: retained for 1 year</li>
          <li>Account data: retained while account is active</li>
          <li>Upon deletion request: all data removed within 30 days</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">6. Your Rights</h2>
        <p className="text-gray-300 mb-2">You have the right to:</p>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Access your data</li>
          <li>Export your data</li>
          <li>Delete your account and all associated data</li>
          <li>Revoke third-party access (GitHub, store credentials)</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">7. Cookies</h2>
        <p className="text-gray-300 mb-4">We use essential cookies for authentication (JWT httponly) and security (device fingerprint). We do not use tracking or advertising cookies.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">8. Security Measures</h2>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>TLS encryption for all communications</li>
          <li>AES-256 encryption for stored credentials</li>
          <li>Rate limiting and abuse protection</li>
          <li>Immutable audit logging</li>
          <li>Tenant isolation for all data</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">9. Contact</h2>
        <p className="text-gray-300 mb-4">For privacy inquiries: <a href="mailto:privacy@apptrack.io" className="text-primary-400 hover:underline">privacy@apptrack.io</a></p>
      </main>
    </div>
  )
}
