# -*- coding: utf-8 -*-
"""
SQL Queries

List of SQL queries as strings for use in adding event info to DB.
Most of these queries are meant to get a primary key from the DB given some
information contained in the fleet list. As such, they should return at most
one row and column.

@author: alexe
"""

get_event_from_url = "SELECT id FROM Events WHERE url = ?"

get_fleet_from_event_player = """
SELECT id FROM Fleets WHERE event_id = ? AND player = ?
"""

get_faction_from_name = """
SELECT id FROM Factions
WHERE LOWER(name) = ? OR LOWER(alias) = ?
"""

get_faction_from_ship = "SELECT faction_id FROM Ships WHERE id = ?"

get_commander_from_upgrades = """
SELECT MIN(n.name) FROM UpgradeNames AS n
LEFT JOIN Upgrades AS u ON n.upgrade_id = u.id
WHERE u.slot_id = 1 AND u.id IN (SELECT value FROM json_each(?))
GROUP BY n.upgrade_id
"""

get_ship_from_name = """
SELECT ship_id FROM ShipNames
WHERE LOWER(name) = ?
"""

get_ship_from_name_faction = """
SELECT n.ship_id FROM ShipNames AS n
LEFT JOIN Ships AS s ON n.ship_id = s.id
WHERE LOWER(n.name) = ? AND s.faction_id = ?
"""

get_ship_from_name_cost = """
SELECT n.ship_id FROM ShipNames AS n
LEFT JOIN Ships AS s ON n.ship_id = s.id
WHERE LOWER(n.name) = ? AND s.cost = ?
"""

get_ship_from_name_faction_cost = """
SELECT n.ship_id FROM ShipNames AS n
LEFT JOIN Ships AS s ON n.ship_id = s.id
WHERE LOWER(n.name) = ? AND s.faction_id = ? AND s.cost = ?
"""

get_ship_from_faction_cost = """
SELECT id FROM Ships
WHERE faction_id = ? AND cost = ?
"""

get_upgrade_from_name = """
SELECT upgrade_id FROM UpgradeNames
WHERE LOWER(name) = ?
"""

get_upgrade_from_name_faction = """
SELECT n.upgrade_id FROM UpgradeNames AS n
LEFT JOIN Upgrades_Factions AS f ON f.upgrade_id = n.upgrade_id
WHERE LOWER(n.name) = ? AND f.faction_id = ?
"""

get_upgrade_from_name_cost = """
SELECT n.upgrade_id FROM UpgradeNames AS n
LEFT JOIN Upgrades AS u ON u.id = n.upgrade_id
WHERE LOWER(n.name) = ? AND u.cost = ?
"""

get_upgrade_from_name_faction_cost = """
SELECT n.upgrade_id FROM UpgradeNames AS n
LEFT JOIN Upgrades_Factions AS f ON f.upgrade_id = n.upgrade_id
LEFT JOIN Upgrades AS u ON u.id = n.upgrade_id
WHERE LOWER(n.name) = ? AND f.faction_id = ? AND u.cost = ?
"""

get_squadron_from_name = """
SELECT squadron_id FROM SquadronNames
WHERE LOWER(name) = ?
"""

get_squadron_from_name_faction = """
SELECT n.squadron_id FROM SquadronNames AS n
LEFT JOIN Squadrons AS s ON n.squadron_id = s.id
WHERE LOWER(n.name) = ? AND s.faction_id = ?
"""

get_squadron_from_name_cost = """
SELECT n.squadron_id FROM SquadronNames AS n
LEFT JOIN Squadrons AS s ON n.squadron_id = s.id
WHERE LOWER(n.name) = ? AND s.cost = ?
"""

get_squadron_from_name_faction_cost = """
SELECT n.squadron_id FROM SquadronNames AS n
LEFT JOIN Squadrons AS s ON n.squadron_id = s.id
WHERE LOWER(n.name) = ? AND s.faction_id = ? AND s.cost = ?
"""

get_squadron_from_faction_cost = """
SELECT id FROM Squadrons
WHERE faction_id = ? AND cost = ?
"""

get_fleet_list = """
SELECT fl.id AS fleet_id,
    un.name AS name
FROM Fleets_Upgrades AS fu
INNER JOIN UpgradeNames AS un
    ON fu.upgrade_id = un.upgrade_id
    AND un.name IN (SELECT MIN(name) FROM UpgradeNames GROUP BY upgrade_id)
LEFT JOIN Fleets_Ships as fs ON fs.id = fu.fleet_ship_id
LEFT JOIN Fleets as fl ON fl.id = fs.fleet_id
WHERE fl.id = ?
UNION
SELECT fs.fleet_id AS fleet_id,
    sn.name AS name
FROM Fleets_Ships AS fs
INNER JOIN ShipNames AS sn ON fs.ship_id = sn.ship_id
    AND sn.name IN (SELECT MAX(name) FROM ShipNames GROUP BY ship_id)
WHERE fs.fleet_id = ?
UNION
SELECT fq.fleet_id AS fleet_id,
    qn.name AS name
FROM Fleets_Squadrons AS fq
INNER JOIN SquadronNames AS qn ON fq.squadron_id = qn.squadron_id
    AND qn.name IN (SELECT MAX(name) FROM SquadronNames GROUP BY squadron_id)
WHERE fq.fleet_id = ?
"""