"""
规则模型定义模块

定义规则引擎使用的数据结构。
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Rule:
    """
    规则定义
    
    单条规则，包含匹配字段、操作符和期望值。
    
    Attributes:
        field: 匹配字段路径（如 "model", "headers.x-priority", "body.temperature"）
        operator: 操作符（如 "eq", "gt", "contains"）
        value: 期望值
    """
    
    field: str
    operator: str
    value: Any
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rule":
        """从字典创建规则"""
        return cls(
            field=data.get("field", ""),
            operator=data.get("operator", "eq"),
            value=data.get("value"),
        )


@dataclass
class RuleSet:
    """
    规则集
    
    包含多条规则和逻辑运算符（AND/OR）。
    
    Attributes:
        rules: 规则列表
        logic: 逻辑运算符，"AND" 或 "OR"，默认 "AND"
    """
    
    rules: list[Rule] = field(default_factory=list)
    logic: str = "AND"  # "AND" 或 "OR"
    
    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> Optional["RuleSet"]:
        """
        从字典创建规则集
        
        Args:
            data: 规则集字典，格式如：
                {
                    "rules": [
                        {"field": "model", "operator": "eq", "value": "gpt-4"}
                    ],
                    "logic": "AND"
                }
        
        Returns:
            Optional[RuleSet]: 规则集，如果 data 为空则返回 None
        """
        if not data:
            return None
        
        rules_data = data.get("rules", [])
        rules = [Rule.from_dict(r) for r in rules_data]
        logic = data.get("logic", "AND").upper()
        
        return cls(rules=rules, logic=logic)
    
    def is_empty(self) -> bool:
        """检查规则集是否为空"""
        return len(self.rules) == 0


@dataclass
class CandidateProvider:
    """
    候选供应商
    
    规则引擎匹配后输出的候选供应商信息。
    
    Attributes:
        provider_id: 供应商 ID
        provider_name: 供应商名称
        base_url: 供应商基础 URL
        protocol: 供应商协议（openai/anthropic）
        api_key: 供应商 API Key
        target_model: 目标模型名（该供应商对应的实际模型）
        priority: 优先级（数值越小优先级越高）
        weight: 权重（用于加权选择）
    """
    
    provider_id: int
    provider_name: str
    base_url: str
    protocol: str
    api_key: Optional[str]
    target_model: str
    extra_headers: Optional[dict[str, str]] = None
    priority: int = 0
    weight: int = 1
