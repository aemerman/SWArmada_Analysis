
# SWArmada_Analysis
Quick project to analyze the metagame of the miniatures wargame Star Wars: Armada. Exploratory analysis of the 2025 World Championship is included in the repository, as well as an SQL database of all fleet-building elements in the game as of Jan 2025
(Rules Errata version 5.5).

## Power BI Dashboard
The Worlds2025_Analysis.pbix file shows metagame analysis and tournament results for the 2025 World Championship tournament, held at AdeptiCon 2025. The data used to produce this dashboard is also stored as csv files in the data directory.

## SQL Database
The `data/armada_events.sql` file is an SQLite database containing dimension tables for all Star Wars: Armada fleet-building elements as well as fact tables for tournament information. The table schema is designed so that joining tables can be always done using primary key to foreign key relationships. For fleet lists, which have a natural hierarchical structure, this is done by splitting the list into ship, squadron, and upgrade components. Ships and squadrons are linked to the primary key of the fleet while upgrades are linked to the primary key of the ship to which they are attached.

Note: no in-game information (such as guns or shields of ships, or text of upgrade cards) is currently included in this database.

A full description of the SQL schema is included below:

#### Fleet Component tables
The game has four factions: Rebel Alliance, Galactic Empire, Galactic Republic, and Separatist Alliance.
```sql
CREATE TABLE Factions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    alias TEXT
)
```
Ships are the basic component of fleet-building that all lists must contain. Ships can be equipped with upgrade cards for an additional cost. All fleets must contain an admiral upgrade on one ship, which becomes the flagship.
```sql
CREATE TABLE Ships (
    id INTEGER PRIMARY KEY,
    faction_id INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    size TEXT NOT NULL,
    FOREIGN KEY (faction_id) REFERENCES Factions (id)
)
```
```sql
CREATE TABLE UpgradeSlots (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
)
```
```sql
CREATE TABLE Ships_UpgradeSlots (
    ship_id INTEGER,
    slot_id INTEGER,
    FOREIGN KEY (ship_id) REFERENCES Ships (id),
    FOREIGN KEY (slot_id) REFERENCES UpgradeSlots (id)
)
```
```sql
CREATE TABLE Upgrades (
    id INTEGER PRIMARY KEY,
    cost INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    uniq INTEGER NOT NULL,
    mod INTEGER NOT NULL,
    FOREIGN KEY (slot_id) REFERENCES UpgradeSlots (id)
)
```
```sql
CREATE TABLE Upgrades_Factions (
    upgrade_id INTEGER,
    faction_id INTEGER,
    FOREIGN KEY (upgrade_id) REFERENCES Upgrades (id),
    FOREIGN KEY (faction_id) REFERENCES Factions (id)
)
```
The squadron wing of a fleet can be up to 25% of the total cost budget.
```sql
CREATE TABLE Squadrons (
    id INTEGER PRIMARY KEY,
    faction_id INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    uniq INTEGER NOT NULL,
    FOREIGN KEY (faction_id) REFERENCES Factions (id)
)
```
Name tables include aliases used by several popular fleet-building websites.
```sql
CREATE TABLE SquadronNames (
    squadron_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (squadron_id) REFERENCES Squadrons (id)
)
```
```sql
CREATE TABLE UpgradeNames (
    upgrade_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (upgrade_id) REFERENCES Upgrades (id)
)
```
```sql
CREATE TABLE ShipNames (
    ship_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (ship_id) REFERENCES Ships (id)
)
```
#### Tournament information tables
```sql
CREATE TABLE Events (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    date TEXT,
    region TEXT
)
```
```sql
CREATE TABLE Fleets (
    id INTEGER PRIMARY KEY,
    player TEXT,
    event_id INTEGER NOT NULL,
    faction_id INTEGER,
    assault_obj TEXT,
    defense_obj TEXT,
    navigation_obj TEXT,
    FOREIGN KEY (event_id) REFERENCES Events (id)
)
```
```sql
CREATE TABLE Fleets_Ships (
    id INTEGER PRIMARY KEY,
    fleet_id INTEGER NOT NULL,
    ship_id INTEGER NOT NULL,
    FOREIGN KEY (fleet_id) REFERENCES Fleets (id),
    FOREIGN KEY (ship_id) REFERENCES Ships (id)
)
```
```sql
CREATE TABLE Fleets_Squadrons (
    fleet_id INTEGER NOT NULL,
    squadron_id INTEGER NOT NULL,
    count INTEGER DEFAULT 1,
    FOREIGN KEY (fleet_id) REFERENCES Fleets (id),
    FOREIGN KEY (squadron_id) REFERENCES Squadrons (id)
)
```
```sql
CREATE TABLE Fleets_Upgrades (
    upgrade_id INTEGER NOT NULL,
    fleet_ship_id INTEGER NOT NULL,
    FOREIGN KEY (upgrade_id) REFERENCES Upgrades (id),
    FOREIGN KEY (fleet_ship_id) REFERENCES Fleets_Ships (id)
)
```
```sql
CREATE TABLE Scores (
    event_id INTEGER NOT NULL,
    round INTEGER DEFAULT 1,
    player TEXT NOT NULL,
    points INTEGER NOT NULL,
    tournament_points INTEGER NOT NULL,
    opponent TEXT,
    FOREIGN KEY (event_id) REFERENCES Events (id)
)
```

## Web Scraper
The website [TableTop Tournament Tools](https://t4.tools/) is the standard tournament hosting tool used in the Star Wars: Armada community, and also serves as a repository of results and fleet list data on past tournaments. I've written a tool, `web_scraper.py` to scrape this information for any particular tournament from the HTML of that tournaments webpage. The data is then added to the SQLite file `data/armada_events.sql` for easy analysis.

As there is no standard formatting for fleet lists, or even standard naming convention for fleet components, I've used an LLM (Google Gemini) to help sort the information into a easy-to-process format. In order to use this functionality, you will need to set up and provide your own API key. Writing in May 2025, I've found the free tier Gemini API sufficient for this task. 

When adding fleet components to the database, the user will be prompted if no matching component can be found (for instance, if there is a typo in the component name).

`web_scraper.py` usage:
```
usage: web_scraper [-h] [-n NAME] [--no-scores] [--no-fleets] url

program to get SW Armada event data from T4.tools

positional arguments:
  url                   URL of tournament that you want to analyze

options:
  -h, --help            show this help message and exit
  -n NAME, --name NAME  Name for tournament within DB (taken from URL if not
                        specified)
  --no-scores           flag to skip storing tournament results
  --no-fleets           flag to skip storing fleet information
```
