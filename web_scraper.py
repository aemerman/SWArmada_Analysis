# -*- coding: utf-8 -*-
"""
Webdriver

Use selenium to open an events page on T4.tools, wait for the Javascript to
load event information into the html tree, including fleet lists and tournament
results. The html tree is sent to event_to_file for parsing.

@author: alexe
"""

import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup
import event_to_file

def parse_webpage(url, name, do_scores=True, do_fleets=True):
    chrome_options = Options()
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)
    # Wait for Javascript to load
    time.sleep(2)

    # Fleet info loaded into html source, just need to parse it
    soup = BeautifulSoup(driver.page_source, 'html5lib')
    kwargs = {'url': url, 'name': name,
              'do_scores': do_scores,
              'do_fleets': do_fleets}
    event_to_file.parse_site(soup, **kwargs)

    driver.quit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="web_scraper",
        description="program to get SW Armada event data from T4.tools")
    parser.add_argument("url", type=str,
                    help="URL of tournament that you want to analyze")
    parser.add_argument("-n", "--name", type=str,
                        help="Name for tournament within DB (taken from"
                        + " URL if not specified)")
    parser.add_argument("--no-scores", action='store_true',
                        help="flag to skip storing tournament results")
    parser.add_argument("--no-fleets", action='store_true',
                        help="flag to skip storing fleet information")
    args = parser.parse_args()
    url = args.url
    name = args.name
    if not name:
        name = url.split("/")[-1]

    kwargs = {'url': url, 'name': name,
              'do_scores': not args.no_scores,
              'do_fleets': not args.no_fleets}
    parse_webpage(**kwargs)