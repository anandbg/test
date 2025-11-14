# Mobbin Section Data Extraction Report

## Section Information
- **Section ID**: `26660d92-77ce-470d-a481-fa9873bd1b3e`
- **Title**: V7 section
- **URL**: https://mobbin.com/sites/sections/26660d92-77ce-470d-a481-fa9873bd1b3e

## Extracted Data Summary

### Images Found
- **Total Images**: 163
- **App Logos**: 123
- **App Screenshots**: 40

### Files Generated
1. `mobbin_section_summary.json` - Complete summary with all metadata and categorized image URLs
2. `mobbin_section_images.txt` - List of all image URLs (one per line)
3. `mobbin_section.html` - Full HTML page source
4. `fetch_mobbin_section.py` - Python script used for extraction

## Image Sources
All images are hosted on Supabase storage:
- Base URL: `https://ujasntkfphywizsdaapi.supabase.co/storage/v1/object/public/content/`
- App logos: `/app_logos/`
- App screenshots: `/app_screens/`

## Usage
To re-fetch the data, run:
```bash
python3 fetch_mobbin_section.py
```

## Notes
- The page is a Next.js application that loads content dynamically
- Images are stored in Supabase public storage
- The extraction script parses HTML to find image URLs embedded in the page source
