/**
 * 供应商表单组件
 * 用于创建和编辑供应商
 */

'use client';

import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
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
    } else {
      reset({
        name: '',
        base_url: '',
        protocol: 'openai',
        api_type: 'chat',
        api_key: '',
        is_active: true,
      });
    }
  }, [provider, reset]);

  // 提交表单
  const onFormSubmit = (data: FormData) => {
    // 过滤掉空字符串
    const submitData: ProviderCreate | ProviderUpdate = {
      name: data.name,
      base_url: data.base_url,
      protocol: data.protocol,
      api_type: data.api_type,
      is_active: data.is_active,
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
