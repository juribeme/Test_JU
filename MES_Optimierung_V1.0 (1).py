"""
Version 1.0.
15.5.2023, Erstellt von Nicolas
PyPSA optimiert die Größe der Erzeugungsanlagen und der Speicher für die kostengünstigste Stromversorgung
der Verrbaucher. Dabei wird die Autarkie von 70 % mit einer Schleife berücksichtigt.
"""


import pandas as pd
import pypsa

# Daten von CSV-Datei einlesen
solar_power = pd.read_csv('solar_power.csv', index_col=0, parse_dates=True)  # als PU (zwischen 0 und 1)
wind_power = pd.read_csv('wind_power.csv', index_col=0, parse_dates=True)  # als PU (zwischen 0 und 1)
load_profiles = pd.read_csv('load_profiles.csv', index_col=0, parse_dates=True)  # in MW

# Kosten einstellen
pv_capital_cost = 1000  # €/kW
wind_capital_cost = 1000  # €/kW
cost_per_mwh_pv = 50  # Kosten für PV-Anlage in €/MWh
cost_per_mwh_wind = 40  # Kosten für Windenergieanlage in €/MWh
cost_per_mwh_grid = 300  # €/MWh


# Netzwerk erstellen
network = pypsa.Network()

# Zeitintervall setzen
network.set_snapshots(solar_power.index)

# Knoten für alle Erzeugungsanlagen, Speicher und Verbraucher einfügen
network.add("Bus", "main_bus")

# Hinzufügen der Generatoren
network.add("Generator", "grid", bus="main_bus",
            p_nom=1e6,  # Sehr hohe Nennleistung
            marginal_cost=cost_per_mwh_grid)  # Kosten pro MWh

network.add("Generator", "pv",
            bus="main_bus",
            p_nom=None,  # keine feste Nennleistung
            p_nom_extendable=True,  # Nennleistung ist optimierbar
            capital_cost=pv_capital_cost,
            marginal_cost=cost_per_mwh_pv,
            p_max_pu=solar_power)

network.add("Generator", "wind",
            bus="main_bus",
            p_nom=None,  # keine feste Nennleistung
            p_nom_extendable=True,  # Nennleistung ist optimierbar
            capital_cost=wind_capital_cost,
            marginal_cost=cost_per_mwh_wind,
            p_max_pu=wind_power)

# Speicher hinzufügen
storage_efficiency = 0.9
storage_lifetime = 15
storage_capital_cost = 1000  # Kosten pro kWh Speicherkapazität
storage_max_capacity = 500  # Setzen Sie dies auf den maximal zulässigen Wert

network.add("StorageUnit",
            "storage",
            bus="main_bus",
            p_nom_extendable=True,
            p_nom_max=storage_max_capacity,
            capital_cost=storage_capital_cost,
            efficiency_dispatch=storage_efficiency,
            efficiency_store=storage_efficiency,
            cyclic_state_of_charge=True)

# Hinzufügen der Lasten (wobei 30 Haushalte das gleiche Lastprofil enthalten)
load_profiles *= 30  # Jedes Lastprofil um den Faktor 30 erhöhen

for i in range(load_profiles.shape[1]):  # [1] gibt die Anzahl der Spalten in der CSV Datei zurück
    network.add("Load", f"household_group_{i}", bus="main_bus", p_set=load_profiles.iloc[:, i])


# Optimierung durchführen
network.lopf(network.snapshots, solver_name='gurobi')

# PyPSA hat keine direkte Funktion um die Autarkie in der Optimierung zu berücksichten. Daher mit Schleife?
# Autarkie berechnen


def calculate_autarky(network):
    energy_from_grid = network.generators_t.p['grid'].sum()
    total_energy_demand = network.loads_t.p.sum().sum()
    autarky = 1 - (energy_from_grid / total_energy_demand)
    return autarky


autarky_target = 0.7  # Zielautarkie

# Optimierung einmal durchführen
network.lopf(network.snapshots, solver_name='gurobi')

# Autarkie berechnen
autarky = calculate_autarky(network)

while autarky < autarky_target:  # Logik: Eine Reduzierung der Netzkapazität führt zu einer höheren Autarkie.
    # Maximale Kapazität des Netzes reduzieren (z.B. um 5%)
    network.generators.loc['grid', 'p_nom_max'] *= 0.95

    # Optimierung neu durchführen
    network.lopf(network.snapshots, solver_name='gurobi')

    # Autarkie erneut berechnen
    autarky = calculate_autarky(network)

    print("Autarkie: {:.2f}%".format(autarky))

# Optimale Anlagengröße anzeigen
optimal_pv_size = network.generators.p_nom_opt["pv"]
optimal_wind_size = network.generators.p_nom_opt["wind"]

print(f"Optimale Größe für PV: {optimal_pv_size} MW")
print(f"Optimale Größe für Wind: {optimal_wind_size} MW")