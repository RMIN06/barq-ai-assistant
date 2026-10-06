"""Current weather from Open-Meteo for an explicitly selected city."""
import requests


def get_weather(city: str) -> dict:
    city = city.strip()
    if not 2 <= len(city) <= 80:
        raise ValueError("Enter a city name between 2 and 80 characters.")
    location_response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    location_response.raise_for_status()
    matches = location_response.json().get("results") or []
    if not matches:
        raise ValueError(f"No weather location found for {city}.")
    location = matches[0]
    forecast_response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
        timeout=10,
    )
    forecast_response.raise_for_status()
    current = forecast_response.json()["current"]
    return {
        "city": location["name"],
        "country": location.get("country", ""),
        "temperature": current["temperature_2m"],
        "humidity": current["relative_humidity_2m"],
        "feels_like": current["apparent_temperature"],
        "wind": current["wind_speed_10m"],
        "code": current["weather_code"],
        "time": current["time"],
    }
