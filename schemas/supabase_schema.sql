-- ShamaiAI Database Schema
-- PostgreSQL + PostGIS for Israeli Real Estate Intelligence
-- Date: January 2, 2026

-- Enable PostGIS for geographic data
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================================
-- TABLE 1: il_properties - Current Listings (All Sources)
-- ============================================================================

CREATE TABLE IF NOT EXISTS il_properties (
    id BIGSERIAL PRIMARY KEY,
    
    -- Source tracking
    source TEXT NOT NULL CHECK (source IN ('onmap', 'yad2', 'madlan', 'gov')),
    external_id TEXT, -- Source's unique ID
    listing_type TEXT NOT NULL CHECK (listing_type IN ('buy', 'rent', 'commercial', 'new_homes')),
    property_type TEXT, -- 'apartment', 'penthouse', 'cottage', 'duplex', etc
    
    -- Location
    address_street TEXT,
    address_city TEXT NOT NULL,
    address_neighborhood TEXT,
    location GEOGRAPHY(POINT, 4326), -- PostGIS point for lat/long
    lat DECIMAL(9,6),
    long DECIMAL(9,6),
    
    -- Pricing
    price_current INTEGER,
    price_original INTEGER, -- If price was reduced
    price_per_sqm INTEGER, -- Auto-calculated
    currency TEXT DEFAULT 'ILS' CHECK (currency IN ('ILS', 'USD')),
    
    -- Property details
    rooms DECIMAL(3,1), -- 2.5, 3, 4.5, etc
    square_meters INTEGER,
    floor INTEGER,
    building_floors INTEGER,
    year_built INTEGER,
    parking_spots INTEGER DEFAULT 0,
    
    -- Features (JSONB for flexibility)
    features JSONB, -- {"balcony": true, "elevator": true, "storage": true, "renovated": true}
    construction_status TEXT, -- 'planning', 'construction', 'completed' (for new homes)
    
    -- Media & links
    images TEXT[], -- Array of image URLs
    listing_url TEXT,
    description_he TEXT,
    description_en TEXT,
    
    -- Agent/Owner info (if available)
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    
    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'sold', 'rented', 'removed')),
    days_on_market INTEGER DEFAULT 0,
    
    -- Timestamps
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    status_changed_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT unique_external_id UNIQUE (source, external_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_il_properties_city ON il_properties(address_city);
CREATE INDEX IF NOT EXISTS idx_il_properties_neighborhood ON il_properties(address_neighborhood);
CREATE INDEX IF NOT EXISTS idx_il_properties_price ON il_properties(price_current);
CREATE INDEX IF NOT EXISTS idx_il_properties_type ON il_properties(listing_type, property_type);
CREATE INDEX IF NOT EXISTS idx_il_properties_source ON il_properties(source);
CREATE INDEX IF NOT EXISTS idx_il_properties_status ON il_properties(status);
CREATE INDEX IF NOT EXISTS idx_il_properties_rooms ON il_properties(rooms);
CREATE INDEX IF NOT EXISTS idx_il_properties_location ON il_properties USING GIST(location);

-- Trigger to update price_per_sqm
CREATE OR REPLACE FUNCTION update_price_per_sqm()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.square_meters > 0 AND NEW.price_current > 0 THEN
        NEW.price_per_sqm := ROUND(NEW.price_current::DECIMAL / NEW.square_meters);
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_il_properties_price_per_sqm
    BEFORE INSERT OR UPDATE ON il_properties
    FOR EACH ROW
    EXECUTE FUNCTION update_price_per_sqm();

-- ============================================================================
-- TABLE 2: il_transactions - Historical Sales (Tax Authority)
-- ============================================================================

CREATE TABLE IF NOT EXISTS il_transactions (
    id BIGSERIAL PRIMARY KEY,
    
    -- Source
    source TEXT DEFAULT 'tax_authority' CHECK (source IN ('tax_authority', 'madlan', 'manual')),
    transaction_id TEXT UNIQUE, -- Tax Authority's ID
    
    -- Location
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    neighborhood TEXT,
    location GEOGRAPHY(POINT, 4326),
    
    -- Transaction details
    sale_price INTEGER NOT NULL,
    sale_date DATE NOT NULL,
    buyer_name TEXT,
    seller_name TEXT,
    tax_paid INTEGER, -- Mas Rechisha (purchase tax)
    
    -- Property details
    property_type TEXT,
    rooms DECIMAL(3,1),
    square_meters INTEGER,
    price_per_sqm INTEGER,
    floor INTEGER,
    year_built INTEGER,
    
    -- Outlier detection
    is_outlier BOOLEAN DEFAULT FALSE,
    outlier_reason TEXT, -- 'assisted_living', 'partial_sale', 'multiple_buyers', 'reporting_error'
    outlier_detected_at TIMESTAMPTZ,
    
    -- Metadata
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CHECK (sale_price > 0)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_il_transactions_city ON il_transactions(city);
CREATE INDEX IF NOT EXISTS idx_il_transactions_neighborhood ON il_transactions(neighborhood);
CREATE INDEX IF NOT EXISTS idx_il_transactions_date ON il_transactions(sale_date);
CREATE INDEX IF NOT EXISTS idx_il_transactions_price ON il_transactions(sale_price);
CREATE INDEX IF NOT EXISTS idx_il_transactions_outlier ON il_transactions(is_outlier);
CREATE INDEX IF NOT EXISTS idx_il_transactions_location ON il_transactions USING GIST(location);

-- Trigger to update price_per_sqm
CREATE OR REPLACE FUNCTION update_transaction_price_per_sqm()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.square_meters > 0 AND NEW.sale_price > 0 THEN
        NEW.price_per_sqm := ROUND(NEW.sale_price::DECIMAL / NEW.square_meters);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_il_transactions_price_per_sqm
    BEFORE INSERT OR UPDATE ON il_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_transaction_price_per_sqm();

-- ============================================================================
-- TABLE 3: il_market_signals - Calculated Market Intelligence
-- ============================================================================

CREATE TABLE IF NOT EXISTS il_market_signals (
    id BIGSERIAL PRIMARY KEY,
    
    -- Area definition
    area_type TEXT NOT NULL CHECK (area_type IN ('city', 'neighborhood', 'custom')),
    area_name TEXT NOT NULL,
    area_polygon GEOGRAPHY(POLYGON, 4326), -- Custom drawn areas
    
    -- Listing type
    listing_type TEXT CHECK (listing_type IN ('buy', 'rent', 'commercial', 'new_homes', 'all')),
    
    -- Price metrics (calculated from il_properties + il_transactions)
    avg_price INTEGER,
    median_price INTEGER,
    min_price INTEGER,
    max_price INTEGER,
    avg_price_per_sqm INTEGER,
    median_price_per_sqm INTEGER,
    
    -- Volume metrics
    active_listings INTEGER DEFAULT 0,
    monthly_sales_volume INTEGER DEFAULT 0,
    transaction_count INTEGER DEFAULT 0,
    
    -- Velocity metrics
    avg_days_on_market INTEGER,
    median_days_on_market INTEGER,
    inventory_months DECIMAL(4,2), -- Months of supply at current sales rate
    
    -- Market signals (6 core indicators)
    price_trend TEXT CHECK (price_trend IN ('increasing', 'decreasing', 'stable')),
    price_change_1m_pct DECIMAL(5,2), -- 1-month price change %
    price_change_3m_pct DECIMAL(5,2), -- 3-month price change %
    price_change_1y_pct DECIMAL(5,2), -- 1-year price change %
    
    sales_velocity TEXT CHECK (sales_velocity IN ('fast', 'normal', 'slow')),
    marketing_intensity TEXT CHECK (marketing_intensity IN ('aggressive', 'normal', 'low')),
    market_status TEXT CHECK (market_status IN ('hot', 'balanced', 'stagnant', 'exhausted')),
    
    -- Additional metrics
    new_vs_used_ratio DECIMAL(4,2), -- Ratio of new homes to second-hand
    outlier_percentage DECIMAL(4,2), -- % of outlier transactions
    
    -- Timestamps
    calculation_period_start DATE NOT NULL,
    calculation_period_end DATE NOT NULL,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_area_period UNIQUE (area_type, area_name, listing_type, calculation_period_end)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_il_market_signals_area ON il_market_signals(area_type, area_name);
CREATE INDEX IF NOT EXISTS idx_il_market_signals_date ON il_market_signals(calculated_at);
CREATE INDEX IF NOT EXISTS idx_il_market_signals_type ON il_market_signals(listing_type);
CREATE INDEX IF NOT EXISTS idx_il_market_signals_polygon ON il_market_signals USING GIST(area_polygon);

-- ============================================================================
-- TABLE 4: il_custom_areas - User-Defined Regions
-- ============================================================================

CREATE TABLE IF NOT EXISTS il_custom_areas (
    id BIGSERIAL PRIMARY KEY,
    
    -- User info (for future multi-user support)
    user_id TEXT, -- Future: link to auth system
    
    -- Area definition
    area_name TEXT NOT NULL,
    area_description TEXT,
    area_polygon GEOGRAPHY(POLYGON, 4326) NOT NULL,
    
    -- Settings
    saved_filters JSONB, -- {"price_max": 2000000, "rooms_min": 3}
    alert_enabled BOOLEAN DEFAULT FALSE,
    alert_frequency TEXT CHECK (alert_frequency IN ('daily', 'weekly', 'monthly')),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    
    -- Constraints
    CONSTRAINT area_name_not_empty CHECK (LENGTH(area_name) > 0)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_il_custom_areas_user ON il_custom_areas(user_id);
CREATE INDEX IF NOT EXISTS idx_il_custom_areas_polygon ON il_custom_areas USING GIST(area_polygon);

-- ============================================================================
-- TABLE 5: il_scraping_logs - Audit Trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS il_scraping_logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Scrape session
    session_id UUID DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    listing_type TEXT,
    
    -- Results
    properties_scraped INTEGER DEFAULT 0,
    properties_new INTEGER DEFAULT 0,
    properties_updated INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- Performance
    duration_seconds INTEGER,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    
    -- Errors (if any)
    error_log JSONB, -- Array of error messages
    
    -- Status
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    
    -- Metadata
    triggered_by TEXT DEFAULT 'cron' CHECK (triggered_by IN ('cron', 'manual', 'api')),
    github_run_id TEXT -- If triggered by GitHub Actions
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_il_scraping_logs_source ON il_scraping_logs(source);
CREATE INDEX IF NOT EXISTS idx_il_scraping_logs_start ON il_scraping_logs(start_time);
CREATE INDEX IF NOT EXISTS idx_il_scraping_logs_status ON il_scraping_logs(status);

-- ============================================================================
-- VIEWS - Convenient Data Access
-- ============================================================================

-- View 1: Active listings with valuations
CREATE OR REPLACE VIEW il_active_listings AS
SELECT 
    p.*,
    m.avg_price_per_sqm AS neighborhood_avg_price_per_sqm,
    m.price_trend AS neighborhood_price_trend,
    m.market_status AS neighborhood_market_status,
    CASE 
        WHEN p.price_per_sqm < m.avg_price_per_sqm * 0.9 THEN 'underpriced'
        WHEN p.price_per_sqm > m.avg_price_per_sqm * 1.1 THEN 'overpriced'
        ELSE 'fair'
    END AS price_assessment
FROM il_properties p
LEFT JOIN il_market_signals m 
    ON p.address_neighborhood = m.area_name 
    AND m.area_type = 'neighborhood'
    AND m.listing_type = p.listing_type
    AND m.calculated_at = (
        SELECT MAX(calculated_at) 
        FROM il_market_signals 
        WHERE area_name = p.address_neighborhood
    )
WHERE p.status = 'active';

-- View 2: Recent transactions (non-outliers)
CREATE OR REPLACE VIEW il_recent_transactions AS
SELECT 
    t.*,
    EXTRACT(YEAR FROM t.sale_date) AS sale_year,
    EXTRACT(MONTH FROM t.sale_date) AS sale_month
FROM il_transactions t
WHERE 
    t.is_outlier = FALSE
    AND t.sale_date >= CURRENT_DATE - INTERVAL '2 years'
ORDER BY t.sale_date DESC;

-- View 3: Market summary by city
CREATE OR REPLACE VIEW il_city_summary AS
SELECT 
    city,
    listing_type,
    COUNT(*) AS total_listings,
    AVG(price_current) AS avg_price,
    AVG(price_per_sqm) AS avg_price_per_sqm,
    AVG(rooms) AS avg_rooms,
    AVG(days_on_market) AS avg_days_on_market,
    MIN(price_current) AS min_price,
    MAX(price_current) AS max_price
FROM il_active_listings
WHERE city IS NOT NULL
GROUP BY city, listing_type
ORDER BY city, listing_type;

-- ============================================================================
-- FUNCTIONS - Helper Functions
-- ============================================================================

-- Function: Get properties within custom polygon
CREATE OR REPLACE FUNCTION get_properties_in_area(polygon_geojson TEXT, listing_type_filter TEXT DEFAULT NULL)
RETURNS TABLE (
    id BIGINT,
    address_street TEXT,
    price_current INTEGER,
    rooms DECIMAL,
    square_meters INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.address_street,
        p.price_current,
        p.rooms,
        p.square_meters
    FROM il_properties p
    WHERE 
        p.status = 'active'
        AND ST_Within(p.location::geometry, ST_GeomFromGeoJSON(polygon_geojson)::geometry)
        AND (listing_type_filter IS NULL OR p.listing_type = listing_type_filter);
END;
$$ LANGUAGE plpgsql;

-- Function: Calculate market signals for an area
CREATE OR REPLACE FUNCTION calculate_market_signals(
    p_area_type TEXT,
    p_area_name TEXT,
    p_listing_type TEXT,
    p_start_date DATE DEFAULT CURRENT_DATE - INTERVAL '30 days',
    p_end_date DATE DEFAULT CURRENT_DATE
)
RETURNS VOID AS $$
BEGIN
    -- This is a placeholder - actual calculation logic would be in Python
    -- Insert calculated signals into il_market_signals table
    RAISE NOTICE 'Calculate market signals for % (%) from % to %', p_area_name, p_area_type, p_start_date, p_end_date;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA - Sample Cities
-- ============================================================================

-- This would be populated by the scraper
-- Sample structure only

-- ============================================================================
-- GRANTS - Security (adjust based on your needs)
-- ============================================================================

-- Grant read access to anonymous users (for public API)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- Grant full access to authenticated users
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;

-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Auto-vacuum settings for performance
ALTER TABLE il_properties SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE il_transactions SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE il_market_signals SET (autovacuum_vacuum_scale_factor = 0.1);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

-- Verify installation
SELECT 
    'ShamaiAI Schema Installed' AS status,
    COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name LIKE 'il_%';
