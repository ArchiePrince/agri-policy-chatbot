#!/usr/bin/env python3
"""
Test extraction with the provided sample document
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.data.policy_extractor import PolicyInstrumentExtractor

# Your sample document content
sample_content = """[file name]: AgripolicyKit _ Accident insurance scheme.pdf
[file content begin]
===== Page 1 =====

Instraumatic  
Accident insurance scheme  

---

# Instrument

# Accident insurance scheme

## Description

A statutory or cooperative agricultural accident insurance scheme covers the in-sured against occupational accidents or illness. This scheme covers all costs incurred as a result of accidents suffered during land management, livestock farming, for-esty, fishing or hunting activities. The insurance pays the cost of medical care for the accident victim, including rehabilitation, and, depending on the policy, provides social security for the surviving dependants in the event of a fatality. A distinction is made between compulsory and voluntary accident insurance schemes.

An agricultural accident insurance scheme usually takes the form of a risk-sharing community organised as a cooperative, which is financed on a pay-as-you-go basis by the regular contributions of member businesses, in some cases supplemented with state grants. The financial contributions are determined on the basis of the size of the farm, livestock numbers and the number of staff.

Some of the insurance premiums go towards accident prevention measures (e.g. safety guards on tractors and machines and in housing systems prescribed by law). Failure to practice accident prevention can be sanctioned with higher contributions to reflect the higher risk.

## Requirements

A properly functioning country-wide administration and monitoring system with access to the relevant information and sufficient technical and human capacities for its design, implementation and monitoring

### (Emerging) Insurance industry

#### Close cooperation and knowledge sharing with farmers' organisations

This site uses cookies in order to provide you with the best possible service.

Agree  
Close

---

https://agripolicykit.net/en/instruments/statutory-or-cooperative-accident-insurance-scheme

===== Page 2 =====

# Possible Negative Effects

Conventional state social insurance systems do not cover workers in the informal sector

Farmers fail to implement accident prevention measures

This page was last edited on 1 July 2024 | 22:28 (CEST)

---

## Policy Objective

1. Gender equality  
2. Improved living and working conditions  
3. Protect minorities and vulnerable groups  
4. Reduced risk of accidents and improved farm safety  
5. Improved legal framework  

---

## Implementation Level

- **Competent Authority**  
- **National Government**  

---

## Required Budget

medium ($$)  

---

## Impact Horizon

medium  
long  

---

This site uses cookies in order to provide you with the best possible service.

---

https://agripolicykit.net/en/instruments/statutory-or-cooperative-accident-insurance-scheme

===== Page 3 =====

# Ministries Involved

Agriculture, Fisheries & Forests  
Labour & Social Affairs  
Health  

---

## Trade Impact

not distorting  

---

## Relevant SDG

EN  

This site uses cookies in order to provide you with the best possible service.

https://agripolicykit.net/en/instruments/statutory-or-cooperative-accident-insurance-scheme 3/3


[file content end]"""

def test_extraction():
    """Test the extraction with the sample content"""
    print("🧪 Testing Policy Instrument Extraction")
    print("=" * 60)
    
    # Clean the sample (remove the wrapper text)
    content = sample_content.split("[file content begin]")[1].split("[file content end]")[0].strip()
    
    # Initialize extractor
    extractor = PolicyInstrumentExtractor()
    
    # Extract instrument
    instrument = extractor.extract_from_text(content, "sample.pdf")
    
    print(f"✅ Successfully extracted instrument!")
    print(f"\n📋 Instrument Details:")
    print(f"   Name: {instrument.instrument_name}")
    print(f"   ID: {instrument.instrument_id}")
    print(f"   URL: {instrument.url}")
    print(f"   Last Edited: {instrument.last_edited}")
    
    print(f"\n📊 Requirements:")
    print(f"   Main: {instrument.requirements.main_requirement[:100]}...")
    print(f"   Sub-requirements: {instrument.requirements.sub_requirements}")
    
    print(f"\n🎯 Policy Objectives ({len(instrument.policy_objectives)}):")
    for i, obj in enumerate(instrument.policy_objectives, 1):
        print(f"   {i}. {obj}")
    
    print(f"\n🏛️  Ministries Involved:")
    for ministry in instrument.ministries_involved:
        print(f"   • {ministry}")
    
    print(f"\n💰 Budget & Impact:")
    print(f"   Required Budget: {instrument.required_budget}")
    print(f"   Impact Horizon: {', '.join([h.value for h in instrument.impact_horizon])}")
    print(f"   Trade Impact: {instrument.trade_impact}")
    print(f"   Relevant SDG: {instrument.relevant_sdg}")
    
    print(f"\n📝 Description Preview:")
    print(f"   {instrument.description[:200]}...")
    
    print(f"\n🔑 Categories & Keywords:")
    print(f"   Categories: {', '.join(instrument.categories)}")
    print(f"   Keywords: {', '.join(instrument.keywords[:5])}...")
    
    # Convert to dict for full view
    instrument_dict = instrument.to_dict()
    
    print(f"\n📄 Full JSON Structure Available:")
    print(f"   Keys: {', '.join(instrument_dict.keys())}")
    
    return instrument

if __name__ == "__main__":
    test_extraction()