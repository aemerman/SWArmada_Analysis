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
def do_fleet_lists(fleets, base_dir, ev_name, ev_id, ship_id):
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

def do_scores(rounds, base_dir, ev_id):
    dict_scores = {"event_id": [], "round": [],
                   "playerA": [], "pointsA": [],
                   "playerB": [], "pointsB": []}
    
    rounds = rounds.find_all('div', {'role': 'tabpanel'})
    print(f'found {len(rounds)} rounds')
    for ii, rnd in enumerate(rounds):
        rows = rnd.find_all('div', {'class': 'col-11'})
        print(f'round {ii+1}: found {len(rows)} rows')
        for row in rows:
            info = row.find_all('span')
            if len(info) != 6:
                continue
            dict_scores['event_id'].append(ev_id)
            dict_scores['round'].append(ii+1)
            dict_scores['playerA'].append(clean_name(info[0].text))
            dict_scores['pointsA'].append(int(info[1].text))
            dict_scores['playerB'].append(clean_name(info[3].text))
            dict_scores['pointsB'].append(int(info[4].text))
                
    df_scores = pd.DataFrame(dict_scores)
    df_scores.to_csv(f'{base_dir}/armada_scores.csv', mode='a',
                     header=False, index=False)
    
def parse_site(soup, ev_name, no_event_info=False, parse_args=None):
    base_dir = 'data/events'
    df_events = pd.read_csv(f'{base_dir}/armada_events.csv')
    if ev_name in df_events['name'].values:
        ev_id = df_events[df_events['name'] == ev_name]['id'].values[0]
    else:
        ev_id = df_events['id'].max() + 1
    ship_id = 1
    try:
        with open(f'{base_dir}/armada_fleets_ships.csv', 'r') as f:
            ship_id = int(f.readlines()[-1].split(',')[0]) + 1
    except Exception as e:
        print(f'Failed to get ship_id: {e}')

    fleets = soup.find(id='uncontrolled-tab-example-tabpane-lists')
    do_fleet_lists(fleets, base_dir, ev_name, ev_id, ship_id)
    
    if no_event_info:
        return
    # add event info to events csv
    select_str = 'div.pt-3.small.row div.col:has(> i.bi.bi-calendar3)'
    ev_date = soup.select_one(select_str).text
    ev_date = ev_date.replace(',','').split()[1:]
    with open(f'{base_dir}/armada_events.csv', 'a') as f:
        f.write(",".join([str(ev_id), ev_name, *ev_date]))
    
    # add results to event_results csv
    rounds = soup.find(id='uncontrolled-tab-example-tabpane-rounds')
    do_scores(rounds, base_dir, ev_id)
