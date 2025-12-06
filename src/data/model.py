from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import hashlib
from datetime import datetime

class BudgetLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very high"

class ImpactHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_LONG = "very long"

class ImplementationLevel(str, Enum):
    LOCAL = "local"
    REGIONAL = "regional"
    NATIONAL = "national"
    INTERNATIONAL = "international"

@dataclass
class PolicyRequirement:
    """Hierarchical requirement structure"""
    main_requirement: str
    sub_requirements: List[str] = field(default_factory=list)
    category: Optional[str] = None
    
@dataclass
class PolicyDimension:
    """Individual policy dimension"""
    name: str
    values: List[str]
    description: Optional[str] = None
    
@dataclass
class PolicyInstrument:
    """Complete policy instrument model"""
    # Core identification
    instrument_id: str
    instrument_name: str
    description: str
    url: str
    
    # Requirements
    requirements: PolicyRequirement
    
    # Policy dimensions
    possible_negative_effects: List[str]
    policy_objectives: List[str]
    implementation_level: List[str]
    required_budget: BudgetLevel
    impact_horizon: List[ImpactHorizon]
    ministries_involved: List[str]
    trade_impact: str
    relevant_sdg: str
    
    # Metadata
    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    last_edited: Optional[str] = None
    regions: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)  # agriculture, fisheries, etc.
    
    # Processing info
    source_file: Optional[str] = None
    extraction_date: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "description": self.description,
            "url": self.url,
            "requirements": {
                "main_requirement": self.requirements.main_requirement,
                "sub_requirements": self.requirements.sub_requirements,
                "category": self.requirements.category
            },
            "possible_negative_effects": self.possible_negative_effects,
            "policy_objectives": self.policy_objectives,
            "implementation_level": self.implementation_level,
            "required_budget": self.required_budget.value if hasattr(self.required_budget, 'value') else self.required_budget,
            "impact_horizon": [h.value if hasattr(h, 'value') else h for h in self.impact_horizon],
            "ministries_involved": self.ministries_involved,
            "trade_impact": self.trade_impact,
            "relevant_sdg": self.relevant_sdg,
            "categories": self.categories,
            "keywords": self.keywords,
            "last_edited": self.last_edited,
            "regions": self.regions,
            "sectors": self.sectors,
            "metadata": {
                "source_file": self.source_file,
                "extraction_date": self.extraction_date,
                "confidence_score": self.confidence_score
            }
        }
    
    def generate_embedding_text(self) -> str:
        """Generate text for embedding/search"""
        sections = [
            f"Instrument: {self.instrument_name}",
            f"Description: {self.description}",
            f"Requirements: {self.requirements.main_requirement}",
            f"Policy Objectives: {', '.join(self.policy_objectives)}",
            f"Implementation: {', '.join(self.implementation_level)}",
            f"Ministries: {', '.join(self.ministries_involved)}",
            f"Trade Impact: {self.trade_impact}",
            f"SDG: {self.relevant_sdg}"
        ]
        return "\n".join(sections)
    
    @classmethod
    def generate_id(cls, instrument_name: str, url: str) -> str:
        """Generate unique ID for instrument"""
        unique_string = f"{instrument_name}_{url}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]