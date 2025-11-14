#!/usr/bin/env python3
"""
Script to fetch and process Mobbin section data
"""
import requests
import json
import re
from urllib.parse import urlparse, parse_qs

def fetch_mobbin_section(section_url):
    """Fetch Mobbin section page and extract data"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    print(f"Fetching: {section_url}")
    response = requests.get(section_url, headers=headers)
    response.raise_for_status()
    
    # Extract section ID from URL
    section_id_match = re.search(r'/sections/([a-f0-9-]+)', section_url)
    section_id = section_id_match.group(1) if section_id_match else None
    
    print(f"Section ID: {section_id}")
    
    # Save HTML
    with open('/workspace/mobbin_section.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    # Try to extract image URLs
    image_urls = re.findall(
        r'https://ujasntkfphywizsdaapi\.supabase\.co/storage/v1/object/public/content/[^"\s<>]+\.(?:jpg|jpeg|png|webp|gif)',
        response.text,
        re.IGNORECASE
    )
    
    # Remove duplicates and sort
    unique_images = sorted(set(image_urls))
    
    print(f"\nFound {len(unique_images)} unique image URLs")
    
    # Extract metadata
    title_match = re.search(r'<title>([^<]+)</title>', response.text)
    title = title_match.group(1) if title_match else "Unknown"
    
    og_title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
    og_title = og_title_match.group(1) if og_title_match else title
    
    # Create summary
    summary = {
        'section_id': section_id,
        'title': title,
        'og_title': og_title,
        'url': section_url,
        'image_count': len(unique_images),
        'image_urls': unique_images[:20],  # First 20 images
    }
    
    # Save summary
    with open('/workspace/mobbin_section_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    # Save all image URLs
    with open('/workspace/mobbin_section_images.txt', 'w', encoding='utf-8') as f:
        for url in unique_images:
            f.write(url + '\n')
    
    print(f"\nSummary saved to mobbin_section_summary.json")
    print(f"Image URLs saved to mobbin_section_images.txt")
    print(f"\nTitle: {title}")
    print(f"Found {len(unique_images)} images")
    
    return summary

if __name__ == '__main__':
    url = "https://mobbin.com/sites/sections/26660d92-77ce-470d-a481-fa9873bd1b3e?utm_source=copy_link&utm_medium=link&utm_campaign=section_sharing"
    fetch_mobbin_section(url)
