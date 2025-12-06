#!/usr/bin/env python3
"""
Extract policy instruments from Agricultural Policy Toolkit documents
"""

import argparse
import logging
import sys
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.policy_extractor import PolicyInstrumentExtractor, BatchPolicyExtractor

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

def extract_single_file(file_path: str, output_dir: str = "data/processed"):
    """Extract single policy instrument file"""
    extractor = PolicyInstrumentExtractor()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    instrument = extractor.extract_from_text(content, file_path)
    
    # Save individual instrument
    output_path = Path(output_dir) / f"{instrument.instrument_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(instrument.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Extracted instrument: {instrument.instrument_name}")
    print(f"   ID: {instrument.instrument_id}")
    print(f"   URL: {instrument.url}")
    print(f"   Saved to: {output_path}")
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   Objectives: {len(instrument.policy_objectives)}")
    print(f"   Ministries: {', '.join(instrument.ministries_involved)}")
    print(f"   Budget: {instrument.required_budget}")
    print(f"   Horizon: {', '.join([h.value for h in instrument.impact_horizon])}")
    
    return instrument

def extract_batch(input_dir: str, output_dir: str = "data/processed"):
    """Extract all policy instruments from a directory"""
    batch_extractor = BatchPolicyExtractor()
    
    print(f"🔍 Processing directory: {input_dir}")
    
    # Process all text files
    instruments = batch_extractor.process_directory(input_dir, "*.txt")
    
    if not instruments:
        print("❌ No instruments extracted")
        return
    
    # Save to JSON
    json_path = Path(output_dir) / "policy_instruments.json"
    batch_extractor.save_to_json(str(json_path))
    
    # Save to JSONL for vector storage
    jsonl_path = Path(output_dir) / "policy_instruments.jsonl"
    batch_extractor.save_to_jsonl(str(jsonl_path))
    
    # Generate statistics
    stats = generate_statistics(instruments)
    stats_path = Path(output_dir) / "extraction_statistics.json"
    
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n🎉 Batch extraction complete!")
    print(f"   Instruments extracted: {stats['total_instruments']}")
    print(f"   JSON output: {json_path}")
    print(f"   JSONL output: {jsonl_path}")
    print(f"   Statistics: {stats_path}")
    
    return instruments

def generate_statistics(instruments):
    """Generate extraction statistics"""
    stats = {
        'total_instruments': len(instruments),
        'by_budget': {},
        'by_impact_horizon': {},
        'common_ministries': {},
        'common_objectives': {},
        'instrument_types': set()
    }
    
    all_objectives = []
    
    for instrument in instruments:
        # Budget distribution
        budget = instrument.required_budget.value if hasattr(instrument.required_budget, 'value') else instrument.required_budget
        stats['by_budget'][budget] = stats['by_budget'].get(budget, 0) + 1
        
        # Impact horizon
        for horizon in instrument.impact_horizon:
            horizon_val = horizon.value if hasattr(horizon, 'value') else horizon
            stats['by_impact_horizon'][horizon_val] = stats['by_impact_horizon'].get(horizon_val, 0) + 1
        
        # Ministries
        for ministry in instrument.ministries_involved:
            stats['common_ministries'][ministry] = stats['common_ministries'].get(ministry, 0) + 1
        
        # Objectives
        all_objectives.extend(instrument.policy_objectives)
        
        # Instrument types (from name)
        stats['instrument_types'].add(instrument.instrument_name.split()[0].lower() if instrument.instrument_name else 'unknown')
    
    # Count objectives
    from collections import Counter
    objective_counts = Counter(all_objectives)
    stats['common_objectives'] = dict(objective_counts.most_common(10))
    
    # Convert set to list
    stats['instrument_types'] = list(stats['instrument_types'])
    
    return stats

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Extract policy instruments from Agricultural Policy Toolkit documents'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input file or directory'
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
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    input_path = Path(args.input)
    
    try:
        if args.mode == 'single' and input_path.is_file():
            print(f"📄 Processing single file: {input_path}")
            instrument = extract_single_file(str(input_path), args.output_dir)
            
            # Print instrument details
            print(f"\n📋 Full instrument details:")
            print(json.dumps(instrument.to_dict(), indent=2, ensure_ascii=False))
            
        elif args.mode == 'batch' and input_path.is_dir():
            print(f"📁 Processing directory: {input_path}")
            instruments = extract_batch(str(input_path), args.output_dir)
            
            if instruments:
                # Print sample
                print(f"\n📄 Sample instrument (first of {len(instruments)}):")
                sample = instruments[0].to_dict()
                print(json.dumps({k: v for k, v in sample.items() if k != 'description'}, indent=2))
                
        else:
            print(f"❌ Invalid input: {args.input}")
            print(f"   For single file mode, provide a file path")
            print(f"   For batch mode, provide a directory path")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()