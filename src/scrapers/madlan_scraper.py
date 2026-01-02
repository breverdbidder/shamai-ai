"""
Madlan.co.il Scraper
Scrapes Israeli real estate listings from Madlan
Based on reverse engineering from Madlan Professional PRD
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


class MadlanScraper(BaseIsraeliScraper):
    """
    Scraper for Madlan.co.il - Israel's #1 real estate platform
    
    Listing types:
    - buy (למכירה)
    - rent (להשכרה)
    
    Note: Professional features (market analysis, Tax Authority data) 
    require subscription and cannot be scraped from public pages.
    """
    
    # Madlan URLs
    BASE_URL = "https://www.madlan.co.il"
    URLS = {
        'buy': f"{BASE_URL}/for-sale",
        'rent': f"{BASE_URL}/for-rent"
    }
    
    def __init__(self, **kwargs):
        super().__init__(source='madlan', **kwargs)
        logger.info("Initialized Madlan scraper")
    
    async def scrape(
        self,
        listing_types: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Property]:
        """
        Scrape Madlan listings
        
        Args:
            listing_types: ['buy', 'rent']
            cities: ['תל אביב', 'חיפה', etc]
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
            
            logger.info(f"Scraping Madlan {listing_type}...")
            
            try:
                properties = await self._scrape_listing_type(
                    listing_type=listing_type,
                    cities=cities,
                    max_pages=limit or 3
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
        max_pages: int = 3
    ) -> List[Property]:
        """Scrape a single listing type"""
        
        all_properties = []
        
        # Build URL
        base_url = self.URLS[listing_type]
        
        if cities:
            # Madlan uses city names in URLs
            # Format: /for-sale/tel-aviv or /for-rent/haifa
            city_slug = cities[0].lower().replace(' ', '-')
            # Hebrew city names need translation (simplified)
            city_map = {
                'תל אביב': 'tel-aviv',
                'חיפה': 'haifa',
                'ירושלים': 'jerusalem',
                'באר שבע': 'beer-sheva',
                'פתח תקווה': 'petah-tikva'
            }
            city_slug = city_map.get(cities[0], city_slug)
            url = f"{base_url}/{city_slug}"
        else:
            url = base_url
        
        # Scrape pages
        for page in range(1, max_pages + 1):
            logger.info(f"Scraping page {page} of {listing_type}")
            
            page_url = f"{url}?page={page}"
            
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
            
            # Wait for content
            await self.page.wait_for_timeout(3000)
            
            # Madlan uses dynamic loading - scroll to trigger
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(2000)
            
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
        
        # Find property cards
        # Note: Madlan structure - this is simplified based on common patterns
        property_cards = soup.find_all('div', class_=lambda x: x and 'property' in str(x).lower())
        
        if not property_cards:
            # Try alternative selectors
            property_cards = soup.find_all('a', class_=lambda x: x and 'listing' in str(x).lower())
        
        logger.debug(f"Found {len(property_cards)} property cards")
        
        for card in property_cards:
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
            # Price
            price = None
            price_elem = card.find(string=re.compile(r'₪'))
            if price_elem:
                price_text = re.sub(r'[^\d]', '', price_elem.parent.text)
                if price_text:
                    price = int(price_text)
            
            # Address
            address_elem = card.find('div', class_=lambda x: x and 'address' in str(x).lower())
            address = address_elem.text.strip() if address_elem else None
            
            # Parse city and street
            city = None
            street = address
            if address:
                # Madlan format: "Street Number, City"
                parts = [p.strip() for p in address.split(',')]
                if len(parts) >= 2:
                    city = parts[-1]
                    street = ', '.join(parts[:-1])
            
            # Rooms
            rooms = None
            rooms_elem = card.find(string=re.compile(r'\d+\.?\d*\s*חד'))
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
            
            # External ID
            external_id = None
            link = card.find('a', href=True)
            if link:
                match = re.search(r'/listing/(\d+)', link['href'])
                if match:
                    external_id = f"madlan_{match.group(1)}"
            
            if not external_id:
                external_id = f"madlan_{listing_type}_{street}_{price}"
            
            # URL
            listing_url = None
            if link and 'href' in link.attrs:
                href = link['href']
                listing_url = href if href.startswith('http') else f"https://www.madlan.co.il{href}"
            
            # Images
            images = []
            img_tags = card.find_all('img')
            for img in img_tags:
                if 'src' in img.attrs:
                    images.append(img['src'])
            
            # Create Property object
            prop = Property(
                source='madlan',
                external_id=external_id,
                listing_type=listing_type,
                address_street=street,
                address_city=city,
                price_current=price,
                rooms=rooms,
                square_meters=sqm,
                floor=floor,
                images=images if images else None,
                listing_url=listing_url,
                scraped_at=datetime.now()
            )
            
            return prop
            
        except Exception as e:
            logger.debug(f"Error parsing property: {e}")
            return None


# For testing
if __name__ == "__main__":
    async def test():
        scraper = MadlanScraper()
        await scraper.init_browser()
        
        try:
            # Test scraping buy listings
            properties = await scraper.scrape(
                listing_types=['buy'],
                limit=1  # Just 1 page for testing
            )
            
            print(f"\nScraped {len(properties)} properties")
            
            for prop in properties[:5]:
                print(f"\n{prop.address_city} - {prop.address_street}")
                print(f"  Price: ₪{prop.price_current:,}" if prop.price_current else "  Price: N/A")
                print(f"  Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
                if prop.listing_url:
                    print(f"  URL: {prop.listing_url}")
            
        finally:
            await scraper.close_browser()
    
    # Run test
    asyncio.run(test())
