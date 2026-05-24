import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
}

class ESPNScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_soup(self, url, retries=3):
        for attempt in range(retries):
            try:
                # Enforce a 1.5 second architectural delay between ALL requests
                time.sleep(1.5)
                
                response = self.session.get(url, timeout=15)
                
                # CloudFront Rate Limiting Block Check
                if response.status_code == 403 or "too much traffic" in response.text.lower():
                    logging.warning(f"Rate limited on {url} (Attempt {attempt+1}/{retries}). Sleeping for {10 * (attempt + 1)}s...")
                    time.sleep(10 * (attempt + 1))
                    continue
                    
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
                
            except requests.exceptions.RequestException as e:
                # Catch generic exceptions that have response objects (like standard 403s caught by raise_for_status before the manual check)
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 403:
                    logging.warning(f"403 Forbidden Error on {url}. Sleeping for {10 * (attempt + 1)}s...")
                    time.sleep(10 * (attempt + 1))
                    continue
                    
                logging.error(f"Error fetching {url}: {e}")
                return None
                
        logging.error(f"Exhausted {retries} retries fetching {url} due to rate limiting blocks.")
        return None

    def extract_espnfitt_json(self, soup):
        if not soup:
            return None
            
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and "window['__espnfitt__']=" in script.string:
                try:
                    content = script.string
                    parts = content.split("window['__espnfitt__']=")
                    if len(parts) > 1:
                        json_str = parts[1].strip()
                        if json_str.endswith(';'):
                            json_str = json_str[:-1]
                        return json.loads(json_str)
                except Exception as e:
                    logging.error(f"Error parsing __espnfitt__: {e}")
        return None

    def scrape_fighter_profile(self, espn_id=None, url=None):
        if not url and espn_id:
            url = f"https://www.espn.com/mma/fighter/_/id/{espn_id}"
        elif not url:
            return {}
            
        if not espn_id:
            match = re.search(r'/id/(\d+)', url)
            if match:
                espn_id = match.group(1)
                
        logging.info(f"Scraping fighter profile: {url}")
        soup = self.get_soup(url)
        data = self.extract_espnfitt_json(soup)
        
        stats = {
            'espn_id': espn_id,
            'name': 'Unknown',
            'nickname': None,
            'weight_class': None,
            'nationality': None,
            'dob': None,
            'height_cm': None,
            'reach_cm': None,
            'stance': None,
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'url': url
        }

        if data:
             # Try extracting from nextjs context if available
             try:
                 player_info = data.get('page', {}).get('content', {}).get('player', {})
                 if player_info:
                     # Prefer firstName + lastName when present — ESPN occasionally
                     # ships fullName already concatenated without a space, which
                     # was leaving us with names like "AljamainSterling".
                     first = (player_info.get('firstName') or '').strip()
                     last = (player_info.get('lastName') or '').strip()
                     if first and last:
                         stats['name'] = f"{first} {last}"
                     else:
                         stats['name'] = (
                             player_info.get('displayName')
                             or player_info.get('fullName')
                             or stats['name']
                         )
                     stats['weight_class'] = player_info.get('position', stats['weight_class'])
                     # Sometimes 'birthPlace' is accessible
                     stats['nationality'] = player_info.get('birthPlace', {}).get('country', stats['nationality'])
             except Exception:
                 pass
        
        if not soup:
             return stats

        # Fallback to DOM if json is sparse
        header_div = soup.find('div', class_=lambda x: x and 'PlayerHeader' in x)
        if header_div:
            text = header_div.get_text(separator='|', strip=True)
            parts = [p.strip() for p in text.split('|')]
            
            def get_val(keys):
                for i, p in enumerate(parts):
                    if p.lower() in [k.lower() for k in keys] and i + 1 < len(parts):
                        return parts[i+1]
                return None
                
            if stats['name'] == 'Unknown':
                # Attempt to get name from h1. ESPN wraps first/last in separate
                # <span> children, so a bare get_text(strip=True) would glue them
                # together ("AljamainSterling"). Pass a space separator instead.
                h1 = header_div.find('h1')
                if h1:
                    stats['name'] = h1.get_text(separator=' ', strip=True)

            hw = get_val(['HT/WT', 'Height', 'Ht'])
            if hw:
                subparts = hw.split(',')
                if len(subparts) > 0: 
                    # 5' 11" to cm
                    ht_str = subparts[0].strip()
                    m = re.match(r"(\d+)'\s*(\d+)", ht_str)
                    if m:
                        feet, inches = int(m.group(1)), int(m.group(2))
                        stats['height_cm'] = round((feet * 12 + inches) * 2.54, 1)

            dob = get_val(['Birthdate', 'DOB'])
            if dob:
                 # 11/14/1988 (37)
                 d_str = dob.split('(')[0].strip()
                 try:
                     stats['dob'] = datetime.strptime(d_str, "%m/%d/%Y").date()
                 except Exception:
                     pass
                     
            reach = get_val(['Reach'])
            if reach:
                r_str = reach.replace('"', '').strip()
                try:
                    stats['reach_cm'] = round(float(r_str) * 2.54, 1)
                except Exception:
                    pass

            stance = get_val(['Stance'])
            if stance:
                stats['stance'] = stance
                
            record = get_val(['Record', 'W-L-D'])
            if record:
                 m = re.match(r"(\d+)-(\d+)-(\d+)", record)
                 if m:
                     stats['wins'] = int(m.group(1))
                     stats['losses'] = int(m.group(2))
                     stats['draws'] = int(m.group(3))
        
        # Scrape nickname natively
        # Usually ESPN just uses first, last name. Let's look for known elements
        stats['nickname'] = self._extract_element_text(soup, 'div', 'PlayerHeader__Bio_Item', 'nickname')
        
        return stats

    def _extract_element_text(self, soup, tag, class_, keyword):
        items = soup.find_all(tag, class_=class_)
        for item in items:
            if keyword.lower() in item.get_text().lower():
                 val = item.find('div', class_='PlayerHeader__Data')
                 return val.get_text(strip=True) if val else None
        return None

    def scrape_schedule(self, year):
        url = f"https://www.espn.com/mma/schedule/_/year/{year}/league/ufc"
        logging.info(f"Targeting schedule: {url}")
        soup = self.get_soup(url)
        if not soup: return []

        events = []
        tables = soup.find_all('table', class_='Table')
        for table in tables:
            rows = table.find_all('tr', class_='Table__TR')
            for row in rows:
                event_col = row.find('td', class_='event__col')
                if not event_col: continue
                link = event_col.find('a')
                if not link: continue
                
                event_name = link.get_text(strip=True)
                event_url = link.get('href', '')
                
                match = re.search(r'/id/(\d+)', event_url)
                if not match: continue
                
                espn_event_id = match.group(1)
                
                if event_url.startswith('/'):
                    event_url = "https://www.espn.com" + event_url
                    
                date_col = row.find('td', class_='date__col')
                date_text = date_col.get_text(strip=True) if date_col else "TBD"
                
                # Parse date
                clean_date = re.sub(r'^[A-Za-z]+,\s*', '', date_text)
                if clean_date.upper() == 'LIVE':
                    event_date = datetime.now().date()
                else:
                    try:
                        event_date = datetime.strptime(f"{clean_date} {year}", "%b %d %Y").date()
                    except Exception:
                        continue
                    
                loc_col = row.find('td', class_='location__col')
                location = loc_col.get_text(strip=True) if loc_col else None
                
                events.append({
                    'espn_event_id': espn_event_id,
                    'name': event_name,
                    'location': location,
                    'event_date': event_date,
                    'url': event_url
                })
        return events

    def scrape_event_fights(self, event_url, espn_event_id):
        logging.info(f"Scraping EVENT fights: {event_url}")
        soup = self.get_soup(event_url)
        data = self.extract_espnfitt_json(soup)
        
        fights_data = []
        total_matches_seen = 0

        if data:
            gp = data.get('page', {}).get('content', {}).get('gamepackage', {})
            segs = gp.get('cardSegs', [])
            # cardSegs is ordered Main Card → Prelims → Early Prelims, and
            # mtchs within each seg is in display order (main event first).
            # card_order preserves that for the frontend sort.
            for seg_index, seg in enumerate(segs):
                 matches = seg.get('mtchs', [])
                 total_matches_seen += len(matches)
                 for match_index, m in enumerate(matches):
                     card_order = seg_index * 100 + match_index
                     match_id = m.get('id')

                     awy = m.get('awy', {})
                     hme = m.get('hme', {})

                     # ESPN's MMA gamepackage nests athlete data under 'ath'. Older/hero
                     # wrappers occasionally expose 'lnk' directly — fall back to that,
                     # and finally to the numeric athlete id if no link is present.
                     awy_ath = awy.get('ath', {}) or {}
                     hme_ath = hme.get('ath', {}) or {}

                     n1_id = (
                         self._extract_id_from_link(awy_ath.get('lnk'))
                         or self._extract_id_from_link(awy.get('lnk'))
                         or (str(awy_ath.get('id')) if awy_ath.get('id') else None)
                     )
                     n2_id = (
                         self._extract_id_from_link(hme_ath.get('lnk'))
                         or self._extract_id_from_link(hme.get('lnk'))
                         or (str(hme_ath.get('id')) if hme_ath.get('id') else None)
                     )

                     if not n1_id or not n2_id:
                         logging.warning(
                             f"Skipping match {match_id} in event {espn_event_id}: "
                             f"could not resolve athlete id (awy keys={list(awy.keys())}, "
                             f"hme keys={list(hme.keys())})"
                         )
                         continue
                     
                     is_title = False
                     note = m.get('nte', '')
                     if note and "Title Fight" in note:
                         is_title = True
                         
                     # Results
                     winner_id = None
                     match_status = m.get('status', {}).get('state')
                     method = None
                     time_str = None
                     rnd = None
                     
                     if match_status == 'post':
                         # isWin may live on the wrapper or on the athlete node
                         if awy.get('isWin') or awy_ath.get('isWin'):
                             winner_id = n1_id
                         elif hme.get('isWin') or hme_ath.get('isWin'):
                             winner_id = n2_id
                         
                         method = m.get('dec', {}).get('shrtDspNm')
                         time_str = m.get('status', {}).get('dspClk')
                         rnd_raw = m.get('status', {}).get('rd')
                         rnd = None
                         if rnd_raw is not None:
                             rnd_str = re.sub(r'\D', '', str(rnd_raw))
                             rnd = int(rnd_str) if rnd_str else None
                         
                     fights_data.append({
                         'espn_fight_id': match_id,
                         'espn_event_id': espn_event_id,
                         'fighter_a_espn_id': n1_id,
                         'fighter_b_espn_id': n2_id,
                         'winner_espn_id': winner_id,
                         'method': method,
                         'round': rnd,
                         'time': time_str,
                         'weight_class': None, # hard to extract cleanly, leave for now or extract from title
                         'is_title_fight': is_title,
                         'card_order': card_order,
                     })

        # If __espnfitt__ is empty, we would fallback to DOM. But standard ESPN events
        # heavily rely on this React prop inject. We log a warning if empty.
        if not fights_data:
            logging.warning(f"No fights extracted from JSON via __espnfitt__ for {espn_event_id}")
        elif data and len(fights_data) < total_matches_seen:
            # Partial drop — surface it so silent undercounts don't slip by again.
            logging.warning(
                f"Event {espn_event_id}: extracted {len(fights_data)} fight(s) but "
                f"__espnfitt__ reported {total_matches_seen} match(es). "
                f"{total_matches_seen - len(fights_data)} were skipped — check warnings above."
            )

        return fights_data
        
    def scrape_fighter_stats(self, espn_id):
        """
        Scrape per-fight stats from ESPN's fighter stats page.
        Returns a list of dicts, one per fight, keyed by espn_event_id.

        ESPN provides 3 tables (striking, clinch, ground).
        Each row begins with 4 metadata cells:
          [0] Date object  [1] Opponent object  [2] Event object  [3] Result string
        followed by stat value strings.
        """
        url = f"https://www.espn.com/mma/fighter/stats/_/id/{espn_id}"
        logging.info(f"Scraping fighter stats: {url}")
        soup = self.get_soup(url)
        data = self.extract_espnfitt_json(soup)

        if not data:
            logging.warning(f"No __espnfitt__ data for fighter stats {espn_id}")
            return []

        try:
            tables = data['page']['content']['player']['stat']['tbl']
        except (KeyError, TypeError):
            logging.warning(f"Could not locate stat tables for fighter {espn_id}")
            return []

        # Column layouts for each table (order matches ESPN JSON)
        TABLE_COLS = {
            'striking': [
                'sd_body_la', 'sd_head_la', 'sd_leg_la',
                'tsl', 'tsa', 'ssl', 'ssa', 'tsl_tsa_pct', 'kd',
                'pct_body', 'pct_head', 'pct_leg',
            ],
            'clinch': [
                'sc_body_landed', 'sc_body_attempted',
                'sc_head_landed', 'sc_head_attempted',
                'sc_leg_landed', 'sc_leg_attempted',
                'rv', 'sr', 'tdl', 'tda', 'tds', 'tk_acc',
            ],
            'ground': [
                'sg_body_landed', 'sg_body_attempted',
                'sg_head_landed', 'sg_head_attempted',
                'sg_leg_landed', 'sg_leg_attempted',
                'ad', 'adtb', 'adhg', 'adtm', 'adts', 'sm',
            ],
        }

        # Build a dict keyed by (espn_event_id, result_index) for merging tables
        fights_map = {}  # key = row_index -> merged stat dict

        for tbl_idx, tbl in enumerate(tables):
            tbl_name = tbl.get('ttl', '').lower().strip()
            # Map to our known layouts
            if 'strik' in tbl_name:
                col_names = TABLE_COLS['striking']
            elif 'clinch' in tbl_name:
                col_names = TABLE_COLS['clinch']
            elif 'ground' in tbl_name:
                col_names = TABLE_COLS['ground']
            else:
                logging.warning(f"Unknown table title '{tbl_name}' for fighter {espn_id}")
                continue

            rows = tbl.get('row', [])
            for row_idx, row in enumerate(rows):
                if len(row) < 5:
                    continue

                # Metadata cells (first 4)
                # row[0] = date, row[1] = opponent, row[2] = event, row[3] = result
                if row_idx not in fights_map:
                    # Extract metadata from the first table that sees this row
                    event_obj = row[2] if isinstance(row[2], dict) else {}
                    opponent_obj = row[1] if isinstance(row[1], dict) else {}

                    # Extract ESPN event ID from event link
                    event_lnk = event_obj.get('lnk', '')
                    event_id_match = re.search(r'/id/(\d+)', event_lnk)
                    espn_event_id = event_id_match.group(1) if event_id_match else None

                    # Extract opponent ESPN ID
                    opp_uid = opponent_obj.get('uid', '')
                    opp_id_match = re.search(r'~a:(\d+)', opp_uid)
                    opponent_espn_id = opp_id_match.group(1) if opp_id_match else None

                    result_str = row[3] if isinstance(row[3], str) else ''

                    fights_map[row_idx] = {
                        'espn_event_id': espn_event_id,
                        'opponent_espn_id': opponent_espn_id,
                        'result': result_str,
                    }

                # Parse stat values (cells after the first 4 metadata cells)
                stat_values = row[4:]
                for col_i, col_name in enumerate(col_names):
                    if col_i >= len(stat_values):
                        break
                    raw = str(stat_values[col_i]).strip()
                    fights_map[row_idx][col_name] = raw

        # Post-process: split "landed/attempted" format and convert types
        result_rows = []
        for row_idx in sorted(fights_map.keys()):
            raw = fights_map[row_idx]
            parsed = {
                'espn_fighter_id': espn_id,
                'espn_event_id': raw.get('espn_event_id'),
                'opponent_espn_id': raw.get('opponent_espn_id'),
                'result': raw.get('result'),
            }

            # Striking table: distance strikes are "landed/attempted" format
            for prefix in ['sd_body', 'sd_head', 'sd_leg']:
                la_key = f'{prefix}_la'
                la_val = raw.get(la_key, '0/0')
                landed, attempted = self._parse_landed_attempted(la_val)
                parsed[f'{prefix}_landed'] = landed
                parsed[f'{prefix}_attempted'] = attempted

            # Aggregate striking
            parsed['total_strikes_landed'] = self._parse_int(raw.get('tsl', '0'))
            parsed['total_strikes_attempted'] = self._parse_int(raw.get('tsa', '0'))
            parsed['sig_strikes_landed'] = self._parse_int(raw.get('ssl', '0'))
            parsed['sig_strikes_attempted'] = self._parse_int(raw.get('ssa', '0'))
            parsed['knockdowns'] = self._parse_int(raw.get('kd', '0'))
            parsed['pct_head'] = self._parse_pct(raw.get('pct_head', '0%'))
            parsed['pct_body'] = self._parse_pct(raw.get('pct_body', '0%'))
            parsed['pct_leg'] = self._parse_pct(raw.get('pct_leg', '0%'))

            # Clinch table
            parsed['sc_head_landed'] = self._parse_int(raw.get('sc_head_landed', '0'))
            parsed['sc_head_attempted'] = self._parse_int(raw.get('sc_head_attempted', '0'))
            parsed['sc_body_landed'] = self._parse_int(raw.get('sc_body_landed', '0'))
            parsed['sc_body_attempted'] = self._parse_int(raw.get('sc_body_attempted', '0'))
            parsed['sc_leg_landed'] = self._parse_int(raw.get('sc_leg_landed', '0'))
            parsed['sc_leg_attempted'] = self._parse_int(raw.get('sc_leg_attempted', '0'))
            parsed['reversals'] = self._parse_int(raw.get('rv', '0'))
            parsed['slam_rate'] = self._parse_float(raw.get('sr', '0'))
            parsed['takedowns_landed'] = self._parse_int(raw.get('tdl', '0'))
            parsed['takedowns_attempted'] = self._parse_int(raw.get('tda', '0'))
            parsed['takedown_slams'] = self._parse_int(raw.get('tds', '0'))
            parsed['takedown_accuracy'] = self._parse_pct(raw.get('tk_acc', '0%'))

            # Ground table
            parsed['sg_head_landed'] = self._parse_int(raw.get('sg_head_landed', '0'))
            parsed['sg_head_attempted'] = self._parse_int(raw.get('sg_head_attempted', '0'))
            parsed['sg_body_landed'] = self._parse_int(raw.get('sg_body_landed', '0'))
            parsed['sg_body_attempted'] = self._parse_int(raw.get('sg_body_attempted', '0'))
            parsed['sg_leg_landed'] = self._parse_int(raw.get('sg_leg_landed', '0'))
            parsed['sg_leg_attempted'] = self._parse_int(raw.get('sg_leg_attempted', '0'))
            parsed['advances'] = self._parse_int(raw.get('ad', '0'))
            parsed['advance_to_back'] = self._parse_int(raw.get('adtb', '0'))
            parsed['advance_to_half_guard'] = self._parse_int(raw.get('adhg', '0'))
            parsed['advance_to_mount'] = self._parse_int(raw.get('adtm', '0'))
            parsed['advance_to_side'] = self._parse_int(raw.get('adts', '0'))
            parsed['submissions'] = self._parse_int(raw.get('sm', '0'))

            result_rows.append(parsed)

        logging.info(f"Parsed {len(result_rows)} fight stat rows for fighter {espn_id}")
        return result_rows

    def _parse_landed_attempted(self, val):
        """Parse '4/6' format into (landed, attempted) ints."""
        if '/' in str(val):
            parts = str(val).split('/')
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, IndexError):
                return 0, 0
        return self._parse_int(val), 0

    def _parse_int(self, val):
        """Safely parse an int from a string, returning 0 on failure."""
        try:
            return int(re.sub(r'[^\d\-]', '', str(val)) or '0')
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, val):
        """Safely parse a float from a string, returning 0.0 on failure."""
        try:
            return float(re.sub(r'[^\d.\-]', '', str(val)) or '0')
        except (ValueError, TypeError):
            return 0.0

    def _parse_pct(self, val):
        """Parse '67%' or '40.00%' to a float like 67.0 or 40.0."""
        try:
            return float(str(val).replace('%', '').strip() or '0')
        except (ValueError, TypeError):
            return 0.0

    def _extract_id_from_link(self, lnk):
        if not lnk: return None
        match = re.search(r'/id/(\d+)', lnk)
        return match.group(1) if match else None

if __name__ == "__main__":
    # Dry run example
    scraper = ESPNScraper()
    # Test Fighter Scraping
    f = scraper.scrape_fighter_profile(espn_id="2335639") # Conor McGregor
    print(f"McGregor profile: {f}")
    
    # Test Schedule
    evts = scraper.scrape_schedule(datetime.now().year)
    if evts:
        print(f"Found {len(evts)} events this year. First event: {evts[0]}")
        # Test Event fights
        fights = scraper.scrape_event_fights(evts[0]['url'], evts[0]['espn_event_id'])
        print(f"Found {len(fights)} fights in event. First fight: {fights[0] if fights else 'None'}")
