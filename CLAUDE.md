# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the PRIZM Code Lookup API - a Flask-based web application that scrapes demographic data from Environics Analytics PRIZM website. The API provides REST endpoints for looking up PRIZM codes by Canadian postal codes, with intelligent caching to work within the 10 lookups/day limit.

## Key Commands

### Running the Application

```bash
# Direct Python execution
pip install -r requirements.txt
python app.py
# OR
./run_server.sh

# Docker (recommended)
docker-compose up -d
docker-compose down
```

The server runs on port 8080 by default.

### Running Tests

```bash
# Run all tests
python test_prizm_api.py

# Run specific test suites
python test_comprehensive_data.py
python test_error_handling.py
python test_invalid_caching.py
```

### Cache Management

```bash
# View cache statistics
python cache_cli.py stats

# Clean up expired entries
python cache_cli.py cleanup

# Clear all cache
python cache_cli.py clear --confirm

# Check/retrieve cached data
python cache_cli.py check "V8A 2P4"
python cache_cli.py get "V8A 2P4"

# Delete specific postal code from cache
python cache_cli.py delete "V8A 2P4"
```

## Architecture Overview

### Core Components

1. **app.py**: Main Flask application
   - API endpoints: `/api/prizm` (single), `/api/prizm/batch` (multiple)
   - Cache management endpoints: `/api/cache/*`
   - Serves web interface at root `/`
   - Manages Selenium WebDriver lifecycle

2. **scrape_logic.py**: Web scraping engine
   - Validates Canadian postal codes
   - Interacts with PRIZM website using Selenium
   - Extracts demographic data from search results
   - Handles various error conditions

3. **cache_manager.py**: SQLite-based caching system
   - 90-day cache for successful lookups
   - Separate caching for invalid postal codes
   - Thread-safe operations
   - Automatic cleanup of expired entries

### Data Flow

1. Request arrives at Flask endpoint
2. Cache is checked for existing data
3. If not cached, Selenium scrapes PRIZM website
4. Results are cached and returned
5. Invalid postal codes are cached separately to avoid re-scraping

### Key Design Decisions

- **Selenium WebDriver**: Used because PRIZM site requires JavaScript execution
- **SQLite Cache**: Chosen for simplicity and portability
- **90-day Cache Duration**: Balances data freshness with API limit constraints
- **Batch Processing**: Supports parallel lookups to improve performance
- **Mock Mode**: Available for testing without actual web scraping

## API Endpoints

- `GET /api/prizm?postal_code=V8A2P4` - Single lookup
- `POST /api/prizm/batch` - Multiple lookups (JSON body with postal_codes array)
- `GET /api/cache/stats` - Cache statistics
- `POST /api/cache/cleanup` - Remove expired entries
- `POST /api/cache/clear` - Clear entire cache
- `DELETE /api/cache/delete/<postal_code>` - Delete specific postal code
- `GET /health` - Health check

## Testing Strategy

The project includes comprehensive test coverage:
- Basic API functionality tests
- Comprehensive data extraction validation
- Error handling scenarios
- Invalid postal code caching behavior

When adding new features, ensure tests cover both success and failure cases.

## Docker Deployment

The application is containerized with:
- Python 3.9-slim base image
- Chromium browser for headless scraping
- Environment variables configured for Chrome paths
- Volume mounting for templates directory

## Important Notes

1. **API Rate Limit**: The PRIZM website allows only 10 lookups per day per IP
2. **Postal Code Format**: Canadian postal codes must be 6 characters (e.g., "V8A2P4")
3. **Cache Database**: `prizm_cache.db` stores all cached results
4. **No Linting**: Project doesn't have linting configuration - use standard Python conventions
5. **Dependencies**: Selenium requires Chrome/Chromium browser to be installed