# PRIZM Code Lookup API

This tool provides an API endpoint for users to submit Canadian postal codes and retrieve the associated PRIZM codes from Environics Analytics.

## Website

A static demonstration of the API is available on GitHub Pages at:
https://beaux-riel.github.io/prizm-api/

The GitHub Pages site includes:

- Static demonstration of the API interface
- API documentation
- Project information

Note that the actual API functionality requires running the server locally or deploying it to your own server.

## Features

- **Intelligent Caching System**: Data is cached locally for up to 3 months to reduce API calls to the PRIZM website (limited to 10 calls per day)
- Single postal code lookup via GET request
- Batch postal code lookup via POST request
- Web interface for easy testing with cache status indicators
- Parallel processing for batch requests
- Cache management endpoints for monitoring and maintenance
- Comprehensive demographic data extraction including:
  - PRIZM segment number and name
  - Detailed segment description
  - Average household income and net worth
  - Education level, occupation, and urbanity
  - Family life, tenure, and home type information
  - Diversity metrics
  - Complete "Who They Are" lifestyle descriptions

## Cache System

The API includes an intelligent caching system that:

- **Reduces API calls**: Previously fetched data is stored locally for 3 months
- **Improves performance**: Cached responses are returned instantly
- **Automatic cleanup**: Expired cache entries are automatically removed
- **Cache indicators**: Web interface shows whether data came from cache or live API
- **Management tools**: Built-in cache statistics and management endpoints
- **Invalid postal code caching**: Invalid and malformed postal codes are cached to prevent repeated API calls
- **Smart cache durations**: Different error types use appropriate cache durations (successful results: 90 days, invalid postal codes: 90 days, general errors: 7 days)

### Cache Management

- **View cache stats**: `GET /api/cache/stats`
- **Cleanup expired entries**: `POST /api/cache/cleanup`
- **Clear all cache**: `POST /api/cache/clear`
- **Check if postal code is cached**: `GET /api/cache/check/<postal_code>`

### Command Line Cache Management

Use the included CLI tool for cache management:

```bash
# View cache statistics
python cache_cli.py stats

# Clean up expired entries
python cache_cli.py cleanup

# Clear all cache (use with caution)
python cache_cli.py clear --confirm

# Check if a postal code is cached
python cache_cli.py check "V8A 2P4"

# Get cached data for a postal code
python cache_cli.py get "V8A 2P4"
```

### Testing Cache Functionality

A test script is included to verify that invalid postal codes are properly cached:

```bash
# Test invalid postal code caching (requires requests package)
python test_invalid_caching.py
```

This script tests various invalid postal codes to ensure they are cached properly and subsequent requests return instantly from cache.

## Requirements

- Python 3.6+
- Flask
- Selenium
- Chrome/Chromium browser
- WebDriver Manager

## Installation

### Option 1: Direct Installation

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Ensure Chrome or Chromium is installed on your system

### Option 2: Docker Installation (Recommended)

1. Clone this repository
2. Build and run using Docker Compose:
   ```
   docker-compose up -d
   ```

## Usage

### Running the Server

#### Without Docker:

```bash
./run_server.sh
```

Or:

```bash
python app.py
```

The server will start on port 8080 by default.

#### With Docker:

```bash
docker-compose up -d
```

This will start the server on port 8080.

### API Endpoints

#### Single Postal Code Lookup

```
GET /api/prizm?postal_code=V8A2P4
```

Response:

```json
{
  "postal_code": "V8A 2P4",
  "prizm_code": "62",
  "segment_name": "Boomer Bliss",
  "segment_description": "Older, financially comfortable, suburban couples and families",
  "who_they_are": "Detailed description of the demographic segment lifestyle and characteristics",
  "average_household_income": "$163,097",
  "education": "University/College",
  "urbanity": "Suburban",
  "average_household_net_worth": "$1,513,488",
  "occupation": "White Collar/Service Sector",
  "diversity": "Low",
  "family_life": "Couples/Families",
  "tenure": "Own",
  "home_type": "Single Detached",
  "status": "success"
}
```

#### Batch Postal Code Lookup

```
POST /api/prizm/batch
Content-Type: application/json

{
  "postal_codes": ["V8A2P4", "M5V2H1", "K1A0A9"]
}
```

Response:

```json
{
  "results": [
    {
      "postal_code": "V8A 2P4",
      "prizm_code": "62",
      "segment_name": "Boomer Bliss",
      "segment_description": "Older, financially comfortable, suburban couples and families",
      "who_they_are": "Detailed description of the demographic segment...",
      "average_household_income": "$163,097",
      "education": "University/College",
      "urbanity": "Suburban",
      "average_household_net_worth": "$1,513,488",
      "occupation": "White Collar/Service Sector",
      "diversity": "Low",
      "family_life": "Couples/Families",
      "tenure": "Own",
      "home_type": "Single Detached",
      "status": "success"
    },
    {
      "postal_code": "M5V 2H1",
      "prizm_code": "01",
      "segment_name": "Urban Elite",
      "average_household_income": "$125,000",
      "average_household_net_worth": "$850,000",
      "education": "University/Graduate",
      "urbanity": "Urban Core",
      "occupation": "Executive/Professional",
      "diversity": "High",
      "family_life": "Singles/Couples",
      "tenure": "Own",
      "home_type": "High Rise Condo",
      "status": "success"
    },
    {
      "postal_code": "K1A 0A9",
      "prizm_code": "11",
      "segment_name": "Government Workers",
      "average_household_income": "$95,000",
      "average_household_net_worth": "$650,000",
      "education": "University/College",
      "urbanity": "Suburban",
      "occupation": "Government/Public Service",
      "diversity": "Medium",
      "family_life": "Families",
      "tenure": "Own",
      "home_type": "Single Detached",
      "status": "success"
    }
  ],
  "total": 3,
  "successful": 3
}
```

### Web Interface

A simple web interface is available at the root URL (`/`) for testing the API directly in your browser.

## How It Works

1. The API receives a postal code request
2. It uses Selenium to navigate to the PRIZM website
3. It enters the postal code in the search field
4. It extracts comprehensive demographic data from the search results including:
   - PRIZM segment number and name
   - Detailed descriptions and lifestyle information
   - Financial data (income, net worth)
   - Social and demographic characteristics
   - Housing and location preferences
5. It returns the complete demographic profile to the user

## Mock Mode

The application includes a mock mode that returns predefined PRIZM codes without actually scraping the website. This is useful for:

- Development and testing
- Environments where Chrome/Chromium is not available or has version compatibility issues
- Demonstration purposes

When in mock mode, the API will return a response with a "note" field indicating that the data is mock data.

## Notes

- The tool uses headless Chrome/Chromium for web scraping in production mode
- Batch requests are processed sequentially to avoid browser issues
- Error handling is implemented for invalid postal codes or scraping issues
- The application can be containerized using Docker for easy deployment
