/**
 * 模型映射表单组件
 * 用于创建和编辑模型映射
 */

'use client';

import React, { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
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
import { Switch } from '@/components/ui/switch';
import { RuleBuilder } from '@/components/common';
import { ModelMapping, ModelMappingCreate, ModelMappingUpdate, RuleSet } from '@/types';
import { isValidModelName } from '@/lib/utils';

interface ModelFormProps {
  /** 是否显示对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 编辑模式下的模型数据 */
  model?: ModelMapping | null;
  /** 提交回调 */
  onSubmit: (data: ModelMappingCreate | ModelMappingUpdate) => void;
  /** 是否加载中 */
  loading?: boolean;
}

/** 表单字段定义 */
interface FormData {
  requested_model: string;
  strategy: string;
  matching_rules: RuleSet | null;
  capabilities: string;
  is_active: boolean;
}

/**
 * 模型映射表单组件
 */
export function ModelForm({
  open,
  onOpenChange,
  model,
  onSubmit,
  loading = false,
}: ModelFormProps) {
  // 判断是否为编辑模式
  const isEdit = !!model;
  
  // 表单控制
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    control,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      requested_model: '',
      strategy: 'round_robin',
      matching_rules: null,
      capabilities: '',
      is_active: true,
    },
  });

  const isActive = watch('is_active');

  // 编辑模式下，填充表单数据
  useEffect(() => {
    if (model) {
      reset({
        requested_model: model.requested_model,
        strategy: model.strategy,
        matching_rules: model.matching_rules || null,
        capabilities: model.capabilities
          ? JSON.stringify(model.capabilities, null, 2)
          : '',
        is_active: model.is_active,
      });
    } else {
      reset({
        requested_model: '',
        strategy: 'round_robin',
        matching_rules: null,
        capabilities: '',
        is_active: true,
      });
    }
  }, [model, reset]);

  // 提交表单
  const onFormSubmit = (data: FormData) => {
    const submitData: ModelMappingCreate | ModelMappingUpdate = {
      strategy: data.strategy,
      is_active: data.is_active,
    };
    
    // 创建时需要 requested_model
    if (!isEdit) {
      (submitData as ModelMappingCreate).requested_model = data.requested_model;
    }
    
    // 规则直接赋值
    submitData.matching_rules = data.matching_rules || undefined;
    
    // 解析 JSON 字段
    if (data.capabilities.trim()) {
      try {
        submitData.capabilities = JSON.parse(data.capabilities);
      } catch {
        // 解析失败则忽略
      }
    }
    
    onSubmit(submitData);
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
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑模型映射' : '新增模型映射'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* 请求模型名 */}
          <div className="space-y-2">
            <Label htmlFor="requested_model">
              请求模型名 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="requested_model"
              placeholder="例如: gpt-4, claude-3-opus"
              disabled={isEdit}
              {...register('requested_model', {
                required: !isEdit ? '请求模型名不能为空' : false,
                validate: !isEdit
                  ? (v) => isValidModelName(v) || '模型名只能包含字母、数字、下划线、短横线和点'
                  : undefined,
              })}
            />
            {errors.requested_model && (
              <p className="text-sm text-destructive">
                {errors.requested_model.message}
              </p>
            )}
            {isEdit && (
              <p className="text-sm text-muted-foreground">
                模型名为主键，不可修改
              </p>
            )}
          </div>

          {/* 策略 */}
          <div className="space-y-2">
            <Label htmlFor="strategy">选择策略</Label>
            <Input
              id="strategy"
              value="round_robin"
              disabled
              {...register('strategy')}
            />
            <p className="text-sm text-muted-foreground">
              当前仅支持轮询策略 (round_robin)
            </p>
          </div>

          {/* 匹配规则 */}
          <div className="space-y-2">
            <Label>匹配规则</Label>
            <Controller
              name="matching_rules"
              control={control}
              render={({ field }) => (
                <RuleBuilder
                  value={field.value}
                  onChange={field.onChange}
                />
              )}
            />
          </div>

          {/* 功能描述 */}
          <div className="space-y-2">
            <Label htmlFor="capabilities">
              功能描述 <span className="text-muted-foreground">(JSON, 可选)</span>
            </Label>
            <Textarea
              id="capabilities"
              placeholder='{"streaming": true, "function_calling": true}'
              rows={3}
              {...register('capabilities', {
                validate: validateJson,
              })}
            />
            {errors.capabilities && (
              <p className="text-sm text-destructive">
                {errors.capabilities.message}
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
            <Button type="submit" disabled={loading}>
              {loading ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}