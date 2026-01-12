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
  { value: 'model', label: 'Model Name (model)' },
  { value: 'headers.x-priority', label: 'Header: Priority (headers.x-priority)' },
  { value: 'body.temperature', label: 'Temperature (body.temperature)' },
  { value: 'token_usage.input_tokens', label: 'Input Tokens (token_usage.input_tokens)' },
  { value: 'custom', label: 'Custom Path' },
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
        <div className="space-y-2">
          {ruleSet.rules.map((rule, index) => (
            <div key={index} className="flex items-start gap-2">
              <div className="grid flex-1 gap-2 md:grid-cols-3">
                {/* Field Selection */}
                <Select
                  value={FIELDS.some(f => f.value === rule.field) ? rule.field : 'custom'}
                  onValueChange={(val) => {
                    if (val !== 'custom') {
                      updateRule(index, { ...rule, field: val });
                    }
                  }}
                  disabled={disabled}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select Field" />
                  </SelectTrigger>
                  <SelectContent>
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
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}

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
            <Plus className="mr-2 h-4 w-4" />
            Add Rule
          </Button>
        )}
      </div>
    </Card>
  );
}