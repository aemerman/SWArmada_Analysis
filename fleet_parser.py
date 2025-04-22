# -*- coding: utf-8 -*-
"""
Fleet Parser

Use an LLM to convert Armada fleet lists from raw text into a dictionary.
The dictionary is validated to make sure all required fields are present before
being passed back. The values of the fields are not validated though.

I am using the free tier of Google's Gemini AI for parsing. As of writing,
Gemini allows 15 requests/minute for free which is enough for most Armada
tournaments without hitting the limit, and means the largest tournaments take
around 10 minutes to parse. I put my API key in a config file not included in
the github repo, you will need to replace this with your own API key.

@author: alexe
"""
import logging
logging.basicConfig(
    format = "{levelname}:{message}",
    style = "{",
    filename = "logs/parser.log",
    filemode = "a",
    level = logging.WARNING)
import json
import time
from huggingface_hub import InferenceClient
from google import genai
from config import GEMINI_API_KEY, HUGGINGFACE_API_KEY


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

# Make sure that all required fields are present in the JSON string
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
        parse_fleet_llm.client = genai.Client(api_key=GEMINI_API_KEY)
        # parse_fleet_llm.client = InferenceClient(
        #     provider="novita",
        #     api_key=HUGGINGFACE_API_KEY,
        # )

    prompt = f"""
    # CONTEXT #
    I want to convert a Star Wars Armada fleet list into a standardized format
    for analysis. The fleet list will contain a paragraphs listing the upgrades
    for each ship in the fleet, and potentially a paragraph listing the
    squadrons in the fleet. Each line will only contain one ship, upgrade or
    squadron. The fleet list may include the costs of each ship, squadron and
    upgrade, as well as metadata such as the name, faction and commander of
    the fleet.

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

def parse_fleet(fleet, **kwargs):
    # TODO: switch between parsers depending on kwargs
    return parse_fleet_llm(fleet)