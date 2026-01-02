"""
OnMap.co.il Scraper
Scrapes Israeli real estate listings from OnMap
"""

import asyncio
import logging
import re
from typing import List, Optional, Dict
from datetime import datetime
from bs4 import BeautifulSoup

from .base_scraper import BaseIsraeliScraper, Property

logger = logging.getLogger(__name__)


class OnMapScraper(BaseIsraeliScraper):
    """
    Scraper for OnMap.co.il - Israeli real estate platform
    
    Listing types:
    - buy (למכירה)
    - rent (להשכרה)
    - commercial (מסחרי)
    - new_homes (דירות חדשות)
    """
    
    # OnMap URLs
    BASE_URL = "https://www.onmap.co.il"
    URLS = {
        'buy': f"{BASE_URL}/en/listings/sale",
        'rent': f"{BASE_URL}/en/listings/rent",
        'commercial': f"{BASE_URL}/en/commercial",
        'new_homes': f"{BASE_URL}/en/projects"
    }
    
    # Selectors
    PROPERTIES_XPATH = "//div[@class='s-result']"
    BOTTOM_PAGE_XPATH = "//div[contains(text(), 'End of results')]"
    
    def __init__(self, **kwargs):
        super().__init__(source='onmap', **kwargs)
        logger.info("Initialized OnMap scraper")
    
    async def scrape(
        self,
        listing_types: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Property]:
        """
        Scrape OnMap listings
        
        Args:
            listing_types: ['buy', 'rent', 'commercial', 'new_homes']
            cities: ['תל אביב', 'חיפה', etc] - Note: OnMap doesn't filter by city in URL
            limit: Max properties to scrape per listing type
        
        Returns:
            List of Property objects
        """
        if listing_types is None:
            listing_types = ['buy', 'rent', 'commercial', 'new_homes']
        
        all_properties = []
        
        for listing_type in listing_types:
            if listing_type not in self.URLS:
                logger.warning(f"Unknown listing type: {listing_type}")
                continue
            
            logger.info(f"Scraping OnMap {listing_type}...")
            
            try:
                properties = await self._scrape_listing_type(
                    listing_type=listing_type,
                    limit=limit
                )
                
                # Filter by city if specified
                if cities:
                    properties = [p for p in properties if p.address_city in cities]
                
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
        limit: Optional[int] = None
    ) -> List[Property]:
        """Scrape a single listing type"""
        
        url = self.URLS[listing_type]
        logger.info(f"Accessing {url}")
        
        # Navigate to page
        await self.page.goto(url, wait_until='domcontentloaded')
        await self.page.wait_for_timeout(2000)
        
        # Scroll to load all properties
        await self._scroll_to_load_all(listing_type=listing_type, limit=limit)
        
        # Get page HTML
        html = await self.page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Parse properties
        properties = self._parse_properties(soup, listing_type)
        
        logger.info(f"Parsed {len(properties)} properties from {listing_type}")
        return properties
    
    async def _scroll_to_load_all(
        self,
        listing_type: str,
        limit: Optional[int] = None
    ):
        """Scroll page to load all listings"""
        
        scroll_count = 0
        max_scrolls = limit if limit else 50  # Default max 50 scrolls
        
        logger.info(f"Starting scroll (max {max_scrolls} scrolls)...")
        
        while scroll_count < max_scrolls:
            # Get current property count
            try:
                properties = await self.page.query_selector_all(self.PROPERTIES_XPATH)
                current_count = len(properties)
                
                if current_count == 0:
                    logger.warning("No properties found on page")
                    break
                
                # Scroll to last property
                last_property = properties[-1]
                await last_property.scroll_into_view_if_needed()
                
                # Wait for new content to load
                await self.page.wait_for_timeout(1000)
                
                # Check if we hit bottom
                try:
                    bottom = await self.page.query_selector(self.BOTTOM_PAGE_XPATH)
                    if bottom:
                        logger.info("Reached end of results")
                        break
                except:
                    pass
                
                # Check if new properties loaded
                new_properties = await self.page.query_selector_all(self.PROPERTIES_XPATH)
                new_count = len(new_properties)
                
                if new_count == current_count:
                    # No new properties loaded, we're done
                    logger.info(f"No more properties loading (stuck at {current_count})")
                    break
                
                scroll_count += 1
                logger.debug(f"Scroll {scroll_count}: {new_count} properties visible")
                
            except Exception as e:
                logger.error(f"Error during scrolling: {e}")
                break
        
        logger.info(f"Finished scrolling after {scroll_count} scrolls")
    
    def _parse_properties(
        self,
        soup: BeautifulSoup,
        listing_type: str
    ) -> List[Property]:
        """Parse properties from HTML"""
        
        properties = []
        
        # Find all property cards
        # Note: OnMap structure changes - this is a simplified parser
        # Real implementation would need robust selectors
        
        property_cards = soup.find_all('div', class_='s-result')
        
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
            # Extract basic info
            # Note: This is simplified - real selectors would be more robust
            
            # Price
            price_text = card.find('span', class_='price')
            price = None
            if price_text:
                price_str = re.sub(r'[^\d]', '', price_text.text)
                if price_str:
                    price = int(price_str)
            
            # Address
            address = card.find('div', class_='address')
            street = address.text.strip() if address else None
            
            # City (usually last part of address)
            city = None
            if street and ',' in street:
                parts = street.split(',')
                city = parts[-1].strip()
                street = parts[0].strip()
            
            # Property type
            prop_type_elem = card.find('div', class_='type')
            prop_type = prop_type_elem.text.strip() if prop_type_elem else 'Apartment'
            
            # Rooms
            rooms_elem = card.find('div', class_='rooms')
            rooms = None
            if rooms_elem:
                rooms_text = re.findall(r'[\d.]+', rooms_elem.text)
                if rooms_text:
                    rooms = float(rooms_text[0])
            
            # Area (sqm)
            area_elem = card.find('div', class_='area')
            sqm = None
            if area_elem:
                sqm_text = re.findall(r'\d+', area_elem.text)
                if sqm_text:
                    sqm = int(sqm_text[0])
            
            # Floor
            floor_elem = card.find('div', class_='floor')
            floor = None
            if floor_elem:
                floor_text = re.findall(r'\d+', floor_elem.text)
                if floor_text:
                    floor = int(floor_text[0])
            
            # Parking
            parking_elem = card.find('div', class_='parking')
            parking = 0
            if parking_elem and 'parking' in parking_elem.text.lower():
                parking = 1
            
            # Generate external ID (simple hash of key fields)
            external_id = f"onmap_{listing_type}_{street}_{price}_{sqm}"
            
            # Create Property object
            prop = Property(
                source='onmap',
                external_id=external_id,
                listing_type=listing_type,
                property_type=prop_type,
                address_street=street,
                address_city=city,
                price_current=price,
                rooms=rooms,
                square_meters=sqm,
                floor=floor,
                parking_spots=parking,
                scraped_at=datetime.now()
            )
            
            return prop
            
        except Exception as e:
            logger.debug(f"Error parsing property: {e}")
            return None


# For testing
if __name__ == "__main__":
    async def test():
        scraper = OnMapScraper()
        await scraper.init_browser()
        
        try:
            # Test scraping buy listings
            properties = await scraper.scrape(
                listing_types=['buy'],
                limit=2  # Just 2 scrolls for testing
            )
            
            print(f"\nScraped {len(properties)} properties")
            
            for prop in properties[:5]:
                print(f"\n{prop.address_city} - {prop.property_type}")
                print(f"  Price: ₪{prop.price_current:,}")
                print(f"  Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
            
        finally:
            await scraper.close_browser()
    
    # Run test
    asyncio.run(test())
