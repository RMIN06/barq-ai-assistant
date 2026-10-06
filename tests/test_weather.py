from unittest.mock import patch, Mock

import pytest

from weather import get_weather


def test_current_weather_uses_selected_city():
    location = Mock()
    location.json.return_value = {"results": [{"name": "Karachi", "country": "Pakistan", "latitude": 24.86, "longitude": 67.01}]}
    forecast = Mock()
    forecast.json.return_value = {"current": {"temperature_2m": 30.2, "relative_humidity_2m": 50, "apparent_temperature": 34, "wind_speed_10m": 12, "weather_code": 1, "time": "2026-10-06T12:00"}}
    with patch("weather.requests.get", side_effect=[location, forecast]) as get:
        result = get_weather("Karachi")
    assert result["temperature"] == 30.2
    assert result["city"] == "Karachi"
    assert get.call_args_list[0].kwargs["params"]["name"] == "Karachi"
    location.raise_for_status.assert_called_once()
    forecast.raise_for_status.assert_called_once()


def test_weather_rejects_bad_location():
    with pytest.raises(ValueError):
        get_weather(" ")
    response = Mock()
    response.json.return_value = {"results": []}
    with patch("weather.requests.get", return_value=response):
        with pytest.raises(ValueError, match="No weather location"):
            get_weather("Nowhere City")
