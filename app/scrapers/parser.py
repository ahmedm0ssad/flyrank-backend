import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

RATING_MAP = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def parse_listing_page(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    books: list[dict] = []

    for article in soup.find_all("article", class_="product_pod"):
        title_tag = article.find("h3")
        if not title_tag or not isinstance(title_tag, Tag):
            continue

        link_tag = title_tag.find("a")
        if not isinstance(link_tag, Tag):
            continue

        relative_url = link_tag.get("href", "")
        if not relative_url:
            continue

        book_url = urljoin(page_url, relative_url)
        title = link_tag.get("title") or link_tag.get_text(strip=True)

        rating_tag = article.find("p", class_="star-rating")
        rating_raw = ""
        if isinstance(rating_tag, Tag):
            classes = rating_tag.get("class", [])
            for cls in classes:
                if cls.lower() in RATING_MAP:
                    rating_raw = cls.lower()
                    break

        price_raw = ""
        price_tag = article.find("p", class_="price_color")
        if isinstance(price_tag, Tag):
            price_raw = price_tag.get_text(strip=True)

        availability_raw = ""
        avail_tag = article.find("p", class_="instock availability")
        if isinstance(avail_tag, Tag):
            availability_raw = avail_tag.get_text(strip=True)

        books.append({
            "url": book_url,
            "title": title,
            "rating_raw": rating_raw,
            "price_raw": price_raw,
            "availability_raw": availability_raw,
        })

    return books


def parse_detail_page(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result: dict = {
        "description": None,
        "category": None,
        "upc": None,
        "image_url": None,
    }

    title_tag = soup.find("h1")
    if isinstance(title_tag, Tag):
        result["title"] = title_tag.get_text(strip=True)

    table = soup.find("table", class_="table table-striped")
    if isinstance(table, Tag):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            header = row.find("th")
            if not cells or not isinstance(header, Tag):
                continue
            key = header.get_text(strip=True).lower()
            value = cells[0].get_text(strip=True)
            if "upc" in key:
                result["upc"] = value
            elif "price (incl" in key:
                result["price_raw"] = value
            elif "availability" in key:
                result["availability_raw"] = value

    desc_tag = soup.find("div", id="product_description")
    if isinstance(desc_tag, Tag):
        sibling = desc_tag.find_next_sibling("p")
        if isinstance(sibling, Tag):
            result["description"] = sibling.get_text(strip=True)

    breadcrumb = soup.find("ul", class_="breadcrumb")
    if isinstance(breadcrumb, Tag):
        links = breadcrumb.find_all("a")
        if len(links) >= 3:
            result["category"] = links[2].get_text(strip=True)

    img_tag = soup.find("div", class_="item active")
    if isinstance(img_tag, Tag):
        img_link = img_tag.find("img")
        if isinstance(img_link, Tag):
            src = img_link.get("src", "")
            if src:
                result["image_url"] = urljoin(page_url, src)

    return result


def extract_next_page_url(html: str, page_url: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    li = soup.find("li", class_="next")
    if isinstance(li, Tag):
        a_tag = li.find("a")
        if isinstance(a_tag, Tag):
            href = a_tag.get("href")
            if href:
                return urljoin(page_url, href)
    return None
