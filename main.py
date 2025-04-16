from flask import Flask, request, jsonify
import swisseph as swe
import datetime
import requests

app = Flask(__name__)

TIMEZONE_API_KEY = '9LX1PDNRN4HW'
swe.set_ephe_path('.')

PLANETS = {
    'Sun': swe.SUN,
    'Moon': swe.MOON,
    'Mercury': swe.MERCURY,
    'Venus': swe.VENUS,
    'Mars': swe.MARS,
    'Jupiter': swe.JUPITER,
    'Saturn': swe.SATURN,
    'Uranus': swe.URANUS,
    'Neptune': swe.NEPTUNE,
    'Pluto': swe.PLUTO
}
ASPECTS = [
    ('Conjunction', 0, 8),
    ('Sextile', 60, 5),
    ('Square', 90, 6),
    ('Trine', 120, 6),
    ('Opposition', 180, 8)
]
BURCLAR = ['Koç', 'Boğa', 'İkizler', 'Yengeç', 'Aslan', 'Başak',
           'Terazi', 'Akrep', 'Yay', 'Oğlak', 'Kova', 'Balık']

def get_sign(degree):
    return BURCLAR[int(degree) % 360 // 30]

def get_coords(place):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': place,
        'format': 'json',
        'addressdetails': 1,
        'limit': 1
    }
    headers = {'User-Agent': 'AstroAPI'}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if not data:
            return None
        lat = float(data[0]['lat'])
        lon = float(data[0]['lon'])
        return lat, lon
    except:
        return None

def get_utc_offset(lat, lon, timestamp):
    url = "https://api.timezonedb.com/v2.1/get-time-zone"
    params = {
        'key': TIMEZONE_API_KEY,
        'format': 'json',
        'by': 'position',
        'lat': lat,
        'lng': lon,
        'time': timestamp
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        return data.get('gmtOffset', 0) / 3600
    except:
        return 0

def get_julian_day(dt):
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)

def get_aspects(planet_positions):
    aspects = []
    keys = list(planet_positions.keys())
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            p1, p2 = keys[i], keys[j]
            deg1, deg2 = planet_positions[p1]['degree'], planet_positions[p2]['degree']
            angle = abs(deg1 - deg2)
            if angle > 180:
                angle = 360 - angle
            for aspect_name, exact_angle, orb in ASPECTS:
                if abs(angle - exact_angle) <= orb:
                    aspects.append({
                        'between': [p1, p2],
                        'aspect': aspect_name,
                        'orb': round(abs(angle - exact_angle), 2)
                    })
    return aspects

def get_transits(jd):
    transits = {}
    for name, code in PLANETS.items():
        result = swe.calc_ut(jd, code)
        pos = result[0]
        info = result[1] if isinstance(result[1], dict) else {}
        speed = info.get('speed', 0)
        transits[name] = {
            'degree': round(pos[0], 2),
            'retrograde': "Evet" if speed < 0 else "Hayır"
        }
    return transits

@app.route('/calculate-full-astro', methods=['POST'])
def calculate_full_astro():
    try:
        data = request.get_json()
        birth_date = data.get('birthDate')
        birth_time = data.get('birthTime')
        birth_place = data.get('birthPlace')

        if not all([birth_date, birth_time, birth_place]):
            return jsonify({'error': 'Eksik bilgi'}), 400

        coords = get_coords(birth_place)
        if not coords:
            return jsonify({'error': 'Konum bulunamadı'}), 400
        lat, lon = coords

        dt_obj = datetime.datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
        timestamp = int(dt_obj.timestamp())
        utc_offset = get_utc_offset(lat, lon, timestamp)
        dt_utc = dt_obj - datetime.timedelta(hours=utc_offset)
        jd = get_julian_day(dt_utc)

        planet_positions = {}
        for name, code in PLANETS.items():
            result = swe.calc_ut(jd, code)
            pos = result[0]
            info = result[1] if isinstance(result[1], dict) else {}
            speed = info.get('speed', 0)
            planet_positions[name] = {
                'degree': round(pos[0], 2),
                'sign': get_sign(pos[0]),
                'retrograde': "Evet" if speed < 0 else "Hayır"
            }

        node_pos, _ = swe.calc_ut(jd, swe.MEAN_NODE)
        north_node = round(node_pos[0], 2)
        south_node = round((north_node + 180) % 360, 2)

        houses, ascmc = swe.houses(jd, lat, lon, b'P')
        house_positions = {f'House{i+1}': round(deg, 2) for i, deg in enumerate(houses)}
        asc = round(ascmc[0], 2) if ascmc[0] is not None else 0
        mc = round(ascmc[1], 2) if ascmc[1] is not None else 0

        sun_deg = planet_positions['Sun']['degree']
        moon_deg = planet_positions['Moon']['degree']
        sun_sign = get_sign(sun_deg)
        moon_sign = get_sign(moon_deg)
        asc_sign = get_sign(asc)
        mc_sign = get_sign(mc)

        aspects = get_aspects(planet_positions)

        now = datetime.datetime.utcnow()
        jd_now = swe.julday(now.year, now.month, now.day, now.hour + now.minute / 60.0)
        transits = get_transits(jd_now)

        return jsonify({
            'coordinates': {'lat': lat, 'lon': lon},
            'utcOffsetUsed': f"{utc_offset:+.2f}",
            'ascendant': {'degree': asc, 'sign': asc_sign},
            'midheaven': {'degree': mc, 'sign': mc_sign},
            'sun': {'degree': round(sun_deg, 2), 'sign': sun_sign},
            'moon': {'degree': round(moon_deg, 2), 'sign': moon_sign},
            'planets': planet_positions,
            'houses': house_positions,
            'aspects': aspects,
            'nodes': {
                'north': {
                    'degree': north_node,
                    'sign': get_sign(north_node)
                },
                'south': {
                    'degree': south_node,
                    'sign': get_sign(south_node)
                }
            },
            'transitsDate': now.isoformat() + "Z",
            'transits': transits
        })

    except Exception as e:
        return jsonify({'error': 'Sunucu hatası', 'detail': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
