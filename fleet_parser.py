# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 09:24:49 2025

@author: alexe
"""
import logging
logging.basicConfig(
    format = "{levelname}:{message}",
    style = "{",
    filename = "logs/parser.log",
    filemode = "a",
    level = logging.WARNING)
import pandas as pd
import json
import re
import time
from huggingface_hub import InferenceClient
from google import genai
import config


# Fleet parsers provide methods to convert text string into dictionary with
# the following format (note: brackets doubled for f-string escape):
json_format = """
  {{
  "faction": str (optional),
  "commander": str (optional),
  "ships": [{{
          "name": str,
          "base_cost": int (optional)
          "total_cost": int (optional)
          "upgrades": [{{
              "name": str,
              "cost": int (optional)
          }}]
      }}],
  "squadrons": [{{
          "name: str,
          "cost": int (optional),
          "count": int (optional)
      }}]
  }}
"""

def validate_json(llm_response):
    lines = llm_response.splitlines()
    res_json = None
    # The expected format looks like:
    #   ```json
    #   {
    #       ...
    #   }
    #   ```
    ii = 0
    while ii < len(lines) and len(lines[ii]) > 0 \
                               and "```" in lines[ii]:
        ii += 1
    jj = ii+1
    while jj < len(lines) and not "```" in lines[jj]:
        jj += 1
    if ii < len(lines) and jj > ii:
        try:
            res_json = json.loads('\n'.join(lines[ii:jj]))
        except json.decoder.JSONDecodeError as e:
            logging.warning(f"JSONDecodeError on first pass:\n{e}")

    # If first attempt fails, then try just looking for brackets
    if not res_json:
        ii = llm_response.index('{')
        jj = llm_response.rindex('}')
        if ii > 0 and jj > 0:
            try:
                res_json = json.loads(llm_response[ii:jj+1])
            except json.decoder.JSONDecodeError as e:
                logging.warning(f"JSONDecodeError on second pass:\n{e}")

    # Give up after second attempt
    if not res_json:
        return None
    
    # JSON string has been successfully converted to dictionary.
    # Now check that all required fields are present.
    if not 'ships' in res_json or len(res_json['ships']) < 1:
        logging.warning("No ships in fleet.")
        return None
    if not 'squadrons' in res_json:
        logging.warning("No squadrons in fleet.")
        return None
    for ship in res_json['ships']:
        if not 'name' in ship or not 'upgrades' in ship:
            logging.warning("Ship in fleet missing required properties.")
            return None
        for upgrade in ship['upgrades']:
            if not 'name' in upgrade:
                logging.warning("Upgrade on ship missing required properties.")
                return None
    for squad in res_json['squadrons']:
        if not 'name' in squad:
            logging.warning("Squadron in fleet missing required properties.")
            return None
    return res_json

def parse_fleet_llm(fleet):
    if not hasattr(parse_fleet_llm, 'client'):
        parse_fleet_llm.client = genai.Client(api_key=config.GEMINI_API_KEY)
        # parse_fleet_llm.client = InferenceClient(
        #     provider="novita",
        #     api_key=config.HUGGINGFACE_API_KEY,
        # )
        
    prompt = f"""
    # CONTEXT #
    I want to convert a Star Wars Armada fleet list into a standardized format
    for analysis. The fleet list will contain a paragraphs listing the upgrades
    for each ship in the fleet, and potentially a paragraph listing the
    squadrons in the fleet. The fleet list may include the costs of each ship,
    squadron and upgrade, as well as metadata such as the name, faction and
    commander of the fleet.

    # RESPONSE #
    Return the fleet list in the following JSON format:
    {json_format}
    
    # INPUT DATA #
    {fleet}
    """
    # prompt = f"""The following text is a star wars armada fleet list. Convert
    # the text to json in the format {{name: str, faction: str, commander: 
    # str, ships: [{{name: str, upgrades: [{{name: str, cost: int}}],
    # total_cost: int}}], squadrons: [{{name: str, count: int, cost: 
    # int}}], squadrons_cost: int, total_cost: int}}. Ships are listed with
    # their upgrades in the same paragraph and costs in parenthesis. Squadrons 
    # are listed in paragraph at the end.
    
    # {fleet}
    # """
    def get_google_response(prompt):
        try:
            response = parse_fleet_llm.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
                )
        # if requests per minute quota is exceeded, then wait 60s and try again
        except genai.errors.ClientError:
            time.sleep(60)
            response = parse_fleet_llm.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
                )
        return response.text
        
        
    def get_huggingface_response(prompt):
        completion = parse_fleet_llm.client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3-0324",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )
        return completion.choices[0].message.content

    # Query LLM, then validate that output is valid JSON with required fields.
    response = get_google_response(prompt)
    logging.info(response)
    res_json = validate_json(response)
    if not res_json:
        logging.error(f'Failed to parse LLM response:\n{response}')
        # TODO: try again?
    
    return res_json

def make_fleet_info():
    info = {"name": "", "faction": "", "commander": "", 
            "points": "", "squad_points": "",
            "ships": [], "squads": []}
    return info

def clean_line(line):
    line.strip(' \t\n-•·>=:')
    ridx = line.find(' (')
    if ridx < 0:
        ridx = line.find('(')
    if ridx > 0:
        line = line[:ridx]
    return line

def split_paragraphs(fleet):
    lines = fleet.splitlines()
    pps = []
    ii = 0
    while ii < len(lines) and len(lines[ii].strip()) < 1:
        ii += 1
    while ii < len(lines):
        jj = ii+1
        while jj < len(lines) and len(lines[jj].strip()) > 1:
            jj += 1
        if jj == len(lines):
            pps.append('\n'.join(lines[ii:]))
        else:
            pps.append('\n'.join(lines[ii:jj]))
        ii = jj+1
    return pps

def get_ship_info(name, lines):
    ship_info = {'name': name, 'upgrades': [], 'points': -1}
    # sometimes points cost is in the same line as the ship name
    if re.search('([0-9+ ]+: [0-9]+)^', lines[0]):
        ship_info['points'] = int(lines[0].split()[-1][:-1])
    
    for line in lines[1:]:
        line = clean_line(line)
        # check if line is the points cost of the ship
        if any(x in line.lower() for x in ['points', 'total', 'cost']):
            tkns = line.split()
            for tkn in tkns:
                try:
                    ship_info['points'] = int(tkn)
                    break
                except (ValueError, TypeError):
                    continue
        else:
            ship_info['upgrades'].append(line)
    return ship_info
            
def parse_paragraphs(pps):
    df_ships = pd.read_csv('db/armada_ships.csv')
    df_squads = pd.read_csv('db/armada_squadrons.csv')
    info = {'name': '', 'faction': '', 'commander': '',
            'points': 0, 'squad_points': 0,
            'ships': [], 'squadrons': []}
    
    for pp in pps:
        lines = pp.splitlines()
        # try to isolate ship name from first line
        header = clean_line(lines[0])
        if header.startswith('Name: '):
            info['name'] = header[6:]
        elif header.startswith("Faction:"):
            info["faction"] = header[9:]
        elif header.startswith("Commander:"):
            info["commander"] = header[11:]
        elif header.startswith("Total Points:"):
            info["points"] = int(header[14:])
        df_test = df_ships[df_ships['name'].str.contains(header)]
        if len(df_test) > 0:
            name = df_test['name'][0]
            info['ships'] += get_ship_info(name, lines)
    return info
          
      
    
def parse_fleet_ryankingston(fleet):
    info = make_fleet_info()
    curr = None
    for line in fleet.splitlines():
        if len(line) < 1:
            continue

        if line.startswith("Name:"):
            info["name"] = line[6:]
        elif line.startswith("Faction:"):
            info["faction"] = line[9:]
        elif line.startswith("Commander:"):
                info["commander"] = line[11:]
        elif line.startswith("Total Points:"):
            info["points"] = int(line[14:])
        elif line.startswith("="):
            pts = int(line.split(" ")[1])
            if type(curr) is list:
                info["squads"] = curr
                info["squad_points"] = pts
            elif type(curr) is dict:
                curr["points"] = pts
                info["ships"] += [curr]
            curr = None
        elif line.startswith("Squadrons:"):
            curr = []
        elif line.startswith("•"):
            ridx = line.find("(")
            line = line[2:ridx-1]
            if type(curr) is list:
                if " x " in line:
                    num = int(line[:line.find(" x ")])
                    for _ in range(num):
                        curr += [line[line.find(" x ")+3:]]
                else:
                    curr += [line]
            elif type(curr) is dict:
                curr["upgrades"] += [line]
        else:
            ridx = line.find("(")
            curr = {"name": line[:ridx-1], "upgrades": []}
    return info

# def parse_fleet_warlords(fleet):
#     info = make_fleet_info()

def parse_fleet(fleet, **kwargs):
    # TODO: switch between parsers depending on kwargs
    return parse_fleet_llm(fleet)