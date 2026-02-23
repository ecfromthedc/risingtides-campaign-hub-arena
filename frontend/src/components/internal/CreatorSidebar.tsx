import { useState } from "react"
import { Link } from "react-router-dom"
import {
  useInternalCreators,
  useAddInternalCreators,
  useRemoveInternalCreator,
} from "@/lib/queries"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, X } from "lucide-react"

export function CreatorSidebar() {
  const { data: creators, isLoading } = useInternalCreators()
  const addCreators = useAddInternalCreators()
  const removeCreator = useRemoveInternalCreator()
  const [input, setInput] = useState("")

  const sorted = [...(creators || [])].sort((a, b) =>
    a.username.localeCompare(b.username)
  )

  function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    const value = input.trim()
    if (!value) return
    addCreators.mutate(value, {
      onSuccess: () => setInput(""),
    })
  }

  function handleRemove(username: string) {
    if (!confirm(`Remove @${username} from internal creators?`)) return
    removeCreator.mutate(username)
  }

  return (
    <div className="bg-white border border-[#e8e8ef] rounded-[10px] p-4 lg:sticky lg:top-6">
      <h3 className="text-[15px] font-semibold mb-3">
        Internal Creators ({sorted.length})
      </h3>

      {/* Add form */}
      <form onSubmit={handleAdd} className="mb-3">
        <div className="flex gap-1.5">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="@username"
            className="flex-1 text-[13px] h-8"
          />
          <Button
            type="submit"
            size="sm"
            className="bg-[#0b62d6] hover:bg-[#0951b5] text-white text-xs"
            disabled={addCreators.isPending || !input.trim()}
          >
            {addCreators.isPending ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              "Add"
            )}
          </Button>
        </div>
        <p className="text-[11px] text-[#999] mt-1">
          Comma or newline separated for bulk add
        </p>
      </form>

      {addCreators.isError && (
        <p className="text-red-600 text-xs mb-2">
          {addCreators.error?.message || "Failed to add creators"}
        </p>
      )}

      {/* Creator list */}
      <div className="max-h-[600px] overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="size-4 animate-spin text-[#888]" />
          </div>
        )}

        {!isLoading && sorted.length === 0 && (
          <p className="text-[#888] text-xs text-center py-4">
            No creators added yet.
          </p>
        )}

        {sorted.map((creator) => (
          <div
            key={creator.username}
            className="flex items-center justify-between py-1.5 border-b border-[#f0f0f5] last:border-b-0"
          >
            <Link
              to={`/internal/${creator.username}`}
              className="text-[#0b62d6] text-[13px] hover:underline flex-1 min-w-0"
            >
              @{creator.username}
              {creator.total_videos > 0 && (
                <span className="text-[#888] text-[11px] ml-1">
                  {creator.total_videos} posts &middot;{" "}
                  {creator.total_views.toLocaleString()}v
                </span>
              )}
            </Link>
            <button
              type="button"
              onClick={() => handleRemove(creator.username)}
              className="text-red-500 hover:text-red-700 text-[16px] px-1.5 py-0.5 leading-none flex-shrink-0"
              title="Remove"
              disabled={removeCreator.isPending}
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
