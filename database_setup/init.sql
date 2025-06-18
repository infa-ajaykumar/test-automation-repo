CREATE TABLE IF NOT EXISTS property_listings (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    price_original VARCHAR(255),
    price_usd NUMERIC(12, 2),
    currency_original VARCHAR(10),
    location_original TEXT,
    address_full TEXT,
    city VARCHAR(255),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(10),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    geom GEOMETRY(Point, 4326),
    bedrooms REAL,
    bathrooms REAL,
    area_sqft REAL,
    area_original VARCHAR(100),
    images TEXT[],
    description TEXT,
    date_posted TIMESTAMPTZ,
    date_scraped_utc TIMESTAMPTZ,
    date_processed_utc TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    source_site VARCHAR(100),
    attributes JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_timestamp' AND tgrelid = 'property_listings'::regclass) THEN
        CREATE TRIGGER set_timestamp
        BEFORE UPDATE ON property_listings
        FOR EACH ROW
        EXECUTE PROCEDURE trigger_set_timestamp();
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_listings_price_usd ON property_listings(price_usd);
CREATE INDEX IF NOT EXISTS idx_listings_city ON property_listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_source_site ON property_listings(source_site);
CREATE INDEX IF NOT EXISTS idx_listings_date_posted ON property_listings(date_posted);
CREATE INDEX IF NOT EXISTS idx_listings_geom ON property_listings USING GIST (geom);
