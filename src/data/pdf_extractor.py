import pdfplumber
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging
from dataclasses import asdict
import io
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

from .models import PolicyInstrument, PolicyRequirement, BudgetLevel, ImpactHorizon

logger = logging.getLogger(__name__)

class PDFPolicyExtractor:
    """Specialized extractor for Agricultural Policy Toolkit PDF instruments"""
    
    # Regex patterns for different sections
    SECTION_PATTERNS = {
        'instrument_name': r'#\s*Instrument\s*\n#\s*(.+)',
        'description': r'##\s*Description\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'requirements': r'##\s*Requirements\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'negative_effects': r'#\s*Possible Negative Effects\s*\n(.*?)(?=\n#\s*|\n##\s*|\n---|\Z)',
        'policy_objectives': r'##\s*Policy Objective\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'implementation_level': r'##\s*Implementation Level\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'required_budget': r'##\s*Required Budget\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'impact_horizon': r'##\s*Impact Horizon\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'ministries_involved': r'#\s*Ministries Involved\s*\n(.*?)(?=\n#\s*|\n##\s*|\n---|\Z)',
        'trade_impact': r'##\s*Trade Impact\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
        'relevant_sdg': r'##\s*Relevant SDG\s*\n(.*?)(?=\n##\s*|\n###\s*|\n#\s*|\n---|\Z)',
    }
    
    # Regex for metadata
    METADATA_PATTERNS = {
        'last_edited': r'This page was last edited on (.+?)(?=\s*\|)',
        'url': r'https://agripolicykit\.net/en/instruments/[^\s]+'
    }
    
    def __init__(self, use_pdfminer: bool = False):
        """
        Initialize PDF extractor
        
        Args:
            use_pdfminer: Use pdfminer for better layout preservation (slower but more accurate)
        """
        self.use_pdfminer = use_pdfminer
        self.compiled_patterns = {
            key: re.compile(pattern, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            for key, pattern in self.SECTION_PATTERNS.items()
        }
        self.metadata_patterns = {
            key: re.compile(pattern, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            for key, pattern in self.METADATA_PATTERNS.items()
        }
    
    def extract_from_pdf(self, pdf_path: str) -> Optional[PolicyInstrument]:
        """Extract policy instrument from PDF file"""
        try:
            # Extract text from PDF
            text = self._extract_pdf_text(pdf_path)
            
            if not text or len(text.strip()) < 100:
                logger.error(f"PDF appears empty or too short: {pdf_path}")
                return None
            
            # Clean the extracted text
            cleaned_text = self._clean_pdf_text(text)
            
            # Save extracted text for debugging
            debug_path = Path("logs") / f"{Path(pdf_path).stem}_extracted.txt"
            debug_path.parent.mkdir(exist_ok=True)
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
            logger.debug(f"Saved extracted text to {debug_path}")
            
            # Extract all sections
            sections = self._extract_sections(cleaned_text)
            
            # If instrument name not found, try alternative extraction
            if not sections.get('instrument_name') or sections['instrument_name'] == '':
                sections['instrument_name'] = self._extract_instrument_name_fallback(cleaned_text, pdf_path)
            
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
            url = metadata.get('url') or self._extract_url(cleaned_text) or self._guess_url_from_filename(pdf_path)
            
            # Generate ID
            instrument_name = sections.get('instrument_name', 'Unknown Instrument')
            instrument_id = PolicyInstrument.generate_id(instrument_name, url)
            
            # Create policy instrument
            instrument = PolicyInstrument(
                instrument_id=instrument_id,
                instrument_name=instrument_name,
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
                source_file=pdf_path,
                categories=self._extract_categories(cleaned_text),
                keywords=self._extract_keywords(sections.get('description', '')),
                confidence_score=self._calculate_confidence(sections)
            )
            
            return instrument
            
        except Exception as e:
            logger.error(f"Error extracting from PDF {pdf_path}: {e}")
            return None
    
    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using either pdfplumber or pdfminer"""
        try:
            if self.use_pdfminer:
                # Use pdfminer for better layout preservation
                laparams = LAParams(
                    line_margin=0.5,
                    word_margin=0.1,
                    char_margin=2.0,
                    boxes_flow=0.5
                )
                text = pdfminer_extract_text(pdf_path, laparams=laparams)
            else:
                # Use pdfplumber (faster, good for structured PDFs)
                with pdfplumber.open(pdf_path) as pdf:
                    text_parts = []
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    text = "\n".join(text_parts)
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            # Fallback: try PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(pdf_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e2:
                logger.error(f"PyPDF2 also failed: {e2}")
                return ""
    
    def _clean_pdf_text(self, text: str) -> str:
        """Clean extracted PDF text"""
        # Replace multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common PDF extraction issues
        text = re.sub(r'(?<=\w)-\s+(?=\w)', '', text)  # Remove hyphenation
        text = re.sub(r'\s*-\s*-\s*-\s*', '\n---\n', text)  # Fix separators
        text = re.sub(r'#\s+#', '#', text)  # Fix double # markers
        
        # Ensure proper section markers
        text = re.sub(r'(?<=\n)#(?=\w)', '\n# ', text)
        text = re.sub(r'(?<=\n)##(?=\w)', '\n## ', text)
        text = re.sub(r'(?<=\n)###(?=\w)', '\n### ', text)
        
        # Remove page numbers and headers/footers
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        
        # Remove extra whitespace
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
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
    
    def _extract_instrument_name_fallback(self, text: str, pdf_path: str) -> str:
        """Fallback method to extract instrument name"""
        # Try to find instrument name from first few lines
        lines = text.split('\n')[:10]
        
        for line in lines:
            if 'insurance' in line.lower() or 'scheme' in line.lower():
                return line.strip()
        
        # Try from filename
        filename = Path(pdf_path).stem
        # Remove common prefixes
        name = filename.replace('AgripolicyKit_', '').replace('AgripolicyKit ', '').replace('_', ' ').strip()
        if name:
            return name
        
        return "Unknown Instrument"
    
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
    
    def _guess_url_from_filename(self, pdf_path: str) -> str:
        """Guess URL from PDF filename"""
        filename = Path(pdf_path).stem.lower()
        
        # Common transformations
        filename = filename.replace('agripolicykit_', '').replace('agripolicykit ', '')
        filename = filename.replace('_', '-').replace(' ', '-')
        
        # Remove special characters
        filename = re.sub(r'[^a-z0-9\-]', '', filename)
        
        return f"https://agripolicykit.net/en/instruments/{filename}"
    
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
            'low($)': BudgetLevel.LOW,
            'medium': BudgetLevel.MEDIUM,
            'medium ($$)': BudgetLevel.MEDIUM,
            'medium($$)': BudgetLevel.MEDIUM,
            'high': BudgetLevel.HIGH,
            'high ($$$)': BudgetLevel.HIGH,
            'high($$$)': BudgetLevel.HIGH,
            'very high': BudgetLevel.VERY_HIGH,
            'very high ($$$$)': BudgetLevel.VERY_HIGH,
            'very high($$$$)': BudgetLevel.VERY_HIGH
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
        
        # Look for instrument categories
        category_keywords = {
            'insurance': ['insurance', 'scheme', 'coverage'],
            'subsidy': ['subsidy', 'grant', 'financial support'],
            'regulation': ['regulation', 'standard', 'compliance'],
            'training': ['training', 'education', 'capacity building'],
            'infrastructure': ['infrastructure', 'facility', 'equipment'],
            'research': ['research', 'development', 'innovation'],
            'safety': ['safety', 'accident', 'protection'],
            'environmental': ['environment', 'sustainable', 'conservation']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.append(category)
        
        return list(set(categories))  # Remove duplicates
    
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
    
    def _calculate_confidence(self, sections: Dict[str, str]) -> float:
        """Calculate confidence score based on extracted sections"""
        required_sections = ['instrument_name', 'description', 'policy_objectives']
        optional_sections = ['requirements', 'ministries_involved', 'required_budget']
        
        score = 0.0
        max_score = len(required_sections) + (len(optional_sections) * 0.5)
        
        # Check required sections
        for section in required_sections:
            if sections.get(section) and len(sections[section].strip()) > 10:
                score += 1.0
        
        # Check optional sections
        for section in optional_sections:
            if sections.get(section) and len(sections[section].strip()) > 5:
                score += 0.5
        
        # Normalize to 0-1 scale
        confidence = score / max_score if max_score > 0 else 0.0
        
        return round(confidence, 2)

class BatchPDFExtractor:
    """Batch processor for multiple PDF documents"""
    
    def __init__(self, extractor: PDFPolicyExtractor = None):
        self.extractor = extractor or PDFPolicyExtractor()
        self.instruments = []
        self.failed_files = []
    
    def process_file(self, pdf_path: str) -> Optional[PolicyInstrument]:
        """Process a single PDF file"""
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            instrument = self.extractor.extract_from_pdf(pdf_path)
            
            if instrument and self._validate_instrument(instrument):
                self.instruments.append(instrument)
                logger.info(f"✅ Successfully extracted: {instrument.instrument_name}")
                return instrument
            else:
                self.failed_files.append((pdf_path, "Validation failed or extraction returned None"))
                logger.warning(f"⚠️  Extraction failed for: {pdf_path}")
                return None
                
        except Exception as e:
            self.failed_files.append((pdf_path, str(e)))
            logger.error(f"❌ Error processing {pdf_path}: {e}")
            return None
    
    def process_directory(self, directory: str, pattern: str = "*.pdf") -> List[PolicyInstrument]:
        """Process all PDF files in a directory"""
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory not found: {directory}")
            return []
        
        files = list(directory_path.glob(pattern))
        logger.info(f"Found {len(files)} PDF files to process")
        
        for i, file_path in enumerate(files, 1):
            print(f"\rProcessing file {i}/{len(files)}...", end="")
            self.process_file(str(file_path))
        
        print()  # New line after progress
        
        logger.info(f"Processed {len(self.instruments)} instruments successfully")
        logger.info(f"Failed to process {len(self.failed_files)} files")
        
        # Save failure log
        if self.failed_files:
            self._save_failure_log()
        
        return self.instruments
    
    def save_to_json(self, output_path: str, pretty: bool = True):
        """Save extracted instruments to JSON"""
        instruments_dict = [instrument.to_dict() for instrument in self.instruments]
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(instruments_dict, f, indent=2, ensure_ascii=False)
            else:
                json.dump(instruments_dict, f, ensure_ascii=False)
        
        logger.info(f"Saved {len(instruments_dict)} instruments to {output_path}")
    
    def save_to_jsonl(self, output_path: str):
        """Save extracted instruments to JSONL (one per line)"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
        
        if instrument.confidence_score < 0.3:
            logger.warning(f"Low confidence ({instrument.confidence_score}) for {instrument.instrument_name}")
        
        return True
    
    def _save_failure_log(self):
        """Save log of failed extractions"""
        log_path = Path("logs") / "failed_extractions.json"
        log_path.parent.mkdir(exist_ok=True)
        
        failures = [{"file": file, "error": error} for file, error in self.failed_files]
        
        with open(log_path, 'w') as f:
            json.dump(failures, f, indent=2)
        
        logger.info(f"Saved failure log to {log_path}")
    
    def get_statistics(self) -> Dict:
        """Get extraction statistics"""
        return {
            "total_files_processed": len(self.instruments) + len(self.failed_files),
            "successful_extractions": len(self.instruments),
            "failed_extractions": len(self.failed_files),
            "success_rate": len(self.instruments) / (len(self.instruments) + len(self.failed_files)) if self.instruments or self.failed_files else 0,
            "average_confidence": sum(i.confidence_score for i in self.instruments) / len(self.instruments) if self.instruments else 0
        }