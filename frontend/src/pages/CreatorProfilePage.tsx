import { useState, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronRight,
  ExternalLink,
  Loader2,
} from "lucide-react"
import { useCreatorProfile } from "@/lib/queries"
import type { CreatorCampaignEntry, CreatorVideo } from "@/lib/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"

// ---- Helpers ----

function formatCurrency(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatViews(value: number): string {
  if (!value) return "-"
  return value.toLocaleString("en-US")
}

function formatCpm(value: number | null): string {
  if (value === null || value === undefined) return "-"
  return `$${value.toFixed(2)}`
}

// ---- TikTok Icon ----

function TikTokIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.34-6.34V8.73a8.19 8.19 0 004.76 1.52V6.8a4.84 4.84 0 01-1-.11z" />
    </svg>
  )
}

// ---- Sortable Header ----

function SortableHeader({
  column,
  label,
}: {
  column: {
    getIsSorted: () => false | "asc" | "desc"
    toggleSorting: (desc?: boolean) => void
  }
  label: string
}) {
  const sorted = column.getIsSorted()
  return (
    <button
      type="button"
      className="flex items-center gap-1 hover:text-[#555] transition-colors"
      onClick={() => column.toggleSorting(sorted === "asc")}
    >
      {label}
      {sorted === "asc" ? (
        <ArrowUp className="size-3" />
      ) : sorted === "desc" ? (
        <ArrowDown className="size-3" />
      ) : (
        <ArrowUpDown className="size-3 opacity-40" />
      )}
    </button>
  )
}

// ---- Main Component ----

export default function CreatorProfilePage() {
  const { username } = useParams<{ username: string }>()
  const { data: profile, isLoading, isError, error } = useCreatorProfile(
    username!
  )

  const [campaignSorting, setCampaignSorting] = useState<SortingState>([])
  const [videoSorting, setVideoSorting] = useState<SortingState>([
    { id: "views", desc: true },
  ])

  // Campaign history columns
  const campaignColumns: ColumnDef<CreatorCampaignEntry>[] = useMemo(
    () => [
      {
        accessorKey: "title",
        header: ({ column }) => (
          <SortableHeader column={column} label="Campaign" />
        ),
        cell: ({ row }) => {
          const c = row.original
          return (
            <Link
              to={`/campaign/${c.slug}`}
              className="font-semibold text-[#0b62d6] hover:underline"
            >
              {c.title}
            </Link>
          )
        },
      },
      {
        accessorKey: "posts_done",
        id: "posts",
        header: ({ column }) => (
          <SortableHeader column={column} label="Posts" />
        ),
        cell: ({ row }) => (
          <span className="font-semibold">
            {row.original.posts_done} / {row.original.posts_owed}
          </span>
        ),
        sortingFn: (rowA, rowB) =>
          rowA.original.posts_done - rowB.original.posts_done,
      },
      {
        accessorKey: "total_rate",
        header: ({ column }) => (
          <SortableHeader column={column} label="Rate" />
        ),
        cell: ({ row }) => (
          <span>{formatCurrency(row.original.total_rate)}</span>
        ),
      },
      {
        accessorKey: "paid",
        header: ({ column }) => (
          <SortableHeader column={column} label="Paid" />
        ),
        cell: ({ row }) => {
          const isPaid = row.original.paid?.toLowerCase() === "yes"
          return (
            <span
              className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isPaid
                  ? "bg-[#f0fdf4] text-[#16a34a]"
                  : "bg-[#fef2f2] text-[#dc2626]"
              }`}
            >
              {isPaid ? "Paid" : "Unpaid"}
            </span>
          )
        },
      },
      {
        accessorKey: "status",
        header: ({ column }) => (
          <SortableHeader column={column} label="Status" />
        ),
        cell: ({ row }) => {
          const status = row.original.status || "active"
          return (
            <span
              className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                status === "active"
                  ? "bg-[#eef2ff] text-[#0b62d6]"
                  : "bg-[#f5f5f5] text-[#888]"
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          )
        },
      },
      {
        accessorKey: "notes",
        header: "Notes",
        cell: ({ row }) => (
          <span className="text-[12px] text-[#666]">
            {row.original.notes || ""}
          </span>
        ),
      },
    ],
    []
  )

  // Video columns
  const videoColumns: ColumnDef<CreatorVideo>[] = useMemo(
    () => [
      {
        accessorKey: "campaign_title",
        header: ({ column }) => (
          <SortableHeader column={column} label="Campaign" />
        ),
        cell: ({ row }) => (
          <Link
            to={`/campaign/${row.original.campaign_slug}`}
            className="text-[#0b62d6] hover:underline text-[13px]"
          >
            {row.original.campaign_title}
          </Link>
        ),
      },
      {
        accessorKey: "url",
        header: "Post",
        cell: ({ row }) => (
          <a
            href={row.original.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#0b62d6] hover:underline inline-flex items-center gap-1 text-[13px]"
          >
            View Post
            <ExternalLink className="size-3" />
          </a>
        ),
      },
      {
        accessorKey: "views",
        header: ({ column }) => (
          <SortableHeader column={column} label="Views" />
        ),
        cell: ({ row }) => (
          <span className="text-[14px]">
            {formatViews(row.original.views)}
          </span>
        ),
      },
      {
        accessorKey: "likes",
        header: ({ column }) => (
          <SortableHeader column={column} label="Likes" />
        ),
        cell: ({ row }) => (
          <span className="text-[14px]">
            {formatViews(row.original.likes)}
          </span>
        ),
      },
      {
        accessorKey: "upload_date",
        header: ({ column }) => (
          <SortableHeader column={column} label="Date" />
        ),
        cell: ({ row }) => (
          <span className="text-[13px] text-[#666]">
            {row.original.upload_date || "-"}
          </span>
        ),
      },
    ],
    []
  )

  const campaignTable = useReactTable({
    data: profile?.campaigns ?? [],
    columns: campaignColumns,
    state: { sorting: campaignSorting },
    onSortingChange: setCampaignSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const videoTable = useReactTable({
    data: profile?.videos ?? [],
    columns: videoColumns,
    state: { sorting: videoSorting },
    onSortingChange: setVideoSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  // Loading
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 animate-spin text-[#888]" />
        <span className="ml-2 text-[#888] text-sm">Loading creator...</span>
      </div>
    )
  }

  // Error
  if (isError || !profile) {
    return (
      <div className="bg-white border border-[#e8e8ef] rounded-[10px] p-10 text-center">
        <p className="text-red-600 text-sm">
          {error?.message || "Failed to load creator profile"}
        </p>
        <Link
          to="/creators"
          className="text-[#0b62d6] text-sm mt-2 inline-block hover:underline"
        >
          Back to Creator Database
        </Link>
      </div>
    )
  }

  const { stats } = profile

  const statCards = [
    {
      label: "Campaigns",
      value: stats.campaigns_count.toString(),
    },
    {
      label: "Total Spend",
      value: formatCurrency(stats.total_spend),
    },
    {
      label: "Total Payout",
      value: formatCurrency(stats.total_payout),
      sub:
        stats.total_spend > 0
          ? `${Math.round((stats.total_payout / stats.total_spend) * 100)}% paid`
          : undefined,
    },
    {
      label: "Posts",
      value: `${stats.total_posts_done} / ${stats.total_posts_owed}`,
    },
    {
      label: "Total Views",
      value: formatViews(stats.total_views),
    },
    {
      label: "Avg CPM",
      value: formatCpm(stats.avg_cpm),
    },
  ]

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-[13px] text-[#888]">
        <Link
          to="/creators"
          className="hover:text-[#555] transition-colors"
        >
          Creator Database
        </Link>
        <ChevronRight className="size-3.5" />
        <span className="text-[#333] font-medium">@{profile.username}</span>
      </div>

      {/* Header */}
      <div className="bg-white border border-[#e8e8ef] rounded-[10px] px-6 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-semibold text-[#1a1a2e]">
            @{profile.username}
          </h1>
          {profile.paypal_email && (
            <p className="text-[13px] text-[#888] mt-0.5">
              PayPal: {profile.paypal_email}
            </p>
          )}
        </div>
        <a
          href={`https://www.tiktok.com/@${profile.username}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button
            variant="outline"
            className="gap-2"
          >
            <TikTokIcon className="size-4" />
            View on TikTok
          </Button>
        </a>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white border border-[#e8e8ef] rounded-[10px] p-4"
          >
            <div className="text-[#888] text-xs font-semibold uppercase tracking-wide mb-1">
              {card.label}
            </div>
            <div className="text-[22px] font-bold text-[#1a1a2e]">
              {card.value}
            </div>
            {card.sub && (
              <div className="text-[#888] text-[13px] mt-0.5">{card.sub}</div>
            )}
          </div>
        ))}
      </div>

      {/* Campaign History */}
      <div>
        <h2 className="text-[16px] font-semibold text-[#1a1a2e] mb-3">
          Campaign History
        </h2>
        <div className="bg-white border border-[#e8e8ef] rounded-[10px] overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                {campaignTable.getHeaderGroups().map((headerGroup) => (
                  <TableRow
                    key={headerGroup.id}
                    className="border-b-2 border-[#e8e8ef] hover:bg-transparent"
                  >
                    {headerGroup.headers.map((header) => (
                      <TableHead
                        key={header.id}
                        className="text-[#888] text-xs font-semibold uppercase tracking-[0.3px] px-4 py-3 border-b-2 border-[#e8e8ef]"
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {campaignTable.getRowModel().rows.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={campaignColumns.length}
                      className="text-center text-[#888] py-10 text-sm"
                    >
                      No campaign history.
                    </TableCell>
                  </TableRow>
                ) : (
                  campaignTable.getRowModel().rows.map((row) => (
                    <TableRow
                      key={row.id}
                      className="hover:bg-[#fafaff] border-b border-[#f0f0f5]"
                    >
                      {row.getVisibleCells().map((cell) => (
                        <TableCell
                          key={cell.id}
                          className="px-4 py-2 text-[14px] border-b border-[#f0f0f5] align-middle"
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      {/* Live Posts */}
      {profile.videos.length > 0 && (
        <div>
          <h2 className="text-[16px] font-semibold text-[#1a1a2e] mb-3">
            Live Posts ({profile.videos.length})
          </h2>
          <div className="bg-white border border-[#e8e8ef] rounded-[10px] overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  {videoTable.getHeaderGroups().map((headerGroup) => (
                    <TableRow
                      key={headerGroup.id}
                      className="border-b-2 border-[#e8e8ef] hover:bg-transparent"
                    >
                      {headerGroup.headers.map((header) => (
                        <TableHead
                          key={header.id}
                          className="text-[#888] text-xs font-semibold uppercase tracking-[0.3px] px-4 py-3 border-b-2 border-[#e8e8ef]"
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </TableHead>
                      ))}
                    </TableRow>
                  ))}
                </TableHeader>
                <TableBody>
                  {videoTable.getRowModel().rows.map((row) => (
                    <TableRow
                      key={row.id}
                      className="hover:bg-[#fafaff] border-b border-[#f0f0f5]"
                    >
                      {row.getVisibleCells().map((cell) => (
                        <TableCell
                          key={cell.id}
                          className="px-4 py-2 text-[14px] border-b border-[#f0f0f5] align-middle"
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
