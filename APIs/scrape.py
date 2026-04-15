"""
scrape API

Unified, extendable scraper runner for multiple platforms.

Features:
- Raw JSON and raw images saved in "raw/json" and "raw/images" folders under each company_name
- Combined and resized images saved in "preprocessed/images" folder under each company_name
- Preprocessed JSONs with useful fields saved under "preprocessed/json" folder under each company_name
- Concurrent scrapers and concurrent image downloads

Output structure:
raw/
  json/{company_name}/
  images/{company_name}/
preprocessed/
  json/{company_name}/
  images/{company_name}/

File naming conventions:
Raw JSON:
  companyName_platform_hh_mm_ss_DD_MM_YY.json
Raw Images:
  ad_<num>_image_<num>_companyName_platform_hh_mm_ss_DD_MM_YYYY.ext
Preprocessed JSON:
  companyName_platform_hh_mm_ss_DD_MM_YY.json
Preprocessed Combined Image:
  ad_<num>_companyName_platform_hh_mm_ss_DD_MM_YY.jpg

Useful fields extraction:
{
  "meta": [
    "page_name", "page_categories", "title", "body_text",
    "caption", "cta_text", "cta_type", "display_format", "publisher_platform"
  ],
  "reddit": [
    "profile_name", "industry", "objective", "placements",
    "headline", "body", "call_to_action"
  ],
  "linkedin": [
    "advertiser", "headline", "description", "adType", "cta"
  ],
  "google": [
    "variations.headline", "variations.description"
  ]
}

API Input Parameters (lambda_handler):
- companyId: str (DynamoDB companyId)
- jobId: str (DynamoDB jobId)

All API output scenarios (lambda_handler):

1. Success - Scraping Completed Successfully
   Status Code: 200
   Response Body:
   {
       "status": 2,
       "numAds": int
   }
   Meaning:
   - All configured scrapers completed successfully.
   - numAds = total ads collected across all enabled platforms.
   - n8n workflow is triggered asynchronously after scrape completion.

2. Error - Missing Required Parameters
   (companyId or jobId not provided)
   Status Code: 200
   Response Body:
   {
       "status": 0,
       "numAds": 0
   }

3. Error - Company Not Found in DynamoDB
   Status Code: 200
   Response Body:
   {
       "status": 0,
       "numAds": 0
   }

4. Error - DynamoDB Access or Network Error While Fetching Company
   Status Code: 200
   Response Body:
   {
       "status": 0,
       "numAds": 0
   }

5. Error - Scraping Failed (No Platforms or No Ads Found)
   Raises Exception (caught by scrapeHandler)
   Message: "Scraping failed: {num_platforms_scraped} platforms scraped, {num_ads} ads found"

6. Error - Fatal Runtime or API Error During Scraping
   Raises Exception (caught by scrapeHandler)
   Message: "Scraping failed: <error details>"

Additional Notes:
- This scraper also triggers an external n8n workflow for image-to-text extraction after scraping.
- image2textStatus is updated automatically by the n8n workflow after this Lambda triggers it.
- image2textRetryCount is also managed by the n8n workflow.
- For more references on the scrapers and their parameters, see: https://docs.scrapecreators.com/
"""

import boto3
import datetime
import json
import os
import mimetypes
import time
from typing import List, Dict, Optional
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import count
from urllib.parse import urljoin
import re

from datetime import date, timedelta

import requests
from PIL import Image, ImageOps

# ----------------------------
# AWS Setup
# ----------------------------
dynamodb = boto3.resource("dynamodb")
companies_table = dynamodb.Table("companies")
jobs_table = dynamodb.Table("jobs")
s3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET", "test-2-adspy")

# ----------------------------
# Configuration from Environment
# ----------------------------
META_API_KEY = os.environ.get("META_API_KEY")
LINKEDIN_API_KEY = os.environ.get("LINKEDIN_API_KEY")
REDDIT_API_KEY = os.environ.get("REDDIT_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Platform enable/disable flags
ENABLE_META = os.environ.get("ENABLE_META", "true").lower() == "true"
ENABLE_LINKEDIN = os.environ.get("ENABLE_LINKEDIN", "true").lower() == "true"
ENABLE_REDDIT = os.environ.get("ENABLE_REDDIT", "true").lower() == "true"
ENABLE_GOOGLE = os.environ.get("ENABLE_GOOGLE", "true").lower() == "true"

# Date window configuration (in days)
try:
    # 90 days before today
    WINDOW_DAYS_BEFORE = int(os.environ.get("WINDOW_DAYS_BEFORE", "90"))
except ValueError:
    WINDOW_DAYS_BEFORE = 90
try:
    # 0 days after today
    WINDOW_DAYS_AFTER = int(os.environ.get("WINDOW_DAYS_AFTER", "-1"))
except ValueError:
    WINDOW_DAYS_AFTER = -1

# Calculate start and end dates based on today's date
today = date.today()
START_DATE = (today - timedelta(days=WINDOW_DAYS_BEFORE)).strftime("%Y-%m-%d")
END_DATE = (today + timedelta(days=WINDOW_DAYS_AFTER)).strftime("%Y-%m-%d")

# Meta/Facebook API parameters
META_STATUS = os.environ.get("META_STATUS", "ACTIVE")   # ACTIVE, INACTIVE, or ALL
META_COUNTRY = os.environ.get("META_COUNTRY", "")       # 2 letters country code. Default: ALL
META_MEDIA_TYPE = os.environ.get("META_MEDIA_TYPE", "")     # IMAGE, VIDEO, etc. Default: ALL
META_TRIM = os.environ.get("META_TRIM", "false")            # true or false

# LinkedIn API parameters
LINKEDIN_KEYWORD = os.environ.get("LINKEDIN_KEYWORD", "")  # Empty = no filter
LINKEDIN_COUNTRIES = os.environ.get("LINKEDIN_COUNTRIES", "")  # Comma-separated list of 2-letter country codes e.g., "US,CA,MX"
# LinkedIn dates: 15 days before and after today (30-day window)
LINKEDIN_START_DATE = START_DATE
LINKEDIN_END_DATE = END_DATE

# Reddit filters (optional)
REDDIT_INDUSTRIES = os.environ.get("REDDIT_INDUSTRIES", "")  # Empty = no filter
REDDIT_BUDGETS = os.environ.get("REDDIT_BUDGETS", "")
REDDIT_FORMATS = os.environ.get("REDDIT_FORMATS", "")
REDDIT_PLACEMENTS = os.environ.get("REDDIT_PLACEMENTS", "")
REDDIT_OBJECTIVES = os.environ.get("REDDIT_OBJECTIVES", "")

# Google API parameters
# Google scraper auto-detects if query is domain or advertiserId
GOOGLE_TOPIC = os.environ.get("GOOGLE_TOPIC", "all")  # all or political
GOOGLE_REGION = os.environ.get("GOOGLE_REGION", "")  # Empty = anywhere
# Google dates: 15 days before and after today (30-day window)
GOOGLE_START_DATE = START_DATE
GOOGLE_END_DATE = END_DATE        

# General scraping configuration
MAX_PAGES = int(os.environ.get("MAX_PAGES", "3"))
RESIZE_FACTOR = float(os.environ.get("RESIZE_FACTOR", "0.5"))
RESIZE_KEEP_ASPECT = os.environ.get("RESIZE_KEEP_ASPECT", "true").lower() == "true"
GENERATE_COMBINED = os.environ.get("GENERATE_COMBINED", "true").lower() == "true"
RESIZE_PREPROCESSED = os.environ.get("RESIZE_PREPROCESSED", "true").lower() == "true"
SAVE_RAW_IMAGES = os.environ.get("SAVE_RAW_IMAGES", "true").lower() == "true"
SAVE_RAW_JSON = os.environ.get("SAVE_RAW_JSON", "true").lower() == "true"

SCRAPER_WORKERS = int(os.environ.get("SCRAPER_WORKERS", "4"))
IMAGE_DOWNLOAD_WORKERS = int(os.environ.get("IMAGE_DOWNLOAD_WORKERS", "12"))
REQUESTS_TIMEOUT = int(os.environ.get("REQUESTS_TIMEOUT", "300"))
RATE_LIMIT_SLEEP = float(os.environ.get("RATE_LIMIT_SLEEP", "1.0"))

# ----------------------------
# Counters (will be reset per invocation)
# ----------------------------
ad_counter = count(1)
image_counter = count(1)

# ----------------------------
# Utility Functions
# ----------------------------
def safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in (" ", ".", "_", "-") else "_" for c in s).replace(" ", "_").lower()

def log(msg: str):
    print(msg)

def is_domain(query: str) -> bool:
    """Check if query looks like a domain name"""
    if not query or " " in query:
        return False
    
    # Must contain a dot and have a valid TLD
    if "." not in query:
        return False
    
    # Common TLDs to check
    valid_tlds = ['.com', '.org', '.net', '.io', '.co', '.ai', '.edu', '.gov', 
                  '.uk', '.ca', '.au', '.de', '.fr', '.jp', '.cn', '.in']
    
    query_lower = query.lower()
    return any(query_lower.endswith(tld) for tld in valid_tlds)

def extract_name_from_domain(domain: str) -> str:
    """Extract company name from domain (e.g., 'example.com' -> 'Example')"""
    # Remove www. prefix if present
    if domain.lower().startswith("www."):
        domain = domain[4:]
    
    # Take the part before the first dot
    name = domain.split(".")[0]
    
    # Replace hyphens with spaces and capitalize
    name = name.replace("-", " ").replace("_", " ")
    
    # Capitalize each word
    return name.title()

def lookup_domain_from_name(name: str) -> Optional[str]:
    """
    Attempt to determine company domain from name using heuristics.
    Tries common domain patterns and validates via DNS lookup.
    Returns domain string or None if not found.
    
    Limitations: Only works for companies whose domain matches their name.
    Examples that work: "Facebook" -> facebook.com
    Examples that fail: "Procter & Gamble" -> pg.com (will try procterandgamble.com)
    """
    try:
        log(f"[lookup] Attempting to derive domain from name: {name}")
        
        # Convert name to potential domain format
        # Remove spaces, replace & with 'and'
        simple_domain = name.lower().replace(" ", "").replace("&", "and")
        
        # Try common TLDs in order of likelihood
        potential_domains = [
            f"{simple_domain}.com",
            f"{simple_domain}.io",
            f"{simple_domain}.co",
            f"{simple_domain}.net",
            f"{simple_domain}.org",
            f"{simple_domain}.ai",
            f"{simple_domain}.ca"
        ]
        
        # Validate each domain by checking DNS resolution
        for domain in potential_domains:
            try:
                import socket
                socket.gethostbyname(domain)
                log(f"[lookup] Found valid domain via heuristic: {domain}")
                return domain
            except socket.gaierror:
                # Domain doesn't resolve, try next
                continue
        
        log(f"[lookup] Could not determine domain for: {name} (tried: {', '.join(potential_domains)})")
        return None
        
    except Exception as e:
        log(f"[lookup] Error looking up domain for {name}: {e}")
        return None

def update_company_queries(company_id: str, queries: dict, domain: str = ""):
    """
    Update the query fields and domain in the companies table.
    
    Args:
        company_id: Company ID to update
        queries: Dict with keys meta_query, google_query, reddit_query, linkedin_query
        domain: Domain name (if determined)
    """
    try:
        companies_table.update_item(
            Key={"companyId": company_id},
            UpdateExpression="SET meta_query = :meta, google_query = :google, reddit_query = :reddit, linkedin_query = :linkedin, #domain = :domain",
            ExpressionAttributeNames={
                "#domain": "domain"
            },
            ExpressionAttributeValues={
                ":meta": queries.get("meta_query", ""),
                ":google": queries.get("google_query", ""),
                ":reddit": queries.get("reddit_query", ""),
                ":linkedin": queries.get("linkedin_query", ""),
                ":domain": domain
            }
        )
        log(f"[dynamodb] Updated query fields and domain for company {company_id}")
        return True
    except Exception as e:
        log(f"[dynamodb] Failed to update queries: {e}")
        return False
    
def prepare_queries(query: str) -> dict:
    """
    Prepare queries for all platforms based on input type.
    Returns dict with keys: meta_query, linkedin_query, reddit_query, google_query
    """
    query = query.strip()
    
    if is_domain(query):
        # Scenario 1: Input is a domain
        log(f"[prepare_queries] Detected domain: {query}")
        extracted_name = extract_name_from_domain(query)
        log(f"[prepare_queries] Extracted name: {extracted_name}")
        
        return {
            "meta_query": extracted_name,
            "linkedin_query": extracted_name,
            "reddit_query": extracted_name,
            "google_query": query  # Use original domain
        }
    else:
        # Scenario 2: Input is a company name
        log(f"[prepare_queries] Detected company name: {query}")
        looked_up_domain = lookup_domain_from_name(query)
        
        if looked_up_domain:
            log(f"[prepare_queries] Found domain: {looked_up_domain}")
        else:
            log(f"[prepare_queries] Could not find domain, Google scraper will be skipped")
        
        return {
            "meta_query": query,
            "linkedin_query": query,
            "reddit_query": query,
            "google_query": looked_up_domain  # May be None
        }

def ensure_prefix(prefix: str):
    """Ensure S3 prefix exists by creating empty object"""
    if not prefix.endswith("/"):
        prefix += "/"
    try:
        s3.put_object(Bucket=BUCKET, Key=prefix, Body=b"")
    except Exception as e:
        log(f"[s3] Could not create prefix {prefix}: {e}")

# ----------------------------
# Image Helper Functions
# ----------------------------
def guess_extension_from_content_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ".jpg"
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    if not ext or ext == ".jfif":
        return ".jpg"
    return ext

def download_image_to_memory(session: requests.Session, url: str, timeout: int = REQUESTS_TIMEOUT) -> Optional[Dict]:
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        return {"bytes": resp.content, "content_type": content_type, "pil": img}
    except Exception as e:
        log(f"[download_image_to_memory] Failed to download {url}: {e}")
        return None

def save_raw_image_to_s3(company_name: str, ad_num: int, img_idx: int, content_type: str, 
                         data: bytes, platform: str, timestamp: str) -> str:
    ext = guess_extension_from_content_type(content_type)
    filename = f"ad_{ad_num}_image_{img_idx}_{safe_name(company_name)}_{safe_name(platform)}_{timestamp}{ext}"
    key = f"raw/images/{safe_name(company_name)}/{filename}"
    
    try:
        s3.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)
        log(f"[s3] Saved raw image: {key}")
        return key
    except Exception as e:
        log(f"[s3] Failed to save raw image {key}: {e}")
        return ""

def combine_images_horizontally(images: List[Image.Image], background=(255, 255, 255)) -> Image.Image:
    widths = [img.width for img in images]
    heights = [img.height for img in images]
    total_w = sum(widths)
    max_h = max(heights)
    combined = Image.new("RGB", (total_w, max_h), background)
    x = 0
    for img in images:
        y = (max_h - img.height) // 2
        combined.paste(img, (x, y))
        x += img.width
    return combined

def resize_image(img: Image.Image, keep_aspect=True) -> Image.Image:
    target_w = int(img.width * RESIZE_FACTOR)
    target_h = int(img.height * RESIZE_FACTOR)
    if keep_aspect:
        return ImageOps.contain(img, (target_w, target_h))
    return img.resize((target_w, target_h), Image.LANCZOS)

# ----------------------------
# Platform-Specific Image URL Extraction
# ----------------------------
def _extract_image_urls_meta(ad: dict) -> list:
    """Extract image URLs from Meta/Facebook ad"""
    snapshot = ad.get("snapshot", {}) or {}
    urls = []
    for c in snapshot.get("cards", []):
        if c.get("original_image_url"):
            urls.append(c["original_image_url"])
    for i in snapshot.get("images", []):
        if i.get("original_image_url"):
            urls.append(i["original_image_url"])
    return urls

def _extract_image_urls_linkedin(ad: dict) -> list:
    """Extract image URLs from LinkedIn ad"""
    urls = []
    # Single image
    img = ad.get("image")
    if isinstance(img, str) and img.startswith("http"):
        urls.append(img)
    # Carousel images
    for u in ad.get("carouselImages") or []:
        if isinstance(u, str) and u.startswith("http"):
            urls.append(u)
    return urls

def _extract_image_urls_reddit(ad: dict) -> list:
    """Extract image URLs from Reddit ad"""
    creative = ad.get("creative") or {}
    ctype = (creative.get("type") or "").upper()
    content = creative.get("content") or []
    urls = []
    # Only process IMAGE and CAROUSEL types (skip VIDEO)
    if ctype in ("IMAGE", "CAROUSEL"):
        for item in content:
            u = item.get("media_url")
            if isinstance(u, str) and u.startswith("http"):
                urls.append(u)
    return urls

def _extract_image_urls_google(ad: dict) -> list:
    """Extract image URLs from Google ad (already processed from variations)"""
    # For Google, image URLs are passed directly in snapshot.images
    # because we pre-process them in scrape_google()
    snapshot = ad.get("snapshot", {}) or {}
    urls = []
    for i in snapshot.get("images", []):
        if i.get("original_image_url"):
            urls.append(i["original_image_url"])
    return urls

# ----------------------------
# Core Image Processing
# ----------------------------
def _process_ad_images(platform: str, ad: dict, session: requests.Session,
                       company_name: str, timestamp: str,
                       image_executor: ThreadPoolExecutor):
    ad_num = next(ad_counter)
    
    # Extract image URLs based on platform
    if platform == "meta":
        urls = _extract_image_urls_meta(ad)
    elif platform == "linkedin":
        urls = _extract_image_urls_linkedin(ad)
    elif platform == "reddit":
        urls = _extract_image_urls_reddit(ad)
    elif platform == "google":
        urls = _extract_image_urls_google(ad)
    else:
        log(f"[warn] Unknown platform {platform}, attempting generic extraction")
        snapshot = ad.get("snapshot", {}) or {}
        urls = []
        for i in snapshot.get("images", []):
            if i.get("original_image_url"):
                urls.append(i["original_image_url"])
    
    # Deduplicate while preserving order
    seen = set()
    image_urls = [u for u in urls if not (u in seen or seen.add(u))]
    if not image_urls:
        return None

    futures = [image_executor.submit(download_image_to_memory, session, url) for url in image_urls]
    downloaded = [f.result() for f in as_completed(futures) if f.result() and f.result().get("pil")]
    if not downloaded:
        log(f"[warn] No images downloaded for ad {ad.get('id')}")
        return None

    if SAVE_RAW_IMAGES:
        for i, obj in enumerate(downloaded, start=1):
            save_raw_image_to_s3(company_name, ad_num, i, obj.get("content_type", ""), 
                                obj["bytes"], platform, timestamp)

    pil_images = [resize_image(obj["pil"], keep_aspect=RESIZE_KEEP_ASPECT) for obj in downloaded]

    if pil_images and GENERATE_COMBINED:
        combined_img = combine_images_horizontally(pil_images)
    else:
        combined_img = None
    
    if RESIZE_PREPROCESSED and combined_img:
        buffer = BytesIO()
        combined_img.save(buffer, format="JPEG")
        buffer.seek(0)
        
        filename = f"ad_{ad_num}_{safe_name(company_name)}_{safe_name(platform)}_{timestamp}.jpg"
        key = f"preprocessed/images/{safe_name(company_name)}/{filename}"
        
        try:
            s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue(), ContentType="image/jpeg")
            log(f"[s3] Saved combined image: {key}")
            return key
        except Exception as e:
            log(f"[s3] Failed to save combined image {key}: {e}")
            return None
    
    return None

# ----------------------------
# JSON Helper Functions
# ----------------------------
def _save_raw_json_to_s3(platform: str, company_name: str, data: dict, timestamp: str) -> str:
    safe_company = safe_name(company_name)
    filename = f"{safe_company}_{safe_name(platform)}_{timestamp}.json"
    key = f"raw/json/{safe_company}/{filename}"
    
    try:
        s3.put_object(
            Bucket=BUCKET, 
            Key=key, 
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType="application/json"
        )
        log(f"[s3] Saved raw JSON: {key}")
        return key
    except Exception as e:
        log(f"[s3] Failed to save raw JSON {key}: {e}")
        return ""

def _save_preprocessed_json_to_s3(platform: str, company_name: str, data: List[dict], timestamp: str) -> str:
    safe_company = safe_name(company_name)
    filename = f"{safe_company}_{safe_name(platform)}_{timestamp}.json"
    key = f"preprocessed/json/{safe_company}/{filename}"
    
    try:
        s3.put_object(
            Bucket=BUCKET, 
            Key=key, 
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType="application/json"
        )
        log(f"[s3] Saved preprocessed JSON: {key}")
        return key
    except Exception as e:
        log(f"[s3] Failed to save preprocessed JSON {key}: {e}")
        return ""

# ----------------------------
# Field Extraction Functions
# ----------------------------
def _extract_useful_fields_meta(all_ads: List[dict]) -> List[dict]:
    result = []
    for ad in all_ads:
        snap = ad.get("snapshot") or {}
        creative = ad.get("creative") or {}

        def find_field(*paths):
            for path_func in paths:
                try:
                    val = path_func()
                    if val is not None:
                        return val
                except Exception:
                    continue
            return None

        body_text = find_field(
            lambda: snap.get("body", {}).get("text") if isinstance(snap.get("body"), dict) else snap.get("body"),
            lambda: creative.get("body"),
            lambda: ad.get("body")
        )

        entry = {
            "page_name": find_field(lambda: snap.get("page_name"), lambda: ad.get("page_name"), lambda: snap.get("current_page_name")),
            "page_categories": find_field(lambda: snap.get("page_categories"), lambda: ad.get("page_categories"), lambda: creative.get("categories")),
            "title": find_field(lambda: snap.get("title"), lambda: creative.get("title"), lambda: ad.get("title")),
            "body_text": body_text,
            "caption": find_field(lambda: snap.get("caption"), lambda: creative.get("caption")),
            "cta_text": find_field(lambda: snap.get("cta_text"), lambda: creative.get("call_to_action_text")),
            "cta_type": find_field(lambda: snap.get("cta_type"), lambda: creative.get("call_to_action_type")),
            "display_format": find_field(lambda: snap.get("display_format"), lambda: ad.get("ad_snapshot", {}).get("format")),
            "publisher_platform": ad.get("publisher_platform")
        }
        result.append(entry)
    return result

def _extract_useful_fields_reddit(all_ads: List[dict]) -> List[dict]:
    result = []
    for ad in all_ads:
        creative = ad.get("creative") or {}
        content = creative.get("content") or []

        def find_field(*paths):
            for path_func in paths:
                try:
                    val = path_func()
                    if val is not None:
                        return val
                except Exception:
                    continue
            return None

        body = find_field(lambda: creative.get("body"), lambda: content[0].get("text") if content else None, lambda: ad.get("body"))

        entry = {
            "profile_name": find_field(lambda: ad.get("profile_name"), lambda: ad.get("advertiser_name")),
            "industry": find_field(lambda: ad.get("industry")),
            "objective": find_field(lambda: ad.get("objective")),
            "placements": find_field(lambda: ad.get("placements")),
            "headline": find_field(lambda: ad.get("headline"), lambda: creative.get("headline")),
            "body": body,
            "call_to_action": find_field(lambda: ad.get("call_to_action"), lambda: creative.get("call_to_action_text"))
        }
        result.append(entry)
    return result

def _extract_useful_fields_linkedin(all_ads: List[dict]) -> List[dict]:
    result = []
    for ad in all_ads:
        creative = ad.get("creative") or {}

        def find_field(*paths):
            for path_func in paths:
                try:
                    val = path_func()
                    if val is not None:
                        return val
                except Exception:
                    continue
            return None

        entry = {
            "advertiser": find_field(lambda: ad.get("advertiser")),
            "headline": find_field(lambda: ad.get("headline"), lambda: creative.get("headline")),
            "description": find_field(lambda: ad.get("description"), lambda: creative.get("description")),
            "adType": find_field(lambda: ad.get("adType"), lambda: creative.get("type")),
            "cta": find_field(lambda: ad.get("cta"), lambda: creative.get("call_to_action"))
        }
        result.append(entry)
    return result

def _extract_useful_fields_google(all_ads: list) -> list:
    result = []
    for ad in all_ads:
        variations = ad.get("variations") or []
        simplified_variations = [{"headline": v.get("headline"), "description": v.get("description")} for v in variations]
        entry = {"variations": simplified_variations}
        result.append(entry)
    return result

def _process_and_save_useful_fields(platform: str, company_name: str, all_ads: List[dict], timestamp: str):
    if platform == "meta":
        useful = _extract_useful_fields_meta(all_ads)
    elif platform == "linkedin":
        useful = _extract_useful_fields_linkedin(all_ads)
    elif platform == "reddit":
        useful = _extract_useful_fields_reddit(all_ads)
    elif platform == "google":
        useful = _extract_useful_fields_google(all_ads)
    else:
        useful = all_ads
    return _save_preprocessed_json_to_s3(platform, company_name, useful, timestamp)

# ----------------------------
# Platform Scrapers
# ----------------------------
def scrape_meta(query: str, company_name: str, timestamp: str, max_pages: int = MAX_PAGES):
    log(f"[meta] Scraping ads for: {query} (status={META_STATUS}, country={META_COUNTRY}, media_type={META_MEDIA_TYPE})")
    session = requests.Session()
    session.headers.update({"x-api-key": META_API_KEY})
    params = {
        "companyName": query
    }

    # Add optional filters if provided
    if META_STATUS:
        params["status"] = META_STATUS.upper()
    if META_COUNTRY:
        params["country"] = META_COUNTRY.upper()
    if META_MEDIA_TYPE:
        params["media_type"] = META_MEDIA_TYPE.upper()
    if META_TRIM:
        params["trim"] = META_TRIM.lower()

    log(f"[meta] Using params: {params}")

    all_ads, cursor = [], None
    for page in range(max_pages):
        if cursor: 
            params["cursor"] = cursor
        try:
            resp = session.get("https://api.scrapecreators.com/v1/facebook/adLibrary/company/ads",
                               params=params, timeout=REQUESTS_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results", []) or []
            all_ads.extend(batch)
            log(f"[meta] fetched {len(batch)} ads (page {page+1})")
            cursor = data.get("cursor")
            if not cursor: 
                break
            time.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            error_msg = str(e)
            
            # Classify HTTP errors
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status in [400, 401, 403, 404, 422]:
                    log(f"[meta] Permanent error {status} on page {page+1}: {e}")
                    raise Exception(f"Permanent error {status}: {error_msg}")
                elif status in [429, 500, 502, 503, 504]:
                    log(f"[meta] Transient error {status} on page {page+1}: {e}")
                    raise Exception(f"Transient error {status}: {error_msg}")
            
            # Check for timeout/connection errors
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                log(f"[meta] Transient network error on page {page+1}: {e}")
                raise Exception(f"Transient network error: {error_msg}")
            
            # Unknown error - treat as transient
            log(f"[meta] Error on page {page+1}: {e}")
            raise Exception(f"Transient error: {error_msg}")

    json_path = _save_raw_json_to_s3("meta", company_name, {"results": all_ads}, timestamp) if SAVE_RAW_JSON else None
    prepro_json_path = _process_and_save_useful_fields("meta", company_name, all_ads, timestamp)

    processed_images = []
    with ThreadPoolExecutor(max_workers=IMAGE_DOWNLOAD_WORKERS) as image_executor:
        for ad in all_ads:
            res = _process_ad_images("meta", ad, session, company_name, timestamp, image_executor)
            if res: 
                processed_images.append(res)

    return {"platform": "meta", "company": company_name, "json_path": json_path,
            "prepro_json_path": prepro_json_path, "processed_images": processed_images, "num_ads": len(all_ads)}

def scrape_linkedin(query: str, company_name: str, timestamp: str, max_pages: int = MAX_PAGES):
    log(f"[linkedin] Scraping ads for: {query}")
    session = requests.Session()
    session.headers.update({"x-api-key": LINKEDIN_API_KEY})

    params = {"company": query}

    # Add optional filters if provided
    if LINKEDIN_KEYWORD:
        params["keyword"] = LINKEDIN_KEYWORD
    if LINKEDIN_COUNTRIES:
        params["countries"] = LINKEDIN_COUNTRIES
    if LINKEDIN_START_DATE:
        params["startDate"] = LINKEDIN_START_DATE
    if LINKEDIN_END_DATE:
        params["endDate"] = LINKEDIN_END_DATE

    log(f"[linkedin] Using params: {params}")

    all_ads, cursor = [], None
    for page in range(max_pages):
        if cursor: 
            params["paginationToken"] = cursor  # LinkedIn uses "paginationToken", not "cursor"
        try:
            resp = session.get("https://api.scrapecreators.com/v1/linkedin/ads/search",
                               params=params, timeout=REQUESTS_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("ads", []) or []
            all_ads.extend(batch)
            log(f"[linkedin] fetched {len(batch)} ads (page {page+1})")
            cursor = data.get("paginationToken")
            if not cursor: 
                break
            time.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            error_msg = str(e)
            
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status in [400, 401, 403, 404, 422]:
                    log(f"[linkedin] Permanent error {status} on page {page+1}: {e}")
                    raise Exception(f"Permanent error {status}: {error_msg}")
                elif status in [429, 500, 502, 503, 504]:
                    log(f"[linkedin] Transient error {status} on page {page+1}: {e}")
                    raise Exception(f"Transient error {status}: {error_msg}")
            
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                log(f"[linkedin] Transient network error on page {page+1}: {e}")
                raise Exception(f"Transient network error: {error_msg}")
            
            log(f"[linkedin] Error on page {page+1}: {e}")
            raise Exception(f"Transient error: {error_msg}")

    json_path = _save_raw_json_to_s3("linkedin", company_name, {"results": all_ads}, timestamp) if SAVE_RAW_JSON else None
    prepro_json_path = _process_and_save_useful_fields("linkedin", company_name, all_ads, timestamp)

    processed_images = []
    with ThreadPoolExecutor(max_workers=IMAGE_DOWNLOAD_WORKERS) as image_executor:
        for ad in all_ads:
            res = _process_ad_images("linkedin", ad, session, company_name, timestamp, image_executor)
            if res: 
                processed_images.append(res)

    return {"platform": "linkedin", "company": company_name, "json_path": json_path,
            "prepro_json_path": prepro_json_path, "processed_images": processed_images, "num_ads": len(all_ads)}

def scrape_reddit(query: str, company_name: str, timestamp: str, max_pages: int = MAX_PAGES):
    log(f"[reddit] Scraping ads for: {query}")
    session = requests.Session()
    session.headers.update({"x-api-key": REDDIT_API_KEY})
    params = {
        "query": query,
    }

    # Add optional filters if provided
    if REDDIT_INDUSTRIES:
        params["industries"] = REDDIT_INDUSTRIES
    if REDDIT_BUDGETS:
        params["budgets"] = REDDIT_BUDGETS
    if REDDIT_FORMATS:
        params["formats"] = REDDIT_FORMATS
    if REDDIT_PLACEMENTS:
        params["placements"] = REDDIT_PLACEMENTS
    if REDDIT_OBJECTIVES:
        params["objectives"] = REDDIT_OBJECTIVES

    log(f"[reddit] Using params: {params}")
    
    all_ads, after = [], None
    for page in range(max_pages):
        if after: 
            params["after"] = after
        try:
            resp = session.get("https://api.scrapecreators.com/v1/reddit/ads/search",
                               params=params, timeout=REQUESTS_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("ads", []) or []
            all_ads.extend(batch)
            log(f"[reddit] fetched {len(batch)} ads (page {page+1})")
            after = data.get("after")
            if not after: 
                break
            time.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            error_msg = str(e)
            
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status in [400, 401, 403, 404, 422]:
                    log(f"[reddit] Permanent error {status} on page {page+1}: {e}")
                    raise Exception(f"Permanent error {status}: {error_msg}")
                elif status in [429, 500, 502, 503, 504]:
                    log(f"[reddit] Transient error {status} on page {page+1}: {e}")
                    raise Exception(f"Transient error {status}: {error_msg}")
            
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                log(f"[reddit] Transient network error on page {page+1}: {e}")
                raise Exception(f"Transient network error: {error_msg}")
            
            log(f"[reddit] Error on page {page+1}: {e}")
            raise Exception(f"Transient error: {error_msg}")

    json_path = _save_raw_json_to_s3("reddit", company_name, {"results": all_ads}, timestamp) if SAVE_RAW_JSON else None
    prepro_json_path = _process_and_save_useful_fields("reddit", company_name, all_ads, timestamp)

    processed_images = []
    with ThreadPoolExecutor(max_workers=IMAGE_DOWNLOAD_WORKERS) as image_executor:
        for ad in all_ads:
            res = _process_ad_images("reddit", ad, session, company_name, timestamp, image_executor)
            if res: 
                processed_images.append(res)

    return {"platform": "reddit", "company": company_name, "json_path": json_path,
            "prepro_json_path": prepro_json_path, "processed_images": processed_images, "num_ads": len(all_ads)}

def scrape_google(query: str, company_name: str, timestamp: str, max_pages: int = MAX_PAGES):
    # Handle None query (when domain lookup failed)
    if query is None:
        log("[google] No query provided (domain lookup failed), skipping Google scraper")
        return {
            "platform": "google",
            "company": company_name,
            "json_path": None,
            "prepro_json_path": None,
            "processed_images": [],
            "num_ads": 0
        }
    
    log(f"[google] Scraping ads for: {query}")
    
    session = requests.Session()
    session.headers.update({"x-api-key": GOOGLE_API_KEY})

    if "." in query:
        query_params = {"domain": query}
    elif query.upper().startswith("AR"):
        query_params = {"advertiserId": query}
    else:
        query_params = {"domain": query}

    # Add optional filters if provided
    if GOOGLE_TOPIC:
        query_params["topic"] = GOOGLE_TOPIC
    if GOOGLE_REGION:
        query_params["region"] = GOOGLE_REGION
    if GOOGLE_START_DATE:
        query_params["start_date"] = GOOGLE_START_DATE
    if GOOGLE_END_DATE:
        query_params["end_date"] = GOOGLE_END_DATE

    log(f"[google] Using params: {query_params}")

    all_ads, page_token = [], None
    for page in range(max_pages):
        page_params = dict(query_params)
        if page_token:
            page_params["cursor"] = page_token
        try:
            resp = session.get(
                "https://api.scrapecreators.com/v1/google/company/ads",
                params=page_params,
                timeout=REQUESTS_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("ads", []) or []
            all_ads.extend(batch)
            log(f"[google] fetched {len(batch)} ads (page {page+1})")

            if data.get("isLastPage", True) or not data.get("cursor"):
                break
            page_token = data.get("cursor")  # Google uses "cursor"
            time.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            error_msg = str(e)
            
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status in [400, 401, 403, 404, 422]:
                    log(f"[google] Permanent error {status} on page {page+1}: {e}")
                    raise Exception(f"Permanent error {status}: {error_msg}")
                elif status in [429, 500, 502, 503, 504]:
                    log(f"[google] Transient error {status} on page {page+1}: {e}")
                    raise Exception(f"Transient error {status}: {error_msg}")
            
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                log(f"[google] Transient network error on page {page+1}: {e}")
                raise Exception(f"Transient network error: {error_msg}")
            
            log(f"[google] Error on page {page+1}: {e}")
            raise Exception(f"Transient error: {error_msg}")

    json_path = _save_raw_json_to_s3("google", company_name, {"results": all_ads}, timestamp) if SAVE_RAW_JSON else None

    image_ads = [ad for ad in all_ads if (ad.get("format") or "").lower() == "image"]
    processed_images = []

    def fetch_ad_details(ad_url):
        resp = session.get(
            "https://api.scrapecreators.com/v1/google/ad",
            params={"url": ad_url},
            timeout=REQUESTS_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()

    with ThreadPoolExecutor(max_workers=IMAGE_DOWNLOAD_WORKERS) as image_executor:
        for ad in image_ads:
            ad_url = ad.get("adUrl") or ad.get("url")
            if not (ad_url and ad_url.startswith("http")):
                log(f"[google] skip ad missing adUrl")
                continue
            try:
                details = fetch_ad_details(ad_url)
            except Exception as e:
                error_msg = str(e)
                
                if hasattr(e, 'response') and e.response is not None:
                    status = e.response.status_code
                    if status in [400, 401, 403, 404, 422]:
                        log(f"[google] Permanent error {status} fetching details {ad_url}: {e}")
                        raise Exception(f"Permanent error {status}: {error_msg}")
                    elif status in [429, 500, 502, 503, 504]:
                        log(f"[google] Transient error {status} fetching details {ad_url}: {e}")
                        raise Exception(f"Transient error {status}: {error_msg}")
                
                if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    log(f"[google] Transient network error fetching details {ad_url}: {e}")
                    raise Exception(f"Transient network error: {error_msg}")
                
                log(f"[google] Error fetching details {ad_url}: {e}")
                raise Exception(f"Transient error: {error_msg}")

            variations = details.get("variations", [])
            for idx, var in enumerate(variations, start=1):
                image_urls = set()
                if var.get("imageUrl"):
                    image_urls.add(var["imageUrl"])
                
                if not image_urls:
                    log(f"[google] no image URLs for ad {details.get('creativeId')}, skipping")
                    continue

                for u in image_urls:
                    _ad_obj = {"snapshot": {"images": [{"original_image_url": u}]},
                            "id": details.get("creativeId")}
                    res = _process_ad_images("google", _ad_obj, session, company_name, timestamp, image_executor)
                    if res:
                        processed_images.append(res)

    prepro_json_path = _process_and_save_useful_fields("google", company_name, all_ads, timestamp)

    return {
        "platform": "google",
        "company": company_name,
        "json_path": json_path,
        "prepro_json_path": prepro_json_path,
        "processed_images": processed_images,
        "num_ads": len(all_ads)
    }

# ----------------------------
# Main Scrape Runner
# ----------------------------
def scrape(company_name: str, job_id: str, queries: dict):
    """
    Unified scrape runner for company.
    queries: dict with keys = ["meta_query", "google_query", "reddit_query", "linkedin_query"]
    
    Returns:
    - tuple: (num_platforms_scraped, num_ads, results, error_info)
      where error_info = None if success, or {"type": "permanent"/"transient", "message": "..."} if failed
    """
    company_name = company_name.lower()
    timestamp = datetime.datetime.utcnow().strftime("%H_%M_%S_%d_%m_%Y")

    # Validate API keys for enabled platforms
    missing_keys = []
    if ENABLE_META and not META_API_KEY:
        missing_keys.append("META_API_KEY")
    if ENABLE_LINKEDIN and not LINKEDIN_API_KEY:
        missing_keys.append("LINKEDIN_API_KEY")
    if ENABLE_REDDIT and not REDDIT_API_KEY:
        missing_keys.append("REDDIT_API_KEY")
    if ENABLE_GOOGLE and not GOOGLE_API_KEY:
        missing_keys.append("GOOGLE_API_KEY")
    
    if missing_keys:
        return 0, 0, {}, {
            "type": "permanent", 
            "message": f"Missing required API keys: {', '.join(missing_keys)}"
        }

    # Ensure S3 folder structure
    base_prefixes = [
        f"raw/json/{safe_name(company_name)}/",
        f"raw/images/{safe_name(company_name)}/",
        f"preprocessed/json/{safe_name(company_name)}/",
        f"preprocessed/images/{safe_name(company_name)}/"
    ]

    # Delete all existing content in these folders
    for prefix in base_prefixes:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
        if "Contents" in response:
            for obj in response["Contents"]:
                s3.delete_object(Bucket=BUCKET, Key=obj["Key"])

    # Recreate empty folder placeholders after deletion
    for p in base_prefixes:
        ensure_prefix(p)

    # Map query keys to scraper functions
    scraper_map = {
        "meta_query": ("meta", scrape_meta, ENABLE_META),
        "linkedin_query": ("linkedin", scrape_linkedin, ENABLE_LINKEDIN),
        "reddit_query": ("reddit", scrape_reddit, ENABLE_REDDIT),
        "google_query": ("google", scrape_google, ENABLE_GOOGLE)
    }

    results = {}
    num_ads = 0
    errors = []

    with ThreadPoolExecutor(max_workers=SCRAPER_WORKERS) as executor:
        futures = {}
        for query_key, (platform, scraper_func, is_enabled) in scraper_map.items():
            if not is_enabled:
                log(f"[{platform}] Skipped (disabled via ENABLE_{platform.upper()})")
                continue
                
            query = queries.get(query_key)
            if query:
                future = executor.submit(scraper_func, query, company_name, timestamp, MAX_PAGES)
                futures[future] = platform
            else:
                log(f"[{platform}] Skipped (no query provided)")

        for future in as_completed(futures):
            platform = futures[future]
            try:
                result = future.result()
                results[platform] = result
                num_ads += result.get("num_ads", 0)
                log(f"[{platform}] Completed successfully")
            except Exception as e:
                error_str = str(e)
                error_type = "transient"  # default to transient
                
                # Classify error based on keywords in error message
                if any(keyword in error_str.lower() for keyword in [
                    "permanent error",  # Add this
                    "401", "403", "404", "400", "422",
                    "unauthorized", "forbidden", "not found", "bad request",
                    "invalid company", "missing api key"
                ]):
                    error_type = "permanent"
                
                log(f"[{platform}] {error_type.capitalize()} failure: {e}")
                errors.append({"platform": platform, "error": error_str, "type": error_type})
                results[platform] = {"error": error_str}

    num_platforms_scraped = len([r for r in results.values() if "error" not in r])
    
    # Determine if scraping failed completely
    if num_platforms_scraped == 0:
        has_transient = any(e["type"] == "transient" for e in errors)
        
        if has_transient:
            return 0, 0, results, {
                "type": "transient",
                "message": f"All platforms failed. Errors: {'; '.join(e['error'] for e in errors)}"
            }
        elif errors:
            return 0, 0, results, {
                "type": "permanent",
                "message": f"All platforms failed with permanent errors. Errors: {'; '.join(e['error'] for e in errors)}"
            }
        else:
            return 0, 0, results, {
                "type": "permanent",
                "message": "No platforms enabled or no queries provided"
            }
    
    return num_platforms_scraped, num_ads, results, None

# ----------------------------
# Lambda Handler
# ----------------------------
def update_image2text_status(company_id: str, job_id: str, status: int):
    """
    Update the image2textStatus attribute in both companies and jobs tables.
    
    Args:
        company_id: Company ID to update
        job_id: Job ID to update
        status: 0 = not executed, 1 = currently running, 2 = done
    """
    success = True
    
    # Update companies table
    try:
        companies_table.update_item(
            Key={"companyId": company_id},
            UpdateExpression="SET image2textStatus = :status",
            ExpressionAttributeValues={":status": status}
        )
        log(f"[dynamodb] Updated companies.image2textStatus={status} for company {company_id}")
    except Exception as e:
        log(f"[dynamodb] Failed to update companies.image2textStatus: {e}")
        success = False
    
    # Update jobs table
    try:
        jobs_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET image2textStatus = :status",
            ExpressionAttributeValues={":status": status}
        )
        log(f"[dynamodb] Updated jobs.image2textStatus={status} for job {job_id}")
    except Exception as e:
        log(f"[dynamodb] Failed to update jobs.image2textStatus: {e}")
        success = False
    
    return success

def trigger_n8n_workflow(company_id: str, company_name: str, job_id: str, num_ads: int):
    """
    Trigger external n8n workflow for image-to-text extraction after scraping completes.
    Returns immediately after triggering (fire-and-forget pattern).
    
    Sets image2textStatus=1 (running) in both companies and jobs tables before trigger.
    N8N workflow should set image2textStatus=2 when done.
    
    Args:
        company_id: Company ID for DynamoDB updates
        company_name: Name of the company scraped
        job_id: Job identifier
        num_ads: Total number of ads scraped
    """
    n8n_webhook_url = os.environ.get("N8N_WEBHOOK_URL")
    
    if not n8n_webhook_url:
        log("[n8n] No webhook URL configured, skipping trigger")
        return False
    
    # Update both tables to indicate image2text workflow is starting (status = 1)
    update_image2text_status(company_id, job_id, 1)
    
    # Create S3-safe timestamp: replace colons and periods with hyphens
    raw_timestamp = datetime.datetime.utcnow().isoformat()
    safe_timestamp = raw_timestamp.replace(":", "-").replace(".", "-")
    
    payload = {
        "companyId": company_id,
        "companyName": safe_name(company_name),
        "jobId": job_id,
        "numAds": num_ads,
        "bucket": BUCKET,
        "preprocessedImagesPath": f"preprocessed/images/{safe_name(company_name)}/",
        "preprocessedJsonPath": f"preprocessed/json/{safe_name(company_name)}/",
        "timestamp": safe_timestamp
    }
    
    try:
        # Fire-and-forget: very short timeout, don't wait for n8n to complete
        response = requests.post(
            n8n_webhook_url,
            json=payload,
            timeout=3,  # Only wait 3 seconds to confirm trigger accepted
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        log(f"[n8n] Successfully triggered workflow for {company_name} (returning immediately)")
        return True
    except requests.exceptions.Timeout:
        # Timeout is OK - webhook was triggered, it's just taking time to respond
        log(f"[n8n] Webhook triggered for {company_name} (timed out waiting for response, but that's OK)")
        return True
    except Exception as e:
        log(f"[n8n] Failed to trigger workflow: {e}")
        # Revert the image2textStatus to 0 (not executed) in both tables since trigger failed
        update_image2text_status(company_id, job_id, 0)
        return False

def lambda_handler(event, context):
    """
    Lambda handler for ad scraping workflow.
    
    Expected event format:
    {
        "companyId": "company-123",
        "jobId": "job-456"
    }
    
    Returns simple response for calling lambda:
    {
        "status": 2,  # status of scraping process (2 = done)
        "numAds": 127  # total ads scraped across all platforms
    }
    """
    company_id = event.get("companyId")
    job_id = event.get("jobId")

    # Validate input
    if not company_id or not job_id:
        log(f"[error] Missing required parameters: companyId={company_id}, jobId={job_id}")
        raise ValueError("Permanent error: Missing required parameters (companyId or jobId)")

    # Fetch company from DynamoDB
    try:
        company_item = companies_table.get_item(Key={"companyId": company_id}).get("Item")
    except Exception as e:
        log(f"[dynamodb] Error fetching company: {e}")
        raise Exception(f"Transient error: Failed to fetch company from DynamoDB: {str(e)}")

    if not company_item:
        log(f"[error] Company not found: {company_id}")
        raise ValueError(f"Permanent error: Company not found: {company_id}")

    # Validate company name
    company_name = company_item.get("companyName", "").strip().lower()
    if not company_name:
        raise ValueError(f"Permanent error: Invalid or missing company name for company {company_id}")

    query_keys = ["meta_query", "google_query", "reddit_query", "linkedin_query"]

    # Build queries: use table value if exists, otherwise prepare from generic query
    queries = {}
    
    # Check if all query keys exist in DB
    all_queries_in_db = all(company_item.get(k) for k in query_keys)
    
    if all_queries_in_db:
        # Use DB values directly (existing behavior)
        for k in query_keys:
            queries[k] = company_item.get(k)
        log("[queries] Using all queries from database")
    else:
        # Company not fully configured in DB - use intelligent query preparation
        log("[queries] Company queries not in DB, preparing from company name")
        queries = prepare_queries(company_name)

                # Determine domain for persistence
        domain = ""
        if is_domain(company_name):
            domain = company_name
        elif queries.get("google_query"):
            domain = queries.get("google_query")

        # Persist prepared queries and domain back to database for future runs
        update_company_queries(company_id, queries, domain)

    # Perform scraping
    try:
        num_platforms_scraped, num_ads, results, error_info = scrape(company_name, job_id, queries)
        
        # Check if scraping failed
        if error_info:
            if error_info["type"] == "permanent":
                log(f"[scrape] Permanent error: {error_info['message']}")
                raise ValueError(error_info["message"])
            else:  # transient
                log(f"[scrape] Transient error: {error_info['message']}")
                raise Exception(error_info["message"])
        
        # Success case
        total_processed_images = sum(len(r.get("processed_images", [])) for r in results.values())

        if num_platforms_scraped > 0 and num_ads == 0:
            log(f"[info] Platforms scraped successfully, but no ads found for {company_name}")

        for platform, res in results.items():
            if "processed_images" in res and not res["processed_images"]:
                log(f"[info] {platform} scraped ads, but no images found")

        log(f"[complete] Scraped {num_ads} ads from {num_platforms_scraped} platforms for {company_name}")

        # Trigger n8n workflow if images were processed
        if total_processed_images > 0:
            trigger_n8n_workflow(company_id, company_name, job_id, total_processed_images)
        else:
            log("[info] No images processed, skipping image2text workflow")

        return {
            "status": 2,
            "numAds": num_ads
        }
    
    except ValueError as e:
        # Permanent error from scrape() - propagate as ValueError
        log(f"[scrape] Permanent error: {e}")
        raise
    
    except Exception as e:
        # Transient error or unknown error from scrape() - treat as transient
        log(f"[scrape] Transient/unknown error: {e}")
        # Check if error message indicates it's permanent
        error_msg = str(e)
        if "permanent error" in error_msg.lower():
            raise ValueError(error_msg)
        # Otherwise treat as transient (retry-able)
        raise Exception(f"Transient error during scraping: {error_msg}")