import pdfplumber
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging
from dataclasses import asdict
from collections import defaultdict

from .models import PolicyInstrument, PolicyRequirement, BudgetLevel, ImpactHorizon

logger = logging.getLogger(__name__)

class EnhancedPDFExtractor:
    """Advanced extractor that handles real PDF structure from Agricultural Policy Toolkit"""
    
    def __init__(self, use_pdfminer: bool = False):
        self.use_pdfminer = use_pdfminer
        self.section_indicators = {
            'instrument': ['instrument', 'policy instrument', 'scheme', 'program'],
            'description': ['description'],
            'requirements': ['requirements', 'requirement', 'needs'],
            'negative_effects': ['possible negative effects', 'negative effects', 'risks'],
            'policy_objectives': ['policy objective', 'policy objectives', 'objectives', 'goals'],
            'implementation': ['implementation level', 'implementation', 'administrative level'],
            'budget': ['required budget', 'budget required', 'cost', 'financial'],
            'impact': ['impact horizon', 'time horizon', 'timeframe'],
            'ministries': ['ministries involved', 'responsible ministries', 'government departments'],
            'trade': ['trade impact', 'trade implications', 'trade effects'],
            'sdg': ['relevant sdg', 'sustainable development goals', 'sdg']
        }
    
    def extract_from_pdf(self, pdf_path: str) -> Optional[PolicyInstrument]:
        """Extract policy instrument from PDF with enhanced parsing"""
        try:
            # Extract text with better structure preservation
            text = self._extract_structured_text(pdf_path)
            
            if not text or len(text) < 200:
                logger.error(f"PDF too short or empty: {pdf_path}")
                return None
            
            # Save extracted text for debugging
            self._save_debug_text(pdf_path, text)
            
            # Parse the document structure
            parsed_data = self._parse_document_structure(text)
            
            # Extract metadata
            metadata = self._extract_metadata(text, pdf_path)
            
            # Build the instrument
            instrument = self._build_instrument(parsed_data, metadata, pdf_path)
            
            return instrument
            
        except Exception as e:
            logger.error(f"Error extracting from PDF {pdf_path}: {e}", exc_info=True)
            return None
    
    def _extract_structured_text(self, pdf_path: str) -> str:
        """Extract text with structure preservation"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = []
                
                for page_num, page in enumerate(pdf.pages):
                    # Extract text with layout preservation
                    page_text = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=2,
                        keep_blank_chars=False,
                        use_text_flow=False
                    )
                    
                    if page_text:
                        # Add page marker for structure
                        all_text.append(f"\n--- PAGE {page_num + 1} ---\n{page_text}")
                
                return "\n".join(all_text)
                
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            # Fallback to simple extraction
            with pdfplumber.open(pdf_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
    
    def _save_debug_text(self, pdf_path: str, text: str):
        """Save extracted text for debugging"""
        debug_path = Path("logs/debug_extractions") / f"{Path(pdf_path).stem}_raw.txt"
        debug_path.parent.mkdir(exist_ok=True)
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.debug(f"Saved debug text to {debug_path}")
    
    def _parse_document_structure(self, text: str) -> Dict[str, Any]:
        """Parse the document into structured sections"""
        lines = text.split('\n')
        parsed = defaultdict(str)
        current_section = None
        
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean:
                continue
            
            # Check if this line starts a new section
            section_match = self._identify_section(line_clean.lower())
            if section_match:
                current_section = section_match
                # Skip the section header line
                continue
            
            # Add content to current section
            if current_section:
                parsed[current_section] += line_clean + "\n"
            else:
                # If no section identified yet, assume it's the instrument name or description
                if not parsed['instrument'] and len(line_clean) < 100:
                    parsed['instrument'] = line_clean
                else:
                    parsed['description'] += line_clean + "\n"
        
        # Clean up the parsed sections
        for key in parsed:
            parsed[key] = parsed[key].strip()
        
        return parsed
    
    def _identify_section(self, line: str) -> Optional[str]:
        """Identify which section this line belongs to"""
        line_lower = line.lower()
        
        for section, indicators in self.section_indicators.items():
            for indicator in indicators:
                if indicator in line_lower:
                    return section
        
        # Special case for numbered objectives
        if re.match(r'^\d+\.\s', line_lower) or 'objective' in line_lower:
            return 'policy_objectives'
        
        # Special case for bullet points
        if line_lower.startswith(('- ', '• ', '* ', '— ')):
            if 'ministry' in line_lower or 'department' in line_lower:
                return 'ministries'
            elif 'budget' in line_lower or 'cost' in line_lower:
                return 'budget'
            elif 'impact' in line_lower or 'horizon' in line_lower:
                return 'impact'
        
        return None
    
    def _extract_metadata(self, text: str, pdf_path: str) -> Dict[str, str]:
        """Extract metadata from text"""
        metadata = {
            'url': '',
            'last_edited': '',
            'categories': [],
            'sectors': []
        }
        
        # Extract URL - look for agripolicykit.net URLs
        url_pattern = r'https?://agripolicykit\.net/[^\s)\]]+'
        urls = re.findall(url_pattern, text)
        if urls:
            metadata['url'] = urls[0].strip()
            # Clean URL
            metadata['url'] = re.sub(r'[)>\]].*$', '', metadata['url'])
        
        # Extract last edited date
        date_pattern = r'last edited on (.+?)(?:\||\n|$)'
        date_match = re.search(date_pattern, text, re.IGNORECASE)
        if date_match:
            metadata['last_edited'] = date_match.group(1).strip()
        
        # Extract from filename
        filename = Path(pdf_path).stem
        if 'afforestation' in filename.lower():
            metadata['categories'] = ['environment', 'forestry']
            metadata['sectors'] = ['forestry', 'environment']
        elif 'insurance' in filename.lower():
            metadata['categories'] = ['insurance', 'social protection']
            metadata['sectors'] = ['agriculture', 'insurance']
        
        return metadata
    
    def _build_instrument(self, parsed: Dict[str, str], metadata: Dict, pdf_path: str) -> PolicyInstrument:
        """Build PolicyInstrument from parsed data"""
        
        # Extract instrument name
        instrument_name = parsed.get('instrument', '')
        if not instrument_name:
            # Try to extract from first few lines of description
            desc_lines = parsed.get('description', '').split('\n')
            for line in desc_lines[:3]:
                if line and len(line) < 100:
                    instrument_name = line
                    break
        
        if not instrument_name:
            # Fallback to filename
            filename = Path(pdf_path).stem
            instrument_name = filename.replace('AgripolicyKit_', '').replace('AgripolicyKit ', '').replace('_', ' ')
        
        # Parse requirements
        requirements = self._parse_requirements_enhanced(parsed.get('requirements', ''))
        
        # Parse policy objectives
        policy_objectives = self._parse_policy_objectives_enhanced(parsed.get('policy_objectives', ''))
        
        # Parse ministries
        ministries = self._parse_ministries_enhanced(parsed.get('ministries', ''))
        
        # Parse budget
        budget = self._parse_budget_enhanced(parsed.get('budget', ''))
        
        # Parse impact horizon
        impact_horizon = self._parse_impact_horizon_enhanced(parsed.get('impact', ''))
        
        # Generate ID
        url = metadata.get('url', '')
        instrument_id = PolicyInstrument.generate_id(instrument_name, url)
        
        # Build instrument
        instrument = PolicyInstrument(
            instrument_id=instrument_id,
            instrument_name=instrument_name.strip(),
            description=parsed.get('description', '').strip(),
            url=url,
            requirements=requirements,
            possible_negative_effects=self._parse_list_enhanced(parsed.get('negative_effects', '')),
            policy_objectives=policy_objectives,
            implementation_level=self._parse_implementation_enhanced(parsed.get('implementation', '')),
            required_budget=budget,
            impact_horizon=impact_horizon,
            ministries_involved=ministries,
            trade_impact=self._extract_trade_impact(parsed.get('trade', '')),
            relevant_sdg=self._extract_sdg(parsed.get('sdg', '')),
            last_edited=metadata.get('last_edited'),
            categories=metadata.get('categories', []),
            sectors=metadata.get('sectors', []),
            source_file=pdf_path,
            confidence_score=self._calculate_confidence_enhanced(parsed)
        )
        
        return instrument
    
    def _parse_requirements_enhanced(self, text: str) -> PolicyRequirement:
        """Enhanced requirements parsing"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return PolicyRequirement(main_requirement="", sub_requirements=[])
        
        main_requirement = lines[0]
        sub_requirements = []
        
        for line in lines[1:]:
            # Look for indented or bullet points
            if line.startswith(('- ', '• ', '* ', '— ', '  ', '\t')):
                clean_line = re.sub(r'^[-\*•—\s]+', '', line)
                if clean_line:
                    sub_requirements.append(clean_line)
            elif len(line) > 20:  # Another requirement
                sub_requirements.append(line)
        
        return PolicyRequirement(
            main_requirement=main_requirement,
            sub_requirements=sub_requirements,
            category=self._categorize_requirement(main_requirement)
        )
    
    def _parse_policy_objectives_enhanced(self, text: str) -> List[str]:
        """Enhanced policy objectives parsing"""
        objectives = []
        
        # Split by lines and look for numbered items
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for numbered objectives (1., 2., etc.)
            match = re.match(r'^(\d+)[\.\)]\s*(.+)$', line)
            if match:
                objectives.append(match.group(2).strip())
            elif line.startswith(('- ', '• ', '* ', '— ')):
                # Bullet points
                clean_line = re.sub(r'^[-\*•—\s]+', '', line)
                if clean_line:
                    objectives.append(clean_line)
            elif 'objective' in line.lower() and len(line) < 200:
                # Might be an objective without numbering
                objectives.append(line)
        
        # If no structured objectives found, try to extract from text
        if not objectives and text:
            # Look for sentences that might be objectives
            sentences = re.split(r'[.!?]\s+', text)
            for sentence in sentences:
                if (len(sentence) > 20 and len(sentence) < 200 and 
                    any(word in sentence.lower() for word in ['improve', 'increase', 'reduce', 'enhance', 'promote', 'support'])):
                    objectives.append(sentence.strip())
        
        return objectives
    
    def _parse_ministries_enhanced(self, text: str) -> List[str]:
        """Enhanced ministries parsing"""
        ministries = []
        
        # Common ministry patterns
        ministry_patterns = [
            r'(?:Ministry|Department|Agency)\s+of\s+([A-Za-z\s&]+)',
            r'([A-Za-z\s&]+)\s+(?:Ministry|Department|Agency)'
        ]
        
        # First try pattern matching
        for pattern in ministry_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            ministries.extend([m.strip() for m in matches])
        
        # If no patterns matched, try line-based extraction
        if not ministries:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for common ministry keywords
                if any(keyword in line.lower() for keyword in ['agriculture', 'environment', 'health', 'finance', 'trade', 'labour']):
                    # Clean the line
                    clean_line = re.sub(r'^[-\*•—\s]+', '', line)
                    clean_line = re.sub(r'[.,;]$', '', clean_line)
                    if clean_line:
                        ministries.append(clean_line)
        
        return list(set(ministries))  # Remove duplicates
    
    def _parse_budget_enhanced(self, text: str) -> BudgetLevel:
        """Enhanced budget parsing"""
        text_lower = text.lower()
        
        budget_keywords = {
            BudgetLevel.LOW: ['low', 'small', 'minimal', '($)', 'affordable'],
            BudgetLevel.MEDIUM: ['medium', 'moderate', 'reasonable', '($$)', 'average'],
            BudgetLevel.HIGH: ['high', 'large', 'significant', '($$$)', 'substantial'],
            BudgetLevel.VERY_HIGH: ['very high', 'very large', 'extensive', '($$$$)']
        }
        
        for level, keywords in budget_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return level
        
        # Default to medium
        return BudgetLevel.MEDIUM
    
    def _parse_impact_horizon_enhanced(self, text: str) -> List[ImpactHorizon]:
        """Enhanced impact horizon parsing"""
        horizons = []
        text_lower = text.lower()
        
        horizon_keywords = {
            ImpactHorizon.SHORT: ['short', 'immediate', 'near-term', '<1 year', '0-1'],
            ImpactHorizon.MEDIUM: ['medium', 'mid-term', 'medium-term', '1-5', '2-5'],
            ImpactHorizon.LONG: ['long', 'long-term', 'sustained', '5+', '5-10'],
            ImpactHorizon.VERY_LONG: ['very long', 'permanent', 'generational', '10+', '10+ years']
        }
        
        for level, keywords in horizon_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    horizons.append(level)
        
        # Default if none found
        if not horizons:
            horizons.append(ImpactHorizon.MEDIUM)
        
        return list(set(horizons))
    
    def _parse_list_enhanced(self, text: str) -> List[str]:
        """Enhanced list parsing"""
        items = []
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove bullet points and numbering
            clean_line = re.sub(r'^(\d+[\.\)]|[-\*•—])\s*', '', line)
            if clean_line:
                items.append(clean_line)
        
        return items
    
    def _parse_implementation_enhanced(self, text: str) -> List[str]:
        """Enhanced implementation level parsing"""
        levels = []
        
        # Common implementation levels
        common_levels = [
            'local', 'regional', 'national', 'international',
            'municipal', 'provincial', 'state', 'federal',
            'community', 'district', 'county'
        ]
        
        text_lower = text.lower()
        for level in common_levels:
            if level in text_lower:
                levels.append(level.capitalize())
        
        # Extract from text if no common levels found
        if not levels:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) < 100:
                    levels.append(line)
        
        return levels
    
    def _extract_trade_impact(self, text: str) -> str:
        """Extract trade impact"""
        if not text:
            return ""
        
        text_lower = text.lower()
        
        if 'not distorting' in text_lower:
            return "Not distorting"
        elif 'positive' in text_lower or 'beneficial' in text_lower:
            return "Positive"
        elif 'negative' in text_lower or 'harmful' in text_lower:
            return "Negative"
        elif 'neutral' in text_lower or 'no impact' in text_lower:
            return "Neutral"
        else:
            # Return the first sentence
            sentences = re.split(r'[.!?]', text)
            if sentences:
                return sentences[0].strip()
            return text.strip()[:100]
    
    def _extract_sdg(self, text: str) -> str:
        """Extract relevant SDG"""
        if not text:
            return ""
        
        # Look for SDG numbers
        sdg_pattern = r'SDG\s*(\d+)'
        match = re.search(sdg_pattern, text, re.IGNORECASE)
        if match:
            return f"SDG {match.group(1)}"
        
        # Look for SDG-related text
        sdg_keywords = ['sustainable development', 'sdg', 'goal']
        for keyword in sdg_keywords:
            if keyword in text.lower():
                # Extract relevant part
                sentences = re.split(r'[.!?]', text)
                for sentence in sentences:
                    if keyword in sentence.lower():
                        return sentence.strip()[:100]
        
        return text.strip()[:50]
    
    def _categorize_requirement(self, requirement: str) -> str:
        """Categorize requirements"""
        req_lower = requirement.lower()
        
        categories = {
            'administrative': ['administration', 'monitoring', 'system', 'capacity', 'management'],
            'technical': ['technical', 'technology', 'infrastructure', 'equipment', 'tools'],
            'financial': ['financial', 'funding', 'budget', 'investment', 'cost', 'money'],
            'legal': ['legal', 'regulatory', 'legislation', 'policy', 'law', 'regulation'],
            'human': ['human', 'staff', 'personnel', 'expertise', 'training', 'capacity building'],
            'institutional': ['institutional', 'organization', 'agency', 'institution', 'body']
        }
        
        for category, keywords in categories.items():
            if any(keyword in req_lower for keyword in keywords):
                return category
        
        return 'general'
    
    def _calculate_confidence_enhanced(self, parsed: Dict[str, str]) -> float:
        """Calculate confidence based on extracted data"""
        scores = []
        
        # Instrument name
        if parsed.get('instrument') and len(parsed['instrument']) > 5:
            scores.append(1.0)
        else:
            scores.append(0.2)
        
        # Description
        if parsed.get('description') and len(parsed['description']) > 100:
            scores.append(1.0)
        else:
            scores.append(0.3)
        
        # Policy objectives
        if parsed.get('policy_objectives'):
            scores.append(0.8)
        else:
            scores.append(0.1)
        
        # Ministries
        if parsed.get('ministries'):
            scores.append(0.7)
        else:
            scores.append(0.1)
        
        # Budget
        if parsed.get('budget'):
            scores.append(0.6)
        else:
            scores.append(0.3)
        
        # Average the scores
        return round(sum(scores) / len(scores), 2)

class BatchEnhancedExtractor:
    """Batch processor using enhanced extractor"""
    
    def __init__(self, extractor: EnhancedPDFExtractor = None):
        self.extractor = extractor or EnhancedPDFExtractor()
        self.instruments = []
        self.failed_files = []
    
    def process_file(self, pdf_path: str) -> Optional[PolicyInstrument]:
        """Process a single PDF file"""
        try:
            logger.info(f"Processing: {pdf_path}")
            instrument = self.extractor.extract_from_pdf(pdf_path)
            
            if instrument and self._validate_instrument(instrument):
                self.instruments.append(instrument)
                logger.info(f"✅ Success: {instrument.instrument_name} (confidence: {instrument.confidence_score})")
                return instrument
            else:
                self.failed_files.append((pdf_path, "Extraction failed or validation failed"))
                logger.warning(f"⚠️ Failed: {pdf_path}")
                return None
                
        except Exception as e:
            self.failed_files.append((pdf_path, str(e)))
            logger.error(f"❌ Error: {pdf_path} - {e}")
            return None
    
    def process_directory(self, directory: str) -> List[PolicyInstrument]:
        """Process all PDFs in directory"""
        dir_path = Path(directory)
        pdf_files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.PDF"))
        
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\rProcessing {i}/{len(pdf_files)}: {pdf_file.name[:30]:30s}", end="")
            self.process_file(str(pdf_file))
        
        print()  # New line
        
        logger.info(f"Successfully processed {len(self.instruments)} files")
        logger.info(f"Failed to process {len(self.failed_files)} files")
        
        return self.instruments
    
    def save_results(self, output_dir: str = "data/processed"):
        """Save all results"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save instruments as JSON
        json_path = output_path / "enhanced_instruments.json"
        instruments_dict = [instrument.to_dict() for instrument in self.instruments]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(instruments_dict, f, indent=2, ensure_ascii=False)
        
        # Save as JSONL for vector storage
        jsonl_path = output_path / "enhanced_instruments.jsonl"
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for instrument in self.instruments:
                f.write(json.dumps(instrument.to_dict(), ensure_ascii=False) + '\n')
        
        # Save statistics
        stats = self._generate_statistics()
        stats_path = output_path / "enhanced_statistics.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Save failure log
        if self.failed_files:
            failures_path = output_path / "enhanced_failures.json"
            failures = [{"file": str(f), "error": e} for f, e in self.failed_files]
            with open(failures_path, 'w') as f:
                json.dump(failures, f, indent=2)
        
        return {
            "json": str(json_path),
            "jsonl": str(jsonl_path),
            "stats": str(stats_path),
            "instruments": len(self.instruments),
            "failures": len(self.failed_files)
        }
    
    def _validate_instrument(self, instrument: PolicyInstrument) -> bool:
        """Validate extracted instrument"""
        if not instrument.instrument_name or instrument.instrument_name.strip() == "":
            return False
        
        if len(instrument.description) < 50:
            logger.warning(f"Short description for {instrument.instrument_name}")
        
        if instrument.confidence_score < 0.3:
            logger.warning(f"Low confidence for {instrument.instrument_name}")
        
        return True
    
    def _generate_statistics(self) -> Dict:
        """Generate statistics about extraction"""
        stats = {
            "total_processed": len(self.instruments) + len(self.failed_files),
            "successful": len(self.instruments),
            "failed": len(self.failed_files),
            "success_rate": len(self.instruments) / (len(self.instruments) + len(self.failed_files)) if self.instruments or self.failed_files else 0,
            "confidence_distribution": defaultdict(int),
            "instruments_by_category": defaultdict(int)
        }
        
        if self.instruments:
            conf_scores = [i.confidence_score for i in self.instruments]
            stats["average_confidence"] = round(sum(conf_scores) / len(conf_scores), 2)
            stats["min_confidence"] = round(min(conf_scores), 2)
            stats["max_confidence"] = round(max(conf_scores), 2)
            
            # Distribution
            for score in conf_scores:
                if score >= 0.8:
                    stats["confidence_distribution"]["high"] += 1
                elif score >= 0.6:
                    stats["confidence_distribution"]["medium"] += 1
                else:
                    stats["confidence_distribution"]["low"] += 1
            
            # Categories
            for instrument in self.instruments:
                for category in instrument.categories:
                    stats["instruments_by_category"][category] += 1
        
        return stats