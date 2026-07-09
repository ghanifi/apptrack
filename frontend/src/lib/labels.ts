// Ham backend enum değerlerini kullanıcıya gösterilecek etiketlere çevirir.
// UI'da asla ham değer ("flutter", "ios", "react_native") basma — bu map'i kullan.

export const FRAMEWORK_LABELS: Record<string, string> = {
  flutter: 'Flutter',
  react_native: 'React Native',
  expo: 'Expo',
  swift: 'Swift (iOS)',
  kotlin: 'Kotlin (Android)',
  capacitor: 'Capacitor',
  ionic: 'Ionic',
  cordova: 'Cordova',
  pwa: 'PWA',
  unknown: 'Unknown',
}

export function frameworkLabel(framework: string | null | undefined): string {
  if (!framework) return 'Unknown'
  return FRAMEWORK_LABELS[framework] ?? framework
}

export function platformLabel(platform: string): string {
  switch (platform) {
    case 'ios': return 'iOS'
    case 'android': return 'Android'
    case 'both': return 'Android + iOS'
    case 'web': return 'Web Deploy'
    default: return platform.charAt(0).toUpperCase() + platform.slice(1)
  }
}
