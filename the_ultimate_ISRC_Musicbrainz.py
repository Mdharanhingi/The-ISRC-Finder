import requests
import pandas as pd
import time
import os
from datetime import datetime
from fuzzywuzzy import fuzz

# File paths
INPUT_PATH = r"C:\Users\IT Support\Pictures\Book3.csv"
OUTPUT_PATH = r"C:\Users\IT Support\Pictures\song_metadata_2025only.csv"
UNMATCHED_PATH = r"C:\\Users\\IT Support\\Pictures\\unmatched_records.csv"
#OUTPUT_PATH = r"C:\\Users\\IT Support\\Pictures\\updated_songs_with_isrc.csv"
LOG_PATH = r"C:\\Users\\IT Support\\Pictures\\isrc_fetch_log.txt"

# Start logging
log_lines = []
log_lines.append(f"ISRC Fetch Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Fuzzy match helper
def is_similar(a, b, threshold=40):
    return fuzz.token_set_ratio(a.lower().strip(), b.lower().strip()) >= threshold

# MusicBrainz artist search cache
artist_cache = {}

# Function to search for recordings by artist name
def fetch_artist_recordings(artist_name):
    base_url = "https://musicbrainz.org/ws/2/recording/"
    params = {
        "query": f"artist:\"{artist_name}\"",
        "fmt": "json",
        "limit": 10,
        "offset": 0
    }
    headers = {"User-Agent": "ISRCFetcher/1.0 ( contact@example.com )"}
    all_recordings = []

    try:
        while True:
            print(f"Fetching recordings for artist: {artist_name} offset {params['offset']}")
            response = requests.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                log_lines.append(f"Failed to fetch artist recordings: {response.status_code}")
                break

            data = response.json()
            recordings = data.get("recordings", [])
            all_recordings.extend(recordings)

            if len(recordings) < 100:
                break  # no more pages

            params['offset'] += 100
            time.sleep(1)  # rate limiting

    except Exception as e:
        print(f"Error fetching recordings for {artist_name}: {e}")
        log_lines.append(f"Error fetching recordings for {artist_name}: {e}")

    return all_recordings

# Try loading the CSV with fallback strategies
def load_csv_flexible(path):
    try:
        return pd.read_csv(path, encoding='utf-8')
    except Exception:
        try:
            return pd.read_csv(path, encoding='ISO-8859-1')
        except Exception:
            try:
                return pd.read_csv(path, sep=';', encoding='ISO-8859-1', engine='python')
            except Exception:
                return pd.read_csv(path, sep='\t', encoding='ISO-8859-1', engine='python')

# Load the CSV
try:
    df = load_csv_flexible(INPUT_PATH)
    df.columns = df.columns.str.strip()
    print(f"Loaded {len(df)} records from the input file.")
    log_lines.append(f"Loaded {len(df)} records from the input file.")
except Exception as e:
    print(f"Failed to load input CSV: {e}")
    log_lines.append(f"Failed to load input CSV: {e}")
    df = pd.DataFrame()

unmatched_rows = []
updated = 0

# Attempt to locate the best matching artist column
artist_col = None
for col in df.columns:
    if 'artist' in col.lower():
        artist_col = col
        break

if "Title" not in df.columns or artist_col is None:
    print("Missing required columns: 'Title' and/or an artist column")
    log_lines.append("Missing required columns: 'Title' and/or an artist column")
else:
    for index, row in df.iterrows():
        try:
            if pd.isna(row.get("ISRC", "")):
                track_name = str(row.get("Title", "")).strip()
                artist_name = str(row.get(artist_col, "")).strip()

                if not track_name or not artist_name:
                    unmatched_rows.append(row)
                    continue

                if artist_name not in artist_cache:
                    artist_cache[artist_name] = fetch_artist_recordings(artist_name)

                best_match = None
                for recording in artist_cache[artist_name]:
                    if is_similar(track_name, recording.get("title", "")):
                        if recording.get("isrcs"):
                            best_match = recording.get("isrcs")[0]
                            break

                if best_match:
                    df.at[index, "ISRC"] = best_match
                    updated += 1
                    print(f"[MATCH] {track_name} - {artist_name} => {best_match}")
                    log_lines.append(f"[MATCH] {track_name} - {artist_name} => {best_match}")
                else:
                    unmatched_rows.append(row)
                    print(f"[NO MATCH] {track_name} - {artist_name}")
                    log_lines.append(f"[NO MATCH] {track_name} - {artist_name}")

                time.sleep(1)
        except Exception as e:
            print(f"Error on row {index}: {e}")
            log_lines.append(f"Error on row {index}: {e}")
            unmatched_rows.append(row)
            continue

# Save updated CSV
df.to_csv(OUTPUT_PATH, index=False)
print(f"Saved updated file to: {OUTPUT_PATH}")
log_lines.append(f"Saved updated file to: {OUTPUT_PATH}")

# Save unmatched records
if unmatched_rows:
    pd.DataFrame(unmatched_rows).to_csv(UNMATCHED_PATH, index=False)
    print(f"Saved unmatched records to: {UNMATCHED_PATH}")
    log_lines.append(f"Saved unmatched records to: {UNMATCHED_PATH}")

# Write log
with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))

print(f"Log saved to: {LOG_PATH}")
