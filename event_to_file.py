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
import sql_queries

# Replace tabs, commas etc in player names with spaces
def clean_name(name):
    name = name.replace(',',' ')
    return ' '.join(name.strip().split())

def get_last_primary_key(cursor):
    res = cursor.execute('SELECT last_insert_rowid()')
    try:
        rowid = res.fetchone()[0]
    except TypeError:
        print('ERROR: failed to get last primary key!')
        rowid = None
    return rowid

def get_from_sql(cursor, query, params=()):
    try:
        res = cursor.execute(query, params).fetchall()
    except sqlite3.ProgrammingError as e:
        print(f'ERROR: Faulty query: {e}')
        print(query)
        print(params)
        return None
    except sqlite3.OperationalError as e:
        print(f'ERROR: Failed to run query: {e}')
        print(query)
        print(params)
        return None
    if not res or len(res) < 1:
        return None
    else:
        return res

def get_one_from_sql(cursor, query, params):
    res = get_from_sql(cursor, query, params)
    if res and len(res) == 1:
        return res[0][0]
    else:
        return None

# Try several methods to get ID. Name is enough to ID most things, and
# name + faction or name + cost is enough for all. Cost and/or faction can
# be used to ID things with typos in the name, but cost is the most likely
# field to be missing or wrong. Faction may also be missing.
# Strategy: Start with most precise and work down. Try faction + cost if all
# others fail to maybe catch misspelled names. As a last resort, query the
# user for the correct name and then rerun the function with new input
def get_obj_id(cursor, obj, name, faction_id=None, cost=None):
    # name must be lower case
    name = name.lower()

    def get_id_from_name_faction_cost(name, faction_id, cost):
        if not faction_id or not cost:
            return None
        try:
            query_str = getattr(sql_queries,
                                f'get_{obj}_from_name_faction_cost')
        except AttributeError:
            return None
        return get_from_sql(cursor, query_str, (name, faction_id, cost))
    
    def get_id_from_name_faction(name, faction_id):
        if not faction_id:
            return None
        try:
            query_str = getattr(sql_queries,
                                f'get_{obj}_from_name_faction')
        except AttributeError:
            return None
        return get_from_sql(cursor, query_str, (name, faction_id))

    def get_id_from_name_cost(name, cost):
        if not cost:
            return None
        try:
            query_str = getattr(sql_queries,
                                f'get_{obj}_from_name_cost')
        except AttributeError:
            return None
        return get_from_sql(cursor, query_str, (name, cost))

    def get_id_from_name(name):
        try:
            query_str = getattr(sql_queries,
                                f'get_{obj}_from_name')
        except AttributeError:
            return None
        return get_from_sql(cursor, query_str, (name,))
    
    def get_id_from_faction_cost(faction_id, cost):
        if not faction_id or not cost:
            return None
        try:
            query_str = getattr(sql_queries,
                                f'get_{obj}_from_faction_cost')
        except AttributeError:
            return None
        return get_from_sql(cursor, query_str, (faction_id, cost))
    
    # Start from most precise and work down
    obj_id = get_id_from_name_faction_cost(name, faction_id, cost)
    if not obj_id:
        obj_id = get_id_from_name_faction(name, faction_id)
    if not obj_id:
        obj_id = get_id_from_name_cost(name, cost)
    if not obj_id:
        obj_id = get_id_from_name(name)
    if not obj_id: # In case of misspelled name
        obj_id = get_id_from_faction_cost(faction_id, cost)

    if not obj_id or len(obj_id) == 0: # No matches found, check with user
        print(f'''Failed to find ID for {obj} with name: "{name}",
              faction_id: {faction_id}, cost: {cost}''')
        new_name = input('Please provide correct name:\n')
        return get_obj_id(cursor, obj, new_name, faction_id, cost)

    elif len(obj_id) == 1: # Positive ID, exactly one found
        return obj_id[0][0]

    else: # Multiple matches found, need disambiguation
        print(f'''Found multiple IDs for {obj} with name: "{name}",
              faction_id: {faction_id}, cost: {cost}''')
        print(obj_id)
        new_name = input('Please provide disambiguated name:\n')
        return get_obj_id(cursor, obj, new_name, faction_id, cost)

# Take a fleet list in dictionary form, and make sure that all ships,
# squadrons, and upgrades are listed in the database. Get ids for each so
# that the fleet list can be properly added to the database.
def apply_fleet_cleaning(cursor, fleet):
    faction = fleet.get('faction', None)
    # Try to get faction ID from name or alias. If that doesn't work,
    # then try using ship names
    faction_id = None
    if faction:
        # Stored faction names are one word, so split faction into
        # tokens and check separately.
        # Gets e.g. Rebel from 'Rebel Alliance'
        tkns = faction.split()
        for tkn in tkns:
            tkn = tkn.strip(' ()').lower()
            faction_id = get_one_from_sql(cursor, 
                                          sql_queries.get_faction_from_name,
                                          (tkn, tkn,))
            if faction_id:
                fleet['faction_id'] = faction_id
                break
    
    for iis, ship in enumerate(fleet['ships']):
        # Name is a required field and can be assumed to exist. Cost is not
        name = ship.get('name', None)
        cost = ship.get('base_cost', None)
        
        ship_id = get_obj_id(cursor, 'ship', name, faction_id, cost)
        fleet['ships'][iis]['id'] = ship_id
        
        # Once the ship has been IDed, get faction ID if not yet available
        if not faction_id:
            faction_id = get_one_from_sql(cursor,
                              sql_queries.get_faction_from_ship, (ship_id,))
            fleet['faction_id'] = faction_id
        
        for iiu, upgrade in enumerate(ship['upgrades']):
            name = upgrade.get('name', None)
            cost = upgrade.get('cost', None)
            
            upgrade_id = get_obj_id(cursor, 'upgrade', name, faction_id, cost)
            fleet['ships'][iis]['upgrades'][iiu]['id'] = upgrade_id

    for iiq, squad in enumerate(fleet['squadrons']):
        name = squad.get('name', None)
        cost = squad.get('cost', None)
        
        squad_id = get_obj_id(cursor, 'squadron', name, faction_id, cost)
        fleet['squadrons'][iiq]['id'] = squad_id
    
    # Get fleet admiral from upgrades list if not provided in json
    commander = fleet.get('commander', None)
    if not commander:
        upgrades = {}
        for ship in fleet['ships']:
            for upgrade in ship['upgrades']:
                upgrades[upgrade['name']] = upgrade['id']
        commander = get_one_from_sql(cursor,
                         sql_queries.get_commander_from_upgrades,
                         (json.dumps(upgrades),))
        fleet['commander'] = commander
    return fleet

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
def get_fleet_lists(fleets, conn, ev_id):
    
    cursor = conn.cursor()

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
            filename = f'logs/{ev_id}_{"_".join(name.split())}.json'
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                f.write(json.dumps(fleet, indent=2))

            continue

        # Fleet list has been converted into a dictionary, but values may
        # not be suitable for adding to database. Some data cleaning needs
        # to be done first.
        # Do not add fleet to database until cleaning steps are done.
        fleet = apply_fleet_cleaning(cursor, fleet)

        # Now check that all values have been properly validated and, if so,
        # add the fleet list to the database
        insert_fleet_str = """
        INSERT INTO Fleets (player, event_id, faction_id, commander)
        VALUES (?, ?, ?, ?)
        """
        insert_ship_str = """
        INSERT INTO Fleets_Ships (fleet_id, ship_id) VALUES (?, ?)
        """
        insert_upgrades_str = """
        INSERT INTO Fleets_Upgrades (fleet_id, upgrade_id, ship_id)
        VALUES (?, ?, ?)
        """
        insert_squadrons_str = """
        INSERT INTO Fleets_Squadrons (fleet_id, squadron_id, count)
        VALUES (?, ?, ?)
        """

        faction_id = fleet.get('faction_id', None)
        commander = fleet.get('commander', None)
        fleet_values = (name, ev_id, faction_id, commander,)
        cursor.execute(insert_fleet_str, fleet_values)
        conn.commit()

        #Get the newly generated id from Fleets
        fleet_id = get_last_primary_key(cursor)
        if not fleet_id:
            break

        for ship in fleet['ships']:
            ship_values = (fleet_id, ship['id'],)
            cursor.execute(insert_ship_str, ship_values)
            conn.commit()

            fleet_ship_id = get_last_primary_key(cursor)
            if not fleet_ship_id:
                continue

            for upgrade in ship['upgrades']:
                upgrade_values = (upgrade['id'], fleet_id, fleet_ship_id,)
                cursor.execute(insert_upgrades_str, upgrade_values)

        for squad in fleet['squadrons']:
            count = squad.get('count', 1)
            squad_values = (squad['id'], fleet_id, count,)
            cursor.execute(insert_squadrons_str, squad_values)
        conn.commit()

def get_scores(rounds, conn, ev_id):
    
    cursor = conn.cursor()
    insert_str = 'INSERT INTO Scores VALUES (?, ?, ?, ?, ?, ?)'
    insert_values = []
    rounds = rounds.find_all('div', {'role': 'tabpanel'})
    print(f'found {len(rounds)} rounds')
    for ii, rnd in enumerate(rounds):
        rows = rnd.find_all('div', {'class': 'col-11'})
        print(f'round {ii+1}: found {len(rows)} rows')
        for row in rows:
            info = row.find_all('span')
            if len(info) == 6:
                playerA = clean_name(info[0].text)
                ptsA = int(info[1].text)
                playerB = clean_name(info[3].text)
                ptsB = int(info[4].text)
            elif len(info) == 4:
                if info[0].text == 'Bye':
                    playerA = None
                    ptsA = None
                    playerB = clean_name(info[1].text)
                    ptsB = 140
                elif info[3].text == 'Bye':
                    playerA = clean_name(info[0].text)
                    ptsA = 140
                    playerB = None
                    ptsB = None
                else:
                    continue
            else:
                continue
            
            insert_values += [(ev_id, ii+1, playerA, ptsA, playerB, ptsB)]

    cursor.executemany(insert_str, insert_values)
    conn.commit()
    
def parse_site(soup, url, name, no_event_info=False,
                  do_scores=True, do_fleets=True):
    sql_path = 'data/armada_events.sql'
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    
    # Check if event already in DB. If not, add to Events table
    res = cursor.execute(sql_queries.get_event_by_url, (url,))
    try:
        ev_id = res.fetchone()[0]
    except TypeError:
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
        
        insert_str = 'INSERT INTO Events (name, url, date, region) ' \
            + 'VALUES (?, ?, ?, ?)'
        insert_values = (name, url, ev_date, ev_region,)
        
        cursor.execute(insert_str, insert_values)
        conn.commit()
        
        ev_id = get_last_primary_key(cursor)
    
    # add results to event_results csv
    if do_scores:
        rounds = soup.find(id='uncontrolled-tab-example-tabpane-rounds')
        get_scores(rounds, conn, ev_id)
        conn.commit()

    if do_fleets:
        fleets = soup.find(id='uncontrolled-tab-example-tabpane-lists')
        get_fleet_lists(fleets, conn, ev_id)
    
