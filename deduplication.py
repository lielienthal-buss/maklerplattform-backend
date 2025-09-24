import re
import json
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import YachtListing, SessionLocal
import hashlib
from difflib import SequenceMatcher

class YachtDeduplicator:
    def __init__(self):
        self.similarity_threshold = 0.85  # 85% similarity threshold
        
    def deduplicate_listings(self) -> Dict[str, int]:
        """Run deduplication on all listings"""
        db = SessionLocal()
        results = {
            'processed': 0,
            'duplicates_found': 0,
            'duplicates_marked': 0
        }
        
        try:
            # Get all non-duplicate listings
            listings = db.query(YachtListing).filter(
                YachtListing.is_duplicate == False
            ).all()
            
            results['processed'] = len(listings)
            
            # Group listings for comparison
            duplicates = self.find_duplicates(listings)
            
            # Mark duplicates in database
            for duplicate_group in duplicates:
                # Keep the first listing (usually oldest), mark others as duplicates
                for i in range(1, len(duplicate_group)):
                    listing = duplicate_group[i]
                    listing.is_duplicate = True
                    results['duplicates_marked'] += 1
                    
                results['duplicates_found'] += len(duplicate_group) - 1
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
        return results
    
    def find_duplicates(self, listings: List[YachtListing]) -> List[List[YachtListing]]:
        """Find duplicate listings using multiple criteria"""
        duplicate_groups = []
        processed_ids = set()
        
        for i, listing1 in enumerate(listings):
            if listing1.id in processed_ids:
                continue
                
            current_group = [listing1]
            processed_ids.add(listing1.id)
            
            for j, listing2 in enumerate(listings[i+1:], i+1):
                if listing2.id in processed_ids:
                    continue
                    
                if self.are_duplicates(listing1, listing2):
                    current_group.append(listing2)
                    processed_ids.add(listing2.id)
            
            # Only add groups with actual duplicates
            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                
        return duplicate_groups
    
    def are_duplicates(self, listing1: YachtListing, listing2: YachtListing) -> bool:
        """Determine if two listings are duplicates"""
        
        # 1. Check HIN/MMSI if available (most reliable)
        if listing1.hin and listing2.hin and listing1.hin == listing2.hin:
            return True
        if listing1.mmsi and listing2.mmsi and listing1.mmsi == listing2.mmsi:
            return True
            
        # 2. Check exact title match
        if listing1.title and listing2.title:
            if self.normalize_text(listing1.title) == self.normalize_text(listing2.title):
                return True
        
        # 3. Comprehensive similarity check
        similarity_score = self.calculate_similarity(listing1, listing2)
        return similarity_score >= self.similarity_threshold
    
    def calculate_similarity(self, listing1: YachtListing, listing2: YachtListing) -> float:
        """Calculate overall similarity between two listings"""
        scores = []
        weights = []
        
        # Title similarity (high weight)
        if listing1.title and listing2.title:
            title_sim = self.text_similarity(
                self.normalize_text(listing1.title),
                self.normalize_text(listing2.title)
            )
            scores.append(title_sim)
            weights.append(0.4)
        
        # Brand + Model similarity (high weight)
        brand_model1 = f"{listing1.brand or ''} {listing1.model or ''}".strip()
        brand_model2 = f"{listing2.brand or ''} {listing2.model or ''}".strip()
        if brand_model1 and brand_model2:
            brand_sim = self.text_similarity(
                self.normalize_text(brand_model1),
                self.normalize_text(brand_model2)
            )
            scores.append(brand_sim)
            weights.append(0.3)
        
        # Year similarity (medium weight)
        if listing1.year and listing2.year:
            year_diff = abs(listing1.year - listing2.year)
            year_sim = 1.0 if year_diff == 0 else max(0, 1.0 - (year_diff / 5.0))
            scores.append(year_sim)
            weights.append(0.1)
        
        # Length similarity (medium weight)
        if listing1.length and listing2.length:
            length_diff = abs(listing1.length - listing2.length)
            length_sim = 1.0 if length_diff < 0.5 else max(0, 1.0 - (length_diff / 5.0))
            scores.append(length_sim)
            weights.append(0.1)
        
        # Price similarity (lower weight, prices can vary)
        if listing1.price and listing2.price:
            price_diff = abs(listing1.price - listing2.price)
            price_ratio = price_diff / max(listing1.price, listing2.price)
            price_sim = max(0, 1.0 - price_ratio)
            scores.append(price_sim)
            weights.append(0.1)
        
        # Calculate weighted average
        if not scores:
            return 0.0
            
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove common words and punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

class YachtScorer:
    def __init__(self):
        self.current_year = datetime.now().year
        
    def score_all_listings(self) -> Dict[str, int]:
        """Score all active listings"""
        db = SessionLocal()
        results = {
            'processed': 0,
            'scored': 0
        }
        
        try:
            # Get all non-duplicate listings
            listings = db.query(YachtListing).filter(
                YachtListing.is_duplicate == False
            ).all()
            
            results['processed'] = len(listings)
            
            for listing in listings:
                score = self.calculate_score(listing)
                listing.score = score
                results['scored'] += 1
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
        return results
    
    def calculate_score(self, listing: YachtListing) -> float:
        """Calculate attractiveness score for a listing"""
        score = 0.0
        
        # Base score
        score += 1.0
        
        # Age factor (newer boats score higher)
        if listing.year:
            age = self.current_year - listing.year
            if age <= 5:
                score += 2.0
            elif age <= 10:
                score += 1.5
            elif age <= 15:
                score += 1.0
            elif age <= 20:
                score += 0.5
        
        # Price factor (reasonable prices score higher)
        if listing.price and listing.length:
            price_per_meter = listing.price / listing.length
            
            # Typical price ranges per meter for used yachts
            if 10000 <= price_per_meter <= 50000:  # Sweet spot
                score += 2.0
            elif 5000 <= price_per_meter <= 80000:  # Reasonable range
                score += 1.0
            elif price_per_meter < 5000:  # Suspiciously cheap
                score += 0.5
        
        # Length factor (popular sizes score higher)
        if listing.length:
            if 10 <= listing.length <= 15:  # Popular cruising size
                score += 1.5
            elif 8 <= listing.length <= 20:  # Good range
                score += 1.0
            elif listing.length > 20:  # Luxury range
                score += 0.5
        
        # Brand factor (premium brands score higher)
        premium_brands = [
            'bavaria', 'jeanneau', 'beneteau', 'hanse', 'dehler', 
            'x-yachts', 'hallberg-rassy', 'najad', 'swan', 'oyster'
        ]
        
        if listing.brand:
            brand_lower = listing.brand.lower()
            if any(premium in brand_lower for premium in premium_brands):
                score += 1.0
        
        # Seller type factor (dealers might be more reliable)
        if listing.seller_type == 'dealer':
            score += 0.5
        
        # Location factor (major sailing areas)
        major_locations = [
            'hamburg', 'kiel', 'bremen', 'rostock', 'flensburg',
            'lübeck', 'stralsund', 'greifswald'
        ]
        
        if listing.location:
            location_lower = listing.location.lower()
            if any(loc in location_lower for loc in major_locations):
                score += 0.5
        
        # Description quality factor
        if listing.description:
            desc_length = len(listing.description)
            if desc_length > 500:  # Detailed description
                score += 1.0
            elif desc_length > 200:  # Moderate description
                score += 0.5
        
        # Images factor
        if listing.images:
            try:
                images_list = json.loads(listing.images)
                if len(images_list) >= 5:  # Good photo coverage
                    score += 1.0
                elif len(images_list) >= 2:  # Basic photos
                    score += 0.5
            except:
                pass
        
        # Condition factor
        if listing.condition:
            condition_lower = listing.condition.lower()
            if 'new' in condition_lower:
                score += 1.5
            elif 'excellent' in condition_lower or 'very good' in condition_lower:
                score += 1.0
            elif 'good' in condition_lower:
                score += 0.5
        
        # Normalize score to 0-10 range
        max_possible_score = 12.0  # Theoretical maximum
        normalized_score = min(10.0, (score / max_possible_score) * 10.0)
        
        return round(normalized_score, 2)

def run_deduplication_and_scoring():
    """Run both deduplication and scoring processes"""
    results = {}
    
    # Run deduplication
    deduplicator = YachtDeduplicator()
    dedup_results = deduplicator.deduplicate_listings()
    results['deduplication'] = dedup_results
    
    # Run scoring
    scorer = YachtScorer()
    scoring_results = scorer.score_all_listings()
    results['scoring'] = scoring_results
    
    return results

