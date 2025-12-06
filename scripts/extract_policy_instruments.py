#!/usr/bin/env python3
"""
Extract policy instruments from Agricultural Policy Toolkit PDF documents
"""

import argparse
import logging
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.pdf_extractor import PDFPolicyExtractor, BatchPDFExtractor

def setup_logging(log_level: str = "INFO"):
    """Configure logging"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.FileHandler('logs/policy_extraction.log'),
            logging.StreamHandler()
        ]
    )

def extract_single_pdf(pdf_path: str, output_dir: str = "data/processed", use_pdfminer: bool = False) -> dict:
    """Extract single policy instrument from PDF"""
    extractor = PDFPolicyExtractor(use_pdfminer=use_pdfminer)
    
    print(f"📄 Processing PDF: {pdf_path}")
    
    try:
        instrument = extractor.extract_from_pdf(pdf_path)
        
        if not instrument:
            print(f"❌ Failed to extract instrument from {pdf_path}")
            return None
        
        # Save individual instrument
        output_path = Path(output_dir) / f"{instrument.instrument_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(instrument.to_dict(), f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Successfully extracted: {instrument.instrument_name}")
        print(f"   ID: {instrument.instrument_id}")
        print(f"   URL: {instrument.url}")
        print(f"   Confidence: {instrument.confidence_score}")
        print(f"   Saved to: {output_path}")
        
        # Print summary
        print(f"\n📊 Summary:")
        print(f"   Objectives: {len(instrument.policy_objectives)}")
        print(f"   Ministries: {', '.join(instrument.ministries_involved[:3])}{'...' if len(instrument.ministries_involved) > 3 else ''}")
        print(f"   Budget: {instrument.required_budget}")
        print(f"   Horizon: {', '.join([h.value for h in instrument.impact_horizon])}")
        print(f"   Categories: {', '.join(instrument.categories[:3])}{'...' if len(instrument.categories) > 3 else ''}")
        
        return instrument.to_dict()
        
    except Exception as e:
        print(f"❌ Error extracting from {pdf_path}: {e}")
        logging.error(f"Error extracting from {pdf_path}: {e}", exc_info=True)
        return None

def extract_batch_pdfs(input_dir: str, output_dir: str = "data/processed", use_pdfminer: bool = False) -> dict:
    """Extract all policy instruments from PDFs in a directory"""
    batch_extractor = BatchPDFExtractor(PDFPolicyExtractor(use_pdfminer=use_pdfminer))
    
    print(f"🔍 Processing directory: {input_dir}")
    
    # Process all PDF files
    instruments = batch_extractor.process_directory(input_dir, "*.pdf")
    
    if not instruments:
        print("❌ No instruments extracted")
        return None
    
    # Save to JSON
    json_path = Path(output_dir) / "policy_instruments.json"
    batch_extractor.save_to_json(str(json_path))
    
    # Save to JSONL for vector storage
    jsonl_path = Path(output_dir) / "policy_instruments.jsonl"
    batch_extractor.save_to_jsonl(str(jsonl_path))
    
    # Generate statistics
    stats = generate_statistics(instruments, batch_extractor.get_statistics())
    stats_path = Path(output_dir) / "extraction_statistics.json"
    
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n🎉 Batch extraction complete!")
    print(f"   Instruments extracted: {len(instruments)}")
    print(f"   Success rate: {batch_extractor.get_statistics()['success_rate']:.1%}")
    print(f"   JSON output: {json_path}")
    print(f"   JSONL output: {jsonl_path}")
    print(f"   Statistics: {stats_path}")
    
    # Show sample
    if instruments:
        print(f"\n📄 Sample instrument (first of {len(instruments)}):")
        sample = instruments[0].to_dict()
        # Don't print full description to keep output clean
        sample_without_desc = {k: v for k, v in sample.items() if k not in ['description', 'metadata']}
        print(json.dumps(sample_without_desc, indent=2))
    
    return {
        "instruments": [i.to_dict() for i in instruments],
        "statistics": stats,
        "output_files": {
            "json": str(json_path),
            "jsonl": str(jsonl_path),
            "stats": str(stats_path)
        }
    }

def generate_statistics(instruments, extraction_stats):
    """Generate extraction statistics"""
    stats = {
        'extraction': extraction_stats,
        'instruments': {
            'total': len(instruments),
            'by_budget': {},
            'by_impact_horizon': {},
            'by_category': {},
            'confidence_distribution': {
                'high': 0,
                'medium': 0,
                'low': 0
            }
        },
        'common_ministries': {},
        'common_objectives': {}
    }
    
    all_objectives = []
    all_ministries = []
    
    for instrument in instruments:
        # Budget distribution
        budget = instrument.required_budget.value if hasattr(instrument.required_budget, 'value') else instrument.required_budget
        stats['instruments']['by_budget'][budget] = stats['instruments']['by_budget'].get(budget, 0) + 1
        
        # Impact horizon
        for horizon in instrument.impact_horizon:
            horizon_val = horizon.value if hasattr(horizon, 'value') else horizon
            stats['instruments']['by_impact_horizon'][horizon_val] = stats['instruments']['by_impact_horizon'].get(horizon_val, 0) + 1
        
        # Categories
        for category in instrument.categories:
            stats['instruments']['by_category'][category] = stats['instruments']['by_category'].get(category, 0) + 1
        
        # Confidence distribution
        if instrument.confidence_score >= 0.7:
            stats['instruments']['confidence_distribution']['high'] += 1
        elif instrument.confidence_score >= 0.4:
            stats['instruments']['confidence_distribution']['medium'] += 1
        else:
            stats['instruments']['confidence_distribution']['low'] += 1
        
        # Ministries
        all_ministries.extend(instrument.ministries_involved)
        
        # Objectives
        all_objectives.extend(instrument.policy_objectives)
    
    # Count ministries
    from collections import Counter
    ministry_counts = Counter(all_ministries)
    stats['common_ministries'] = dict(ministry_counts.most_common(10))
    
    # Count objectives
    objective_counts = Counter(all_objectives)
    stats['common_objectives'] = dict(objective_counts.most_common(10))
    
    return stats

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Extract policy instruments from Agricultural Policy Toolkit PDF documents'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input PDF file or directory'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/processed',
        help='Output directory'
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['single', 'batch'],
        default='batch',
        help='Extraction mode'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    parser.add_argument(
        '--use-pdfminer',
        action='store_true',
        help='Use pdfminer instead of pdfplumber (slower but more accurate for complex layouts)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    Path('logs').mkdir(exist_ok=True)
    
    input_path = Path(args.input)
    
    try:
        if args.mode == 'single' and input_path.is_file() and input_path.suffix.lower() == '.pdf':
            print(f"📄 Processing single PDF: {input_path}")
            
            if not input_path.exists():
                print(f"❌ PDF file not found: {input_path}")
                sys.exit(1)
            
            result = extract_single_pdf(str(input_path), args.output_dir, args.use_pdfminer)
            
            if result:
                print(f"\n📋 Full instrument details available in: {args.output_dir}/{result.get('instrument_id', 'unknown')}.json")
            else:
                print(f"\n❌ Extraction failed for {input_path}")
                sys.exit(1)
            
        elif args.mode == 'batch' and input_path.is_dir():
            print(f"📁 Processing directory: {input_path}")
            
            if not input_path.exists():
                print(f"❌ Directory not found: {input_path}")
                sys.exit(1)
            
            # Check for PDF files
            pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
            if not pdf_files:
                print(f"❌ No PDF files found in {input_path}")
                print(f"   Supported extensions: .pdf, .PDF")
                sys.exit(1)
            
            print(f"   Found {len(pdf_files)} PDF files")
            
            result = extract_batch_pdfs(str(input_path), args.output_dir, args.use_pdfminer)
            
            if not result:
                print(f"\n❌ Batch extraction failed or no instruments extracted")
                sys.exit(1)
                
        else:
            print(f"❌ Invalid input: {args.input}")
            print(f"   For single file mode, provide a PDF file (.pdf)")
            print(f"   For batch mode, provide a directory containing PDF files")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        print(f"\n❌ Extraction failed with error: {e}")
        print("Check logs/policy_extraction.log for details")
        sys.exit(1)

if __name__ == "__main__":
    main()