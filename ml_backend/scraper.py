import requests
from bs4 import BeautifulSoup
import logging
import requests
from bs4 import BeautifulSoup
import time
from random import randint
from datetime import datetime
import re
from lxml import html
import pandas as pd
import os
import concurrent.futures
import threading
import queue

# ------------------------------------------------
# Setup Logging: Log to file and console for live monitoring
# ------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# File handler: logs INFO and above to a file
file_handler = logging.FileHandler('scraping.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console (stream) handler: logs DEBUG and above to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ------------------------------------------------
# Constants and configuration
# ------------------------------------------------
BASE_URL_IKMAN = "https://ikman.lk"
BASE_URL_LANKA = "https://www.lankapropertyweb.com"
MAX_PAGES = 20 
MAX_WORKERS = 20 
DETAIL_WORKERS = 40 
PAGE_SCRAPE_DELAY = (0, 1) 
DETAIL_SCRAPE_DELAY = (0, 1) 

# Thread-safe queue for data to be appended to sheets
data_queue = queue.Queue()

# Locks for thread safety
sheet_lock = threading.Lock()
log_lock = threading.Lock()

# Thread-local storage for session reuse
thread_local = threading.local()

# Global flag to insert header only on first append
HEADER_ADDED = False

# ------------------------------------------------
# Thread-safe logging
# ------------------------------------------------
def safe_log(level, message):
    with log_lock:
        if level == 'debug':
            logger.debug(message)
        elif level == 'info':
            logger.info(message)
        elif level == 'warning':
            logger.warning(message)
        elif level == 'error':
            logger.error(message)

# ------------------------------------------------
# Session Management for Thread Safety
# ------------------------------------------------
def get_session():
    """Get a thread-local session for making requests"""
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

# ------------------------------------------------
# Helper Functions
# ------------------------------------------------
def fetch_html(url, max_retries=5, retry_delay=5):
    """Fetch HTML using a retry mechanism with random user agents."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...',
        'Mozilla/5.0 (X11; Linux x86_64)...',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0)...'
    ]
    session = get_session()
    
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': user_agents[randint(0, len(user_agents)-1)],
                'Accept': 'text/html,application/xhtml+xml,application/xml',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive'
            }
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            if '<html' in response.text.lower():
                safe_log('debug', f"Successfully fetched URL: {url}")
                return response.text
            else:
                safe_log('warning', f"Non-HTML response from {url}")
        except requests.exceptions.RequestException as e:
            safe_log('warning', f"Attempt {attempt+1} failed for {url}: {e}")
        
        sleep_time = retry_delay * (attempt + 1)
        safe_log('info', f"Retrying in {sleep_time} seconds...")
        time.sleep(sleep_time)
    
    safe_log('error', f"All {max_retries} attempts failed for {url}")
    return None

def clean_price(price, website):
    if not price or price == "N/A":
        return "N/A"
    if website == "ikman":
        return re.sub(r'[Rs.,/month]', '', price).strip()
    elif website == "lankaweb":
        cleaned = re.sub(r'[Rs.\$,() ]', '', price).strip()
        return cleaned.split(" ")[0] if " " in cleaned else cleaned

def clean_sqft(sqft):
    if not sqft or sqft == "N/A":
        return "N/A"
    return re.sub(r'[, sqft]', '', sqft).strip()

def remove_parentheses(value):
    return re.sub(r'\(.*?\)', '', value).strip() if isinstance(value, str) else value

# ------------------------------------------------
# Parsing Functions for Ikman.lk
# ------------------------------------------------
def parse_main_page_ikman(html_content):
    """Parse the main listing page of Ikman.lk."""
    soup = BeautifulSoup(html_content, 'html.parser')
    ads = []
    ad_selectors = ['li.normal--2QYVk', 'li.normal', 'div.card', 'div.listing-card']
    ad_tags = []
    
    for selector in ad_selectors:
        ad_tags = soup.select(selector)
        if ad_tags:
            safe_log('info', f"Found Ikman ads using selector: {selector}")
            break
    
    if not ad_tags:
        safe_log('warning', "No Ikman ads found.")
        return []
    
    for ad in ad_tags:
        try:
            title = "N/A"
            for sel in ['h2.heading--2eONR', 'h2.heading', '.title', '.ad-title']:
                tag = ad.select_one(sel)
                if tag:
                    title = tag.text.strip()
                    break
            
            link = "N/A"
            for sel in ['a.card-link--3ssYv', 'a.card-link', 'a[href*="/en/ad/"]', 'a.ad-link']:
                tag = ad.select_one(sel)
                if tag and tag.get('href'):
                    href = tag['href']
                    link = BASE_URL_IKMAN + href if href.startswith('/') else href
                    break
            
            image = "No Image Available"
            for sel in ['img', '.card-img img', '.thumbnail img']:
                tag = ad.select_one(sel)
                if tag:
                    image = tag.get('src') or tag.get('data-src') or image
                    break
            
            if title != "N/A" and link != "N/A":
                ads.append({
                    'Title': remove_parentheses(title),
                    'Link': link,
                    'Sqft': 'N/A',
                    'Property Type': 'N/A',
                    'Location': 'N/A',
                    'Address': 'N/A',
                    'Image URL': image,
                    'Price': 'N/A',
                    'Status': 'N/A',
                    'Source': 'Ikman.lk',
                    'Scrape Date': datetime.now().strftime("%Y-%m-%d")
                })
        except Exception as e:
            safe_log('error', f"Error parsing an Ikman ad: {e}")
    
    return ads

def parse_detailed_page_ikman(url):
    """Parse the detailed property page of Ikman.lk."""
    html_content = fetch_html(url)
    if not html_content:
        return {}
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tree = html.fromstring(html_content)
        details = {}
        
        details['Location'] = "N/A"
        for sel in ['a.subtitle-location-link--1q5zA span', 'a.subtitle-location-link span', '.location span', '.ad-location']:
            tag = soup.select_one(sel)
            if tag:
                details['Location'] = tag.text.strip()
                break
        
        # Extract square footage
        sqft_found = False
        for xp in ['//*[@id="app-wrapper"]//div[contains(text(), "sqft")]/text()', 
                   '//div[contains(@class, "value") and contains(text(), "sqft")]/text()']:
            result = tree.xpath(xp)
            if result and "sqft" in " ".join(map(str, result)):
                details['Sqft'] = clean_sqft(result[0])
                sqft_found = True
                break
        
        if not sqft_found:
            for div in soup.find_all('div'):
                text = div.get_text().strip()
                if 'sqft' in text:
                    match = re.search(r'(\d[\d,]*)\s*sqft', text)
                    if match:
                        details['Sqft'] = clean_sqft(match.group(1))
                        sqft_found = True
                        break
        
        if not sqft_found:
            details['Sqft'] = "N/A"
        
        # Extract Address
        address_found = False
        for xp in ['//*[@id="app-wrapper"]//div[contains(@class, "value") and not(contains(text(), "sqft"))]/text()']:
            result = tree.xpath(xp)
            if result:
                details['Address'] = result[0].strip()
                address_found = True
                break
        
        if not address_found:
            for div in soup.find_all(['div', 'span']):
                if 'sqft' in div.get_text():
                    continue
                text = div.get_text().strip()
                if any(keyword in text.lower() for keyword in ['road', 'street', 'lane', 'avenue', 'colombo', 'kandy']):
                    if len(text) > 5:
                        details['Address'] = text
                        address_found = True
                        break
        
        if not address_found:
            details['Address'] = "N/A"
        
        # Extract price
        details['Price'] = "N/A"
        for sel in ['div.amount--3NTpl', 'div.amount', '.price', '.ad-price', 'span.amount']:
            tag = soup.select_one(sel)
            if tag:
                details['Price'] = clean_price(tag.text.strip(), "ikman")
                break
        
        # Extract property type
        details['Property Type'] = "N/A"
        for sel in ['a.ad-meta-desktop--1Zyra span', 'a.ad-meta-desktop span', '.property-type', '.category span']:
            tag = soup.select_one(sel)
            if tag:
                details['Property Type'] = tag.text.strip()
                break
        
        if details['Property Type'] == "N/A":
            title_text = soup.title.string if soup.title else ""
            if 'office' in url.lower() or 'office' in title_text.lower():
                details['Property Type'] = "Office Space"
            elif 'shop' in url.lower() or 'shop' in title_text.lower():
                details['Property Type'] = "Shop"
            elif 'warehouse' in url.lower() or 'warehouse' in title_text.lower():
                details['Property Type'] = "Warehouse"
            elif 'building' in url.lower() or 'building' in title_text.lower():
                details['Property Type'] = "Building"
            else:
                details['Property Type'] = "Commercial Property"
        
        return details
    except Exception as e:
        safe_log('error', f"Error parsing Ikman detail page {url}: {e}")
        return {}

# ------------------------------------------------
# Parsing Functions for LankaPropertyWeb.com
# ------------------------------------------------
def parse_main_page_lanka(html_content):
    """Parse the main listing page of LankaPropertyWeb.com."""
    soup = BeautifulSoup(html_content, 'html.parser')
    ads = []
    selectors = ['article.listing-item', '.property-listing-item', '.property-card', '.listing']
    ad_tags = []
    
    for sel in selectors:
        ad_tags = soup.select(sel)
        if ad_tags:
            safe_log('info', f"Found Lanka ads using selector: {sel}")
            break
    
    if not ad_tags:
        safe_log('warning', "No Lanka ads found.")
        return []
    
    for ad in ad_tags:
        try:
            title = "N/A"
            for sel in ['h4.listing-title', '.listing-title', '.property-title', 'h3', 'h4 a']:
                tag = ad.select_one(sel)
                if tag:
                    title = tag.text.strip()
                    break
            
            sqft = "N/A"
            for sel in ['span.count', '.sqft', '.area', '.property-area']:
                tag = ad.select_one(sel)
                if tag:
                    sqft = tag.text.strip()
                    break
            
            property_type = "N/A"
            for sel in ['span.type', '.property-type', '.type-tag']:
                tag = ad.select_one(sel)
                if tag:
                    property_type = tag.text.strip()
                    break
            
            link = "N/A"
            for sel in ['a.listing-header', 'a.property-link', '.listing-title a', 'h4 a']:
                tag = ad.select_one(sel)
                if tag and tag.get('href'):
                    href = tag['href']
                    if href.startswith('/'):
                        link = BASE_URL_LANKA + href
                    elif not href.startswith('http'):
                        link = BASE_URL_LANKA + '/' + href
                    else:
                        link = href
                    break
            
            image_url = "No Image Available"
            for sel in ['img', '.property-image img', '.listing-image img']:
                tag = ad.select_one(sel)
                if tag:
                    image_url = tag.get('src') or tag.get('data-src') or image_url
                    break
            
            price = "N/A"
            for sel in ['.price', '.listing-price', '.property-price']:
                tag = ad.select_one(sel)
                if tag:
                    price = clean_price(tag.text.strip(), "lankaweb")
                    break
            
            if title != "N/A" and link != "N/A":
                ads.append({
                    'Title': remove_parentheses(title),
                    'Sqft': clean_sqft(sqft),
                    'Property Type': property_type,
                    'Link': link,
                    'Location': 'N/A',
                    'Address': 'N/A',
                    'Image URL': image_url,
                    'Price': price,
                    'Status': 'N/A',
                    'Source': 'Lankapropertyweb.com',
                    'Scrape Date': datetime.now().strftime("%Y-%m-%d")
                })
        except Exception as e:
            safe_log('error', f"Error parsing Lanka ad: {e}")
    
    return ads

def parse_detailed_page_lanka(url):
    """Parse the detailed property page of LankaPropertyWeb.com."""
    html_content = fetch_html(url)
    if not html_content:
        return {}
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tree = html.fromstring(html_content)
        details = {}
        
        details['Location'] = "N/A"
        for sel in ['div.location.title-light-1', 'div.location', '.property-location', '.address-location']:
            tag = soup.select_one(sel)
            if tag:
                details['Location'] = tag.text.strip()
                break
        
        if details['Location'] == "N/A":
            keywords = ['colombo', 'kandy', 'galle', 'negombo', 'batticaloa', 'jaffna', 'trincomalee']
            for div in soup.find_all(['div', 'span']):
                text = div.get_text().lower().strip()
                if any(keyword in text for keyword in keywords):
                    details['Location'] = div.get_text().strip()
                    break
        
        details['Address'] = "N/A"
        for sel in ['div.word-break--2nyVq.value--1lKHt', 'div.word-break.value', 'div.value--1lKHt', '.property-address', '.address']:
            tag = soup.select_one(sel)
            if tag:
                details['Address'] = tag.text.strip()
                break
        
        if details['Address'] == "N/A":
            for tag in soup.find_all(['div', 'span', 'p']):
                text = tag.get_text().strip()
                if any(keyword in text.lower() for keyword in ['road', 'street', 'lane', 'avenue']) and len(text) > 5:
                    details['Address'] = text
                    break
        
        details['Image URL'] = "No Image Available"
        for sel in ['img.banner-img', '.property-image img', '.gallery img', '.main-image img']:
            tag = soup.select_one(sel)
            if tag and tag.get('src'):
                details['Image URL'] = tag['src']
                break
        
        if details['Image URL'] == "No Image Available":
            for xp in ['//img[@class="banner-img"]/@src', '//div[contains(@class, "banner")]//img/@src', '//div[contains(@class, "gallery")]//img/@src']:
                result = tree.xpath(xp)
                if result:
                    details['Image URL'] = result[0]
                    break
        
        details['Price'] = "N/A"
        price_found = False
        for xp in ['/html/body/section/div[5]/div[2]/div/div[3]/span/text()', 
                   '//span[contains(@class, "main_price")]/text()', 
                   '//div[contains(@class, "price")]/span/text()']:
            result = tree.xpath(xp)
            if result:
                details['Price'] = clean_price(result[0].strip(), "lankaweb")
                price_found = True
                break
        
        if not price_found:
            for sel in ['span.main_price.mb-3.mb-sm-0', 'span.main_price', '.property-price', '.price']:
                tag = soup.select_one(sel)
                if tag:
                    details['Price'] = clean_price(tag.text.strip(), "lankaweb")
                    price_found = True
                    break
        
        if not price_found:
            for tag in soup.find_all(['span', 'div']):
                text = tag.get_text().strip()
                if 'Rs.' in text or '$' in text:
                    if re.search(r'(Rs\.|\$)\s*[\d,]+', text):
                        details['Price'] = clean_price(text, "lankaweb")
                        break
        
        return details
    except Exception as e:
        safe_log('error', f"Error parsing Lanka detail page {url}: {e}")
        return {}
    
# ------------------------------------------------
# CSV Functions for Batch Appending
# ------------------------------------------------
def append_to_csv(filename, ads, include_header=False):
    """
    Append a batch of ads to the CSV file.
    This function is thread-safe using a lock.
    """
    with sheet_lock:
        df = pd.DataFrame(ads)
        # Ensure correct column order
        cols = ['Title', 'Sqft', 'Property Type', 'Link', 'Location', 'Address', 'Image URL', 'Price', 'Status', 'Source', 'Scrape Date']
        # Fill missing columns with N/A
        for c in cols:
            if c not in df.columns:
                df[c] = 'N/A'
        df = df[cols]
        
        try:
            df.to_csv(filename, mode='a', header=include_header, index=False)
            safe_log('info', f"Appended {len(ads)} rows to {filename}.")
            return len(ads)
        except Exception as e:
            safe_log('error', f"Error appending data to {filename}: {e}")
            return 0

def data_writer_thread(filename):
    """Thread for writing data from queue to CSV"""
    global HEADER_ADDED
    total_written = 0
    
    # If the file already exists and isn't empty, don't add header
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        HEADER_ADDED = True
        
    while True:
        data = data_queue.get()
        if data is None:  # None is our signal to stop
            data_queue.task_done()
            break
            
        ads, include_header = data
        if not HEADER_ADDED and include_header:
            rows_written = append_to_csv(filename, ads, include_header=True)
            HEADER_ADDED = True
        else:
            rows_written = append_to_csv(filename, ads, include_header=False)
        
        total_written += rows_written
        data_queue.task_done()
    
    safe_log('info', f"Data writer thread finished. Total ads written: {total_written}")
    return total_written

# ------------------------------------------------
# Threaded Detail Page Processing Functions
# ------------------------------------------------
def process_ad_details(ad, website):
    """Process details for a single ad"""
    try:
        time.sleep(randint(*DETAIL_SCRAPE_DELAY))
        if website == "ikman":
            details = parse_detailed_page_ikman(ad['Link'])
        else:  # lanka
            details = parse_detailed_page_lanka(ad['Link'])
        ad.update(details)
        return ad
    except Exception as e:
        safe_log('error', f"Error processing {website} ad detail: {e}")
        return ad

def process_ads_with_details(ads, website):
    """Process all ads to get their detailed information using thread pool"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
        # Map each ad to a future that will process its details
        future_to_ad = {executor.submit(process_ad_details, ad, website): ad for ad in ads}
        
        processed_ads = []
        for future in concurrent.futures.as_completed(future_to_ad):
            try:
                processed_ad = future.result()
                processed_ads.append(processed_ad)
            except Exception as e:
                safe_log('error', f"Exception processing ad detail: {e}")
    
    return processed_ads

# ------------------------------------------------
# Main Scraping Functions (Multithreaded)
# ------------------------------------------------
def scrape_ikman_page(sheet_name, base_url, status, page, include_header=False):
    """Scrape one page from Ikman.lk and queue the data for writing to Google Sheets."""
    url = f"{base_url}?page={page}" if page > 1 else base_url
    safe_log('info', f"Fetching Ikman page {page} ({status}) from {url}")
    
    html_content = fetch_html(url)
    if not html_content:
        safe_log('warning', f"Failed to fetch Ikman page {page} ({status})")
        return 0
    
    ads = parse_main_page_ikman(html_content)
    if not ads:
        safe_log('info', f"No Ikman ads on page {page} ({status})")
        return 0
    
    # Set status for all ads
    for ad in ads:
        ad['Status'] = status
    
    # Process details for all ads in parallel
    processed_ads = process_ads_with_details(ads, "ikman")
    
    # Queue data for writing
    data_queue.put((processed_ads, include_header))
    
    return len(processed_ads)

def scrape_lanka_page(sheet_name, base_url, status, page, include_header=False):
    """Scrape one page from LankaPropertyWeb.com and queue the data for writing to Google Sheets."""
    url = f"{base_url}&page={page}" if '?' in base_url else f"{base_url}?page={page}"
    safe_log('info', f"Fetching Lanka page {page} ({status}) from {url}")
    
    html_content = fetch_html(url)
    if not html_content:
        safe_log('warning', f"Failed to fetch Lanka page {page} ({status})")
        return 0
    
    ads = parse_main_page_lanka(html_content)
    if not ads:
        safe_log('info', f"No Lanka ads on page {page} ({status})")
        return 0
    
    # Set status for all ads
    for ad in ads:
        ad['Status'] = status
    
    # Process details for all ads in parallel
    processed_ads = process_ads_with_details(ads, "lanka")
    
    # Queue data for writing
    data_queue.put((processed_ads, include_header))
    
    return len(processed_ads)

def scrape_pages_thread(func, args_list):
    """Thread function to scrape multiple pages"""
    total_ads = 0
    for args in args_list:
        try:
            ads_count = func(*args)
            if ads_count > 0:
                total_ads += ads_count
                time.sleep(randint(*PAGE_SCRAPE_DELAY))
            else:
                # If a page returns no ads, stop processing in this thread
                break
        except Exception as e:
            safe_log('error', f"Error in scrape_pages_thread: {e}")
            break
    return total_ads

# ------------------------------------------------
# Main Function (Multithreaded)
# ------------------------------------------------
def main():
    try:
        today_date = datetime.now().strftime("%Y-%m-%d")
        csv_filename = f"property_data_{today_date}.csv"
        
        # Start data writer thread
        writer_thread = threading.Thread(
            target=data_writer_thread, 
            args=(csv_filename,)
        )
        writer_thread.start()
        
        
        # Define scraping tasks
        ikman_rent_url = f"{BASE_URL_IKMAN}/en/ads/sri-lanka/commercial-property-rentals"
        ikman_sale_url = f"{BASE_URL_IKMAN}/en/ads/sri-lanka/commercial-properties-for-sale"
        lanka_rent_url = f"{BASE_URL_LANKA}/rentals/index.php?property-type=Commercial"
        lanka_sale_url = f"{BASE_URL_LANKA}/sale/index.php?property-type=Commercial"
        
        # Set up scraping tasks for each source/status combination
        ikman_rent_tasks = [(csv_filename, ikman_rent_url, "Rent", page, page == 1) 
                           for page in range(1, MAX_PAGES + 1)]
        ikman_sale_tasks = [(csv_filename, ikman_sale_url, "Sale", page, False) 
                           for page in range(1, MAX_PAGES + 1)]
        lanka_rent_tasks = [(csv_filename, lanka_rent_url, "Rent", page, False) 
                           for page in range(1, MAX_PAGES + 1)]
        lanka_sale_tasks = [(csv_filename, lanka_sale_url, "Sale", page, False) 
                           for page in range(1, MAX_PAGES + 1)]
        
        # Divide tasks among threads
        def divide_tasks(tasks, num_threads):
            tasks_per_thread = [[] for _ in range(num_threads)]
            for i, task in enumerate(tasks):
                tasks_per_thread[i % num_threads].append(task)
            return tasks_per_thread
        
        # Determine how many threads to use for each site
        site_threads = max(1, MAX_WORKERS // 4)  # Distribute workers among sites
        
        # Divide tasks for each site
        ikman_rent_divided = divide_tasks(ikman_rent_tasks, site_threads)
        ikman_sale_divided = divide_tasks(ikman_sale_tasks, site_threads)
        lanka_rent_divided = divide_tasks(lanka_rent_tasks, site_threads)
        lanka_sale_divided = divide_tasks(lanka_sale_tasks, site_threads)
        
        # Start scraping threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit scraping tasks for each site and status
            ikman_rent_futures = [
                executor.submit(scrape_pages_thread, scrape_ikman_page, tasks)
                for tasks in ikman_rent_divided
            ]
            
            ikman_sale_futures = [
                executor.submit(scrape_pages_thread, scrape_ikman_page, tasks)
                for tasks in ikman_sale_divided
            ]
            
            lanka_rent_futures = [
                executor.submit(scrape_pages_thread, scrape_lanka_page, tasks)
                for tasks in lanka_rent_divided
            ]
            
            lanka_sale_futures = [
                executor.submit(scrape_pages_thread, scrape_lanka_page, tasks)
                for tasks in lanka_sale_divided
            ]
            
            # Collect all futures
            all_futures = ikman_rent_futures + ikman_sale_futures + lanka_rent_futures + lanka_sale_futures
            
            # Wait for all scraping to complete
            total_ads = 0
            for future in concurrent.futures.as_completed(all_futures):
                try:
                    ads_count = future.result()
                    total_ads += ads_count
                except Exception as e:
                    safe_log('error', f"Error in scraping thread: {e}")
        
        # Signal the data writer thread to stop
        data_queue.put(None)
        
        # Wait for the data writer thread to finish
        writer_thread.join()
        
        safe_log('info', f"Scraping completed. Total ads found: {total_ads}")
        
        if total_ads > 0:
            safe_log('info', f"Data successfully saved to: {csv_filename}")
        else:
            safe_log('warning', "No ads scraped. Nothing to save.")
            
    except Exception as e:
        safe_log('error', f"Error in main: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
