"""
Base scraper class for ShamaiAI
All source-specific scrapers inherit from this class
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import httpx
from playwright.async_api import async_playwright, Browser, Page
from supabase import create_client, Client
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Property:
    """Standardized property data model"""
    # Source tracking
    source: str  # 'onmap', 'yad2', 'madlan', 'gov'
    external_id: Optional[str] = None
    listing_type: str = ''  # 'buy', 'rent', 'commercial', 'new_homes'
    property_type: Optional[str] = None  # 'apartment', 'penthouse', etc
    
    # Location
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_neighborhood: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    
    # Pricing
    price_current: Optional[int] = None
    price_original: Optional[int] = None
    currency: str = 'ILS'
    
    # Property details
    rooms: Optional[float] = None
    square_meters: Optional[int] = None
    floor: Optional[int] = None
    building_floors: Optional[int] = None
    year_built: Optional[int] = None
    parking_spots: int = 0
    
    # Features & media
    features: Optional[Dict] = None
    construction_status: Optional[str] = None
    images: Optional[List[str]] = None
    listing_url: Optional[str] = None
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    
    # Agent info
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_email: Optional[str] = None
    
    # Status
    status: str = 'active'
    days_on_market: int = 0
    
    # Timestamps
    scraped_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dict for Supabase insertion"""
        data = asdict(self)
        # Convert datetime to ISO string
        if self.scraped_at:
            data['scraped_at'] = self.scraped_at.isoformat()
        return data


class BaseIsraeliScraper(ABC):
    """
    Base class for all Israeli real estate scrapers
    
    Provides common functionality:
    - Supabase connection
    - Playwright browser management
    - Rate limiting
    - Error handling
    - Data standardization
    """
    
    def __init__(
        self,
        source: str,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        delay_seconds: int = 2,
        headless: bool = True
    ):
        self.source = source
        self.delay_seconds = delay_seconds
        self.headless = headless
        
        # Initialize Supabase
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Playwright browser will be initialized in context
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # Stats tracking
        self.stats = {
            'properties_scraped': 0,
            'properties_new': 0,
            'properties_updated': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"Initialized {self.source} scraper")
    
    async def init_browser(self):
        """Initialize Playwright browser"""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            # Create context with stealth settings
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                locale='he-IL',
                timezone_id='Asia/Jerusalem'
            )
            
            # Add init script to hide webdriver
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            self.page = await context.new_page()
            logger.info("Browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def close_browser(self):
        """Close Playwright browser"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
    
    @abstractmethod
    async def scrape(
        self,
        listing_types: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Property]:
        """
        Main scraping method - must be implemented by child classes
        
        Args:
            listing_types: List of listing types to scrape ['buy', 'rent', etc]
            cities: List of cities to scrape ['תל אביב', 'חיפה', etc]
            limit: Maximum number of properties to scrape
        
        Returns:
            List of Property objects
        """
        pass
    
    async def save_to_db(self, properties: List[Property]) -> Dict[str, int]:
        """
        Save properties to Supabase
        
        Returns:
            Dict with counts: {'new': X, 'updated': Y, 'errors': Z}
        """
        if not properties:
            logger.warning("No properties to save")
            return {'new': 0, 'updated': 0, 'errors': 0}
        
        counts = {'new': 0, 'updated': 0, 'errors': 0}
        
        for prop in properties:
            try:
                # Check if property already exists
                existing = self.supabase.table('il_properties').select('id').eq(
                    'source', prop.source
                ).eq(
                    'external_id', prop.external_id
                ).execute()
                
                prop_dict = prop.to_dict()
                
                if existing.data:
                    # Update existing
                    self.supabase.table('il_properties').update(
                        prop_dict
                    ).eq('id', existing.data[0]['id']).execute()
                    counts['updated'] += 1
                    logger.debug(f"Updated property: {prop.external_id}")
                else:
                    # Insert new
                    self.supabase.table('il_properties').insert(prop_dict).execute()
                    counts['new'] += 1
                    logger.debug(f"Inserted new property: {prop.external_id}")
                
            except Exception as e:
                logger.error(f"Error saving property {prop.external_id}: {e}")
                counts['errors'] += 1
        
        logger.info(f"Saved to DB: {counts['new']} new, {counts['updated']} updated, {counts['errors']} errors")
        return counts
    
    async def log_scrape_session(self, listing_type: Optional[str] = None):
        """Log scraping session to il_scraping_logs"""
        try:
            duration = None
            if self.stats['start_time'] and self.stats['end_time']:
                duration = int((self.stats['end_time'] - self.stats['start_time']).total_seconds())
            
            log_data = {
                'source': self.source,
                'listing_type': listing_type,
                'properties_scraped': self.stats['properties_scraped'],
                'properties_new': self.stats['properties_new'],
                'properties_updated': self.stats['properties_updated'],
                'errors_count': self.stats['errors'],
                'duration_seconds': duration,
                'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
                'end_time': self.stats['end_time'].isoformat() if self.stats['end_time'] else None,
                'status': 'completed' if self.stats['errors'] == 0 else 'completed_with_errors',
                'triggered_by': os.getenv('GITHUB_RUN_ID', 'manual'),
                'github_run_id': os.getenv('GITHUB_RUN_ID')
            }
            
            self.supabase.table('il_scraping_logs').insert(log_data).execute()
            logger.info("Scrape session logged to database")
            
        except Exception as e:
            logger.error(f"Error logging scrape session: {e}")
    
    async def rate_limit(self):
        """Apply rate limiting between requests"""
        await asyncio.sleep(self.delay_seconds)
    
    async def run(
        self,
        listing_types: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run the complete scraping workflow
        
        Returns:
            Stats dictionary with scraping results
        """
        self.stats['start_time'] = datetime.now()
        
        try:
            # Initialize browser
            await self.init_browser()
            
            # Scrape properties
            logger.info(f"Starting scrape for {self.source}...")
            properties = await self.scrape(
                listing_types=listing_types,
                cities=cities,
                limit=limit
            )
            
            self.stats['properties_scraped'] = len(properties)
            
            # Save to database
            if properties:
                counts = await self.save_to_db(properties)
                self.stats['properties_new'] = counts['new']
                self.stats['properties_updated'] = counts['updated']
                self.stats['errors'] = counts['errors']
            
            self.stats['end_time'] = datetime.now()
            
            # Log session
            await self.log_scrape_session()
            
            logger.info(f"Scrape completed: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
            self.stats['errors'] += 1
            self.stats['end_time'] = datetime.now()
            raise
            
        finally:
            # Clean up
            await self.close_browser()


# Example usage
if __name__ == "__main__":
    # This is just for testing
    pass
