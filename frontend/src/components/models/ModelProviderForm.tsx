/**
 * 模型-供应商映射表单组件
 * 用于为模型添加供应商配置
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
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  Provider,
} from '@/types';

interface ModelProviderFormProps {
  /** 是否显示对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 当前的请求模型名 */
  requestedModel: string;
  /** 可选的供应商列表 */
  providers: Provider[];
  /** 编辑模式下的映射数据 */
  mapping?: ModelMappingProvider | null;
  /** 提交回调 */
  onSubmit: (data: ModelMappingProviderCreate | ModelMappingProviderUpdate) => void;
  /** 是否加载中 */
  loading?: boolean;
}

/** 表单字段定义 */
interface FormData {
  provider_id: string;
  target_model_name: string;
  provider_rules: string;
  priority: number;
  weight: number;
  is_active: boolean;
}

/**
 * 模型-供应商映射表单组件
 */
export function ModelProviderForm({
  open,
  onOpenChange,
  requestedModel,
  providers,
  mapping,
  onSubmit,
  loading = false,
}: ModelProviderFormProps) {
  // 判断是否为编辑模式
  const isEdit = !!mapping;
  
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
      provider_id: '',
      target_model_name: '',
      provider_rules: '',
      priority: 0,
      weight: 1,
      is_active: true,
    },
  });

  const providerId = watch('provider_id');
  const isActive = watch('is_active');

  // 编辑模式下，填充表单数据
  useEffect(() => {
    if (mapping) {
      reset({
        provider_id: String(mapping.provider_id),
        target_model_name: mapping.target_model_name,
        provider_rules: mapping.provider_rules
          ? JSON.stringify(mapping.provider_rules, null, 2)
          : '',
        priority: mapping.priority,
        weight: mapping.weight,
        is_active: mapping.is_active,
      });
    } else {
      reset({
        provider_id: '',
        target_model_name: '',
        provider_rules: '',
        priority: 0,
        weight: 1,
        is_active: true,
      });
    }
  }, [mapping, reset]);

  // 提交表单
  const onFormSubmit = (data: FormData) => {
    if (isEdit) {
      // 更新模式
      const submitData: ModelMappingProviderUpdate = {
        target_model_name: data.target_model_name,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };
      
      if (data.provider_rules.trim()) {
        try {
          submitData.provider_rules = JSON.parse(data.provider_rules);
        } catch {
          // 解析失败则忽略
        }
      } else {
        submitData.provider_rules = null;
      }
      
      onSubmit(submitData);
    } else {
      // 创建模式
      const submitData: ModelMappingProviderCreate = {
        requested_model: requestedModel,
        provider_id: Number(data.provider_id),
        target_model_name: data.target_model_name,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };
      
      if (data.provider_rules.trim()) {
        try {
          submitData.provider_rules = JSON.parse(data.provider_rules);
        } catch {
          // 解析失败则忽略
        }
      }
      
      onSubmit(submitData);
    }
  };

  // 验证 JSON 格式
  const validateJson = (value: string) => {
    if (!value.trim()) return true;
    try {
      JSON.parse(value);
      return true;
    } catch {
      return '请输入有效的 JSON 格式';
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? '编辑供应商配置' : '添加供应商配置'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* 请求模型名（只读） */}
          <div className="space-y-2">
            <Label>请求模型名</Label>
            <Input value={requestedModel} disabled />
          </div>

          {/* 供应商选择 */}
          <div className="space-y-2">
            <Label>
              供应商 <span className="text-destructive">*</span>
            </Label>
            <Select
              value={providerId}
              onValueChange={(value) => setValue('provider_id', value)}
              disabled={isEdit}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择供应商" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={String(provider.id)}>
                    {provider.name} ({provider.protocol})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!providerId && !isEdit && (
              <p className="text-sm text-destructive">请选择供应商</p>
            )}
          </div>

          {/* 目标模型名 */}
          <div className="space-y-2">
            <Label htmlFor="target_model_name">
              目标模型名 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="target_model_name"
              placeholder="该供应商使用的实际模型名，如 gpt-4-0613"
              {...register('target_model_name', {
                required: '目标模型名不能为空',
              })}
            />
            {errors.target_model_name && (
              <p className="text-sm text-destructive">
                {errors.target_model_name.message}
              </p>
            )}
          </div>

          {/* 优先级和权重 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="priority">优先级</Label>
              <Input
                id="priority"
                type="number"
                min={0}
                {...register('priority', { valueAsNumber: true })}
              />
              <p className="text-sm text-muted-foreground">数值越小优先级越高</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="weight">权重</Label>
              <Input
                id="weight"
                type="number"
                min={1}
                {...register('weight', { valueAsNumber: true })}
              />
            </div>
          </div>

          {/* 供应商级规则 */}
          <div className="space-y-2">
            <Label htmlFor="provider_rules">
              供应商级规则 <span className="text-muted-foreground">(JSON, 可选)</span>
            </Label>
            <Textarea
              id="provider_rules"
              placeholder='{"rules": [{"field": "token_usage.input_tokens", "operator": "lte", "value": 4000}]}'
              rows={4}
              {...register('provider_rules', {
                validate: validateJson,
              })}
            />
            {errors.provider_rules && (
              <p className="text-sm text-destructive">
                {errors.provider_rules.message}
              </p>
            )}
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
            <Button
              type="submit"
              disabled={loading || (!isEdit && !providerId)}
            >
              {loading ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
