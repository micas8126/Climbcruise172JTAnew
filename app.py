import pandas as pd
import numpy as np
import streamlit as st
import math

# Daten laden
cruise_df = pd.read_csv("cruise_performance_combined.csv")
climb_df = pd.read_csv("climb_performance_verified.csv")

# UI
st.title("Reisezeit- & Verbrauchsrechner: Climb + Cruise")
st.markdown("Berechnung von **Time** und **Fuel [l]** inkl. realistischer Windberechnung (aus Richtung und Geschwindigkeit)")

# Eingaben
weight_input = st.number_input("Gewicht [kg]", min_value=1111, max_value=1157, step=1)
total_distance = st.number_input("Gesamtdistanz [NM]", min_value=10.0, step=1.0)
start_altitude = st.number_input("Startflughöhe [ft]", min_value=0, max_value=18000, step=100)
target_altitude = st.number_input("Ziel-Flughöhe [ft]", min_value=0, max_value=18000, step=100)
load_input = st.selectbox("Cruise Load [%]", sorted(cruise_df["Load [%]"].unique(), reverse=True))
alternate_distance = st.number_input("Alternate-Distanz [NM]", min_value=0.0, step=1.0)
additional_fuel = st.number_input("Zusätzlicher Kraftstoff [l]", min_value=0.0, step=0.5)

# Winddaten
course_input = st.number_input("Kursrichtung [°]", min_value=0, max_value=359)
wind_dir = st.number_input("Windrichtung (woher) [°]", min_value=0, max_value=359)
wind_speed = st.number_input("Windgeschwindigkeit [KT]", min_value=0, step=1)

# Rundung der Höhen
available_climb_altitudes = sorted(climb_df["Pressure Altitude [ft]"].unique())
available_cruise_altitudes = sorted(cruise_df["Pressure Altitude [ft]"].unique())

raw_climb_altitude = target_altitude - start_altitude
climb_altitude = min([alt for alt in available_climb_altitudes if alt >= raw_climb_altitude], default=None)
rounded_target_altitude = min([alt for alt in available_cruise_altitudes if alt >= target_altitude], default=None)

# Zeitformatierung
def format_time(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}:{m:02d} h"

# Windberechnung (korrekt aus meteorologischer Richtung)
def calc_ground_speed(tas, wind_dir_met, wind_speed, course):
    wind_to = (wind_dir_met + 180) % 360  # Umwandlung: woher → wohin
    angle_deg = (wind_to - course) % 360
    angle_rad = math.radians(angle_deg)
    wind_component = wind_speed * math.cos(angle_rad)
    return max(30.0, tas + wind_component)

# Alternate-Flug (immer 4000 ft bei 60 % Load)
time_alt = 0.0
fuel_alt = 0.0
alt_subset = cruise_df[(cruise_df["Pressure Altitude [ft]"] == 4000) & (cruise_df["Load [%]"] == 60)]
if len(alt_subset) >= 2:
    alt_weights = alt_subset["Weight [kg]"].values
    alt_speed = np.interp(1134, alt_weights, alt_subset["Speed [KTAS]"].values)
    alt_flow = np.interp(1134, alt_weights, alt_subset["Fuel Flow [l/h]"].values)
    alt_gs = calc_ground_speed(alt_speed, wind_dir, wind_speed, course_input)
    time_alt = alternate_distance / alt_gs
    fuel_alt = time_alt * alt_flow

# Hauptflug
if climb_altitude is None or rounded_target_altitude is None:
    st.error("Bitte Zielhöhe reduzieren – keine passenden Climb-/Cruise-Werte.")
else:
    climb_segment = climb_df[climb_df["Pressure Altitude [ft]"] == climb_altitude]
    if len(climb_segment) >= 2:
        weights = climb_segment["Weight [kg]"].values
        time_climb = np.interp(weight_input, weights, climb_segment["Time [MIN]"].values) / 60
        fuel_climb = np.interp(weight_input, weights, climb_segment["Fuel [l]"].values)
        dist_climb = np.interp(weight_input, weights, climb_segment["Distance [NM]"].values)

        remaining_distance = total_distance - dist_climb
        if remaining_distance <= 0:
            st.error("Distanz zu kurz für berechneten Climb.")
        else:
            cruise_subset = cruise_df[(cruise_df["Pressure Altitude [ft]"] == rounded_target_altitude) &
                                      (cruise_df["Load [%]"] == load_input)]
            if len(cruise_subset) >= 2:
                weights = cruise_subset["Weight [kg]"].values
                speed_cruise = np.interp(weight_input, weights, cruise_subset["Speed [KTAS]"].values)
                fuel_flow_cruise = np.interp(weight_input, weights, cruise_subset["Fuel Flow [l/h]"].values)

                cruise_gs = calc_ground_speed(speed_cruise, wind_dir, wind_speed, course_input)
                time_cruise = remaining_distance / cruise_gs
                fuel_cruise = time_cruise * fuel_flow_cruise

                # Fixwerte
                fuel_departure = 4.0
                fuel_landing = 1.0
                fuel_reserve = 17.0

                # Teilsummen
                flight_time = time_climb + time_cruise
                flight_fuel = fuel_climb + fuel_cruise + fuel_departure + fuel_landing
                total_fuel = flight_fuel + fuel_reserve + additional_fuel
                fuel_with_alt = total_fuel + fuel_alt

                # Ausgabe (12 Punkte)
                st.success("Ergebnisse")
                st.markdown(f"**1) Gerundete Climb-Höhe über Startplatz:** {climb_altitude} ft")
                st.markdown(f"**2) Gerundete Cruise-Höhe:** {rounded_target_altitude} ft")
                st.markdown(f"**3) Windkomponente auf dem Kurs:** Wind aus {wind_dir}°, {wind_speed} KT, Kurs {course_input}°")
                st.markdown(f"**4) Climb:** {format_time(time_climb)}, {fuel_climb:.1f} l")
                st.markdown(f"**5) Cruise:** {format_time(time_cruise)}, {fuel_cruise:.1f} l")
                st.markdown(f"**6) Startzuschlag:** {fuel_departure:.1f} l fix")
                st.markdown(f"**7) Landung:** {fuel_landing:.1f} l fix")
                st.markdown("---")
                st.markdown(f"**8) Flug Gesamt (Zeit + Fuel):** {format_time(flight_time)}, {flight_fuel:.1f} l")
                st.markdown(f"**9) Reserve:** {fuel_reserve:.1f} l")
                st.markdown(f"**10) Zusatzkraftstoff:** {additional_fuel:.1f} l")
                st.markdown(f"**11) Alternate-Flug:** {format_time(time_alt)}, {fuel_alt:.1f} l")
                st.markdown(f"**12) Fuel Flug inkl. Alternate:** {fuel_with_alt:.1f} l")
            else:
                st.warning("Nicht genug Daten für Cruise-Interpolation.")
    else:
        st.warning("Keine Climb-Daten für berechnete Climb-Höhe.")
