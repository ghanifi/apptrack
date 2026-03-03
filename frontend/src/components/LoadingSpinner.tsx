import { Loader2 } from 'lucide-react'

export default function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <Loader2 size={32} className="animate-spin text-primary-500" aria-label="Loading" />
    </div>
  )
}
