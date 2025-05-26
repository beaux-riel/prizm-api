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

- Single postal code lookup via GET request
- Batch postal code lookup via POST request
- Web interface for easy testing
- Parallel processing for batch requests

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
      "status": "success"
    },
    {
      "postal_code": "M5V 2H1",
      "prizm_code": "01",
      "status": "success"
    },
    {
      "postal_code": "K1A 0A9",
      "prizm_code": "11",
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
4. It extracts the PRIZM code from the search results
5. It returns the result to the user

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