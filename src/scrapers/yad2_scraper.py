"""
Yad2.co.il Scraper
Scrapes Israeli real estate listings from Yad2
"""

import asyncio
import logging
import re
import json
from typing import List, Optional, Dict
from datetime import datetime
from bs4 import BeautifulSoup

from .base_scraper import BaseIsraeliScraper, Property

logger = logging.getLogger(__name__)


class Yad2Scraper(BaseIsraeliScraper):
    """
    Scraper for Yad2.co.il - Israel's largest classified ads platform
    
    Listing types:
    - buy (קניה)
    - rent (השכרה)
    - commercial (מסחרי)
    """
    
    # Yad2 URLs
    BASE_URL = "https://www.yad2.co.il"
    URLS = {
        'buy': f"{BASE_URL}/realestate/forsale",
        'rent': f"{BASE_URL}/realestate/rent",
        'commercial': f"{BASE_URL}/realestate/commercial"
    }
    
    # Selectors
    FEED_CONTAINER = "div[class*='feedContainer']"
    PROPERTY_CARD = "div[class*='feeditem']"
    
    def __init__(self, **kwargs):
        super().__init__(source='yad2', **kwargs)
        logger.info("Initialized Yad2 scraper")
    
    async def scrape(
        self,
        listing_types: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Property]:
        """
        Scrape Yad2 listings
        
        Args:
            listing_types: ['buy', 'rent', 'commercial']
            cities: ['תל אביב', 'חיפה', etc] - Will add to URL query
            limit: Max pages to scrape per listing type
        
        Returns:
            List of Property objects
        """
        if listing_types is None:
            listing_types = ['buy', 'rent']
        
        all_properties = []
        
        for listing_type in listing_types:
            if listing_type not in self.URLS:
                logger.warning(f"Unknown listing type: {listing_type}")
                continue
            
            logger.info(f"Scraping Yad2 {listing_type}...")
            
            try:
                properties = await self._scrape_listing_type(
                    listing_type=listing_type,
                    cities=cities,
                    max_pages=limit or 5
                )
                
                logger.info(f"Scraped {len(properties)} properties for {listing_type}")
                all_properties.extend(properties)
                
                # Rate limiting
                await self.rate_limit()
                
            except Exception as e:
                logger.error(f"Error scraping {listing_type}: {e}")
                self.stats['errors'] += 1
        
        return all_properties
    
    async def _scrape_listing_type(
        self,
        listing_type: str,
        cities: Optional[List[str]] = None,
        max_pages: int = 5
    ) -> List[Property]:
        """Scrape a single listing type"""
        
        all_properties = []
        
        # Build URL with city filter if provided
        base_url = self.URLS[listing_type]
        
        if cities:
            # Yad2 uses city codes - this is simplified
            # Real implementation would map city names to Yad2 city codes
            city_param = cities[0]  # Just use first city for now
            url = f"{base_url}?city={city_param}"
        else:
            url = base_url
        
        # Scrape multiple pages
        for page in range(1, max_pages + 1):
            logger.info(f"Scraping page {page} of {listing_type}")
            
            page_url = f"{url}&page={page}" if '?' in url else f"{url}?page={page}"
            
            try:
                properties = await self._scrape_page(page_url, listing_type)
                
                if not properties:
                    logger.info(f"No more properties on page {page}, stopping")
                    break
                
                all_properties.extend(properties)
                
                # Rate limiting between pages
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scraping page {page}: {e}")
                break
        
        return all_properties
    
    async def _scrape_page(
        self,
        url: str,
        listing_type: str
    ) -> List[Property]:
        """Scrape a single page"""
        
        logger.info(f"Accessing {url}")
        
        try:
            # Navigate to page
            await self.page.goto(url, wait_until='domcontentloaded')
            
            # Wait for content to load
            await self.page.wait_for_timeout(3000)
            
            # Scroll a bit to load lazy images
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            await self.page.wait_for_timeout(1000)
            
            # Get page HTML
            html = await self.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Parse properties
            properties = self._parse_properties(soup, listing_type)
            
            return properties
            
        except Exception as e:
            logger.error(f"Error scraping page: {e}")
            return []
    
    def _parse_properties(
        self,
        soup: BeautifulSoup,
        listing_type: str
    ) -> List[Property]:
        """Parse properties from HTML"""
        
        properties = []
        
        # Find all property cards
        # Note: Yad2 structure changes frequently - this is simplified
        feed_items = soup.find_all('div', class_=lambda x: x and 'feeditem' in x.lower())
        
        if not feed_items:
            # Try alternative selector
            feed_items = soup.find_all('a', class_=lambda x: x and 'feed_item' in str(x).lower())
        
        logger.debug(f"Found {len(feed_items)} property cards")
        
        for card in feed_items:
            try:
                prop = self._parse_property_card(card, listing_type)
                if prop:
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing property card: {e}")
                continue
        
        return properties
    
    def _parse_property_card(
        self,
        card: BeautifulSoup,
        listing_type: str
    ) -> Optional[Property]:
        """Parse a single property card"""
        
        try:
            # Try to extract structured data (Yad2 sometimes includes JSON-LD)
            json_data = card.find('script', type='application/ld+json')
            if json_data:
                try:
                    data = json.loads(json_data.string)
                    return self._parse_from_json(data, listing_type)
                except:
                    pass
            
            # Fallback to HTML parsing
            
            # Price
            price = None
            price_elem = card.find('div', class_=lambda x: x and 'price' in str(x).lower())
            if price_elem:
                price_text = re.sub(r'[^\d]', '', price_elem.text)
                if price_text:
                    price = int(price_text)
            
            # Address / Location
            location_elem = card.find('div', class_=lambda x: x and ('location' in str(x).lower() or 'address' in str(x).lower()))
            address = location_elem.text.strip() if location_elem else None
            
            # Parse city from address
            city = None
            street = address
            if address:
                # Yad2 format: "Street, Neighborhood, City"
                parts = [p.strip() for p in address.split(',')]
                if len(parts) >= 2:
                    city = parts[-1]
                    street = parts[0]
            
            # Rooms
            rooms = None
            rooms_elem = card.find(string=re.compile(r'\d+\.?\d*\s*חדרים'))
            if rooms_elem:
                rooms_text = re.findall(r'[\d.]+', rooms_elem)
                if rooms_text:
                    rooms = float(rooms_text[0])
            
            # Area (sqm)
            sqm = None
            sqm_elem = card.find(string=re.compile(r'\d+\s*מ"ר'))
            if sqm_elem:
                sqm_text = re.findall(r'\d+', sqm_elem)
                if sqm_text:
                    sqm = int(sqm_text[0])
            
            # Floor
            floor = None
            floor_elem = card.find(string=re.compile(r'קומה\s*\d+'))
            if floor_elem:
                floor_text = re.findall(r'\d+', floor_elem)
                if floor_text:
                    floor = int(floor_text[0])
            
            # External ID (from Yad2 URL or data attribute)
            external_id = None
            link = card.find('a', href=True)
            if link:
                match = re.search(r'/(\d+)$', link['href'])
                if match:
                    external_id = f"yad2_{match.group(1)}"
            
            if not external_id:
                # Generate from available data
                external_id = f"yad2_{listing_type}_{street}_{price}_{sqm}"
            
            # URL
            listing_url = None
            if link and 'href' in link.attrs:
                href = link['href']
                listing_url = href if href.startswith('http') else f"https://www.yad2.co.il{href}"
            
            # Create Property object
            prop = Property(
                source='yad2',
                external_id=external_id,
                listing_type=listing_type,
                address_street=street,
                address_city=city,
                price_current=price,
                rooms=rooms,
                square_meters=sqm,
                floor=floor,
                listing_url=listing_url,
                scraped_at=datetime.now()
            )
            
            return prop
            
        except Exception as e:
            logger.debug(f"Error parsing property: {e}")
            return None
    
    def _parse_from_json(self, data: Dict, listing_type: str) -> Optional[Property]:
        """Parse property from JSON-LD structured data"""
        
        try:
            # Extract from schema.org format
            prop = Property(
                source='yad2',
                external_id=f"yad2_{data.get('@id', '')}",
                listing_type=listing_type,
                address_street=data.get('address', {}).get('streetAddress'),
                address_city=data.get('address', {}).get('addressLocality'),
                price_current=int(data.get('price', 0)) if data.get('price') else None,
                scraped_at=datetime.now()
            )
            
            return prop
            
        except Exception as e:
            logger.debug(f"Error parsing JSON data: {e}")
            return None


# For testing
if __name__ == "__main__":
    async def test():
        scraper = Yad2Scraper()
        await scraper.init_browser()
        
        try:
            # Test scraping buy listings
            properties = await scraper.scrape(
                listing_types=['buy'],
                limit=2  # Just 2 pages for testing
            )
            
            print(f"\nScraped {len(properties)} properties")
            
            for prop in properties[:5]:
                print(f"\n{prop.address_city} - {prop.address_street}")
                print(f"  Price: ₪{prop.price_current:,}" if prop.price_current else "  Price: N/A")
                print(f"  Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
            
        finally:
            await scraper.close_browser()
    
    # Run test
    asyncio.run(test())
