import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import logoImg from '@/assets/logo.png'

export default function TermsPage() {
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
        <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
        <p className="text-gray-400 text-sm mb-8">Last updated: February 25, 2026</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">1. Acceptance of Terms</h2>
        <p className="text-gray-300 mb-4">By accessing or using the AppTrack platform ("Service"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">2. Service Description</h2>
        <p className="text-gray-300 mb-4">AppTrack provides a mobile application CI/CD and publishing automation platform. The Service enables users to connect code repositories, build mobile applications, and deploy them to app stores.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">3. Account Registration</h2>
        <p className="text-gray-300 mb-4">You must provide accurate information when creating an account. You are responsible for maintaining the security of your account credentials. You must notify us immediately of any unauthorized access.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">4. Acceptable Use</h2>
        <p className="text-gray-300 mb-2">You agree not to:</p>
        <ul className="list-disc pl-6 text-gray-300 space-y-1 mb-4">
          <li>Use the Service for any unlawful purpose</li>
          <li>Attempt to gain unauthorized access to any part of the Service</li>
          <li>Submit malicious code or content through the platform</li>
          <li>Exceed your plan's usage quotas through automated means</li>
          <li>Resell access to the Service without authorization</li>
        </ul>

        <h2 className="text-xl font-semibold mt-8 mb-4">5. Your Content and Credentials</h2>
        <p className="text-gray-300 mb-4">You retain ownership of your code, app store credentials, and related content. We encrypt all credentials at rest and in transit. We do not access your code beyond what is necessary to provide the Service (build, analyze, deploy).</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">6. Service Plans and Billing</h2>
        <p className="text-gray-300 mb-4">Free plans have usage limits. Paid plans are billed monthly or annually. You may upgrade or downgrade at any time. Refunds are handled per our refund policy. We reserve the right to suspend accounts with overdue payments after a 14-day grace period.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">7. Build and Deploy Services</h2>
        <p className="text-gray-300 mb-4">Build times and availability depend on third-party providers (Expo EAS, Codemagic, GitHub Actions). We do not guarantee specific build times or zero downtime for third-party services. Store deployment success depends on your app meeting store guidelines.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">8. Data Retention</h2>
        <p className="text-gray-300 mb-4">Build artifacts are retained for 90 days. Audit logs are retained for 1 year. Account data is deleted within 30 days of account closure upon request.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">9. Limitation of Liability</h2>
        <p className="text-gray-300 mb-4">The Service is provided "as is". We are not liable for any indirect, incidental, or consequential damages arising from your use of the Service, including but not limited to app store rejections, build failures, or credential misconfigurations.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">10. Termination</h2>
        <p className="text-gray-300 mb-4">Either party may terminate at any time. We may suspend your access for violations of these terms. Upon termination, your data will be available for export for 30 days.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">11. Changes to Terms</h2>
        <p className="text-gray-300 mb-4">We may update these Terms. Continued use of the Service after changes constitutes acceptance. We will notify you of material changes via email.</p>

        <h2 className="text-xl font-semibold mt-8 mb-4">12. Contact</h2>
        <p className="text-gray-300 mb-4">For questions about these Terms, contact us at <a href="mailto:legal@apptrack.io" className="text-primary-400 hover:underline">legal@apptrack.io</a></p>
      </main>
    </div>
  )
}
