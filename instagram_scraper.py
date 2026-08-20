from playwright.sync_api import sync_playwright
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

import os
import time
import random
import traceback


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY is missing from .env")


# ============================================================
# SUPABASE
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# GET NEXT LEAD
# ============================================================

def get_next_lead():
    response = (
        supabase
        .table("facebook_ads")
        .select("*")
        .eq("status", "pending")
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    lead = response.data[0]

    print(f"\nLoaded: {lead.get('page_name')}")
    print(f"Instagram: {lead.get('link')}")

    return lead


# ============================================================
# CHECK EXISTING INSTAGRAM DATA
# ============================================================

def check_existing_instagram(link):

    response = (
        supabase
        .table("facebook_ads")
        .select(
            "followers, following, posts, bio, website, last_post"
        )
        .eq("link", link)
        .eq("status", "complete")
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


# ============================================================
# UPDATE LEAD
# ============================================================

def update_lead(archive_id, update_data):

    (
        supabase
        .table("facebook_ads")
        .update(update_data)
        .eq("archive_id", archive_id)
        .execute()
    )


# ============================================================
# SCRAPE ONE INSTAGRAM LEAD
# ============================================================

def scrape_instagram(lead, context):

    page_name = lead.get("page_name")
    link = lead.get("link")
    archive_id = lead.get("archive_id")

    print(f"\n{'=' * 60}")
    print(f"Processing: {page_name}")
    print(f"Instagram: {link}")
    print(f"{'=' * 60}")

    # ========================================================
    # CHECK LINK
    # ========================================================

    if not link or link.rstrip("/") == "https://www.instagram.com":

        print("❌ Empty Instagram link")

        update_lead(
            archive_id,
            {
                "status": "invalid_instagram_link"
            }
        )

        return False

    # ========================================================
    # CHECK IF WE ALREADY HAVE THIS INSTAGRAM DATA
    # ========================================================

    existing = check_existing_instagram(link)

    if existing:

        update_data = {
            "followers": existing.get("followers"),
            "following": existing.get("following"),
            "posts": existing.get("posts"),
            "bio": existing.get("bio"),
            "website": existing.get("website"),
            "last_post": existing.get("last_post"),
            "status": "complete"
        }

        update_lead(
            archive_id,
            update_data
        )

        print(
            f"♻️ Reused Instagram data for {page_name}"
        )

        return True

    # ========================================================
    # STORAGE
    # ========================================================

    clinic = {
        "followers": None,
        "following": None,
        "posts": None,
        "bio": None,
        "website": None,
        "last_post": None
    }

    state = {
        "profile_found": False,
        "posts_found": False,
        "scrape_finished": False
    }

    # ========================================================
    # CREATE PAGE
    # ========================================================

    page = context.new_page()

    # ========================================================
    # GRAPHQL RESPONSE HANDLER
    # ========================================================

    def handle_response(response):

        try:

            # ==================================================
            # PROFILE QUERY
            # ==================================================

            if "/api/graphql" in response.url:

                post_data = response.request.post_data or ""

                if "PolarisProfilePageContentQuery" in post_data:

                    data = response.json()

                    profile = (
                        data
                        .get("data", {})
                        .get("user")
                    )

                    if not profile:
                        return

                    bio_links = profile.get(
                        "bio_links",
                        []
                    )

                    clinic["followers"] = profile.get(
                        "follower_count"
                    )

                    clinic["following"] = profile.get(
                        "following_count"
                    )

                    clinic["posts"] = profile.get(
                        "media_count"
                    )

                    clinic["bio"] = profile.get(
                        "biography"
                    )

                    if bio_links:

                        clinic["website"] = (
                            bio_links[0].get("url")
                        )

                    else:

                        clinic["website"] = None

                    state["profile_found"] = True

                    print(
                        f"📊 Profile data captured: "
                        f"{page_name}"
                    )

            # ==================================================
            # POSTS / TIMELINE QUERY
            # ==================================================

            if "/graphql/query" in response.url:

                data = response.json()

                timeline_data = (
                    data
                    .get("data", {})
                    .get(
                        "xdt_api__v1__feed__user_timeline_graphql_connection"
                    )
                )

                if not timeline_data:
                    return

                timeline = timeline_data.get(
                    "edges",
                    []
                )

                latest_timestamp = 0

                for edge in timeline:

                    node = edge.get(
                        "node",
                        {}
                    )

                    caption = node.get(
                        "caption"
                    )

                    if not caption:
                        continue

                    timestamp = caption.get(
                        "created_at"
                    )

                    if timestamp is None:
                        continue

                    try:

                        timestamp = int(timestamp)

                    except (ValueError, TypeError):

                        continue

                    if timestamp > latest_timestamp:

                        latest_timestamp = timestamp

                # ------------------------------------------------
                # WE FOUND A POST
                # ------------------------------------------------

                if latest_timestamp > 0:

                    clinic["last_post"] = (
                        datetime
                        .fromtimestamp(latest_timestamp)
                        .date()
                        .isoformat()
                    )

                    state["posts_found"] = True

                    print(
                        f"📅 Last post captured: "
                        f"{clinic['last_post']}"
                    )

                # ------------------------------------------------
                # ONLY MARK COMPLETE WHEN BOTH ARE FOUND
                # ------------------------------------------------

                if (
                    state["profile_found"]
                    and state["posts_found"]
                ):

                    update_data = {
                        "followers": clinic["followers"],
                        "following": clinic["following"],
                        "posts": clinic["posts"],
                        "bio": clinic["bio"],
                        "website": clinic["website"],
                        "last_post": clinic["last_post"],
                        "status": "complete"
                    }

                    update_lead(
                        archive_id,
                        update_data
                    )

                    print(
                        f"✅ Updated {page_name}"
                    )

                    state["scrape_finished"] = True

        except Exception:

            print(
                f"⚠️ Error while processing response "
                f"for {page_name}"
            )

            traceback.print_exc()

    # ========================================================
    # ATTACH RESPONSE LISTENER
    # ========================================================

    page.on(
        "response",
        handle_response
    )

    try:

        # ====================================================
        # OPEN INSTAGRAM
        # ====================================================

        print(f"\nOpening: {link}")

        page.goto(
            link,
            wait_until="domcontentloaded",
            timeout=30000
        )

        # ====================================================
        # HUMAN-LIKE SCROLLING
        # ====================================================

        page.mouse.wheel(
            0,
            random.randint(500, 1200)
        )

        page.wait_for_timeout(
            random.randint(1000, 3000)
        )

        page.mouse.wheel(
            0,
            random.randint(300, 900)
        )

        # ====================================================
        # WAIT FOR DATA
        # ====================================================

        start = time.time()

        while not state["scrape_finished"]:

            if time.time() - start > 30:

                print(
                    f"❌ Instagram profile data "
                    f"was not captured: {page_name}"
                )

                update_lead(
                    archive_id,
                    {
                        "status": "instagram_not_found"
                    }
                )

                return False

            # IMPORTANT:
            # Prevents the loop from hammering the CPU.

            page.wait_for_timeout(200)

        return True

    except Exception:

        print(
            f"❌ Instagram scraper error: "
            f"{page_name}"
        )

        traceback.print_exc()

        update_lead(
            archive_id,
            {
                "status": "instagram_not_found"
            }
        )

        return False

    finally:

        print(
            f"Closing page: {page_name}"
        )

        try:
            page.close()
        except Exception:
            pass


# ============================================================
# MAIN SCRAPER LOOP
# ============================================================

def run_instagram_scraper():

    print("\n🚀 Instagram scraper starting...\n")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            storage_state="instagram_state.json"
        )

        try:

            while True:

                # ==============================================
                # GET NEXT PENDING LEAD
                # ==============================================

                lead = get_next_lead()

                if lead is None:

                    print(
                        "\n✅ No pending leads left."
                    )

                    break

                # ==============================================
                # SCRAPE
                # ==============================================

                success = scrape_instagram(
                    lead,
                    context
                )

                # ==============================================
                # RESULT
                # ==============================================

                if success:

                    print(
                        f"✅ Finished: "
                        f"{lead.get('page_name')}"
                    )

                else:

                    print(
                        f"⚠️ Failed: "
                        f"{lead.get('page_name')}"
                    )

                # ==============================================
                # RANDOM DELAY
                # ==============================================

                wait_time = random.uniform(
                    8,
                    18
                )

                print(
                    f"Waiting {wait_time:.1f} seconds..."
                )

                time.sleep(wait_time)

        except KeyboardInterrupt:

            print(
                "\n⚠️ Scraper stopped manually."
            )

        except Exception:

            print(
                "\n❌ Fatal scraper error:"
            )

            traceback.print_exc()

        finally:

            print(
                "\n🛑 Closing browser..."
            )

            try:
                context.close()
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass

            print(
                "✅ Browser closed."
            )


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def instagram_scraper():

    run_instagram_scraper()