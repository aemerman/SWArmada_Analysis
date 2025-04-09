# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 14:20:59 2025

@author: alexe
"""
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import fleet_parser
import sqlite3

# Replace tabs, commas etc in player names with spaces
def clean_name(name):
    name = name.replace(',',' ')
    return ' '.join(name.strip().split())

# Parse fleet lists
# - Fleet lists are read as text strings with no standard format
# - Many, but not all, players use an online fleet builder with an export
# function. These lists will have similar formats and use standard names
# for all ships and squadrons.
# - The basic layout of almost all lists will be a series of paragraphs
# with the first line giving the name of a ship and subsequent lines
# listing upgrades added to the ship. Squadrons will be listed in a
# paragraph at the end, one name per line. Points cost information is
# almost always included, but there is no standard convention for how to
# include it.
# - Lists may contain a header with a fleet name, faction, commander,
# total points cost, objectives, etc.
def get_fleet_lists(fleets, base_dir, ev_name, ev_id, ship_id):
    dict_fleets = {"id": [], "player": [], "event_id": [], "faction_name": [],
                   "commander": []}
    dict_ships = {"id": [], "fleet_id": [], "ship_name": []}
    dict_upgrades = {"upgrade_name": [], "fleet_id": [], "fleet_ship_id": []}
    dict_squadrons = {"squadron_name": [], "fleet_id": [], "count": []}
    fleet_id = 1
    for child in fleets.children:
        divs = child.find_all('div')
        name = clean_name(divs[0].span.span.text)
        print(f"parsing fleet list of {name}")
        raw_fleet = divs[1].pre.text
        # Fleet list naturally represented in dictionary format. Start here
        # and then split into csv files
        fleet = fleet_parser.parse_fleet(raw_fleet)
        if not fleet:
            # store info for debugging
            filename = f'{base_dir}/raw/{ev_name}/{name}.json'
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                f.write(json.dumps(fleet, indent=2))
            continue
        
        faction = fleet.get('faction', '')
        commander = fleet.get('commander', '')
        
        dict_fleets['id'].append(fleet_id)
        dict_fleets['player'].append(name)
        dict_fleets['event_id'].append(ev_id)
        dict_fleets['faction_name'].append(faction)
        dict_fleets['commander'].append(commander)
        
        for ship in fleet['ships']:
            dict_ships['id'].append(ship_id)
            dict_ships['fleet_id'].append(fleet_id)
            dict_ships['ship_name'].append(ship['name'])
            for upgrade in ship['upgrades']:
                dict_upgrades['upgrade_name'].append(upgrade['name'])
                dict_upgrades['fleet_id'].append(fleet_id)
                dict_upgrades['fleet_ship_id'].append(ship_id)
            ship_id += 1
        for squad in fleet['squadrons']:
            dict_squadrons['squadron_name'].append(squad['name'])
            dict_squadrons['fleet_id'].append(fleet_id)
            dict_squadrons['count'].append(squad.get('count', 1)) 
        fleet_id += 1
    df_fleets = pd.DataFrame(dict_fleets)
    df_fleets.to_csv(f'{base_dir}/armada_fleets.csv', mode='a',
                     header=False, index=False)
    df_ships = pd.DataFrame(dict_ships)
    df_ships.to_csv(f'{base_dir}/armada_fleets_ships.csv', mode='a',
                     header=False, index=False)
    df_upgrades = pd.DataFrame(dict_upgrades)
    df_upgrades.to_csv(f'{base_dir}/armada_fleets_upgrades.csv', mode='a',
                     header=False, index=False)
    df_squadrons = pd.DataFrame(dict_squadrons)
    df_squadrons.to_csv(f'{base_dir}/armada_fleets_squadrons.csv', mode='a',
                     header=False, index=False)

def get_scores(rounds, cursor, ev_id):
    
    insert_str = 'INSERT INTO Scores VALUES\n'
    rounds = rounds.find_all('div', {'role': 'tabpanel'})
    print(f'found {len(rounds)} rounds')
    for ii, rnd in enumerate(rounds):
        rows = rnd.find_all('div', {'class': 'col-11'})
        print(f'round {ii+1}: found {len(rows)} games')
        for row in rows:
            info = row.find_all('span')
            if len(info) == 6:
                playerA = f'"{clean_name(info[0].text)}"'
                ptsA = int(info[1].text)
                playerB = f'"{clean_name(info[3].text)}"'
                ptsB = int(info[4].text)
            elif len(info) == 4:
                if info[0].text == 'Bye':
                    playerA = None
                    ptsA = None
                    playerB = f'"{clean_name(info[1].text)}"'
                    ptsB = 140
                else:
                    playerA = f'"{clean_name(info[0].text)}"'
                    ptsA = 140
                    playerB = None
                    ptsB = None
            else:
                continue
            
            insert_str += f'({playerA}, {ptsA}, {playerB}, {ptsB}),\n'
    insert_str = insert_str[:-2] + ';'
    print('INFO: Scores are:')
    print(insert_str)
    cursor.execute(insert_str)
    
def parse_site(soup, url, ev_name, no_event_info=False,
                  do_scores=True, do_fleets=True):
    sql_path = 'data/armada_events.sql'
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    
    # Check if event already in DB. If not, add to Events table
    res = cursor.execute(f'SELECT id FROM Events WHERE name = {ev_name}')
    if not res:
        select_str = 'div.pt-3.small.row div.col:has(> i.bi.bi-calendar3)'
        ev_date = soup.select_one(select_str).text
        ev_date = ev_date.replace(',','').split()[1:]
        month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        ev_mon = month.index(ev_date[1])
        ev_date = f'{ev_date[2]}-{ev_mon:02}-{ev_date[0]:02}'
        
        select_str = 'div.pt-3.small.row div.col:has(> i.bi.bi-globe)'
        ev_region = soup.select_one(select_str).text
        print(f'date: {ev_date}, region: {ev_region}')
        
        insert_str = f'''
        INSERT INTO Events (name, url, date, region)
        VALUES ("{ev_name}", "{url}", "{ev_date}", "{ev_region}");
        '''
        cursor.execute(insert_str)
        conn.commit()
    
    res = cursor.execute(f'SELECT id FROM Events WHERE name = {ev_name}')
    ev_id = res.fetchone()[0]
    
    # add results to event_results csv
    if do_scores:
        rounds = soup.find(id='uncontrolled-tab-example-tabpane-rounds')
        get_scores(rounds, cursor, ev_id)
    
    ship_id = 1
    try:
        with open(f'{base_dir}/armada_fleets_ships.csv', 'r') as f:
            ship_id = int(f.readlines()[-1].split(',')[0]) + 1
    except Exception as e:
        print(f'Failed to get ship_id: {e}')

    if do_fleets:
        fleets = soup.find(id='uncontrolled-tab-example-tabpane-lists')
        get_fleet_lists(fleets, base_dir, ev_name, ev_id, ship_id)
    
    if no_event_info:
        return
    # add event info to events csv
    select_str = 'div.pt-3.small.row div.col:has(> i.bi.bi-calendar3)'
    ev_date = soup.select_one(select_str).text
    ev_date = ev_date.replace(',','').split()[1:]
    with open(f'{base_dir}/armada_events.csv', 'a') as f:
        f.write(",".join([str(ev_id), ev_name, *ev_date]))
    
