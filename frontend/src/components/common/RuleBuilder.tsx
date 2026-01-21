/**
 * Rule Builder Component
 * Used to create and edit rules for the rule engine.
 */

'use client';

import React from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Rule, RuleSet, RuleOperator } from '@/types';

interface RuleBuilderProps {
  /** Rule set data */
  value?: RuleSet;
  /** Change callback */
  onChange: (value: RuleSet) => void;
  /** Whether read-only */
  disabled?: boolean;
}

/** Supported Fields */
const FIELDS = [
  // Request Headers (User-defined)
  { value: 'custom_header', label: '🔖 Request Header (Custom)' },
  // Token Usage
  { value: 'token_usage.input_tokens', label: '📥 Token Usage: input_tokens' },

  // Request Body
  { value: 'body.temperature', label: '🌡️ Body: temperature' },
  { value: 'body.max_tokens', label: '📊 Body: max_tokens' },
  { value: 'body.top_p', label: '🎯 Body: top_p' },
  { value: 'body.stream', label: '🌊 Body: stream' },

  // Custom Field Path
  { value: 'custom', label: '✏️ Custom Field Path' },
];

/** Supported Operators */
const OPERATORS = [
  { value: 'eq', label: 'Equals (==)' },
  { value: 'ne', label: 'Not Equals (!=)' },
  { value: 'gt', label: 'Greater Than (>)' },
  { value: 'gte', label: 'Greater Than or Equal (>=)' },
  { value: 'lt', label: 'Less Than (<)' },
  { value: 'lte', label: 'Less Than or Equal (<=)' },
  { value: 'contains', label: 'Contains' },
  { value: 'not_contains', label: 'Not Contains' },
  { value: 'regex', label: 'Regex Match' },
];

/**
 * Rule Builder Component
 */
export function RuleBuilder({ value, onChange, disabled }: RuleBuilderProps) {
  // Initialize default value
  const ruleSet = value || { rules: [], logic: 'AND' };

  // Add Rule
  const addRule = () => {
    onChange({
      ...ruleSet,
      rules: [
        ...ruleSet.rules,
        { field: 'model', operator: 'eq', value: '' },
      ],
    });
  };

  // Remove Rule
  const removeRule = (index: number) => {
    const newRules = [...ruleSet.rules];
    newRules.splice(index, 1);
    onChange({ ...ruleSet, rules: newRules });
  };

  // Update Rule
  const updateRule = (index: number, rule: Rule) => {
    const newRules = [...ruleSet.rules];
    newRules[index] = rule;
    onChange({ ...ruleSet, rules: newRules });
  };

  // Update Logic
  const updateLogic = (logic: 'AND' | 'OR') => {
    onChange({ ...ruleSet, logic });
  };

  return (
    <Card className="p-4">
      <div className="space-y-4">
        {/* Header */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">🎯 Matching Rules</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Configure conditions to match specific requests. Leave empty to match all requests.
          </p>
        </div>

        {/* Logic Selection */}
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium">Match Logic:</span>
          <div className="flex rounded-md border p-1">
            <button
              type="button"
              className={`rounded px-3 py-1 text-sm transition-colors ${
                ruleSet.logic === 'AND'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              }`}
              onClick={() => updateLogic('AND')}
              disabled={disabled}
            >
              AND (Match All)
            </button>
            <button
              type="button"
              className={`rounded px-3 py-1 text-sm transition-colors ${
                ruleSet.logic === 'OR'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              }`}
              onClick={() => updateLogic('OR')}
              disabled={disabled}
            >
              OR (Match Any)
            </button>
          </div>
        </div>

        {/* Rule List */}
        <div className="space-y-3">
          {ruleSet.rules.map((rule, index) => {
            // Determine field type
            const isCustomHeader = rule.field.startsWith('headers.') && !FIELDS.some(f => f.value === rule.field);
            const isCustomField = !FIELDS.some(f => f.value === rule.field) && !isCustomHeader;

            let selectedFieldType = rule.field;
            if (isCustomHeader) {
              selectedFieldType = 'custom_header';
            } else if (isCustomField) {
              selectedFieldType = 'custom';
            }

            // Extract header name (without "headers." prefix)
            const headerName = isCustomHeader ? rule.field.replace(/^headers\./, '') : '';

            return (
              <div key={index} className="rounded-lg border bg-muted/30 p-3 space-y-2">
                <div className="flex items-start gap-2">
                  <div className="grid flex-1 gap-2 md:grid-cols-3">
                    {/* Field Selection */}
                    <Select
                      value={selectedFieldType}
                      onValueChange={(val) => {
                        if (val === 'custom_header') {
                          // Switch to custom header mode
                          updateRule(index, { ...rule, field: 'headers.' });
                        } else if (val === 'custom') {
                          // Switch to custom field mode
                          updateRule(index, { ...rule, field: '' });
                        } else {
                          // Use predefined field
                          updateRule(index, { ...rule, field: val });
                        }
                      }}
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select Field" />
                      </SelectTrigger>
                      <SelectContent className="max-h-[300px]">
                        {FIELDS.map((f) => (
                          <SelectItem key={f.value} value={f.value}>
                            {f.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {/* Operator Selection */}
                    <Select
                      value={rule.operator}
                      onValueChange={(val) => updateRule(index, { ...rule, operator: val as RuleOperator })}
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select Operator" />
                      </SelectTrigger>
                      <SelectContent>
                        {OPERATORS.map((op) => (
                          <SelectItem key={op.value} value={op.value}>
                            {op.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {/* Value Input */}
                    <div className="flex gap-2">
                      <Input
                        placeholder="Match Value"
                        value={String(rule.value)}
                        onChange={(e) => {
                          // Try to convert to number or boolean
                          let val: string | number | boolean = e.target.value;
                          if (!isNaN(Number(val)) && val !== '') {
                            val = Number(val);
                          } else if (val === 'true') {
                            val = true;
                          } else if (val === 'false') {
                            val = false;
                          }
                          updateRule(index, { ...rule, value: val });
                        }}
                        disabled={disabled}
                      />
                      {!disabled && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeRule(index)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <X className="h-4 w-4" suppressHydrationWarning />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Custom Header Name Input */}
                {isCustomHeader && (
                  <div className="space-y-1.5 pl-1">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>🔖</span>
                      <span className="font-medium">Header Name:</span>
                    </div>
                    <Input
                      placeholder="e.g., x-api-key, x-user-id, authorization, content-type"
                      value={headerName}
                      onChange={(e) => updateRule(index, { ...rule, field: `headers.${e.target.value}` })}
                      disabled={disabled}
                      className="font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      💡 Enter the header name only. Examples: <code className="px-1 py-0.5 rounded bg-muted">x-api-key</code>, <code className="px-1 py-0.5 rounded bg-muted">authorization</code>, <code className="px-1 py-0.5 rounded bg-muted">x-custom-header</code>
                    </p>
                  </div>
                )}

                {/* Custom Field Path Input */}
                {isCustomField && (
                  <div className="space-y-1.5 pl-1">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>✏️</span>
                      <span className="font-medium">Custom Field Path:</span>
                    </div>
                    <Input
                      placeholder="e.g., body.user.id, metadata.region, context.session_id"
                      value={rule.field}
                      onChange={(e) => updateRule(index, { ...rule, field: e.target.value })}
                      disabled={disabled}
                      className="font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      💡 Use dot notation to access nested fields. Examples: <code className="px-1 py-0.5 rounded bg-muted">body.user.id</code>, <code className="px-1 py-0.5 rounded bg-muted">metadata.region</code>
                    </p>
                  </div>
                )}
              </div>
            );
          })}

          {/* Empty State */}
          {ruleSet.rules.length === 0 && (
            <div className="flex h-20 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
              No rules configured, matches all requests by default
            </div>
          )}
        </div>

        {/* Add Button */}
        {!disabled && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addRule}
            className="w-full border-dashed"
          >
            <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
            Add Rule
          </Button>
        )}
      </div>
    </Card>
  );
}
