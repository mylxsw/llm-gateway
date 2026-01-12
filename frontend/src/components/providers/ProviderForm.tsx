/**
 * 供应商表单组件
 * 用于创建和编辑供应商
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
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
import { Switch } from '@/components/ui/switch';
import { Provider, ProviderCreate, ProviderUpdate, ProtocolType } from '@/types';
import { isValidUrl, isNotEmpty } from '@/lib/utils';

interface ProviderFormProps {
  /** 是否显示对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 编辑模式下的供应商数据 */
  provider?: Provider | null;
  /** 提交回调 */
  onSubmit: (data: ProviderCreate | ProviderUpdate) => void;
  /** 是否加载中 */
  loading?: boolean;
}

/** 表单字段定义 */
interface FormData {
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_type: string;
  api_key: string;
  is_active: boolean;
}

/** 协议选项 */
const PROTOCOL_OPTIONS: { value: ProtocolType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
];

/** API 类型选项 */
const API_TYPE_OPTIONS = [
  { value: 'chat', label: 'Chat Completions' },
  { value: 'completion', label: 'Text Completions' },
  { value: 'embedding', label: 'Embeddings' },
];

/**
 * 供应商表单组件
 */
export function ProviderForm({
  open,
  onOpenChange,
  provider,
  onSubmit,
  loading = false,
}: ProviderFormProps) {
  // 判断是否为编辑模式
  const isEdit = !!provider;
  
  // 表单控制
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      name: '',
      base_url: '',
      protocol: 'openai',
      api_type: 'chat',
      api_key: '',
      is_active: true,
    },
  });

  // 监听表单值变化
  const protocol = watch('protocol');
  const isActive = watch('is_active');
  
  // 额外请求头状态
  const [extraHeaders, setExtraHeaders] = useState<{ key: string; value: string }[]>([]);

  // 添加请求头
  const addHeader = () => {
    setExtraHeaders([...extraHeaders, { key: '', value: '' }]);
  };

  // 删除请求头
  const removeHeader = (index: number) => {
    const newHeaders = [...extraHeaders];
    newHeaders.splice(index, 1);
    setExtraHeaders(newHeaders);
  };

  // 更新请求头
  const updateHeader = (index: number, field: 'key' | 'value', value: string) => {
    const newHeaders = [...extraHeaders];
    newHeaders[index][field] = value;
    setExtraHeaders(newHeaders);
  };

  // 编辑模式下，填充表单数据
  useEffect(() => {
    if (provider) {
      reset({
        name: provider.name,
        base_url: provider.base_url,
        protocol: provider.protocol,
        api_type: provider.api_type,
        api_key: '', // API Key 不回显
        is_active: provider.is_active,
      });
      
      // 填充额外请求头
      if (provider.extra_headers) {
        setExtraHeaders(
          Object.entries(provider.extra_headers).map(([key, value]) => ({
            key,
            value,
          }))
        );
      } else {
        setExtraHeaders([]);
      }
    } else {
      reset({
        name: '',
        base_url: '',
        protocol: 'openai',
        api_type: 'chat',
        api_key: '',
        is_active: true,
      });
      setExtraHeaders([]);
    }
  }, [provider, reset]);

  // 提交表单
  const onFormSubmit = (data: FormData) => {
    // 处理额外请求头
    const headers: Record<string, string> = {};
    extraHeaders.forEach(({ key, value }) => {
      if (key && value) {
        headers[key] = value;
      }
    });

    // 过滤掉空字符串
    const submitData: ProviderCreate | ProviderUpdate = {
      name: data.name,
      base_url: data.base_url,
      protocol: data.protocol,
      api_type: data.api_type,
      is_active: data.is_active,
      extra_headers: Object.keys(headers).length > 0 ? headers : undefined,
    };
    
    // 只有填写了 API Key 才提交
    if (data.api_key) {
      submitData.api_key = data.api_key;
    }
    
    onSubmit(submitData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑供应商' : '新增供应商'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* 名称 */}
          <div className="space-y-2">
            <Label htmlFor="name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              placeholder="请输入供应商名称"
              {...register('name', {
                required: '名称不能为空',
                validate: (v) => isNotEmpty(v) || '名称不能为空',
              })}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* 接口地址 */}
          <div className="space-y-2">
            <Label htmlFor="base_url">
              接口地址 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="base_url"
              placeholder="https://api.openai.com"
              {...register('base_url', {
                required: '接口地址不能为空',
                validate: (v) => isValidUrl(v) || '请输入有效的 URL',
              })}
            />
            {errors.base_url && (
              <p className="text-sm text-destructive">{errors.base_url.message}</p>
            )}
          </div>

          {/* 协议类型 */}
          <div className="space-y-2">
            <Label>
              协议类型 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={protocol}
              onValueChange={(value: ProtocolType) => setValue('protocol', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择协议类型" />
              </SelectTrigger>
              <SelectContent>
                {PROTOCOL_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* API 类型 */}
          <div className="space-y-2">
            <Label htmlFor="api_type">
              API 类型 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={watch('api_type')}
              onValueChange={(value) => setValue('api_type', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择 API 类型" />
              </SelectTrigger>
              <SelectContent>
                {API_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <Label htmlFor="api_key">
              API Key {!isEdit && <span className="text-muted-foreground">(可选)</span>}
            </Label>
            <Input
              id="api_key"
              type="password"
              placeholder={isEdit ? '留空则不修改' : '请输入供应商 API Key'}
              {...register('api_key')}
            />
          </div>

          {/* 额外请求头 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>额外请求头</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addHeader}
                className="h-8 px-2"
              >
                <Plus className="mr-1 h-3 w-3" />
                添加
              </Button>
            </div>
            
            {extraHeaders.length === 0 && (
              <p className="text-xs text-muted-foreground">
                暂无额外请求头，点击上方按钮添加。
              </p>
            )}

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {extraHeaders.map((header, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    placeholder="Key"
                    value={header.key}
                    onChange={(e) => updateHeader(index, 'key', e.target.value)}
                    className="flex-1"
                  />
                  <Input
                    placeholder="Value"
                    value={header.value}
                    onChange={(e) => updateHeader(index, 'value', e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeHeader(index)}
                    className="h-9 w-9 text-destructive hover:text-destructive/90"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* 状态 */}
          <div className="flex items-center justify-between">
            <Label htmlFor="is_active">启用状态</Label>
            <Switch
              id="is_active"
              checked={isActive}
              onCheckedChange={(checked) => setValue('is_active', checked)}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
