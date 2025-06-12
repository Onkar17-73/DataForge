import requests
from bs4 import BeautifulSoup
from typing import List, Optional

def scrape_images(query: str, num_images: int = 5) -> List[str]:
    """
    Scrape image URLs from Google Images based on a query.
    
    Args:
        query (str): Search query
        num_images (int): Number of images to scrape
        
    Returns:
        List[str]: List of image URLs
    """
    # Google Images search URL
    url = f"https://www.google.com/search?q={query}&tbm=isch"
    
    # Set headers to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all image tags
        image_tags = soup.find_all('img')
        
        # Extract image URLs (skip the first one as it's usually the Google logo)
        image_urls = [img.get('src') for img in image_tags[1:] if img.get('src') and img.get('src').startswith('http')]
        
        # Limit to requested number
        return image_urls[:num_images]
        
    except Exception as e:
        print(f"Error scraping images: {e}")
        return []

def download_image(url: str) -> Optional[bytes]:
    """
    Download an image from a URL.
    
    Args:
        url (str): Image URL
        
    Returns:
        Optional[bytes]: Image data or None if download failed
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None

# Make the function available at module level
download_image = download_image