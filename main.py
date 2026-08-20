from instagram_scraper import instagram_scraper
from facebook_scraper import run_facebook_scraper
def main():

    print()
    print("#" * 60)
    print("#")
    print("#          LEAD SCRAPING PIPELINE")
    print("#")
    print("#" * 60)
    print()

    # ========================================================
    # STEP 1
    # FACEBOOK ADS LIBRARY
    # ========================================================

    print("Starting STEP 1...")
    print()

    run_facebook_scraper(
        keyword="lip filler",
        country="US",
        max_scrolls=200
    )

    print()
    print("STEP 1 complete.")
    print()

    # ========================================================
    # STEP 2
    # INSTAGRAM ENRICHMENT
    # ========================================================
    print("staring IG scraper")
    instagram_scraper()


if __name__ == "__main__":
    main()