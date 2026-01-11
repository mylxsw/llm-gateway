'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Rule, RuleOperator, RuleSet } from '@/types';
import { Trash2, Plus, Code, List } from 'lucide-react';

interface RuleBuilderProps {
  value?: RuleSet | null;
  onChange: (value: RuleSet | null) => void;
  disabled?: boolean;
}

type ValueType = 'string' | 'number' | 'boolean' | 'json';

const OPERATORS: { label: string; value: RuleOperator }[] = [
  { label: 'Equals (eq)', value: 'eq' },
  { label: 'Not Equals (ne)', value: 'ne' },
  { label: 'Greater Than (gt)', value: 'gt' },
  { label: 'Greater or Equal (gte)', value: 'gte' },
  { label: 'Less Than (lt)', value: 'lt' },
  { label: 'Less or Equal (lte)', value: 'lte' },
  { label: 'Contains (contains)', value: 'contains' },
  { label: 'Not Contains (not_contains)', value: 'not_contains' },
  { label: 'Regex (regex)', value: 'regex' },
  { label: 'In List (in)', value: 'in' },
  { label: 'Not In List (not_in)', value: 'not_in' },
  { label: 'Exists (exists)', value: 'exists' },
];

export function RuleBuilder({ value, onChange, disabled }: RuleBuilderProps) {
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const [jsonValue, setJsonValue] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);

  const handleModeChange = (newMode: 'visual' | 'json') => {
    if (newMode === 'visual') {
      // Validate JSON before switching to visual
      if (!jsonValue.trim()) {
        onChange(null);
        setMode('visual');
        return;
      }
      try {
        const parsed = JSON.parse(jsonValue);
        // Basic validation of structure
        if (typeof parsed === 'object' && Array.isArray(parsed.rules)) {
          onChange(parsed);
          setJsonError(null);
          setMode('visual');
        } else {
          setJsonError('Invalid RuleSet structure: must contain "rules" array');
        }
      } catch {
        setJsonError('Invalid JSON syntax');
      }
    } else {
      // Switching to JSON mode, reflect current visual value
      setJsonValue(value ? JSON.stringify(value, null, 2) : '');
      setJsonError(null);
      setMode('json');
    }
  };

  const handleJsonInput = (text: string) => {
    setJsonValue(text);
    if (!text.trim()) {
      onChange(null);
      setJsonError(null);
      return;
    }
    try {
      const parsed = JSON.parse(text);
      onChange(parsed);
      setJsonError(null);
    } catch {
      setJsonError('Invalid JSON syntax');
      // Don't call onChange with invalid JSON
    }
  };

  // Visual Mode Handlers
  const addRule = () => {
    const currentRules = value?.rules || [];
    const newRule: Rule = {
      field: '',
      operator: 'eq',
      value: '',
    };
    onChange({
      rules: [...currentRules, newRule],
      logic: value?.logic || 'AND',
    });
  };

  const removeRule = (index: number) => {
    if (!value) return;
    const newRules = [...value.rules];
    newRules.splice(index, 1);
    onChange({
      ...value,
      rules: newRules,
    });
  };

  const updateRule = (index: number, updates: Partial<Rule>) => {
    if (!value) return;
    const newRules = [...value.rules];
    newRules[index] = { ...newRules[index], ...updates };
    onChange({
      ...value,
      rules: newRules,
    });
  };

  const updateLogic = (logic: 'AND' | 'OR') => {
    onChange({
      rules: value?.rules || [],
      logic,
    });
  };

  // Helper to guess type of value
  const getValueType = (val: unknown): ValueType => {
    if (typeof val === 'boolean') return 'boolean';
    if (typeof val === 'number') return 'number';
    if (typeof val === 'object') return 'json';
    return 'string';
  };

  // Helper to parse value based on type
  const parseValue = (val: string, type: ValueType): unknown => {
    if (type === 'boolean') return val === 'true';
    if (type === 'number') return Number(val);
    if (type === 'json') {
      try {
        return JSON.parse(val);
      } catch {
        return val;
      }
    }
    return val;
  };

  if (mode === 'json') {
    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Rules (JSON)</Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleModeChange('visual')}
            className="h-8"
          >
            <List className="w-4 h-4 mr-2" />
            Switch to Visual
          </Button>
        </div>
        <Textarea
          value={jsonValue}
          onChange={(e) => handleJsonInput(e.target.value)}
          rows={8}
          className={`font-mono ${jsonError ? 'border-destructive' : ''}`}
          placeholder='{"rules": [{"field": "...", "operator": "eq", "value": "..."}], "logic": "AND"}'
          disabled={disabled}
        />
        {jsonError && <p className="text-sm text-destructive">{jsonError}</p>}
      </div>
    );
  }

  // Visual Mode
  const rules = value?.rules || [];
  const logic = value?.logic || 'AND';

  return (
    <div className="space-y-4 border rounded-md p-4">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          <Label>Match Logic:</Label>
          <Select
            value={logic}
            onValueChange={(v) => updateLogic(v as 'AND' | 'OR')}
            disabled={disabled}
          >
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="AND">AND</SelectItem>
              <SelectItem value="OR">OR</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => handleModeChange('json')}
          className="h-8"
        >
          <Code className="w-4 h-4 mr-2" />
          Switch to JSON
        </Button>
      </div>

      <div className="space-y-3">
        {rules.map((rule, index) => {
          const valueType = getValueType(rule.value);
          // For display in input, stringify complex types
          const displayValue = 
            typeof rule.value === 'object' 
              ? JSON.stringify(rule.value) 
              : String(rule.value ?? '');

          return (
            <div key={index} className="flex gap-2 items-start p-2 bg-muted/30 rounded-md">
              <div className="grid gap-2 flex-1 sm:grid-cols-12">
                {/* Field */}
                <div className="sm:col-span-3">
                  <Input
                    placeholder="Field (e.g. model)"
                    value={rule.field}
                    onChange={(e) => updateRule(index, { field: e.target.value })}
                    disabled={disabled}
                    className="h-9"
                  />
                </div>

                {/* Operator */}
                <div className="sm:col-span-3">
                  <Select
                    value={rule.operator}
                    onValueChange={(v) => {
                      const newOp = v as RuleOperator;
                      // Reset value to appropriate default if operator changes
                      let newValue = rule.value;
                      if (newOp === 'exists') newValue = true;
                      else if ((newOp === 'in' || newOp === 'not_in') && !Array.isArray(newValue)) newValue = [];
                      
                      updateRule(index, { operator: newOp, value: newValue });
                    }}
                    disabled={disabled}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OPERATORS.map((op) => (
                        <SelectItem key={op.value} value={op.value}>
                          {op.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Value Input */}
                <div className="sm:col-span-6 flex gap-2">
                  {rule.operator === 'exists' ? (
                    <Select
                      value={String(!!rule.value)}
                      onValueChange={(v) => updateRule(index, { value: v === 'true' })}
                      disabled={disabled}
                    >
                      <SelectTrigger className="flex-1 h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="true">True (Must Exist)</SelectItem>
                        <SelectItem value="false">False (Must Not Exist)</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <>
                      <Input
                        placeholder="Value"
                        value={displayValue}
                        onChange={(e) => {
                          const val = e.target.value;
                          updateRule(index, { value: parseValue(val, valueType) });
                        }}
                        disabled={disabled}
                        className="flex-1 h-9"
                      />
                      <Select
                        value={valueType}
                        onValueChange={(t) => {
                          const type = t as ValueType;
                          // Try to convert current value to new type
                          updateRule(index, { value: parseValue(displayValue, type) });
                        }}
                        disabled={disabled}
                      >
                        <SelectTrigger className="w-[85px] h-9 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="string">String</SelectItem>
                          <SelectItem value="number">Num</SelectItem>
                          <SelectItem value="boolean">Bool</SelectItem>
                          <SelectItem value="json">JSON</SelectItem>
                        </SelectContent>
                      </Select>
                    </>
                  )}
                </div>
              </div>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeRule(index)}
                disabled={disabled}
                className="h-9 w-9 text-destructive hover:text-destructive/90"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          );
        })}

        {rules.length === 0 && (
          <div className="text-center py-4 text-sm text-muted-foreground border border-dashed rounded-md">
            No rules defined.
          </div>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addRule}
          disabled={disabled}
          className="w-full"
        >
          <Plus className="w-4 h-4 mr-2" /> Add Rule
        </Button>
      </div>
    </div>
  );
}
