/**
 * 日志筛选组件
 * 提供多条件日志查询筛选器
 */

'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, RotateCcw } from 'lucide-react';
import { LogQueryParams, Provider } from '@/types';

interface LogFiltersProps {
  /** 当前筛选参数 */
  filters: LogQueryParams;
  /** 筛选参数变更回调 */
  onFiltersChange: (filters: LogQueryParams) => void;
  /** 供应商列表（用于下拉选择） */
  providers: Provider[];
  /** 搜索按钮点击回调 */
  onSearch: () => void;
  /** 重置按钮点击回调 */
  onReset: () => void;
}

/**
 * 日志筛选组件
 */
export function LogFilters({
  filters,
  onFiltersChange,
  providers,
  onSearch,
  onReset,
}: LogFiltersProps) {
  // 更新单个筛选字段
  const updateFilter = <K extends keyof LogQueryParams>(
    key: K,
    value: LogQueryParams[K]
  ) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      {/* 第一行：时间范围 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="space-y-2">
          <Label>开始时间</Label>
          <Input
            type="datetime-local"
            value={filters.start_time || ''}
            onChange={(e) => updateFilter('start_time', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>结束时间</Label>
          <Input
            type="datetime-local"
            value={filters.end_time || ''}
            onChange={(e) => updateFilter('end_time', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>请求模型</Label>
          <Input
            placeholder="模糊匹配"
            value={filters.requested_model || ''}
            onChange={(e) => updateFilter('requested_model', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>目标模型</Label>
          <Input
            placeholder="模糊匹配"
            value={filters.target_model || ''}
            onChange={(e) => updateFilter('target_model', e.target.value)}
          />
        </div>
      </div>

      {/* 第二行：供应商和状态 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="space-y-2">
          <Label>供应商</Label>
          <Select
            value={filters.provider_id ? String(filters.provider_id) : ''}
            onValueChange={(value) =>
              updateFilter('provider_id', value ? Number(value) : undefined)
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="全部" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">全部</SelectItem>
              {providers.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>状态码范围</Label>
          <div className="flex gap-2">
            <Input
              type="number"
              placeholder="最小"
              value={filters.status_min || ''}
              onChange={(e) =>
                updateFilter('status_min', e.target.value ? Number(e.target.value) : undefined)
              }
            />
            <Input
              type="number"
              placeholder="最大"
              value={filters.status_max || ''}
              onChange={(e) =>
                updateFilter('status_max', e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>是否有错误</Label>
          <Select
            value={filters.has_error === undefined ? '' : String(filters.has_error)}
            onValueChange={(value) =>
              updateFilter('has_error', value === '' ? undefined : value === 'true')
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="全部" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">全部</SelectItem>
              <SelectItem value="true">有错误</SelectItem>
              <SelectItem value="false">无错误</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>重试次数</Label>
          <div className="flex gap-2">
            <Input
              type="number"
              placeholder="最小"
              min={0}
              value={filters.retry_count_min ?? ''}
              onChange={(e) =>
                updateFilter('retry_count_min', e.target.value ? Number(e.target.value) : undefined)
              }
            />
            <Input
              type="number"
              placeholder="最大"
              min={0}
              value={filters.retry_count_max ?? ''}
              onChange={(e) =>
                updateFilter('retry_count_max', e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>
        </div>
      </div>

      {/* 第三行：API Key 和 Token */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="space-y-2">
          <Label>API Key 名称</Label>
          <Input
            placeholder="模糊匹配"
            value={filters.api_key_name || ''}
            onChange={(e) => updateFilter('api_key_name', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>输入 Token 区间</Label>
          <div className="flex gap-2">
            <Input
              type="number"
              placeholder="最小"
              value={filters.input_tokens_min ?? ''}
              onChange={(e) =>
                updateFilter('input_tokens_min', e.target.value ? Number(e.target.value) : undefined)
              }
            />
            <Input
              type="number"
              placeholder="最大"
              value={filters.input_tokens_max ?? ''}
              onChange={(e) =>
                updateFilter('input_tokens_max', e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>总耗时区间 (ms)</Label>
          <div className="flex gap-2">
            <Input
              type="number"
              placeholder="最小"
              value={filters.total_time_min ?? ''}
              onChange={(e) =>
                updateFilter('total_time_min', e.target.value ? Number(e.target.value) : undefined)
              }
            />
            <Input
              type="number"
              placeholder="最大"
              value={filters.total_time_max ?? ''}
              onChange={(e) =>
                updateFilter('total_time_max', e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>
        </div>
        <div className="flex items-end gap-2">
          <Button onClick={onSearch} className="flex-1">
            <Search className="mr-2 h-4 w-4" />
            搜索
          </Button>
          <Button variant="outline" onClick={onReset}>
            <RotateCcw className="mr-2 h-4 w-4" />
            重置
          </Button>
        </div>
      </div>
    </div>
  );
}
