/**
 * Pagination Component
 * Used for pagination navigation in list pages.
 */

'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

interface PaginationProps {
  /** Current page number (starts from 1) */
  page: number;
  /** Items per page */
  pageSize: number;
  /** Total records */
  total: number;
  /** Page change callback */
  onPageChange: (page: number) => void;
  /** Page size change callback */
  onPageSizeChange?: (pageSize: number) => void;
  /** Optional page size options */
  pageSizeOptions?: number[];
}

/**
 * Pagination Component
 * Displays pagination navigation and page info
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
}: PaginationProps) {
  // Calculate total pages
  const totalPages = Math.ceil(total / pageSize);
  
  // Can go previous/next
  const canPreviousPage = page > 1;
  const canNextPage = page < totalPages;
  
  // Calculate current display range
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between px-2 py-4">
      {/* Left: Display Info */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>
          Total {total} items, showing {startItem}-{endItem}
        </span>
        
        {/* Page Size Selection */}
        {onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span>Per page</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="h-8 w-16 rounded border border-input bg-background px-2 text-sm"
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            <span>items</span>
          </div>
        )}
      </div>

      {/* Right: Pagination Buttons */}
      <div className="flex items-center gap-1">
        {/* First Page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(1)}
          disabled={!canPreviousPage}
          title="First Page"
        >
          <ChevronsLeft className="h-4 w-4" suppressHydrationWarning />
        </Button>
        
        {/* Previous Page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(page - 1)}
          disabled={!canPreviousPage}
          title="Previous Page"
        >
          <ChevronLeft className="h-4 w-4" suppressHydrationWarning />
        </Button>
        
        {/* Page Number Display */}
        <span className="flex items-center gap-1 px-2 text-sm">
          <span>Page</span>
          <input
            type="number"
            min={1}
            max={totalPages || 1}
            value={page}
            onChange={(e) => {
              const val = Number(e.target.value);
              if (val >= 1 && val <= totalPages) {
                onPageChange(val);
              }
            }}
            className="h-8 w-12 rounded border border-input bg-background px-2 text-center text-sm"
          />
          <span>/ {totalPages || 1}</span>
        </span>
        
        {/* Next Page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(page + 1)}
          disabled={!canNextPage}
          title="Next Page"
        >
          <ChevronRight className="h-4 w-4" suppressHydrationWarning />
        </Button>
        
        {/* Last Page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(totalPages)}
          disabled={!canNextPage}
          title="Last Page"
        >
          <ChevronsRight className="h-4 w-4" suppressHydrationWarning />
        </Button>
      </div>
    </div>
  );
}
