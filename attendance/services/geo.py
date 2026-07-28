import math

EARTH_RADIUS_METERS = 6371000.0  # Mean radius of Earth in meters

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth
    specified in decimal degrees (latitude and longitude).
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = EARTH_RADIUS_METERS * c
    return round(distance, 2)


def verify_location(user_lat, user_lon, campus_config):
    """
    Verify if user coordinates are within campus radius.
    Returns: (is_inside, distance_meters, message)
    """
    if user_lat is None or user_lon is None:
        return False, None, "GPS location is required."

    try:
        user_lat = float(user_lat)
        user_lon = float(user_lon)
    except (ValueError, TypeError):
        return False, None, "Invalid GPS coordinates."

    center_lat = campus_config.center_latitude
    center_lon = campus_config.center_longitude
    radius = campus_config.radius_meters

    distance = haversine_distance(user_lat, user_lon, center_lat, center_lon)

    if distance <= radius:
        return True, distance, f"Inside campus boundary ({distance}m from center)."
    else:
        return False, distance, f"You are outside the campus ({distance}m from center, max allowed: {radius}m)."
