/**
 * 分页组件
 * 用于列表页面的分页导航
 */

'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

interface PaginationProps {
  /** 当前页码（从1开始） */
  page: number;
  /** 每页数量 */
  pageSize: number;
  /** 总记录数 */
  total: number;
  /** 页码改变回调 */
  onPageChange: (page: number) => void;
  /** 每页数量改变回调 */
  onPageSizeChange?: (pageSize: number) => void;
  /** 可选的每页数量选项 */
  pageSizeOptions?: number[];
}

/**
 * 分页组件
 * 显示分页导航和页面信息
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
}: PaginationProps) {
  // 计算总页数
  const totalPages = Math.ceil(total / pageSize);
  
  // 是否可以前进/后退
  const canPreviousPage = page > 1;
  const canNextPage = page < totalPages;
  
  // 计算当前显示范围
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between px-2 py-4">
      {/* 左侧：显示信息 */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>
          共 {total} 条，显示 {startItem}-{endItem}
        </span>
        
        {/* 每页数量选择 */}
        {onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span>每页</span>
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
            <span>条</span>
          </div>
        )}
      </div>

      {/* 右侧：分页按钮 */}
      <div className="flex items-center gap-1">
        {/* 第一页 */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(1)}
          disabled={!canPreviousPage}
          title="第一页"
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        
        {/* 上一页 */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(page - 1)}
          disabled={!canPreviousPage}
          title="上一页"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        
        {/* 页码显示 */}
        <span className="flex items-center gap-1 px-2 text-sm">
          <span>第</span>
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
          <span>/ {totalPages || 1} 页</span>
        </span>
        
        {/* 下一页 */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(page + 1)}
          disabled={!canNextPage}
          title="下一页"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        
        {/* 最后一页 */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(totalPages)}
          disabled={!canNextPage}
          title="最后一页"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
