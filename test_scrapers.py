#!/usr/bin/env python3
"""
Quick test script for ShamaiAI scrapers
Run this locally to test individual scrapers
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.onmap_scraper import OnMapScraper
from scrapers.yad2_scraper import Yad2Scraper
from scrapers.madlan_scraper import MadlanScraper


async def test_onmap():
    """Test OnMap scraper"""
    print("\n" + "="*60)
    print("TESTING ONMAP SCRAPER")
    print("="*60)
    
    scraper = OnMapScraper()
    await scraper.init_browser()
    
    try:
        properties = await scraper.scrape(
            listing_types=['buy'],
            limit=2  # Just 2 scrolls
        )
        
        print(f"\n✅ Scraped {len(properties)} properties from OnMap")
        
        for i, prop in enumerate(properties[:3], 1):
            print(f"\n{i}. {prop.address_city} - {prop.property_type}")
            print(f"   Price: ₪{prop.price_current:,}" if prop.price_current else "   Price: N/A")
            print(f"   Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
        
    except Exception as e:
        print(f"\n❌ OnMap test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await scraper.close_browser()


async def test_yad2():
    """Test Yad2 scraper"""
    print("\n" + "="*60)
    print("TESTING YAD2 SCRAPER")
    print("="*60)
    
    scraper = Yad2Scraper()
    await scraper.init_browser()
    
    try:
        properties = await scraper.scrape(
            listing_types=['buy'],
            limit=1  # Just 1 page
        )
        
        print(f"\n✅ Scraped {len(properties)} properties from Yad2")
        
        for i, prop in enumerate(properties[:3], 1):
            print(f"\n{i}. {prop.address_city} - {prop.address_street}")
            print(f"   Price: ₪{prop.price_current:,}" if prop.price_current else "   Price: N/A")
            print(f"   Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
            if prop.listing_url:
                print(f"   URL: {prop.listing_url}")
        
    except Exception as e:
        print(f"\n❌ Yad2 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await scraper.close_browser()


async def test_madlan():
    """Test Madlan scraper"""
    print("\n" + "="*60)
    print("TESTING MADLAN SCRAPER")
    print("="*60)
    
    scraper = MadlanScraper()
    await scraper.init_browser()
    
    try:
        properties = await scraper.scrape(
            listing_types=['buy'],
            limit=1  # Just 1 page
        )
        
        print(f"\n✅ Scraped {len(properties)} properties from Madlan")
        
        for i, prop in enumerate(properties[:3], 1):
            print(f"\n{i}. {prop.address_city} - {prop.address_street}")
            print(f"   Price: ₪{prop.price_current:,}" if prop.price_current else "   Price: N/A")
            print(f"   Rooms: {prop.rooms}, Area: {prop.square_meters} sqm")
            if prop.listing_url:
                print(f"   URL: {prop.listing_url}")
        
    except Exception as e:
        print(f"\n❌ Madlan test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await scraper.close_browser()


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SHAMAI.AI SCRAPER TESTS")
    print("="*60)
    print("\nNOTE: Set SUPABASE_URL and SUPABASE_KEY env vars to save to database")
    print("Without them, scrapers will test parsing but not save data.")
    
    # Test each scraper
    try:
        await test_onmap()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return
    
    try:
        await test_yad2()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return
    
    try:
        await test_madlan()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted")
        sys.exit(0)
