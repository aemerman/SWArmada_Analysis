# -*- coding: utf-8 -*-
"""
Created on Wed Apr  9 10:23:27 2025

@author: alexe
"""

get_event_by_url = """
SELECT id FROM Events WHERE url = ?
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