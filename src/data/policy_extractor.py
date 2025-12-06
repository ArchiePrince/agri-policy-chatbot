import re
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging
from dataclasses import asdict

from .models import PolicyInstrument, PolicyRequirement, BudgetLevel, ImpactHorizon

logger = logging.getLogger(__name__)

class PolicyInstrumentExtractor:
    """Specialized extractor for Agricultural Policy Toolkit instruments"""
    
    # Regex patterns for different sections
    SECTION_PATTERNS = {
        'instrument_name': r'# Instrument\s*\n# (.+)',
        'description': r'## Description\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'requirements': r'## Requirements\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'negative_effects': r'# Possible Negative Effects\s*\n(.*?)(?=\n# |\n## |\n---|$)',
        'policy_objectives': r'## Policy Objective\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'implementation_level': r'## Implementation Level\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'required_budget': r'## Required Budget\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'impact_horizon': r'## Impact Horizon\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'ministries_involved': r'# Ministries Involved\s*\n(.*?)(?=\n# |\n## |\n---|$)',
        'trade_impact': r'## Trade Impact\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
        'relevant_sdg': r'## Relevant SDG\s*\n(.*?)(?=\n## |\n### |\n# |\n---|$)',
    }
    
    # Regex for metadata
    METADATA_PATTERNS = {
        'last_edited': r'This page was last edited on (.+?)(?=\s*\|)',
        'url': r'https://agripolicykit\.net/en/instruments/[^\s]+'
    }
    
    def __init__(self):
        self.compiled_patterns = {
            key: re.compile(pattern, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            for key, pattern in self.SECTION_PATTERNS.items()
        }
        self.metadata_patterns = {
            key: re.compile(pattern, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            for key, pattern in self.METADATA_PATTERNS.items()
        }
    
    def extract_from_text(self, text: str, source_file: str = None) -> PolicyInstrument:
        """Extract policy instrument from text"""
        
        # Clean the text
        cleaned_text = self._clean_text(text)
        
        # Extract all sections
        sections = self._extract_sections(cleaned_text)
        
        # Extract metadata
        metadata = self._extract_metadata(cleaned_text)
        
        # Parse requirements hierarchy
        requirements = self._parse_requirements(sections.get('requirements', ''))
        
        # Parse policy objectives
        policy_objectives = self._parse_policy_objectives(sections.get('policy_objectives', ''))
        
        # Parse implementation level
        implementation_level = self._parse_implementation_level(sections.get('implementation_level', ''))
        
        # Parse ministries
        ministries_involved = self._parse_ministries(sections.get('ministries_involved', ''))
        
        # Parse budget level
        required_budget = self._parse_budget_level(sections.get('required_budget', ''))
        
        # Parse impact horizon
        impact_horizon = self._parse_impact_horizon(sections.get('impact_horizon', ''))
        
        # Get URL
        url = metadata.get('url') or self._extract_url(cleaned_text)
        
        # Generate ID
        instrument_id = PolicyInstrument.generate_id(
            sections.get('instrument_name', 'Unknown'),
            url
        )
        
        # Create policy instrument
        instrument = PolicyInstrument(
            instrument_id=instrument_id,
            instrument_name=sections.get('instrument_name', 'Unknown Instrument'),
            description=self._clean_description(sections.get('description', '')),
            url=url,
            requirements=requirements,
            possible_negative_effects=self._parse_list_items(sections.get('negative_effects', '')),
            policy_objectives=policy_objectives,
            implementation_level=implementation_level,
            required_budget=required_budget,
            impact_horizon=impact_horizon,
            ministries_involved=ministries_involved,
            trade_impact=sections.get('trade_impact', '').strip(),
            relevant_sdg=sections.get('relevant_sdg', '').strip(),
            last_edited=metadata.get('last_edited'),
            source_file=source_file,
            categories=self._extract_categories(cleaned_text),
            keywords=self._extract_keywords(sections.get('description', ''))
        )
        
        return instrument
    
    def _clean_text(self, text: str) -> str:
        """Clean the input text"""
        # Remove page markers
        text = re.sub(r'===== Page \d+ =====', '', text)
        
        # Remove cookie notices
        text = re.sub(r'This site uses cookies.*?Close', '', text, flags=re.DOTALL)
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        # Remove trailing whitespace
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        
        return text.strip()
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract all sections using regex patterns"""
        sections = {}
        
        for section_name, pattern in self.compiled_patterns.items():
            match = pattern.search(text)
            if match:
                if section_name == 'instrument_name':
                    sections[section_name] = match.group(1).strip()
                else:
                    sections[section_name] = match.group(1).strip()
            else:
                sections[section_name] = ''
                logger.debug(f"Section '{section_name}' not found")
        
        return sections
    
    def _extract_metadata(self, text: str) -> Dict[str, str]:
        """Extract metadata from text"""
        metadata = {}
        
        for meta_name, pattern in self.metadata_patterns.items():
            match = pattern.search(text)
            if match:
                metadata[meta_name] = match.group(1).strip() if match.groups() else match.group(0).strip()
        
        return metadata
    
    def _extract_url(self, text: str) -> str:
        """Extract URL from text"""
        url_pattern = r'https://agripolicykit\.net/en/[^\s]+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else ""
    
    def _parse_requirements(self, requirements_text: str) -> PolicyRequirement:
        """Parse hierarchical requirements"""
        lines = requirements_text.strip().split('\n')
        
        if not lines or not lines[0].strip():
            return PolicyRequirement(main_requirement="", sub_requirements=[])
        
        main_requirement = lines[0].strip()
        sub_requirements = []
        
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('###') or line.startswith('####'):
                # Remove markdown markers and clean
                clean_line = re.sub(r'^#+\s*', '', line).strip()
                if clean_line:
                    sub_requirements.append(clean_line)
        
        return PolicyRequirement(
            main_requirement=main_requirement,
            sub_requirements=sub_requirements,
            category=self._categorize_requirement(main_requirement)
        )
    
    def _parse_policy_objectives(self, objectives_text: str) -> List[str]:
        """Parse numbered policy objectives"""
        objectives = []
        
        # Split by numbered items
        lines = objectives_text.strip().split('\n')
        
        for line in lines:
            # Match numbered items (1., 2., etc.) or bullet points
            line = line.strip()
            if line:
                # Remove numbering and bullet points
                clean_line = re.sub(r'^\d+\.\s*|^-\s*|^\*\s*', '', line)
                if clean_line:
                    objectives.append(clean_line.strip())
        
        return objectives
    
    def _parse_implementation_level(self, implementation_text: str) -> List[str]:
        """Parse implementation level"""
        levels = []
        
        lines = implementation_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-'):
                clean_line = line[1:].strip()
                if clean_line:
                    levels.append(clean_line)
            elif line:
                levels.append(line)
        
        return levels
    
    def _parse_ministries(self, ministries_text: str) -> List[str]:
        """Parse ministries involved"""
        ministries = []
        
        # Split by newline and clean
        lines = ministries_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line:
                # Handle comma-separated ministries
                if ',' in line:
                    ministries.extend([m.strip() for m in line.split(',')])
                else:
                    ministries.append(line)
        
        return ministries
    
    def _parse_budget_level(self, budget_text: str) -> BudgetLevel:
        """Parse required budget level"""
        budget_text = budget_text.strip().lower()
        
        # Map text to enum
        budget_mapping = {
            'low': BudgetLevel.LOW,
            'low ($)': BudgetLevel.LOW,
            'medium': BudgetLevel.MEDIUM,
            'medium ($$)': BudgetLevel.MEDIUM,
            'high': BudgetLevel.HIGH,
            'high ($$$)': BudgetLevel.HIGH,
            'very high': BudgetLevel.VERY_HIGH,
            'very high ($$$$)': BudgetLevel.VERY_HIGH
        }
        
        for key, value in budget_mapping.items():
            if key in budget_text:
                return value
        
        # Default to medium if not found
        return BudgetLevel.MEDIUM
    
    def _parse_impact_horizon(self, horizon_text: str) -> List[ImpactHorizon]:
        """Parse impact horizon"""
        horizons = []
        horizon_text = horizon_text.strip().lower()
        
        horizon_mapping = {
            'short': ImpactHorizon.SHORT,
            'medium': ImpactHorizon.MEDIUM,
            'long': ImpactHorizon.LONG,
            'very long': ImpactHorizon.VERY_LONG
        }
        
        for key, value in horizon_mapping.items():
            if key in horizon_text:
                horizons.append(value)
        
        # If no horizons found, add medium as default
        if not horizons:
            horizons.append(ImpactHorizon.MEDIUM)
        
        return horizons
    
    def _parse_list_items(self, text: str) -> List[str]:
        """Parse bullet list items"""
        items = []
        
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line:
                # Remove bullet points
                clean_line = re.sub(r'^[•\-*]\s*', '', line)
                if clean_line:
                    items.append(clean_line)
        
        return items
    
    def _clean_description(self, description: str) -> str:
        """Clean description text"""
        # Remove markdown formatting
        description = re.sub(r'#+\s*', '', description)
        
        # Normalize whitespace
        description = re.sub(r'\s+', ' ', description)
        
        return description.strip()
    
    def _categorize_requirement(self, requirement: str) -> str:
        """Categorize requirements"""
        requirement_lower = requirement.lower()
        
        categories = {
            'administrative': ['administration', 'monitoring', 'system', 'capacity'],
            'technical': ['technical', 'technology', 'infrastructure'],
            'financial': ['financial', 'funding', 'budget', 'investment'],
            'legal': ['legal', 'regulatory', 'legislation', 'policy'],
            'human': ['human', 'staff', 'personnel', 'expertise'],
            'institutional': ['institutional', 'organization', 'agency']
        }
        
        for category, keywords in categories.items():
            if any(keyword in requirement_lower for keyword in keywords):
                return category
        
        return 'general'
    
    def _extract_categories(self, text: str) -> List[str]:
        """Extract categories from text"""
        categories = []
        text_lower = text.lower()
        
        # Look for instrument categories in URL or text
        if 'accident' in text_lower and 'insurance' in text_lower:
            categories.extend(['insurance', 'safety', 'social protection'])
        
        if 'statutory' in text_lower:
            categories.append('statutory')
        if 'cooperative' in text_lower:
            categories.append('cooperative')
        
        return categories
    
    def _extract_keywords(self, description: str) -> List[str]:
        """Extract keywords from description"""
        # Common stop words to exclude
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        # Extract meaningful words
        words = re.findall(r'\b[a-z]{3,}\b', description.lower())
        keywords = [word for word in words if word not in stop_words]
        
        # Count frequency and take top 10
        from collections import Counter
        word_counts = Counter(keywords)
        top_keywords = [word for word, count in word_counts.most_common(10)]
        
        return top_keywords

class BatchPolicyExtractor:
    """Batch processor for multiple policy documents"""
    
    def __init__(self, extractor: PolicyInstrumentExtractor = None):
        self.extractor = extractor or PolicyInstrumentExtractor()
        self.instruments = []
    
    def process_file(self, file_path: str) -> Optional[PolicyInstrument]:
        """Process a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            instrument = self.extractor.extract_from_text(content, file_path)
            
            # Validate extraction
            if self._validate_instrument(instrument):
                self.instruments.append(instrument)
                logger.info(f"✅ Processed: {instrument.instrument_name}")
                return instrument
            else:
                logger.warning(f"⚠️  Validation failed for: {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error processing {file_path}: {e}")
            return None
    
    def process_directory(self, directory: str, pattern: str = "*.txt") -> List[PolicyInstrument]:
        """Process all files in a directory"""
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory not found: {directory}")
            return []
        
        files = list(directory_path.glob(pattern))
        logger.info(f"Found {len(files)} files to process")
        
        for file_path in files:
            self.process_file(str(file_path))
        
        logger.info(f"Processed {len(self.instruments)} instruments successfully")
        return self.instruments
    
    def save_to_json(self, output_path: str, pretty: bool = True):
        """Save extracted instruments to JSON"""
        instruments_dict = [instrument.to_dict() for instrument in self.instruments]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(instruments_dict, f, indent=2, ensure_ascii=False)
            else:
                json.dump(instruments_dict, f, ensure_ascii=False)
        
        logger.info(f"Saved {len(instruments_dict)} instruments to {output_path}")
    
    def save_to_jsonl(self, output_path: str):
        """Save extracted instruments to JSONL (one per line)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for instrument in self.instruments:
                f.write(json.dumps(instrument.to_dict(), ensure_ascii=False) + '\n')
        
        logger.info(f"Saved {len(self.instruments)} instruments to {output_path}")
    
    def _validate_instrument(self, instrument: PolicyInstrument) -> bool:
        """Validate extracted instrument"""
        # Basic validation
        if not instrument.instrument_name or instrument.instrument_name == "Unknown Instrument":
            return False
        
        if not instrument.description or len(instrument.description) < 50:
            logger.warning(f"Short description for {instrument.instrument_name}")
            # Don't fail, just warn
        
        if not instrument.url:
            logger.warning(f"No URL for {instrument.instrument_name}")
        
        return True