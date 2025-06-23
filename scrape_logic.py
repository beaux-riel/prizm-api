#!/usr/bin/env python3
import argparse
import csv
import time
import re
import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)
from cache_manager import cache_manager

# Set up logging
logger = logging.getLogger(__name__)

# Global variable for delay between requests
request_delay = 2

def validate_postal_code(postal_code):
    """Basic validation for Canadian postal codes (format: A1A 1A1 or A1A1A1)"""
    postal_code = postal_code.strip().upper().replace(" ", "")
    if len(postal_code) != 6:
        return None
    for i, char in enumerate(postal_code):
        if (i % 2 == 0 and not char.isalpha()) or (i % 2 == 1 and not char.isdigit()):
            return None
    return f"{postal_code[:3]} {postal_code[3:]}"

def extract_demographic_data(driver, postal_code):
    """Extract comprehensive demographic data from the PRIZM page"""
    demographic_data = {
        "segment_name": None,
        "segment_description": None,
        "who_they_are": None,
        "average_household_income": None,
        "education": None,
        "urbanity": None,
        "average_household_net_worth": None,
        "occupation": None,
        "diversity": None,
        "family_life": None,
        "tenure": None,
        "home_type": None
    }
    
    try:
        # First, find the segment-details container
        segment_details = None
        try:
            segment_details = driver.find_element(By.ID, "segment-details")
        except (NoSuchElementException, TimeoutException):
            # Fallback to class-based selector
            try:
                segment_details = driver.find_element(By.CSS_SELECTOR, "[id='segment-details'], .segment-details")
            except (NoSuchElementException, TimeoutException):
                print("Could not find segment-details container")
                return demographic_data
        
        print(f"Found segment-details container")
        
        # Find the active segment slide
        active_segment = None
        try:
            active_segment = segment_details.find_element(By.CSS_SELECTOR, ".segment-details__slide--active")
            print("Found active segment slide")
        except (NoSuchElementException, TimeoutException):
            print("Could not find active segment slide, using first segment slide")
            try:
                active_segment = segment_details.find_element(By.CSS_SELECTOR, ".segment-details__slide")
            except (NoSuchElementException, TimeoutException):
                print("Could not find any segment slide")
                return demographic_data
        
        # Get segment name from the active segment
        try:
            segment_title = active_segment.find_element(By.CSS_SELECTOR, ".segment-details__title h2.title")
            segment_name = segment_title.text.strip()
            # Extract just the name part (remove the number prefix if present)
            # The text contains the number and name, so we need to extract just the name
            lines = segment_name.split('\n')
            # Find the line that contains the actual segment name (not just numbers)
            for line in lines:
                line = line.strip()
                if line and not line.isdigit() and not re.match(r'^\d+$', line):
                    demographic_data["segment_name"] = line
                    break
            print(f"Found segment name: {demographic_data['segment_name']}")
        except (NoSuchElementException, TimeoutException):
            print("Could not find segment name")
        
        # Get segment description (short description) from the active segment
        short_description = ""
        try:
            desc_elem = active_segment.find_element(By.CSS_SELECTOR, ".segment-details__short-description")
            short_description = desc_elem.text.strip()
            print(f"Found short description: {short_description[:100]}...")
        except (NoSuchElementException, TimeoutException):
            print("Could not find short description")
        
        # Get "Who They Are" detailed description from the active segment
        detailed_description = ""
        try:
            who_elem = active_segment.find_element(By.CSS_SELECTOR, ".segment-details__slide__who__text")
            detailed_description = who_elem.text.strip()
            print(f"Found detailed description: {detailed_description[:100]}...")
        except (NoSuchElementException, TimeoutException):
            print("Could not find detailed description")
        
        # Concatenate short and detailed descriptions
        if short_description and detailed_description:
            demographic_data["segment_description"] = f"{short_description} | {detailed_description}"
        elif short_description:
            demographic_data["segment_description"] = short_description
        elif detailed_description:
            demographic_data["segment_description"] = detailed_description
        
        # Store the detailed description separately for who_they_are field
        demographic_data["who_they_are"] = detailed_description
        
        print(f"Final concatenated description: {demographic_data['segment_description'][:150]}...")
        
        # Extract demographic fields from the active segment using the correct structure
        demographic_fields = {
            "average_household_income": ["Average Household Income"],
            "education": ["Education"],
            "urbanity": ["Urbanity"],
            "average_household_net_worth": ["Average Household Net Worth"],
            "occupation": ["Occupation"],
            "diversity": ["Diversity"],
            "family_life": ["Family Life"],
            "tenure": ["Tenure"],
            "home_type": ["Home Type"]
        }
        
        # Find the demographic data in the list structure within the active segment
        search_container = active_segment if active_segment else segment_details
        
        for field_key, field_labels in demographic_fields.items():
            for label in field_labels:
                try:
                    # Look for the specific structure: div.react-tabs__tab-item__title containing the label, followed by a p element
                    title_elem = search_container.find_element(By.XPATH, f".//div[@class='react-tabs__tab-item__title' and text()='{label}']")
                    # Find the following p element
                    value_elem = title_elem.find_element(By.XPATH, "./following-sibling::p")
                    value = value_elem.text.strip()
                    if value and value not in ["", "N/A", "n/a", "Not Available"]:
                        demographic_data[field_key] = value
                        print(f"Found {field_key}: {value}")
                        break
                except (NoSuchElementException, TimeoutException):
                    continue
                
                if demographic_data[field_key]:
                    break
        
        # If we didn't find specific fields, try to extract all text content from segment-details
        # and parse it for common patterns
        if not any(demographic_data.values()):
            try:
                all_text = segment_details.text
                print(f"Segment details text content: {all_text[:500]}...")
                
                # Try to extract income patterns
                income_patterns = [
                    r'(?:Average Household Income|Household Income|Income)[:|\s]*\$?([\d,]+)',
                    r'\$?([\d,]+)(?:\s*(?:average|household|income))',
                ]
                for pattern in income_patterns:
                    match = re.search(pattern, all_text, re.IGNORECASE)
                    if match and not demographic_data["average_household_income"]:
                        demographic_data["average_household_income"] = f"${match.group(1)}"
                        break
                        
            except Exception as e:
                print(f"Error parsing segment details text: {e}")
        
    except Exception as e:
        print(f"Error extracting demographic data: {e}")
    
    return demographic_data

def get_segment_number(driver, postal_code):
    """Search for a postal code and extract the segment number and additional fields"""
    
    # First, check if we have cached data for this postal code
    cached_data = cache_manager.get_cached_data(postal_code)
    if cached_data:
        logger.info(f"Returning cached data for postal code: {postal_code}")
        return cached_data
    
    logger.info(f"No cached data found for {postal_code}, fetching from PRIZM website")
    
    try:
        driver.get("https://prizm.environicsanalytics.com/en-ca")
        time.sleep(5)  # let page load
        driver.save_screenshot("debug_screenshots/initial_page.png")

        # find search box
        try:
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "postal-lookup-field--hero"))
            )
        except TimeoutException:
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='text']"))
            )

        search_box.clear()
        search_box.send_keys(postal_code)
        driver.save_screenshot("debug_screenshots/postal_code_entered.png")

        # find & click search button
        try:
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.primary-cta[aria-label='Search']"))
            )
        except TimeoutException:
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'SEARCH')]"))
            )

        try:
            search_button.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", search_button)

        time.sleep(2)
        driver.save_screenshot("debug_screenshots/after_search_initiated.png")

        # Check for error message indicating invalid postal code
        try:
            error_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "p.hero__intro__error.hero__intro__error--active"))
            )
            error_text = error_element.text.strip()
            print(f"Found error message: {error_text}")
            
            # Return error result for invalid postal code
            error_result = {
                "postal_code": postal_code, 
                "segment_number": None,
                "segment_name": None,
                "segment_description": None,
                "who_they_are": None,
                "average_household_income": None,
                "education": None,
                "urbanity": None,
                "average_household_net_worth": None,
                "occupation": None,
                "diversity": None,
                "family_life": None,
                "tenure": None,
                "home_type": None,
                "status": "error: Invalid postal code - not assigned to a segment"
            }
            
            # Cache the invalid postal code result to avoid future API calls
            # Use full cache duration since invalid postal codes won't become valid
            if cache_manager.cache_data(postal_code, error_result):
                logger.info(f"Successfully cached invalid postal code result for: {postal_code}")
            else:
                logger.warning(f"Failed to cache invalid postal code result for: {postal_code}")
            
            return error_result
        except TimeoutException:
            # No error message found, continue with normal processing
            print("No error message found, proceeding with data extraction")

        # wait for result number element
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "segment-details"))
        )
        driver.save_screenshot("debug_screenshots/results_page.png")

        # Find segment details container first
        segment_details = None
        try:
            segment_details = driver.find_element(By.ID, "segment-details")
        except (NoSuchElementException, TimeoutException):
            try:
                segment_details = driver.find_element(By.CSS_SELECTOR, "[id='segment-details'], .segment-details")
            except (NoSuchElementException, TimeoutException):
                print("Could not find segment-details container for segment number extraction")

        # Find the active segment slide for extracting the segment number
        active_segment = None
        if segment_details:
            try:
                active_segment = segment_details.find_element(By.CSS_SELECTOR, ".segment-details__slide--active")
                print("Found active segment slide for number extraction")
            except (NoSuchElementException, TimeoutException):
                print("Could not find active segment slide, using first segment slide")
                try:
                    active_segment = segment_details.find_element(By.CSS_SELECTOR, ".segment-details__slide")
                except (NoSuchElementException, TimeoutException):
                    print("Could not find any segment slide")

        # Extract segment number from the active segment
        segment_number = None
        search_container = active_segment if active_segment else segment_details
        
        if search_container:
            try:
                # Look for the segment number in the title structure
                number_elem = search_container.find_element(By.CSS_SELECTOR, ".segment-details__number span:last-child")
                segment_number = number_elem.text.strip()
                print(f"Found segment number: {segment_number}")
            except (NoSuchElementException, TimeoutException):
                # Fallback: try to extract from the h2 title
                try:
                    title_elem = search_container.find_element(By.CSS_SELECTOR, ".segment-details__title h2")
                    title_text = title_elem.text.strip()
                    m = re.match(r"^\s*(\d+)\s+.+$", title_text)
                    if m:
                        segment_number = m.group(1)
                        print(f"Extracted segment number from title: {segment_number}")
                except (NoSuchElementException, TimeoutException):
                    pass

        # Fallback: search entire page if still no number found
        if not segment_number and segment_details:
            try:
                body_text = segment_details.text
                for pat in [r"Segment\s+(\d+)", r"PRIZM\s+Segment\s+(\d+)", r"(\d+)\s+[A-Z][a-z]+"]:
                    m = re.search(pat, body_text)
                    if m:
                        segment_number = m.group(1)
                        break
            except Exception:
                pass
        
        # Extract comprehensive demographic data
        demographic_data = extract_demographic_data(driver, postal_code)

        result = {
            "postal_code": postal_code, 
            "segment_number": segment_number or "Unknown",
            "segment_name": demographic_data["segment_name"],
            "segment_description": demographic_data["segment_description"],
            "who_they_are": demographic_data["who_they_are"],
            "average_household_income": demographic_data["average_household_income"],
            "education": demographic_data["education"],
            "urbanity": demographic_data["urbanity"],
            "average_household_net_worth": demographic_data["average_household_net_worth"],
            "occupation": demographic_data["occupation"],
            "diversity": demographic_data["diversity"],
            "family_life": demographic_data["family_life"],
            "tenure": demographic_data["tenure"],
            "home_type": demographic_data["home_type"],
            "status": "success"
        }
        
        # Cache the successful result
        if cache_manager.cache_data(postal_code, result):
            logger.info(f"Successfully cached data for postal code: {postal_code}")
        else:
            logger.warning(f"Failed to cache data for postal code: {postal_code}")
        
        return result

    except Exception as e:
        driver.save_screenshot(f"debug_screenshots/error_{postal_code.replace(' ', '_')}.png")
        error_result = {
            "postal_code": postal_code, 
            "segment_number": None,
            "segment_name": None,
            "segment_description": None,
            "who_they_are": None,
            "average_household_income": None,
            "education": None,
            "urbanity": None,
            "average_household_net_worth": None,
            "occupation": None,
            "diversity": None,
            "family_life": None,
            "tenure": None,
            "home_type": None,
            "status": f"error: {e}"
        }
        
        # Cache the error result to avoid future API calls for the same issue
        # Use shorter cache duration (7 days) for general errors as they might be temporary (network issues, etc.)
        if cache_manager.cache_data(postal_code, error_result, custom_duration_days=7):
            logger.info(f"Successfully cached error result for: {postal_code} (7-day duration)")
        else:
            logger.warning(f"Failed to cache error result for: {postal_code}")
        
        return error_result

def process_postal_codes(postal_codes, headless=True):
    """Process a list of postal codes and return their segment numbers"""
    results = []
    debug_folder = "debug_screenshots"
    os.makedirs(debug_folder, exist_ok=True)
    
    # Clean up expired cache entries at the start
    logger.info("Cleaning up expired cache entries...")
    expired_count = cache_manager.cleanup_expired_cache()
    if expired_count > 0:
        logger.info(f"Removed {expired_count} expired cache entries")

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    driver = None
    cache_hits = 0
    api_calls = 0
    
    try:
        print("Creating Chrome WebDriver...")
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1920, 1080)
        print("WebDriver created successfully")

        for code in postal_codes:
            formatted = validate_postal_code(code)
            if not formatted:
                print(f"{code}: error: Invalid postal code format")
                results.append({"postal_code": code, "segment_number": None, "status": "error: Invalid format"})
                continue

            print(f"\nProcessing postal code: {formatted}")
            
            # Check if we have cached data first
            cached_result = cache_manager.get_cached_data(formatted)
            if cached_result:
                print(f"Using cached data for {formatted}")
                results.append(cached_result)
                cache_hits += 1
            else:
                print(f"Fetching new data for {formatted}")
                res = get_segment_number(driver, formatted)
                results.append(res)
                api_calls += 1
                
                print(f"Waiting {request_delay}s before next request...")
                time.sleep(request_delay)

        print(f"\nProcessing complete: {cache_hits} cache hits, {api_calls} API calls")

    except Exception as e:
        print(f"Failed to create WebDriver: {e}")
        return [{"postal_code": "WebDriver Error", "segment_number": None, "status": f"error: {e}"}]
    finally:
        if driver:
            driver.quit()
            print("WebDriver closed")

    return results

def main():
    parser = argparse.ArgumentParser(description="Lookup PRIZM segment numbers for Canadian postal codes")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--postal-code", help="Single postal code to look up")
    group.add_argument("-f", "--file", help="CSV file with one postal code per line")
    parser.add_argument("-o", "--output", help="Output CSV file path")
    parser.add_argument("--no-headless", action="store_true", help="Show the browser window")
    parser.add_argument("-d", "--delay", type=int, default=2, help="Delay (seconds) between requests")
    args = parser.parse_args()

    postal_codes = []
    if args.postal_code:
        postal_codes = [args.postal_code]
    else:
        with open(args.file, newline="") as f:
            postal_codes = [row[0].strip() for row in csv.reader(f) if row]

    global request_delay
    request_delay = args.delay

    results = process_postal_codes(postal_codes, not args.no_headless)

    # ---- Only print the segment number on success ----
    for r in results:
        if r["status"] == "success":
            print(r["segment_number"])
        else:
            print(f"{r['postal_code']}: {r['status']}")

    if args.output:
        fieldnames = [
            "postal_code", "segment_number", "segment_name", "segment_description", 
            "who_they_are", "average_household_income", "education", "urbanity",
            "average_household_net_worth", "occupation", "diversity", "family_life",
            "tenure", "home_type", "status"
        ]
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()