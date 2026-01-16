import requests
import re
from datetime import datetime

def get_weather(lat, lon):
    # Step 1: Get the gridpoint endpoint for the given lat/long
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_resp = requests.get(points_url, headers={"User-Agent": "weather-app (your_email@example.com)"})
    print("\n")
    points_resp.raise_for_status()
    points_data = points_resp.json()

    print(points_data)
    # Step 2: Get forecast URL from the gridpoint response
    forecast_url = points_data["properties"]["forecast"]

    # Step 3: Fetch forecast data
    forecast_resp = requests.get(forecast_url, headers={"User-Agent": "weather-app (your_email@example.com)"})
    forecast_resp.raise_for_status()
    forecast_data = forecast_resp.json()

    print(forecast_data)
    # Step 4: Process the first forecast period and format according to specified structure
    first_period = forecast_data["properties"]["periods"][0]
    
    # Convert temperature to Celsius
    temp_f = first_period["temperature"]
    temp_c = round((temp_f - 32) * 5/9, 1)
    
    # Parse wind speed and convert to mph
    wind_speed_str = first_period.get("windSpeed", "0 mph")
    wind_speed_mph = _parse_wind_speed(wind_speed_str)
    
    # Parse wind direction to degrees
    wind_direction = first_period.get("windDirection", "")
    wind_direction_degrees = _parse_wind_direction(wind_direction)
    
    # Get precipitation probability and convert to estimated mm
    precipitation_prob = first_period.get("probabilityOfPrecipitation", {})
    if isinstance(precipitation_prob, dict):
        prob_value = precipitation_prob.get("value", 0) or 0
    else:
        prob_value = 0
    # Use probability directly instead of converting to mm
    precipitation_prob = prob_value
    
    # Simplify conditions
    conditions = _simplify_conditions(first_period.get("shortForecast", "Clear"))
    
    # Generate timestamp
    start_time = first_period.get("startTime", "")
    timestamp = _parse_timestamp(start_time) if start_time else datetime.utcnow().isoformat() + "Z"
    
    return {
        "timestamp": timestamp,
        "temperature_fahrenheit": temp_c,
        "humidity_percent": 60,  # NWS API doesn't provide humidity, using default
        "precipitation_prob": precipitation_prob,
        "wind_speed_mph": wind_speed_mph,
        "wind_direction_degrees": wind_direction_degrees,
        "conditions": conditions
    }

def _parse_wind_speed(wind_speed_str: str) -> float:
    """Parse wind speed string and convert to mph."""
    numbers = re.findall(r'\d+', wind_speed_str)
    if not numbers:
        return 0.0
    
    # If range (e.g., "5 to 10 mph"), take average
    if len(numbers) >= 2:
        avg_mph = (int(numbers[0]) + int(numbers[1])) / 2
    else:
        avg_mph = int(numbers[0])
    
    # Convert mph to mph
    return round(avg_mph * 1, 1)

def _parse_wind_direction(direction_str: str) -> int:
    """Parse wind direction string to degrees."""
    direction_map = {
        "N": 0, "NNE": 22, "NE": 45, "ENE": 67,
        "E": 90, "ESE": 112, "SE": 135, "SSE": 157,
        "S": 180, "SSW": 202, "SW": 225, "WSW": 247,
        "W": 270, "WNW": 292, "NW": 315, "NNW": 337
    }
    
    direction_str = direction_str.strip().upper()
    return direction_map.get(direction_str, 0)

def _simplify_conditions(short_forecast: str) -> str:
    """Simplify weather conditions to basic categories."""
    forecast_lower = short_forecast.lower()
    
    if any(word in forecast_lower for word in ["sunny", "clear"]):
        return "Clear"
    elif any(word in forecast_lower for word in ["partly cloudy", "partly sunny", "mostly sunny"]):
        return "Partly Cloudy"
    elif "cloudy" in forecast_lower or "overcast" in forecast_lower:
        return "Cloudy"
    elif any(word in forecast_lower for word in ["rain", "shower", "drizzle"]):
        return "Rain"
    elif any(word in forecast_lower for word in ["snow", "sleet", "freezing"]):
        return "Snow"
    elif any(word in forecast_lower for word in ["storm", "thunder"]):
        return "Storm"
    elif "fog" in forecast_lower:
        return "Fog"
    else:
        return "Clear"

def _parse_timestamp(timestamp_str: str) -> str:
    """Parse NWS timestamp and convert to ISO format."""
    try:
        # Parse the timestamp and convert to UTC
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except:
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# Example usage:
if __name__ == "__main__":
    lat, lon = 33.3091336,-111.9353095  # Example coordinates
    weather = get_weather(lat, lon)
    print(weather)
    print(f"Temperature: {weather['temperature_fahrenheit']}°F")
    print(f"Conditions: {weather['conditions']}")
    print(f"Wind: {weather['wind_speed_mph']} mph from {weather['wind_direction_degrees']}°")
    print(f"Precipitation Probability: {weather['precipitation_prob']}%")
