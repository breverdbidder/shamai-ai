"""
ShamaiAI Orchestrator - LangGraph Multi-Source Scraping Pipeline
Coordinates scraping from OnMap, Yad2, and Madlan
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import scrapers
try:
    from scrapers.onmap_scraper import OnMapScraper
    from scrapers.yad2_scraper import Yad2Scraper
    from scrapers.madlan_scraper import MadlanScraper
except ImportError:
    # Fallback for different import paths
    from src.scrapers.onmap_scraper import OnMapScraper
    from src.scrapers.yad2_scraper import Yad2Scraper
    from src.scrapers.madlan_scraper import MadlanScraper


class ShamaiAIOrchestrator:
    """
    Orchestrates multi-source Israeli real estate scraping
    
    Pipeline Stages:
    1. Initialize - Set targets (cities, listing types)
    2. OnMap - Scrape 4 listing types
    3. Yad2 - Scrape residential + commercial
    4. Madlan - Scrape consumer listings
    5. Finalize - Generate reports, log stats
    """
    
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.github_run_id = os.getenv('GITHUB_RUN_ID')
        
        # Parse environment inputs
        self.cities = self._parse_env_list('CITIES', default=['תל אביב', 'חיפה', 'ירושלים'])
        self.listing_types = self._parse_env_list('LISTING_TYPES', default=['buy', 'rent'])
        
        # Stats tracking
        self.stats = {
            'session_id': self.session_id,
            'start_time': datetime.now(),
            'sources_completed': [],
            'sources_failed': [],
            'total_properties': 0,
            'properties_by_source': {},
            'errors': []
        }
        
        logger.info(f"Initialized ShamaiAI Orchestrator - Session: {self.session_id}")
        logger.info(f"Cities: {self.cities}")
        logger.info(f"Listing types: {self.listing_types}")
    
    def _parse_env_list(self, env_var: str, default: List[str]) -> List[str]:
        """Parse comma-separated environment variable"""
        value = os.getenv(env_var, '')
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return default
    
    async def stage_1_initialize(self) -> Dict[str, Any]:
        """Stage 1: Initialize targets and validate environment"""
        logger.info("=== STAGE 1: Initialize ===")
        
        # Verify required environment variables
        required_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        # Optional: ANTHROPIC_API_KEY (for AI features)
        if os.getenv('ANTHROPIC_API_KEY'):
            logger.info("✓ ANTHROPIC_API_KEY found - AI features enabled")
        else:
            logger.warning("⚠ ANTHROPIC_API_KEY not set - AI features disabled")
        
        logger.info("✓ Environment validated")
        logger.info(f"✓ Targets set: {len(self.cities)} cities, {len(self.listing_types)} listing types")
        
        return {'status': 'initialized', 'cities': self.cities, 'listing_types': self.listing_types}
    
    async def stage_2_scrape_onmap(self) -> Dict[str, Any]:
        """Stage 2: Scrape OnMap.co.il"""
        logger.info("=== STAGE 2: Scrape OnMap ===")
        
        try:
            scraper = OnMapScraper()
            stats = await scraper.run(
                listing_types=self.listing_types,
                cities=self.cities,
                limit=5  # 5 scrolls per listing type
            )
            
            self.stats['sources_completed'].append('onmap')
            self.stats['properties_by_source']['onmap'] = stats.get('properties_scraped', 0)
            self.stats['total_properties'] += stats.get('properties_scraped', 0)
            
            logger.info(f"✓ OnMap: {stats.get('properties_scraped', 0)} properties scraped")
            return stats
            
        except Exception as e:
            logger.error(f"OnMap scraping failed: {e}")
            self.stats['sources_failed'].append('onmap')
            self.stats['errors'].append(f"onmap: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def stage_3_scrape_yad2(self) -> Dict[str, Any]:
        """Stage 3: Scrape Yad2.co.il"""
        logger.info("=== STAGE 3: Scrape Yad2 ===")
        
        try:
            scraper = Yad2Scraper()
            stats = await scraper.run(
                listing_types=self.listing_types,
                cities=self.cities,
                limit=3  # 3 pages per listing type
            )
            
            self.stats['sources_completed'].append('yad2')
            self.stats['properties_by_source']['yad2'] = stats.get('properties_scraped', 0)
            self.stats['total_properties'] += stats.get('properties_scraped', 0)
            
            logger.info(f"✓ Yad2: {stats.get('properties_scraped', 0)} properties scraped")
            return stats
            
        except Exception as e:
            logger.error(f"Yad2 scraping failed: {e}")
            self.stats['sources_failed'].append('yad2')
            self.stats['errors'].append(f"yad2: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def stage_4_scrape_madlan(self) -> Dict[str, Any]:
        """Stage 4: Scrape Madlan.co.il"""
        logger.info("=== STAGE 4: Scrape Madlan ===")
        
        try:
            scraper = MadlanScraper()
            stats = await scraper.run(
                listing_types=self.listing_types,
                cities=self.cities,
                limit=2  # 2 pages per listing type
            )
            
            self.stats['sources_completed'].append('madlan')
            self.stats['properties_by_source']['madlan'] = stats.get('properties_scraped', 0)
            self.stats['total_properties'] += stats.get('properties_scraped', 0)
            
            logger.info(f"✓ Madlan: {stats.get('properties_scraped', 0)} properties scraped")
            return stats
            
        except Exception as e:
            logger.error(f"Madlan scraping failed: {e}")
            self.stats['sources_failed'].append('madlan')
            self.stats['errors'].append(f"madlan: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def stage_5_finalize(self) -> Dict[str, Any]:
        """Stage 5: Finalize (generate reports, cleanup)"""
        logger.info("=== STAGE 5: Finalize ===")
        
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        logger.info("=" * 60)
        logger.info("SCRAPING SESSION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info(f"Total properties: {self.stats['total_properties']}")
        
        # Properties by source
        for source, count in self.stats['properties_by_source'].items():
            logger.info(f"  - {source}: {count}")
        
        logger.info(f"Sources completed: {', '.join(self.stats['sources_completed'])}")
        
        if self.stats['sources_failed']:
            logger.warning(f"Sources failed: {', '.join(self.stats['sources_failed'])}")
        
        if self.stats['errors']:
            logger.error(f"Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.error(f"  - {error}")
        
        logger.info("=" * 60)
        
        return self.stats
    
    async def run(self):
        """Execute the full pipeline"""
        try:
            # Run all stages sequentially
            await self.stage_1_initialize()
            await self.stage_2_scrape_onmap()
            await self.stage_3_scrape_yad2()
            await self.stage_4_scrape_madlan()
            await self.stage_5_finalize()
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.stats['end_time'] = datetime.now()
            self.stats['errors'].append(f"pipeline: {str(e)}")
            raise


async def main():
    """Main entry point"""
    logger.info("Starting ShamaiAI Orchestrator...")
    
    try:
        orchestrator = ShamaiAIOrchestrator()
        stats = await orchestrator.run()
        
        # Exit with appropriate code
        if stats.get('errors'):
            logger.error("Scraping completed with errors")
            sys.exit(1)
        else:
            logger.info("Scraping completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
