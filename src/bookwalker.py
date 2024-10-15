import re
import time
import requests
from bs4 import BeautifulSoup
from src.config import *
from src.models.bookwalker import BookwalkerBook, BookwalkerSeries
from src.utils.string_utils import clean_str, similar, get_shortened_title

def search_bookwalker(query, type, print_info=False, alternative_search=False, shortened_search=False, total_pages_to_scrape=5):
    books = []
    series_list = []
    no_book_result_searches = []
    
    search = urllib.parse.quote(query)
    base_url = "https://global.bookwalker.jp/search/"
    
    for page in range(1, total_pages_to_scrape + 1):
        url = f"{base_url}?word={search}&page={page}"
        
        if type.lower() == "m":
            url += "&qcat=2"
        elif type.lower() == "l":
            url += "&qcat=3"
        
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        book_list = soup.find_all("li", class_="o-tile")
        
        if not book_list:
            no_book_result_searches.append(query)
            break
        
        for book in book_list:
            title = book.find("h2", class_="a-tile-ttl").text.strip()
            link = book.find("a", class_="a-tile-thumb-img")['href']
            thumbnail = book.find("img", class_="lazy")['data-original']
            
            book_type = book.find("div", class_="a-tile-tag").text.strip()
            
            date = book.find("p", class_="a-tile-date").text.strip()
            is_released = "Pre-Order" not in date
            
            volume_number = re.search(r'Vol\.(\d+)', title)
            volume_number = int(volume_number.group(1)) if volume_number else None
            
            books.append(BookwalkerBook(title, title, volume_number, None, date, is_released, None, link, thumbnail, book_type, None, None))
    
    for book in books:
        matching_books = [b for b in books if b.book_type == book.book_type and similar(b.title, book.title) >= required_similarity_score]
        if matching_books:
            series = BookwalkerSeries(book.title, matching_books, len(matching_books), book.book_type)
            if series not in series_list:
                series_list.append(series)
    
    return series_list

def check_for_new_volumes_on_bookwalker():
    print("\nChecking for new volumes on bookwalker...")
    
    for path in paths:
        if not os.path.exists(path):
            continue
        
        for root, dirs, files in os.walk(path):
            volumes = [f for f in files if get_file_extension(f) in file_extensions]
            if not volumes:
                continue
            
            series_name = os.path.basename(root)
            volume_type = "m" if any(get_file_extension(f) in manga_extensions for f in volumes) else "l"
            
            bookwalker_volumes = search_bookwalker(series_name, volume_type)
            
            if not bookwalker_volumes:
                continue
            
            existing_volumes = set(get_volume_number(v) for v in volumes)
            new_volumes = [bv for bv in bookwalker_volumes[0].books if bv.volume_number not in existing_volumes]
            
            if new_volumes:
                print(f"\nNew volumes found for {series_name}:")
                for nv in new_volumes:
                    print(f"Volume {nv.volume_number}: {nv.title} - {nv.date}")
                    
                    if bookwalker_webhook_urls:
                        send_discord_message(
                            f"New volume found for {series_name}",
                            [create_bookwalker_embed(nv)],
                            url=bookwalker_webhook_urls[0] if nv.is_released else bookwalker_webhook_urls[1]
                        )

# Add helper functions like get_volume_number and create_bookwalker_embed here
