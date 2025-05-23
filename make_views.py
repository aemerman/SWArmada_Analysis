# -*- coding: utf-8 -*-
"""
Make Views

This file contains a set of SQL commands to add summary statistics to the DB.
The views are:
    Fleet_Summary - fleet_id, event_id, player name, faction, commander,
        flagship, points spent on ships, points spent on ships + upgrades,
        number of ships (split by size category), points spent on squadrons,
        number of squadrons, number of unique squadrons, point bid,
        event results: tournament points, margin of victory, strength of
            schedule, average tournament points per game, variance of
            tournament points per game

    Ship_Summary - ship_id, event_id, ship name, faction, number of fleets
        running this ship, average cost and number of upgrades, average cost of
        squadrons and average bid among fleets running this ship

    Squadron_Summary - squadron_id, event_id, squadron name, faction, number
        of fleets running this squadron, average cost and number of squadrons
        among fleets running this squadron, average bid among fleets running
        this squadron


@author: alexe
"""
import sqlite3
import pandas as pd
import argparse
import os

# Used as CTE to add number of ships to fleet summary
get_ships_summary = """
SELECT f.id AS fleet_id,
    COUNT(fs.id) AS num_ships,
    SUM(CASE WHEN s.size = "Huge" THEN 1 ELSE 0 END) AS num_huge,
    SUM(CASE WHEN s.size = "Large" THEN 1 ELSE 0 END) AS num_large,
    SUM(CASE WHEN s.size = "Medium" THEN 1 ELSE 0 END) AS num_medium,
    SUM(CASE WHEN s.size = "Small" THEN 1 ELSE 0 END) AS num_small,
    SUM(s.cost) AS ships_cost
FROM Fleets_Ships AS fs
INNER JOIN Fleets AS f ON f.id = fs.fleet_id
INNER JOIN Ships AS s ON s.id = fs.ship_id
GROUP BY f.id
"""

# Used as CTE to add number of squadrons to fleet summary
get_squadrons_summary = """
SELECT f.id AS fleet_id,
    SUM(fq.count) AS num_squadrons,
    SUM(s.uniq) AS num_uniques,
    SUM(s.cost * fq.count) AS squadrons_cost
FROM Fleets_Squadrons AS fq
INNER JOIN Fleets AS f ON f.id = fq.fleet_id
INNER JOIN Squadrons AS s ON s.id = fq.squadron_id
GROUP BY f.id
"""

# Used as CTE to add upgrade info to fleet summary
get_upgrades_summary = """
SELECT f.id AS fleet_id,
    SUM(u.cost) AS upgrades_cost
FROM Fleets_Upgrades AS fu
INNER JOIN Fleets_Ships AS fs ON fu.fleet_ship_id = fs.id
INNER JOIN Fleets AS f ON f.id = fs.fleet_id
INNER JOIN Upgrades AS u ON u.id = fu.upgrade_id
GROUP BY f.id
"""

# Used as CTE to add commander and flagship to fleet summary
get_commander = """
SELECT f.id AS fleet_id,
    un.name AS commander,
    sn.name AS flagship
from Fleets_Upgrades AS fu
INNER JOIN Upgrades AS u ON fu.upgrade_id = u.id
INNER JOIN UpgradeNames AS un
    ON fu.upgrade_id = un.upgrade_id
    AND un.name IN (SELECT MIN(name) FROM UpgradeNames GROUP BY upgrade_id)
INNER JOIN Fleets_Ships AS fs ON fu.fleet_ship_id = fs.id
INNER JOIN ShipNames AS sn
    ON fs.ship_id = sn.ship_id
    AND sn.name IN (SELECT MAX(name) FROM ShipNames GROUP BY ship_id)
INNER JOIN Fleets AS f ON f.id = fs.fleet_id
WHERE u.slot_id = 1
"""

# Getting player stats is a multi-step process. First, use a CTE to calculate
# margin of victory (MoV) and aggregate tournament points (TP) across the
# event. Then calculate variance and strength of schedule (SoS) for the event.
# Used as CTEs to add results info to fleet summary
get_player_event = """
player_agg AS (
    SELECT sc1.player AS player,
        sc1.event_id AS event_id,
        SUM(CASE
                WHEN sc2.player IS NULL THEN 140
                WHEN sc1.points > sc2.points THEN sc1.points - sc2.points
                ELSE 0
            END) AS mov,
        SUM(sc1.tournament_points) AS tp,
        AVG(sc1.tournament_points) AS avg_tp
    FROM Scores AS sc1
    LEFT JOIN Scores AS sc2 ON sc1.opponent = sc2.player
    GROUP BY sc1.player, sc1.event_id
    ),
pe AS (
   SELECT pl.player AS player,
        pl.event_id AS event_id,
        pl.mov AS mov,
        pl.tp AS tp,
        pl.avg_tp AS avg_tp,
        SUM((sc.tournament_points - pl.avg_tp)
            *(sc.tournament_points - pl.avg_tp))
            / (COUNT(sc.tournament_points)-1) AS var_tp,
        AVG(opp.avg_tp) AS sos
    FROM player_agg AS pl
    INNER JOIN Scores AS sc ON pl.player = sc.player
        AND pl.event_id = sc.event_id
    INNER JOIN player_agg AS opp ON sc.opponent = opp.player
        AND sc.event_id = opp.event_id
    GROUP BY pl.player, pl.event_id
    )
"""

# Add fleet-level summary to DB for fleet-level analysis. Popularity of
# factions and commanders, size of bids and squad-balls, etc.
view_fleet_summary = f"""
CREATE VIEW IF NOT EXISTS Fleet_Summary AS
WITH co AS ({get_commander}),
fs AS ({get_ships_summary}),
fq AS ({get_squadrons_summary}),
fu AS ({get_upgrades_summary}),
{get_player_event}

SELECT
    fl.id AS id,
    fl.event_id AS event_id,
    fl.player AS player,
    fn.name AS faction,
    co.commander AS commander,
    co.flagship AS flagship,
    fs.ships_cost AS ships_base_cost,
    fs.ships_cost + fu.upgrades_cost AS ships_total_cost,
    fs.num_ships AS num_ships,
    fs.num_huge AS num_huge,
    fs.num_large AS num_large,
    fs.num_medium AS num_medium,
    fs.num_small AS num_small,
    COALESCE(fq.squadrons_cost, 0) AS squadrons_cost,
    COALESCE(fq.num_squadrons, 0) AS num_squadrons,
    COALESCE(fq.num_uniques, 0) AS num_uniq_squadrons,
    fs.ships_cost + COALESCE(fq.squadrons_cost, 0)
        + COALESCE(fu.upgrades_cost, 0) AS total_cost,
    400 - (fs.ships_cost + COALESCE(fq.squadrons_cost, 0)
           + COALESCE(fu.upgrades_cost, 0)) AS bid,
    pe.mov AS mov,
    pe.tp AS tp,
    ROUND(pe.sos, 2) AS sos,
    ROUND(pe.avg_tp, 2) AS avg_tp,
    ROUND(pe.var_tp, 3) AS var_tp
FROM Fleets AS fl
INNER JOIN Factions AS fn ON fl.faction_id = fn.id
LEFT JOIN co ON co.fleet_id = fl.id
LEFT JOIN fs ON fs.fleet_id = fl.id
LEFT JOIN fq ON fq.fleet_id = fl.id
LEFT JOIN fu ON fu.fleet_id = fl.id
LEFT JOIN pe ON pe.player = fl.player AND pe.event_id = fl.event_id
"""

# Add ship-level summary to DB for ship-to-ship comparisons. Popularity of
# ships, average number and cost of upgrades, etc.
view_ship_summary = """
CREATE VIEW IF NOT EXISTS Ship_Summary AS
WITH up AS (
    SELECT fs.id AS id,
        fs.ship_id AS ship_id,
        SUM(CASE WHEN u.id IS NULL THEN 0 ELSE 1 END) AS num_upgrades,
        COALESCE(SUM(u.cost), 0) AS cost_upgrades
    FROM Fleets_Ships AS fs
    LEFT JOIN Fleets_Upgrades AS fu ON fs.id = fu.fleet_ship_id
    LEFT JOIN Upgrades AS u ON u.id = fu.upgrade_id
    WHERE u.slot_id <> 1
    GROUP BY fs.id
    )

SELECT
    s.id AS id,
    fl.event_id AS event_id,
    sn.name AS name,
    fn.name AS faction,
    COUNT(DISTINCT fs.fleet_id) AS num_fleets_containing,
    AVG(up.num_upgrades) AS avg_num_upgrades,
    AVG(up.cost_upgrades) AS avg_cost_upgrades,
    AVG(fl.squadrons_cost) AS avg_squadrons_cost,
    AVG(fl.bid) AS avg_bid
FROM Ships AS s
INNER JOIN Factions AS fn ON fn.id = s.faction_id
INNER JOIN ShipNames AS sn ON s.id = sn.ship_id
    AND sn.name IN (SELECT MAX(name) FROM ShipNames GROUP BY ship_id)
LEFT JOIN Fleets_Ships AS fs ON s.id = fs.ship_id
LEFT JOIN Fleet_Summary AS fl ON fl.id = fs.fleet_id
LEFT JOIN up ON s.id = up.ship_id
GROUP BY s.id, fl.event_id
"""

# Add squadron-level summary to DB for squad-to-squad comparisons.
view_squadron_summary = """
CREATE VIEW IF NOT EXISTS Squadron_Summary AS
SELECT
    q.id AS id,
    fl.event_id AS event_id,
    qn.name AS name,
    fn.name AS faction,
    COUNT(DISTINCT fq.fleet_id) AS num_fleets_containing,
    AVG(fl.squadrons_cost) AS avg_squadrons_cost,
    AVG(fl.num_squadrons) AS avg_num_squadrons,
    AVG(bid) AS avg_bid
FROM Squadrons AS q
INNER JOIN Factions AS fn ON fn.id = q.faction_id
INNER JOIN SquadronNames AS qn ON q.id = qn.squadron_id
    AND qn.name IN (SELECT MAX(name) FROM SquadronNames GROUP BY squadron_id)
LEFT JOIN Fleets_Squadrons AS fq ON q.id = fq.squadron_id
LEFT JOIN Fleet_Summary AS fl ON fl.id = fq.fleet_id
GROUP BY q.id, fl.event_id
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="make_views",
        description="program to add summary statistics to Armada SQL DB")
    parser.add_argument("db_path", type=str, default='data/armada_events.sql')
    parser.add_argument("-f", "--force", action='store_true',
                        description="Overwrite views in DB if they exist")
    parser.add_argument("--no-fleets", action='store_true')
    parser.add_argument("--no-ships", action='store_true')
    parser.add_argument("--no-squadrons", action='store_true')
    args = parser.parse_args()

    sql_path = args.db_path
    if not os.path.isfile(sql_path):
        print('DB path must be a file.')
        parser.print_usage()
        exit()

    do_fleets = not args.no_fleets
    do_ships = not args.no_ships
    do_squadrons = not args.no_squadrons

    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()

    if do_fleets:
        if args.force:
            cursor.execute('DROP VIEW Fleet_Summary')
        res = cursor.execute(view_fleet_summary)
        conn.commit()

        df_fleet = pd.read_sql_query('SELECT * FROM Fleet_Summary', conn)
        df_fleet.to_csv('data/fleet_summary.csv', index=False)

    if do_ships:
        if args.force:
            cursor.execute('DROP VIEW Ship_Summary')
        res = cursor.execute(view_ship_summary)
        conn.commit()

        df_ship = pd.read_sql_query('SELECT * FROM Ship_Summary', conn)
        df_ship.to_csv('data/ship_summary.csv', index=False)

    if do_squadrons:
        if args.force:
            cursor.execute('DROP VIEW Squadron_Summary')
        res = cursor.execute(view_squadron_summary)
        conn.commit()

        df_squad = pd.read_sql_query('SELECT * FROM Squadron_Summary', conn)
        df_squad.to_csv('data/squadron_summary.csv', index=False)

    conn.close()