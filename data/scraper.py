import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin
from typing import List, Dict
import time

class AgriPolicyScraper:
    def __init__(self, base_url="https://agripolicykit.net/en/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AgriPolicyBot/1.0 (Research Project)'
        })
        
    def get_sitemap(self):
        """Extract main navigation structure"""
        response = self.session.get(self.base_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Map the site structure (you'll need to inspect the actual site)
        sitemap = {
            'policy_tools': [],
            'case_studies': [],
            'guides': [],
            'resources': []
        }
        
        # Example: Find navigation links
        nav = soup.find('nav') or soup.find('div', class_='navigation')
        if nav:
            for link in nav.find_all('a', href=True):
                href = urljoin(self.base_url, link['href'])
                text = link.get_text(strip=True)
                
                # Categorize based on URL patterns or text
                if 'policy' in href.lower() or 'policy' in text.lower():
                    sitemap['policy_tools'].append({'title': text, 'url': href})
                elif 'case' in href.lower() or 'study' in text.lower():
                    sitemap['case_studies'].append({'title': text, 'url': href})
                elif 'guide' in href.lower():
                    sitemap['guides'].append({'title': text, 'url': href})
                else:
                    sitemap['resources'].append({'title': text, 'url': href})
        
        return sitemap
    
    def extract_page_content(self, url: str) -> Dict:
        """Extract structured content from a page"""
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            
            # Extract main content
            content = {
                'url': url,
                'title': soup.title.string if soup.title else '',
                'headers': [],
                'paragraphs': [],
                'tables': [],
                'metadata': {}
            }
            
            # Extract headers
            for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                content['headers'].append({
                    'level': header.name,
                    'text': header.get_text(strip=True)
                })
            
            # Extract paragraphs
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 20:  # Filter very short paragraphs
                    content['paragraphs'].append(text)
            
            # Extract tables
            for table in soup.find_all('table'):
                rows = []
                for tr in table.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if cells:
                        rows.append(cells)
                if rows:
                    content['tables'].append(rows)
            
            return content
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_site(self, max_pages=100):
        """Main scraping function"""
        sitemap = self.get_sitemap()
        all_content = []
        
        for category, pages in sitemap.items():
            print(f"Scraping category: {category}")
            for page in pages[:max_pages // len(sitemap)]:
                print(f"  - {page['title']}")
                content = self.extract_page_content(page['url'])
                if content:
                    content['category'] = category
                    all_content.append(content)
                time.sleep(0.5)  # Be polite
        
        # Save to file
        with open('data/agripolicy_content.json', 'w', encoding='utf-8') as f:
            json.dump(all_content, f, indent=2, ensure_ascii=False)
        
        print(f"Scraped {len(all_content)} pages")
        return all_content

if __name__ == "__main__":
    scraper = AgriPolicyScraper()
    scraper.scrape_site(max_pages=50)