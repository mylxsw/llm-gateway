/**
 * API Key 表单组件
 * 用于创建和编辑 API Key
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Copy, Check, AlertCircle } from 'lucide-react';
import { ApiKey, ApiKeyCreate, ApiKeyUpdate } from '@/types';
import { isValidKeyName, copyToClipboard } from '@/lib/utils';

interface ApiKeyFormProps {
  /** 是否显示对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 编辑模式下的 API Key 数据 */
  apiKey?: ApiKey | null;
  /** 提交回调 */
  onSubmit: (data: ApiKeyCreate | ApiKeyUpdate) => void;
  /** 是否加载中 */
  loading?: boolean;
  /** 新创建的 API Key（用于显示完整 key_value） */
  createdKey?: ApiKey | null;
}

/** 表单字段定义 */
interface FormData {
  key_name: string;
  is_active: boolean;
}

/**
 * API Key 表单组件
 */
export function ApiKeyForm({
  open,
  onOpenChange,
  apiKey,
  onSubmit,
  loading = false,
  createdKey,
}: ApiKeyFormProps) {
  // 判断是否为编辑模式
  const isEdit = !!apiKey;
  const [copied, setCopied] = useState(false);
  
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
      key_name: '',
      is_active: true,
    },
  });

  const isActive = watch('is_active');

  // 编辑模式下，填充表单数据
  useEffect(() => {
    if (apiKey) {
      reset({
        key_name: apiKey.key_name,
        is_active: apiKey.is_active,
      });
    } else {
      reset({
        key_name: '',
        is_active: true,
      });
    }
    setCopied(false);
  }, [apiKey, reset, open]);

  // 提交表单
  const onFormSubmit = (data: FormData) => {
    if (isEdit) {
      onSubmit({
        key_name: data.key_name,
        is_active: data.is_active,
      });
    } else {
      onSubmit({
        key_name: data.key_name,
      });
    }
  };

  // 复制 API Key
  const handleCopy = async () => {
    if (createdKey?.key_value) {
      const success = await copyToClipboard(createdKey.key_value);
      if (success) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    }
  };

  // 如果是显示新创建的 Key
  if (createdKey) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>API Key 创建成功</DialogTitle>
            <DialogDescription>
              请立即复制保存以下 API Key，关闭后将无法再次查看完整内容
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-md border bg-muted/50 p-3">
              <AlertCircle className="h-5 w-5 text-yellow-500" />
              <span className="text-sm text-muted-foreground">
                这是唯一一次显示完整 Key 的机会
              </span>
            </div>
            
            <div className="space-y-2">
              <Label>API Key 名称</Label>
              <Input value={createdKey.key_name} disabled />
            </div>
            
            <div className="space-y-2">
              <Label>API Key</Label>
              <div className="flex gap-2">
                <Input
                  value={createdKey.key_value}
                  readOnly
                  className="font-mono text-sm"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>
              我已复制保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑 API Key' : '新建 API Key'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* 名称 */}
          <div className="space-y-2">
            <Label htmlFor="key_name">
              名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="key_name"
              placeholder="请输入 API Key 名称，如：生产环境"
              {...register('key_name', {
                required: '名称不能为空',
                validate: (v) => isValidKeyName(v) || '名称格式不正确',
              })}
            />
            {errors.key_name && (
              <p className="text-sm text-destructive">{errors.key_name.message}</p>
            )}
          </div>

          {/* 状态 */}
          {isEdit && (
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">启用状态</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={(checked) => setValue('is_active', checked)}
              />
            </div>
          )}

          {!isEdit && (
            <p className="text-sm text-muted-foreground">
              API Key 将由系统自动生成，创建后请立即保存
            </p>
          )}

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
              {loading ? '保存中...' : isEdit ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
