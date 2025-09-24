import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from models import YachtListing, ScrapeLog, SessionLocal
import time
import random

class YachtScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_all_platforms(self) -> Dict[str, int]:
        """Scrape all supported platforms and return counts"""
        results = {}
        
        # Scrape top 3 platforms for MVP
        platforms = [
            ('yachtworld_demo', self.scrape_yachtworld_demo),
            ('boats_demo', self.scrape_boats_demo),
            ('yachtall_demo', self.scrape_yachtall_demo)
        ]
        
        for platform_name, scraper_func in platforms:
            try:
                count = scraper_func()
                results[platform_name] = count
                self.log_scrape_result(platform_name, 'success', count)
            except Exception as e:
                print(f"Error scraping {platform_name}: {str(e)}")
                results[platform_name] = 0
                self.log_scrape_result(platform_name, 'failed', 0, str(e))
                
        return results
    
    def scrape_yachtworld_demo(self) -> int:
        """Demo scraper for YachtWorld (simulated data)"""
        # In a real implementation, this would scrape actual YachtWorld listings
        # For demo purposes, we'll create sample data
        
        demo_listings = [
            {
                'title': 'Bavaria 46 Cruiser - Excellent Condition',
                'price': 185000.0,
                'currency': 'EUR',
                'year': 2018,
                'brand': 'Bavaria',
                'model': '46 Cruiser',
                'length': 14.27,
                'location': 'Hamburg, Germany',
                'condition': 'used',
                'description': 'Well-maintained Bavaria 46 with full equipment. Perfect for long-distance cruising.',
                'seller_name': 'Hamburg Yacht Center',
                'seller_type': 'dealer',
                'source_platform': 'yachtworld_demo',
                'source_url': 'https://yachtworld.com/demo/listing1',
                'images': json.dumps(['https://example.com/yacht1_1.jpg', 'https://example.com/yacht1_2.jpg'])
            },
            {
                'title': 'Jeanneau Sun Odyssey 519 - Ready to Sail',
                'price': 320000.0,
                'currency': 'EUR',
                'year': 2020,
                'brand': 'Jeanneau',
                'model': 'Sun Odyssey 519',
                'length': 15.37,
                'location': 'Kiel, Germany',
                'condition': 'used',
                'description': 'Modern cruising yacht with luxury interior and advanced navigation systems.',
                'seller_name': 'Baltic Yachts GmbH',
                'seller_type': 'dealer',
                'source_platform': 'yachtworld_demo',
                'source_url': 'https://yachtworld.com/demo/listing2',
                'images': json.dumps(['https://example.com/yacht2_1.jpg', 'https://example.com/yacht2_2.jpg'])
            }
        ]
        
        return self.save_listings(demo_listings)
    
    def scrape_boats_demo(self) -> int:
        """Demo scraper for Boats.com (simulated data)"""
        demo_listings = [
            {
                'title': 'Hanse 455 - Performance Cruiser',
                'price': 275000.0,
                'currency': 'EUR',
                'year': 2019,
                'brand': 'Hanse',
                'model': '455',
                'length': 13.98,
                'location': 'Bremen, Germany',
                'condition': 'used',
                'description': 'Fast and comfortable cruising yacht with innovative design.',
                'seller_name': 'North Sea Yachts',
                'seller_type': 'dealer',
                'source_platform': 'boats_demo',
                'source_url': 'https://boats.com/demo/listing1',
                'images': json.dumps(['https://example.com/yacht3_1.jpg', 'https://example.com/yacht3_2.jpg'])
            },
            {
                'title': 'Beneteau Oceanis 51.1 - Blue Water Cruiser',
                'price': 410000.0,
                'currency': 'EUR',
                'year': 2021,
                'brand': 'Beneteau',
                'model': 'Oceanis 51.1',
                'length': 15.94,
                'location': 'Rostock, Germany',
                'condition': 'used',
                'description': 'Premium sailing yacht with spacious interior and excellent sailing performance.',
                'seller_name': 'Private Owner',
                'seller_type': 'private',
                'source_platform': 'boats_demo',
                'source_url': 'https://boats.com/demo/listing2',
                'images': json.dumps(['https://example.com/yacht4_1.jpg', 'https://example.com/yacht4_2.jpg'])
            }
        ]
        
        return self.save_listings(demo_listings)
    
    def scrape_yachtall_demo(self) -> int:
        """Demo scraper for Yachtall (simulated data)"""
        demo_listings = [
            {
                'title': 'Dehler 46 - Racing Performance',
                'price': 295000.0,
                'currency': 'EUR',
                'year': 2020,
                'brand': 'Dehler',
                'model': '46',
                'length': 14.05,
                'location': 'Lübeck, Germany',
                'condition': 'used',
                'description': 'High-performance sailing yacht with racing pedigree and luxury comfort.',
                'seller_name': 'Dehler Yachts',
                'seller_type': 'dealer',
                'source_platform': 'yachtall_demo',
                'source_url': 'https://yachtall.com/demo/listing1',
                'images': json.dumps(['https://example.com/yacht5_1.jpg', 'https://example.com/yacht5_2.jpg'])
            },
            {
                'title': 'X-Yachts X4³ - Premium Cruiser',
                'price': 520000.0,
                'currency': 'EUR',
                'year': 2022,
                'brand': 'X-Yachts',
                'model': 'X4³',
                'length': 12.98,
                'location': 'Flensburg, Germany',
                'condition': 'used',
                'description': 'Scandinavian craftsmanship meets modern technology in this premium cruiser.',
                'seller_name': 'X-Yachts Germany',
                'seller_type': 'dealer',
                'source_platform': 'yachtall_demo',
                'source_url': 'https://yachtall.com/demo/listing2',
                'images': json.dumps(['https://example.com/yacht6_1.jpg', 'https://example.com/yacht6_2.jpg'])
            }
        ]
        
        return self.save_listings(demo_listings)
    
    def save_listings(self, listings: List[Dict]) -> int:
        """Save listings to database, avoiding duplicates"""
        db = SessionLocal()
        saved_count = 0
        
        try:
            for listing_data in listings:
                # Check for existing listing by source_url
                existing = db.query(YachtListing).filter_by(
                    source_url=listing_data['source_url']
                ).first()
                
                if not existing:
                    listing = YachtListing(**listing_data)
                    db.add(listing)
                    saved_count += 1
                else:
                    # Update existing listing
                    for key, value in listing_data.items():
                        if key != 'created_at':  # Don't update creation time
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
            
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
        return saved_count
    
    def log_scrape_result(self, platform: str, status: str, listings_found: int, error_message: str = None):
        """Log scraping results"""
        db = SessionLocal()
        
        try:
            log_entry = ScrapeLog(
                platform=platform,
                status=status,
                listings_found=listings_found,
                error_message=error_message,
                completed_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error logging scrape result: {str(e)}")
        finally:
            db.close()
    
    def extract_price(self, price_text: str) -> tuple:
        """Extract price and currency from text"""
        if not price_text:
            return None, 'EUR'
            
        # Remove common formatting
        price_text = re.sub(r'[^\d.,€$£]', '', price_text)
        
        # Determine currency
        currency = 'EUR'
        if '$' in price_text:
            currency = 'USD'
        elif '£' in price_text:
            currency = 'GBP'
            
        # Extract numeric value
        price_match = re.search(r'[\d.,]+', price_text)
        if price_match:
            price_str = price_match.group().replace(',', '')
            try:
                return float(price_str), currency
            except ValueError:
                return None, currency
                
        return None, currency
    
    def extract_year(self, text: str) -> Optional[int]:
        """Extract year from text"""
        if not text:
            return None
            
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            year = int(year_match.group())
            if 1950 <= year <= datetime.now().year + 1:
                return year
        return None
    
    def extract_length(self, text: str) -> Optional[float]:
        """Extract length in meters from text"""
        if not text:
            return None
            
        # Look for patterns like "14.5m", "45ft", "14,5 m"
        length_match = re.search(r'(\d+[.,]?\d*)\s*(m|ft|meter|feet)', text.lower())
        if length_match:
            length_str = length_match.group(1).replace(',', '.')
            unit = length_match.group(2)
            
            try:
                length = float(length_str)
                # Convert feet to meters
                if unit in ['ft', 'feet']:
                    length = length * 0.3048
                return round(length, 2)
            except ValueError:
                pass
                
        return None

# Utility function for manual scraping trigger
def run_scraping():
    """Run scraping for all platforms"""
    scraper = YachtScraper()
    results = scraper.scrape_all_platforms()
    return results

