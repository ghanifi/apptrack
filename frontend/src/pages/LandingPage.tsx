import { Link } from 'react-router-dom'
import { Rocket, Github, Smartphone, Store, Shield, Zap, ArrowRight, Check, Globe, BarChart3 } from 'lucide-react'

const FEATURES = [
  { icon: Github, title: 'GitHub Import', desc: 'Connect your repo and we auto-detect your framework.' },
  { icon: Smartphone, title: 'Live Preview', desc: 'Test your app on a virtual device before building.' },
  { icon: Zap, title: 'Auto Build', desc: 'EAS, Codemagic, or GitHub Actions — we pick the best.' },
  { icon: Store, title: 'Store Deploy', desc: 'Publish to App Store & Google Play in one click.' },
  { icon: Shield, title: 'Enterprise Security', desc: 'Encrypted credentials, audit logs, RBAC, SOC2 ready.' },
  { icon: BarChart3, title: 'Usage Analytics', desc: 'Track builds, costs, and usage across your team.' },
]

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    features: ['3 projects', '10 builds/month', '500 MB storage', 'Community support'],
    cta: 'Get Started',
    highlight: false,
  },
  {
    name: 'Pro',
    price: '$29',
    period: '/month',
    features: ['20 projects', '100 builds/month', '5 GB storage', '5 concurrent builds', 'Priority support', 'Deploy policies'],
    cta: 'Start Free Trial',
    highlight: true,
  },
  {
    name: 'Enterprise',
    price: '$199',
    period: '/month',
    features: ['Unlimited projects', '999 builds/month', '50 GB storage', '20 concurrent builds', 'RBAC & SSO', 'SLA guarantee', 'Dedicated support'],
    cta: 'Contact Sales',
    highlight: false,
  },
]

const STEPS = [
  { num: '1', title: 'Connect GitHub', desc: 'Link your repository in seconds.' },
  { num: '2', title: 'Auto Detect', desc: 'We identify React Native, Flutter, Swift, or Kotlin.' },
  { num: '3', title: 'Build & Preview', desc: 'Get a live preview and production build.' },
  { num: '4', title: 'Publish', desc: 'Deploy to App Store & Google Play automatically.' },
]

const COMPETITORS = [
  { feature: 'Multi-framework support', us: true, others: 'Limited' },
  { feature: 'Free tier available', us: true, others: 'Varies' },
  { feature: 'Store deploy automation', us: true, others: 'Manual' },
  { feature: 'Built-in cost tracking', us: true, others: 'No' },
  { feature: 'Encrypted credentials', us: true, others: 'Varies' },
  { feature: 'Open source friendly', us: true, others: 'No' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Rocket size={24} className="text-primary-500" />
            <span className="font-bold text-xl tracking-tight">AppTrack</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <Link to="/login" className="hover:text-white transition-colors">Sign In</Link>
            <Link to="/login" className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
              Get Started Free
            </Link>
          </nav>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 py-24 text-center">
        <div className="inline-flex items-center gap-2 bg-primary-600/10 border border-primary-600/20 text-primary-400 text-sm px-4 py-1.5 rounded-full mb-6">
          <Globe size={14} /> From GitHub to App Store in minutes
        </div>
        <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6 max-w-4xl mx-auto">
          Ship your mobile app<br />
          <span className="text-primary-500">without the CI/CD headache</span>
        </h1>
        <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
          Connect your GitHub repo, we auto-detect your framework, build for iOS & Android, and deploy to stores. No DevOps required.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/login" className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-8 py-3 rounded-xl text-lg font-semibold transition-colors">
            Start Free <ArrowRight size={18} />
          </Link>
          <a href="#how-it-works" className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 px-8 py-3 rounded-xl text-lg font-medium transition-colors">
            See How It Works
          </a>
        </div>
        <p className="text-sm text-gray-600 mt-4">No credit card required. Free plan includes 10 builds/month.</p>
      </section>

      <section className="border-t border-gray-800 py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { label: 'Frameworks Supported', value: '4+' },
              { label: 'Avg Build Time', value: '~12 min' },
              { label: 'Deploy Success Rate', value: '99.2%' },
              { label: 'Avg Cost Per Build', value: '$0.50' },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-3xl font-bold text-primary-400">{value}</p>
                <p className="text-sm text-gray-500 mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="border-t border-gray-800 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-4">Everything you need to ship</h2>
          <p className="text-gray-400 text-center mb-12 max-w-xl mx-auto">
            From code to store, we handle the entire pipeline so you can focus on your product.
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors">
                <div className="w-10 h-10 bg-primary-600/10 rounded-lg flex items-center justify-center mb-4">
                  <Icon size={20} className="text-primary-400" />
                </div>
                <h3 className="font-semibold mb-2">{title}</h3>
                <p className="text-sm text-gray-400">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-t border-gray-800 py-20 bg-gray-900/30">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-4">Deploy in 4 simple steps</h2>
          <p className="text-gray-400 text-center mb-12">From zero to App Store in under 30 minutes.</p>
          <div className="grid md:grid-cols-4 gap-6">
            {STEPS.map(({ num, title, desc }) => (
              <div key={num} className="text-center">
                <div className="w-12 h-12 bg-primary-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                  {num}
                </div>
                <h3 className="font-semibold mb-1">{title}</h3>
                <p className="text-sm text-gray-400">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="border-t border-gray-800 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-4">Simple, transparent pricing</h2>
          <p className="text-gray-400 text-center mb-12">Start free. Upgrade when you need more.</p>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {PLANS.map(({ name, price, period, features, cta, highlight }) => (
              <div
                key={name}
                className={`rounded-xl p-6 ${
                  highlight
                    ? 'bg-primary-600/10 border-2 border-primary-500 relative'
                    : 'bg-gray-900 border border-gray-800'
                }`}
              >
                {highlight && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-600 text-xs font-semibold px-3 py-1 rounded-full">
                    Most Popular
                  </span>
                )}
                <h3 className="text-lg font-semibold mb-2">{name}</h3>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-4xl font-bold">{price}</span>
                  <span className="text-gray-400 text-sm">{period}</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
                      <Check size={14} className="text-green-400 flex-shrink-0" /> {f}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/login"
                  className={`block text-center py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    highlight
                      ? 'bg-primary-600 hover:bg-primary-700 text-white'
                      : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                  }`}
                >
                  {cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-gray-800 py-20 bg-gray-900/30">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">How we compare</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800 text-sm font-semibold text-gray-400">
              <span>Feature</span>
              <span className="text-center text-primary-400">AppTrack</span>
              <span className="text-center">Others</span>
            </div>
            {COMPETITORS.map(({ feature, us, others }) => (
              <div key={feature} className="grid grid-cols-3 gap-4 px-6 py-3 border-b border-gray-800/50 text-sm">
                <span className="text-gray-300">{feature}</span>
                <span className="text-center">
                  {us ? <Check size={16} className="text-green-400 mx-auto" /> : '-'}
                </span>
                <span className="text-center text-gray-500">{others}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-gray-800 py-20">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to ship your app?</h2>
          <p className="text-gray-400 mb-8">Join developers who deploy faster with AppTrack.</p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-8 py-3 rounded-xl text-lg font-semibold transition-colors"
          >
            Start Free <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-gray-800 py-12">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Rocket size={18} className="text-primary-500" />
                <span className="font-bold">AppTrack</span>
              </div>
              <p className="text-sm text-gray-500">Mobile app publishing automation platform.</p>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Product</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
                <li><Link to="/status" className="hover:text-white transition-colors">Status</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Legal</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><Link to="/terms" className="hover:text-white transition-colors">Terms of Service</Link></li>
                <li><Link to="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link></li>
                <li><Link to="/sla" className="hover:text-white transition-colors">SLA</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Support</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="mailto:support@apptrack.io" className="hover:text-white transition-colors">support@apptrack.io</a></li>
                <li><Link to="/support" className="hover:text-white transition-colors">Help Center</Link></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-xs text-gray-600">
            &copy; {new Date().getFullYear()} AppTrack. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
