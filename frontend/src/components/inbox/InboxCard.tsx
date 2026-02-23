import { useState } from "react"
import type { InboxItem, InboxCreator, CampaignSummary } from "@/lib/types"
import { useApproveInbox, useDismissInbox } from "@/lib/queries"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Loader2 } from "lucide-react"

interface InboxCardProps {
  item: InboxItem
  campaigns: CampaignSummary[]
}

// ----- Pending Card -----

function PendingCard({ item, campaigns }: InboxCardProps) {
  const [selectedSlug, setSelectedSlug] = useState(item.campaign_slug || "")
  const [creators, setCreators] = useState<InboxCreator[]>(
    item.creators?.length
      ? item.creators.map((c) => ({ ...c }))
      : [{ username: "", posts_owed: 0, total_rate: 0, paypal_email: "" }]
  )

  const approve = useApproveInbox()
  const dismiss = useDismissInbox()

  function updateCreator(
    idx: number,
    field: keyof InboxCreator,
    value: string | number
  ) {
    setCreators((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], [field]: value }
      return next
    })
  }

  function handleApprove() {
    if (!selectedSlug) {
      return
    }
    const cleaned = creators
      .filter((c) => c.username.trim())
      .map((c) => ({
        username: c.username.trim().replace(/^@/, ""),
        posts_owed: Number(c.posts_owed) || 0,
        total_rate: Number(c.total_rate) || 0,
        paypal_email: c.paypal_email?.trim() || "",
      }))
    approve.mutate({ id: item.id, data: { campaign_slug: selectedSlug, creators: cleaned } })
  }

  function handleDismiss() {
    dismiss.mutate(item.id)
  }

  const timestamp = item.created_at ? item.created_at.slice(0, 16).replace("T", " ") : ""

  return (
    <div className="bg-white border border-[#e8e8ef] rounded-[10px] p-4 mb-3 border-l-4 border-l-[#4f8ff7]">
      {/* Top row: campaign selector + meta */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[13px] text-[#888] font-medium">Campaign:</label>
          <Select value={selectedSlug} onValueChange={setSelectedSlug}>
            <SelectTrigger className="min-w-[220px] h-8 text-[13px]">
              <SelectValue placeholder="-- Select Campaign --" />
            </SelectTrigger>
            <SelectContent>
              {campaigns.map((c) => (
                <SelectItem key={c.slug} value={c.slug}>
                  {c.title || c.slug}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {item.campaign_suggested && (
            <span className="text-[11px] text-[#f59e0b] bg-[#fef3c7] px-2 py-0.5 rounded">
              Suggested
            </span>
          )}
          <span className="text-[12px] text-[#888]">from {item.source || "slack"}</span>
        </div>
        <div className="text-[12px] text-[#aaa]">{timestamp}</div>
      </div>

      {/* Raw message */}
      {item.raw_message && (
        <div className="text-[13px] text-[#666] bg-[#f7f7f9] px-3 py-2 rounded-md mb-2">
          {item.raw_message}
        </div>
      )}

      {/* Creator table */}
      {creators.length > 0 && (
        <div className="overflow-x-auto mb-2">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left">
                <th className="px-3 py-1 font-medium text-[#888]">Creator</th>
                <th className="px-3 py-1 font-medium text-[#888]">Posts</th>
                <th className="px-3 py-1 font-medium text-[#888]">Rate</th>
                <th className="px-3 py-1 font-medium text-[#888]">PayPal</th>
              </tr>
            </thead>
            <tbody>
              {creators.map((cr, idx) => (
                <tr key={idx}>
                  <td className="px-3 py-1">
                    <Input
                      value={cr.username}
                      onChange={(e) => updateCreator(idx, "username", e.target.value)}
                      className="w-[130px] h-7 text-[13px] font-semibold"
                    />
                  </td>
                  <td className="px-3 py-1">
                    <Input
                      type="number"
                      min={0}
                      value={cr.posts_owed}
                      onChange={(e) =>
                        updateCreator(idx, "posts_owed", Number(e.target.value))
                      }
                      className="w-[60px] h-7 text-[13px]"
                    />
                  </td>
                  <td className="px-3 py-1">
                    <Input
                      type="number"
                      step="0.01"
                      min={0}
                      value={cr.total_rate}
                      onChange={(e) =>
                        updateCreator(idx, "total_rate", Number(e.target.value))
                      }
                      className="w-[80px] h-7 text-[13px]"
                    />
                  </td>
                  <td className="px-3 py-1">
                    <Input
                      value={cr.paypal_email || ""}
                      onChange={(e) =>
                        updateCreator(idx, "paypal_email", e.target.value)
                      }
                      placeholder="paypal"
                      className="w-[160px] h-7 text-[13px]"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <Button
          onClick={handleApprove}
          disabled={!selectedSlug || approve.isPending}
          className="bg-[#0b62d6] hover:bg-[#0951b5] text-white text-[13px] h-8"
        >
          {approve.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Adding...
            </>
          ) : (
            "Approve & Add"
          )}
        </Button>
        <Button
          variant="outline"
          onClick={handleDismiss}
          disabled={dismiss.isPending}
          className="text-[13px] h-8"
        >
          {dismiss.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Dismissing...
            </>
          ) : (
            "Dismiss"
          )}
        </Button>
      </div>
    </div>
  )
}

// ----- Approved Card -----

function ApprovedCard({ item }: { item: InboxItem }) {
  const timestamp = (item.approved_at || item.created_at || "")
    .slice(0, 16)
    .replace("T", " ")

  return (
    <div className="bg-white border border-[#e8e8ef] rounded-[10px] p-4 mb-2 opacity-70 border-l-4 border-l-[#22c55e]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-[14px]">
            {item.campaign_name || item.campaign_slug}
          </span>
          <span className="text-[12px] text-[#22c55e] font-medium">Approved</span>
          {item.creators_added && item.creators_added.length > 0 && (
            <span className="text-[12px] text-[#888]">
              -- added {item.creators_added.length} creator(s)
            </span>
          )}
        </div>
        <div className="text-[12px] text-[#aaa]">{timestamp}</div>
      </div>
    </div>
  )
}

// ----- Dismissed Card -----

function DismissedCard({ item }: { item: InboxItem }) {
  const timestamp = (item.dismissed_at || item.created_at || "")
    .slice(0, 16)
    .replace("T", " ")

  return (
    <div className="bg-white border border-[#e8e8ef] rounded-[10px] p-4 mb-2 opacity-40">
      <div className="flex items-center justify-between">
        <span className="text-[14px]">
          {item.campaign_name || item.campaign_slug || "Unknown"}
        </span>
        <span className="text-[12px] text-[#aaa]">{timestamp}</span>
      </div>
    </div>
  )
}

// ----- Exports -----

export function InboxCard({ item, campaigns }: InboxCardProps) {
  switch (item.status) {
    case "pending":
      return <PendingCard item={item} campaigns={campaigns} />
    case "approved":
      return <ApprovedCard item={item} />
    case "dismissed":
      return <DismissedCard item={item} />
    default:
      return null
  }
}
