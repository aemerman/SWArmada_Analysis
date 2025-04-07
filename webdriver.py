# -*- coding: utf-8 -*-
"""
Created on Sun Mar 30 16:04:06 2025

@author: alexe
"""

import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup
import event_to_file

def parse_webpage(url, name, no_event_info=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
        
    driver = webdriver.Chrome(options=chrome_options)
    
    driver.get(url)
    # Wait for Javascript to load
    time.sleep(2)
    
    # Fleet info loaded into html source, just need to parse it
    soup = BeautifulSoup(driver.page_source, 'html5lib')
    event_to_file.parse_site(soup, name, no_event_info)
    
    driver.quit()
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="T4_web_scraper",
        description="program to get SW Armada event data from T4.tools")
    parser.add_argument("url", type=str)
    parser.add_argument("-n", "--name", type=str)
    parser.add_argument("--no-event-info", action='store_true')
    args = parser.parse_args()
    url = args.url
    name = args.name
    if not name:
        name = url.split("/")[-1]
    
    parse_webpage(url, name, no_event_info = args.no_event_info)