"""Weather data retrieval."""

import requests


def _weather_description(code: int) -> str:
    """Return an Italian description for an Open-Meteo weather code."""
    if code == 0:
        return "cielo sereno"
    if code in {1, 2, 3}:
        return "cielo parzialmente nuvoloso o coperto"
    if code in {45, 48}:
        return "nebbia"
    if code in {51, 53, 55, 56, 57}:
        return "pioviggine"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "pioggia"
    if code in {71, 73, 75, 77, 85, 86}:
        return "neve"
    if code in {95, 96, 99}:
        return "temporali"
    return "condizioni variabili"


def get_weather_data(latitude: float, longitude: float) -> str:
    """Retrieve current conditions, daily ranges, and weather alerts from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": (
            "temperature_2m_min,temperature_2m_max,relative_humidity_2m_min,relative_humidity_2m_max,"
            "weather_code,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max"
        ),
        "forecast_days": 1,
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        current = data.get("current", {})
        daily = data.get("daily", {})

        temperature = current.get("temperature_2m", "N/D")
        humidity = current.get("relative_humidity_2m", "N/D")
        current_wind = current.get("wind_speed_10m", "N/D")
        weather_code = int(current.get("weather_code", 0))
        condition = _weather_description(weather_code)

        temperature_min = daily.get("temperature_2m_min", ["N/D"])[0]
        temperature_max = daily.get("temperature_2m_max", ["N/D"])[0]
        humidity_min = daily.get("relative_humidity_2m_min", ["N/D"])[0]
        humidity_max = daily.get("relative_humidity_2m_max", ["N/D"])[0]
        precipitation_probability = daily.get("precipitation_probability_max", [0])[0]
        precipitation = daily.get("precipitation_sum", [0])[0]
        wind_max = daily.get("wind_speed_10m_max", [0])[0]
        gust_max = daily.get("wind_gusts_10m_max", [0])[0]
        daily_code = int(daily.get("weather_code", [weather_code])[0])

        alerts: list[str] = []
        if precipitation > 0 or precipitation_probability >= 40:
            alerts.append(f"Possibili precipitazioni: {precipitation_probability}% ({precipitation} mm previsti)")
        if wind_max >= 30 or gust_max >= 50:
            alerts.append(f"Vento sostenuto: fino a {wind_max} km/h, raffiche fino a {gust_max} km/h")
        if daily_code in {45, 48, 71, 73, 75, 77, 85, 86, 95, 96, 99}:
            alerts.append(f"Attenzione per {_weather_description(daily_code)} durante la giornata")
        alert_text = (
            "\n".join(f"• {alert}" for alert in alerts) if alerts else "• Nessuna condizione di attenzione prevista"
        )

        return (
            "🌡️ *Meteo*\n\n"
            "*Adesso*\n"
            f"• Temperatura: {temperature}°C\n"
            f"• Umidità: {humidity}%\n"
            f"• Condizioni: {condition}\n"
            f"• Vento: {current_wind} km/h\n\n"
            "*Oggi*\n"
            f"• Temperatura minima/massima: {temperature_min}°C / {temperature_max}°C\n"
            f"• Umidità minima/massima: {humidity_min}% / {humidity_max}%\n\n"
            "*Attenzioni*\n"
            f"{alert_text}"
        )
    except (requests.RequestException, TypeError, ValueError, IndexError) as error:
        return f"Impossibile recuperare il meteo: {error}"
