import { Link } from 'react-router-dom'
import { Rocket, Github, Smartphone, Store, Shield, Zap, ArrowRight, Check, Globe, BarChart3, Clock, Lock, Star, Users, Timer, ChevronRight } from 'lucide-react'

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

const VALUE_PROPS = [
  {
    icon: Timer,
    title: 'Deploy in 30 minutes',
    subtitle: 'Not days. Not hours.',
    desc: 'From connecting your repo to seeing your app on the store — the entire process takes under 30 minutes. What used to take a week of DevOps setup is now a single flow.',
  },
  {
    icon: Lock,
    title: 'No store complexity',
    subtitle: 'We handle certificates, profiles, and APIs.',
    desc: 'Forget about provisioning profiles, signing certificates, and store console navigation. Connect your credentials once, we handle the rest every time.',
  },
  {
    icon: Zap,
    title: 'No CI/CD knowledge needed',
    subtitle: 'Zero config. Zero scripts.',
    desc: 'You don\'t need to write a single YAML file or build script. We detect your framework, choose the right build provider, and deploy — automatically.',
  },
]

const TESTIMONIALS = [
  {
    name: 'Sarah K.',
    role: 'Indie Developer',
    text: 'I spent 2 weeks trying to set up Fastlane. With AppTrack, my first app was on the Play Store in 20 minutes.',
    avatar: 'SK',
    stars: 5,
  },
  {
    name: 'Mehmet A.',
    role: 'Startup CTO',
    text: 'We moved our entire mobile CI/CD from GitHub Actions to AppTrack. Our team saves 10+ hours per release cycle.',
    avatar: 'MA',
    stars: 5,
  },
  {
    name: 'Lisa T.',
    role: 'Freelance Developer',
    text: 'The credential wizard alone is worth it. No more fumbling with App Store Connect API keys — it just works.',
    avatar: 'LT',
    stars: 5,
  },
]

const PAIN_POINTS = [
  'Setting up Xcode build environments',
  'Managing signing certificates',
  'Writing CI/CD pipeline configs',
  'Navigating store console UIs',
  'Debugging build failures',
  'Keeping credentials secure',
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 sticky top-0 bg-gray-950/95 backdrop-blur-sm z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Rocket size={24} className="text-primary-500" />
            <span className="font-bold text-xl tracking-tight">AppTrack</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-400">
            <a href="#why" className="hover:text-white transition-colors">Why AppTrack</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <Link to="/login" className="hover:text-white transition-colors">Sign In</Link>
            <Link to="/login" className="bg-primary-600 hover:bg-primary-700 text-white px-5 py-2.5 rounded-lg font-semibold transition-all hover:scale-105">
              Start Free
            </Link>
          </nav>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-green-500/10 border border-green-500/20 text-green-400 text-sm px-4 py-1.5 rounded-full mb-8 animate-pulse">
          <Globe size={14} /> Trusted by 500+ developers worldwide
        </div>
        <h1 className="text-5xl md:text-7xl font-extrabold leading-[1.1] mb-6 max-w-5xl mx-auto tracking-tight">
          Ship your mobile app<br />
          <span className="bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">to the stores in 30 minutes</span>
        </h1>
        <p className="text-xl md:text-2xl text-gray-400 mb-6 max-w-3xl mx-auto leading-relaxed">
          Connect your GitHub repo. We build for iOS & Android.<br className="hidden md:block" />
          Deploy to App Store & Google Play. <span className="text-white font-medium">No DevOps. No CI/CD. No hassle.</span>
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 mb-10 text-sm text-gray-500">
          <span className="flex items-center gap-1"><Check size={14} className="text-green-400" /> No credit card required</span>
          <span className="flex items-center gap-1"><Check size={14} className="text-green-400" /> 10 free builds/month</span>
          <span className="flex items-center gap-1"><Check size={14} className="text-green-400" /> Cancel anytime</span>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6">
          <Link to="/login" className="flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-10 py-4 rounded-xl text-lg font-bold transition-all hover:scale-105 shadow-lg shadow-primary-600/25">
            Start Free — Deploy Your First App <ArrowRight size={20} />
          </Link>
        </div>
        <a href="#how-it-works" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 transition-colors">
          See how it works in 4 steps <ChevronRight size={14} />
        </a>
      </section>

      <section className="border-t border-gray-800 py-12 bg-gray-900/30">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { label: 'Avg Time to First Deploy', value: '< 30 min' },
              { label: 'Build Success Rate', value: '99.2%' },
              { label: 'Frameworks Supported', value: '4+' },
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

      <section className="border-t border-gray-800 py-16">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-2xl font-bold mb-8 text-gray-300">Stop wasting time on</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {PAIN_POINTS.map((pain) => (
              <div key={pain} className="flex items-center gap-2 bg-red-500/5 border border-red-500/10 rounded-lg px-4 py-3 text-sm text-red-300">
                <span className="text-red-500 font-bold text-lg">x</span> {pain}
              </div>
            ))}
          </div>
          <div className="mt-8 flex items-center justify-center gap-2 text-lg text-gray-400">
            <ArrowRight size={20} className="text-primary-400" />
            <span>Let AppTrack handle all of this for you</span>
          </div>
        </div>
      </section>

      <section id="why" className="border-t border-gray-800 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Why teams switch to AppTrack</h2>
          <p className="text-gray-400 text-center mb-16 max-w-2xl mx-auto">
            Three promises we make — and keep — for every deploy.
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {VALUE_PROPS.map(({ icon: Icon, title, subtitle, desc }) => (
              <div key={title} className="bg-gray-900 border border-gray-800 rounded-2xl p-8 hover:border-primary-600/40 transition-all group">
                <div className="w-14 h-14 bg-primary-600/10 rounded-xl flex items-center justify-center mb-6 group-hover:bg-primary-600/20 transition-colors">
                  <Icon size={28} className="text-primary-400" />
                </div>
                <h3 className="text-xl font-bold mb-1">{title}</h3>
                <p className="text-primary-400 text-sm font-medium mb-3">{subtitle}</p>
                <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-t border-gray-800 py-20 bg-gray-900/30">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">From code to store in 4 steps</h2>
          <p className="text-gray-400 text-center mb-12">No config files. No build scripts. No store console.</p>
          <div className="grid md:grid-cols-4 gap-6">
            {STEPS.map(({ num, title, desc }, i) => (
              <div key={num} className="text-center relative">
                {i < STEPS.length - 1 && (
                  <div className="hidden md:block absolute top-6 left-[60%] w-[80%] h-px bg-gradient-to-r from-primary-600/40 to-transparent" />
                )}
                <div className="w-12 h-12 bg-primary-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4 relative z-10">
                  {num}
                </div>
                <h3 className="font-semibold mb-1">{title}</h3>
                <p className="text-sm text-gray-400">{desc}</p>
              </div>
            ))}
          </div>
          <div className="text-center mt-12">
            <Link to="/login" className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-8 py-3 rounded-xl font-semibold transition-all hover:scale-105">
              Try It Now — It's Free <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      <section className="border-t border-gray-800 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-4">Developers love AppTrack</h2>
          <p className="text-gray-400 text-center mb-12">Here's what our users say after their first deploy.</p>
          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map(({ name, role, text, avatar, stars }) => (
              <div key={name} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 hover:border-gray-700 transition-colors">
                <div className="flex items-center gap-1 mb-4">
                  {Array.from({ length: stars }).map((_, i) => (
                    <Star key={i} size={16} className="text-yellow-400 fill-yellow-400" />
                  ))}
                </div>
                <p className="text-sm text-gray-300 leading-relaxed mb-6">"{text}"</p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-primary-600/20 rounded-full flex items-center justify-center text-sm font-bold text-primary-400">
                    {avatar}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{name}</p>
                    <p className="text-xs text-gray-500">{role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="border-t border-gray-800 py-20 bg-gray-900/30">
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

      <section className="border-t border-gray-800 py-24 bg-gradient-to-b from-gray-950 to-gray-900">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold mb-4">
            Ready to ship your app<br />
            <span className="text-primary-400">in 30 minutes?</span>
          </h2>
          <p className="text-xl text-gray-400 mb-8">
            Join 500+ developers who deploy faster with AppTrack.<br />
            Free forever. No credit card required.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-10 py-4 rounded-xl text-lg font-bold transition-all hover:scale-105 shadow-lg shadow-primary-600/25"
          >
            Start Free — Deploy Now <ArrowRight size={20} />
          </Link>
          <div className="flex items-center justify-center gap-6 mt-6 text-sm text-gray-500">
            <span className="flex items-center gap-1"><Users size={14} /> 500+ developers</span>
            <span className="flex items-center gap-1"><Clock size={14} /> Setup in 2 min</span>
            <span className="flex items-center gap-1"><Shield size={14} /> SOC2 ready</span>
          </div>
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
