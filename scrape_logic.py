#!/usr/bin/env python3
import argparse
import csv
import time
import re
import os
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

def get_segment_number(driver, postal_code):
    """Search for a postal code and extract the segment number"""
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

        # wait for result number element
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "segment-details__number"))
        )
        driver.save_screenshot("debug_screenshots/results_page.png")

        # try extracting from a heading first
        segment_number = None
        for sel in [
            ".segment-details__name",
            ".segment-name",
            ".segment-title",
            ".profile-segment h1",
            ".profile-segment h2",
            ".segment-details h1",
            ".segment-details h2",
        ]:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                text = el.text.strip()
                m = re.match(r"^\s*(\d+)\s+.+$", text)
                if m:
                    segment_number = m.group(1)
                    break
            if segment_number:
                break

        # fallback: grab the standalone number element
        if not segment_number:
            num_el = driver.find_element(By.CLASS_NAME, "segment-details__number")
            digits = re.sub(r"\D", "", num_el.text or "")
            if digits:
                segment_number = digits

        # last resort: search page text
        if not segment_number:
            body = driver.find_element(By.TAG_NAME, "body").text
            for pat in [r"Segment\s+(\d+)", r"PRIZM\s+Segment\s+(\d+)"]:
                m = re.search(pat, body)
                if m:
                    segment_number = m.group(1)
                    break

        return {"postal_code": postal_code, "segment_number": segment_number or "Unknown", "status": "success"}

    except Exception as e:
        driver.save_screenshot(f"debug_screenshots/error_{postal_code.replace(' ', '_')}.png")
        return {"postal_code": postal_code, "segment_number": None, "status": f"error: {e}"}

def process_postal_codes(postal_codes, headless=True):
    """Process a list of postal codes and return their segment numbers"""
    results = []
    debug_folder = "debug_screenshots"
    os.makedirs(debug_folder, exist_ok=True)

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
            res = get_segment_number(driver, formatted)
            results.append(res)

            print(f"Waiting {request_delay}s before next request...")
            time.sleep(request_delay)

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
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["postal_code", "segment_number", "status"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()