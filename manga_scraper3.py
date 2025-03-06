import asyncio
import json
import random
import re
import os
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from tqdm import tqdm

# Update to use the specific URL
BASE_URL = "https://mangareader.to"
AZ_LIST_URL = "https://mangareader.to/az-list"
OUTPUT_FILE = "manga_data.json"
MAX_PAGES = 710  # Start with fewer pages for testing

# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def extract_manga_list(url: str, crawler: AsyncWebCrawler) -> List[Dict]:
    """Extract manga links and basic info from the list page"""
    try:
        # Print the URL we're attempting to access for debugging
        print(f"Fetching manga list from: {url}")
        
        # Configure the run with longer timeout
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,
            page_timeout=180000  # 3 minutes timeout
        )
        
        result = await crawler.arun(url=url, config=run_config)
        
        # Save HTML for debugging if needed
        # debug_file = f"debug_page_{random.randint(1000, 9999)}.html"
        # with open(debug_file, "w", encoding="utf-8") as f:
        #     f.write(result.html)
        # print(f"Saved HTML to {debug_file} for debugging")
            
        soup = BeautifulSoup(result.html, 'html.parser')
        manga_items = []
        
        # Mangareader.to specific selectors
        # First try the AZ list specific layout
        manga_elements = soup.select('.item-list .item')
        
        if not manga_elements:
            # Try alternative selectors
            manga_elements = soup.select('.book-item') or soup.select('.manga-item') or soup.select('.item')
            print(f"Found {len(manga_elements)} manga items using alternative selector")
        else:
            print(f"Found {len(manga_elements)} manga items using primary selector")
        
        for manga in manga_elements:
            try:
                # Mangareader.to selectors
                link_element = manga.select_one('a.manga-poster') or manga.select_one('a.poster') or manga.find('a')
                title_element = manga.select_one('.manga-detail h3.manga-name a') or manga.select_one('.detail h3 a') or link_element
                
                if link_element:
                    manga_url = link_element.get('href')
                    if manga_url and not manga_url.startswith('http'):
                        manga_url = BASE_URL + manga_url
                        
                    cover_img = link_element.select_one('img')
                    cover_url = cover_img.get('src') or cover_img.get('data-src') if cover_img else None
                    
                    title = title_element.text.strip() if title_element else "Unknown Title"
                    
                    manga_items.append({
                        "title": title,
                        "url": manga_url,
                        "cover_url": cover_url,
                    })
            except Exception as e:
                print(f"Error parsing a manga item: {e}")
                continue
        
        print(f"Successfully extracted {len(manga_items)} manga items")
        return manga_items
    except Exception as e:
        print(f"Error in extract_manga_list: {e}")
        return []

async def extract_manga_details(url, basic_info, crawler):
    """Extract detailed information about a manga from its page."""
    print(f"Extracting details for: {basic_info.get('title', 'Unknown')}")
    
    try:
        # Use the crawler.arun method to get the page content
        result = await crawler.arun(url)
        html = result.html
        soup = BeautifulSoup(html, "html.parser")
        
        # Save detail HTML for debugging if needed
        # debug_file = f"debug_detail_{random.randint(1000, 9999)}.html"
        # with open(debug_file, "w", encoding="utf-8") as f:
        #     f.write(html)
        
        # Use basic info as starting point
        manga_data = basic_info.copy()
        
        # Extract synopsis if available
        synopsis_element = soup.select_one("div.container div.detail-content div.story p.description")
        manga_data["synopsis"] = synopsis_element.text.strip() if synopsis_element else "Not available"
        
        # Extract author information
        author_element = soup.select_one("div.container div.detail-info div.author")
        if author_element:
            authors = author_element.select("a")
            manga_data["author"] = [a.text.strip() for a in authors] if authors else ["Unknown"]
        else:
            manga_data["author"] = ["Unknown"]
        
        # Extract genre information - try multiple selectors
        genre_elements = soup.select("div.container div.detail-info div.genres a")
        manga_data["genres"] = [genre.text.strip() for genre in genre_elements] if genre_elements else []
        
        # Extract more specific information about genres if first attempt failed
        if not manga_data["genres"]:
            # Try alternative selectors for genres
            alt_genre_elements = soup.select(".genres-content .genres-button") or soup.select(".genres a")
            manga_data["genres"] = [genre.text.strip() for genre in alt_genre_elements] if alt_genre_elements else []
        
        # Another set of fallback selectors for genres
        if not manga_data["genres"]:
            # Try broader selectors
            for selector in [".info .genres a", ".manga-info .genres a", "[class*='genre']"]:
                alt_genre_elements = soup.select(selector)
                if alt_genre_elements:
                    manga_data["genres"] = [genre.text.strip() for genre in alt_genre_elements]
                    break
        
        # Set empty array if no genres found
        if not manga_data["genres"]:
            manga_data["genres"] = []
            print(f"No genres found for {manga_data['title']}")
        
        # Extract cover image if available
        cover_element = soup.select_one("div.container div.thumb img")
        if cover_element and cover_element.has_attr("src"):
            manga_data["cover_image"] = cover_element["src"]
        
        # Extract rating if available
        rating_element = soup.select_one("div.container div.detail-info div.detail-info-right span.vote-avg strong")
        if rating_element:
            rating_text = rating_element.text.strip()
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                manga_data["rating"] = float(match.group(1))
            else:
                manga_data["rating"] = None
        else:
            manga_data["rating"] = None
        
        # Try to extract status information (ongoing, completed, etc.)
        status_element = soup.select_one("div.container div.detail-info .status span.value") or soup.select_one(".manga-status")
        manga_data["status"] = status_element.text.strip() if status_element else "Unknown"
        
        return manga_data
    except Exception as e:
        print(f"Error extracting details from {url}: {e}")
        # Return basic info with empty genres if detailed extraction fails
        basic_info["genres"] = []
        return basic_info

def filter_navigation_links(extracted_data):
    if isinstance(extracted_data, list):
        # Filter out items with "az-list" in the URL
        return [item for item in extracted_data if not (
            isinstance(item, dict) and
            "url" in item and
            "az-list" in item["url"]
        )]
    return extracted_data

# Update the save_to_json function
def save_to_json(data: List[Dict], filename: str) -> None:
    """Save the manga data to a JSON file"""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved {len(data)} manga items to {filename}")
    except Exception as e:
        print(f"Error saving data to {filename}: {e}")

# Modify the main function to extract genres for page-specific files
async def main():
    # Import os and json at the top of your file if not already there
    global OUTPUT_FILE
    
    manga_list = []
    all_manga_data = []
    
    print(f"Starting crawler with random user agent...")
    user_agent = random.choice(USER_AGENTS)
    
    crawler = AsyncWebCrawler(
        browser_type="firefox",
        headless=True,
        user_agent=user_agent
    )
    
    try:
        # Process manga list pages
        for page in range(595, MAX_PAGES + 1):
            page_url = f"{BASE_URL}/az-list?page={page}"
            print(f"\n--- Processing page {page} ---")
            page_manga_list = await extract_manga_list(page_url, crawler)

            # Filter out unwanted links
            page_manga_list = filter_navigation_links(page_manga_list)
            
            # Extract genres and details for each manga on the page
            page_manga_data = []
            print(f"Processing genres and details for page {page} ({len(page_manga_list)} mangas)...")
            
            for i, manga in enumerate(tqdm(page_manga_list, desc=f"Processing page {page} manga details")):
                try:
                    # Extract detailed information including genres
                    manga_data = await extract_manga_details(manga["url"], manga, crawler)
                    page_manga_data.append(manga_data)
                    
                    # Add randomized delay to avoid rate limiting
                    if i < len(page_manga_list) - 1:
                        delay = random.uniform(2.0, 4.0)
                        await asyncio.sleep(delay)
                except Exception as e:
                    print(f"Error processing manga {manga.get('title', 'Unknown')}: {e}")
                    # Add basic info with empty genres
                    manga["genres"] = []
                    page_manga_data.append(manga)
            
            # Save page-specific data with genres included
            page_output_file = f"manga_data_page{page}.json"
            save_to_json(page_manga_data, page_output_file)
            
            # Add to the overall list
            manga_list.extend(page_manga_data)
            
            # Add randomized delay between pages
            if page < MAX_PAGES:  # No need to sleep after the last page
                delay = random.uniform(3.0, 6.0)
                print(f"Waiting {delay:.2f} seconds before next page...")
                await asyncio.sleep(delay)
        
        # Remove duplicates based on URL
        unique_urls = set()
        unique_manga_list = []
        for manga in manga_list:
            if manga["url"] not in unique_urls:
                unique_urls.add(manga["url"])
                unique_manga_list.append(manga)
        
        manga_list = unique_manga_list
        print(f"Found {len(manga_list)} unique manga titles across {MAX_PAGES} pages")
        
        # Save complete data to JSON file
        if manga_list:
            save_to_json(manga_list, OUTPUT_FILE)
            print("Scraping completed!")
        else:
            print("No manga data collected. Please check the site structure and try again.")
    
    finally:
        await crawler.close()


if __name__ == "__main__":
    print("Starting manga scraper for mangareader.to/az-list...")
    asyncio.run(main())