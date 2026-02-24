import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useInternalScrapeStatus, keys } from "@/lib/queries"
import { Loader2 } from "lucide-react"

interface ScrapeProgressProps {
  /** Whether polling is enabled (turn on after triggering a scrape) */
  enabled: boolean
  /** Called when the scrape finishes, so the parent can reset state */
  onComplete: () => void
}

export function ScrapeProgress({ enabled, onComplete }: ScrapeProgressProps) {
  const queryClient = useQueryClient()
  const { data: status } = useInternalScrapeStatus(enabled)
  const completedRef = useRef(false)

  useEffect(() => {
    // Reset the guard when a new scrape starts
    if (enabled && status?.running) {
      completedRef.current = false
    }
  }, [enabled, status?.running])

  useEffect(() => {
    if (status && status.done && !status.running && !completedRef.current) {
      completedRef.current = true
      // Scrape finished -- refetch results + creators
      queryClient.invalidateQueries({ queryKey: keys.internalResults })
      queryClient.invalidateQueries({ queryKey: keys.internalCreators })
      onComplete()
    }
  }, [status, queryClient, onComplete])

  // Don't render anything if not actively scraping
  if (!enabled || !status?.running) return null

  return (
    <div className="mb-4">
      <div className="bg-white border border-[#e8e8ef] rounded-[10px] px-4 py-3 border-l-[3px] border-l-[#0b62d6]">
        <div className="flex items-center gap-2.5">
          <Loader2 className="size-4 animate-spin text-[#0b62d6] flex-shrink-0" />
          <span className="text-[14px] text-[#333]">
            {status?.progress || "Starting..."}
          </span>
        </div>
      </div>
    </div>
  )
}
