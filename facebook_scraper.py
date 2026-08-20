from playwright.sync_api import sync_playwright
from urllib.parse import urlencode

import random
import time
import os

from supabase import create_client
from dotenv import load_dotenv


# ============================================================
# SUPABASE
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# BUILD FACEBOOK ADS LIBRARY URL
# ============================================================

def build_ads_library_url(keyword, country="US"):

    base_url = "https://www.facebook.com/ads/library/"

    params = {
        "active_status": "active",
        "ad_type": "all",
        "country": country,
        "is_targeted_country": "false",
        "media_type": "all",
        "q": keyword,
        "search_type": "keyword_unordered",
        "sort_data[mode]": "total_impressions",
        "sort_data[direction]": "desc",
    }

    return f"{base_url}?{urlencode(params)}"


# ============================================================
# PRINT AD
# ============================================================

def print_instagram_ad(ad_data):

    print("=" * 60)
    print("Page:", ad_data["page_name"])
    print("Title:", ad_data["title"])
    print("CTA:", ad_data["cta"])
    print("Body:", ad_data["body"])
    print("Link:", ad_data["link"])
    print("Archive:", ad_data["archive_id"])


# ============================================================
# PROCESS FACEBOOK GRAPHQL EDGES
# ============================================================

def process_edges(edges, seen_ads):

    for edge in edges:

        collated_results = edge["node"].get("collated_results")

        if not collated_results:
            continue

        for ad in collated_results:

            archive_id = ad.get("ad_archive_id")

            if not archive_id:
                continue

            # Prevent processing the same ad multiple times
            if archive_id in seen_ads:
                continue

            seen_ads.add(archive_id)

            snapshot = ad.get("snapshot", {})

            link = (
                snapshot.get("link_url") or ""
            ).rstrip("/")

            # ------------------------------------------------
            # ONLY INSTAGRAM LINKS
            # ------------------------------------------------

            if "instagram.com" not in link.lower():
                continue

            # Ignore generic Instagram URLs
            generic_instagram_urls = {
                "https://www.instagram.com",
                "http://www.instagram.com",
                "https://instagram.com",
                "http://instagram.com",
            }

            if link.lower() in generic_instagram_urls:
                continue

            # ------------------------------------------------
            # CHECK IF INSTAGRAM PROFILE ALREADY EXISTS
            # ------------------------------------------------

            try:

                existing = (
                    supabase
                    .table("facebook_ads")
                    .select("link")
                    .eq("link", link)
                    .limit(1)
                    .execute()
                )

                if existing.data:

                    print(
                        f"Skipping existing Instagram profile: "
                        f"{link}"
                    )

                    continue

            except Exception as e:

                print(
                    f"Supabase duplicate check failed: {e}"
                )

                continue

            # ------------------------------------------------
            # BUILD DATABASE RECORD
            # ------------------------------------------------

            ad_data = {

                "archive_id": archive_id,

                "page_name": snapshot.get(
                    "page_name",
                    ""
                ),

                "title": snapshot.get(
                    "title",
                    ""
                ),

                "cta": snapshot.get(
                    "cta_text",
                    ""
                ),

                "body": (
                    snapshot
                    .get("body", {})
                    .get("text", "")
                ),

                "link": link,

                # Instagram enrichment fields
                "followers": None,
                "following": None,
                "posts": None,
                "bio": None,
                "website": None,
                "last_post": None,

                # Pipeline status
                "status": "pending",
            }

            print_instagram_ad(ad_data)

            # ------------------------------------------------
            # UPSERT
            # ------------------------------------------------

            try:

                (
                    supabase
                    .table("facebook_ads")
                    .upsert(
                        ad_data,
                        on_conflict="archive_id"
                    )
                    .execute()
                )

                print(
                    f"Saved: {ad_data['page_name']}"
                )

            except Exception as e:

                print(
                    f"Supabase insert error: {e}"
                )


# ============================================================
# MAIN FACEBOOK SCRAPER FUNCTION
# ============================================================

def run_facebook_scraper(
    keyword="lip filler",
    country="US",
    max_scrolls=200
):

    url = build_ads_library_url(
        keyword,
        country
    )

    seen_ads = set()

    print()
    print("=" * 60)
    print("FACEBOOK ADS LIBRARY SCRAPER")
    print("=" * 60)
    print(f"Keyword: {keyword}")
    print(f"Country: {country}")
    print(f"Max scrolls: {max_scrolls}")
    print()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        # ====================================================
        # FACEBOOK GRAPHQL RESPONSE HANDLER
        # ====================================================

        def handle_response(response):

            if "graphql" not in response.url:
                return

            post_data = response.request.post_data or ""

            if (
                "AdLibrarySearchPaginationQuery"
                not in post_data
            ):
                return

            try:

                data = response.json()

                edges = (
                    data["data"]
                    ["ad_library_main"]
                    ["search_results_connection"]
                    ["edges"]
                )

                if not edges:
                    return

                process_edges(
                    edges,
                    seen_ads
                )

            except Exception:

                import traceback
                traceback.print_exc()

        # Register response listener
        page.on(
            "response",
            handle_response
        )

        # ====================================================
        # OPEN ADS LIBRARY
        # ====================================================

        print("Opening Facebook Ads Library...")

        page.goto(
            url,
            wait_until="domcontentloaded"
        )

        time.sleep(5)

        # ====================================================
        # SCROLL
        # ====================================================

        for i in range(max_scrolls):

            scroll = random.randint(
                2500,
                5000
            )

            wait = random.uniform(
                1.5,
                3.8
            )

            page.mouse.wheel(
                0,
                scroll
            )

            time.sleep(wait)

            # Occasional longer pause
            if random.random() < 0.1:

                extra_wait = random.uniform(
                    5,
                    10
                )

                print(
                    f"Taking a longer pause: "
                    f"{extra_wait:.2f}s"
                )

                time.sleep(
                    extra_wait
                )

            print(
                f"Scroll {i + 1}/{max_scrolls} | "
                f"{scroll}px | "
                f"waited {wait:.2f}s"
            )

        # ====================================================
        # CLOSE
        # ====================================================

        page.close()
        browser.close()

    print()
    print("=" * 60)
    print("FACEBOOK SCRAPER FINISHED")
    print("=" * 60)
    print(
        f"Unique ads encountered: "
        f"{len(seen_ads)}"
    )
    print()