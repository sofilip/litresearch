import re
import subprocess
import time
import urllib.request
import urllib.parse
import json
from bs4 import BeautifulSoup
from dateutil import parser
import datetime
import os
import glob
import zipfile
import xml.etree.ElementTree as ET
import unicodedata

ALLOWED_FIELDS = {
    'Item Type', 'Author', 'Abstract', 'Date', 
    'URL', 'Extra', 'DOI', 
    'Citation Key', 'Archive ID'
}

# --- Cache variables ---
pubpeer_cache = {}
author_hindex_cache = {}
excel_author_data = {}
OPENREVIEW_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openreview_cache.json')

# Helper Functions
def escape_latex(text):
    if not isinstance(text, str):
        return text
    # Remove control characters except tab and newline/carriage return
    text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
    conv = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', 
        '^': r'\textasciicircum{}', '\\': r'\textbackslash{}',
        '<': r'\textless{}', '>': r'\textgreater{}',
        'τ': r'\ensuremath{\tau}',
        'α': r'\ensuremath{\alpha}',
        'β': r'\ensuremath{\beta}',
        'γ': r'\ensuremath{\gamma}',
        'μ': r'\ensuremath{\mu}',
        'λ': r'\ensuremath{\lambda}',
        'π': r'\ensuremath{\pi}',
        'θ': r'\ensuremath{\theta}',
        'σ': r'\ensuremath{\sigma}',
        'Ω': r'\ensuremath{\Omega}',
        'Δ': r'\ensuremath{\Delta}',
        'ε': r'\ensuremath{\epsilon}',
        '∗': r'\ensuremath{\ast}',
        '∼': r'\ensuremath{\sim}',
        '≥': r'\ensuremath{\ge}',
        '≤': r'\ensuremath{\le}',
        '±': r'\ensuremath{\pm}',
        '“': '``',
        '”': "''",
        '‘': '`',
        '’': "'",
        '–': '--',
        '—': '---',
        '*': r'\ensuremath{\ast}',
    }
    regex = re.compile('|'.join(re.escape(str(key)) for key in sorted(conv.keys(), key=lambda item: -len(item))))
    return regex.sub(lambda match: conv[match.group()], text)

def fetch_pubpeer_data(clean_doi):
    if not clean_doi:
        return '0'
    return str(pubpeer_cache.get(clean_doi.lower().strip(), 0))

def batch_fetch_pubpeer_data(dois):
    cache = {}
    if not dois:
        return cache
    url = "https://pubpeer.com/v3/publications?devkey=PubMedChrome"
    dois_list = list(set(dois))
    for i in range(0, len(dois_list), 50):
        chunk = dois_list[i:i+50]
        payload = {"dois": chunk}
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, 
                data=data,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Content-Type': 'application/json'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode())
                feedbacks = res_data.get('feedbacks', [])
                for feedback in feedbacks:
                    doi_id = feedback.get('id')
                    total_comments = feedback.get('total_comments', 0)
                    if doi_id:
                        cache[doi_id.lower().strip()] = total_comments
        except Exception as e:
            print(f"Error querying PubPeer batch {i}: {e}")
    return cache

# --- OpenReview API helper functions & caching ---
def load_openreview_cache():
    if os.path.exists(OPENREVIEW_CACHE_FILE):
        try:
            with open(OPENREVIEW_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_openreview_cache(cache):
    try:
        with open(OPENREVIEW_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving OpenReview cache: {e}")

def compute_paperhash(first_author, title):
    if not title:
        return ""
    title = title.strip()
    # Strip punctuation using regex matching OpenReview normalization
    clean_title = re.sub(r'[^A-zÀ-ÿ\d\s]', '', title)
    clean_title = re.sub(r'\s+', '_', clean_title).lower()
    
    # Extract lowercased last name
    if first_author:
        author_parts = first_author.strip().split()
        if author_parts:
            last_name = author_parts[-1].lower()
        else:
            last_name = ""
    else:
        last_name = ""
    return f"{last_name}|{clean_title}"

def fetch_openreview_data(authors, title, cache):
    if not authors or not title:
        return {
            'found': False,
            'is_peer_reviewed': False,
            'retracted': False,
            'comments_count': 0
        }
        
    first_author = authors[0]
    paperhash = compute_paperhash(first_author, title)
    if not paperhash:
        return {
            'found': False,
            'is_peer_reviewed': False,
            'retracted': False,
            'comments_count': 0
        }
        
    # Check cache first
    if paperhash in cache:
        return cache[paperhash]
        
    # Query OpenReview API
    result = {
        'found': False,
        'is_peer_reviewed': False,
        'retracted': False,
        'comments_count': 0
    }
    
    params = {'paperhash': paperhash}
    qs = urllib.parse.urlencode(params)
    url = f"https://api2.openreview.net/notes?{qs}"
    
    notes = []
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                notes = data.get('notes', [])
                break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
            else:
                break
        except Exception:
            break
            
    if notes:
        result['found'] = True
        forum_ids = list(set(n['forum'] for n in notes if 'forum' in n))
        all_forum_notes = []
        for fid in forum_ids:
            time.sleep(0.5)
            forum_url = f"https://api2.openreview.net/notes?forum={fid}"
            for attempt in range(5):
                try:
                    req = urllib.request.Request(forum_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        fdata = json.loads(resp.read().decode())
                        all_forum_notes.extend(fdata.get('notes', []))
                        break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        time.sleep(2 ** attempt)
                    else:
                        break
                except Exception:
                    break
                    
        is_peer_reviewed = False
        retracted = False
        comments_count = 0
        seen_ids = set()
        
        for n in all_forum_notes:
            nid = n.get('id')
            if not nid or nid in seen_ids:
                continue
            seen_ids.add(nid)
            
            invitations = n.get('invitations', [])
            inv_str = " ".join(invitations).lower()
            
            if any(x in inv_str for x in ['review', 'decision', 'comment']):
                if not any(x in inv_str for x in ['submission', 'revision', 'blind_submission']):
                    comments_count += 1
                    
                    if any(x in inv_str for x in ['retract', 'withdraw', 'withdrawn']):
                        retracted = True
                        
                    content = n.get('content', {})
                    for k, v in content.items():
                        val_str = str(v.get('value', '') if isinstance(v, dict) else v).lower()
                        if any(x in val_str for x in ['retract', 'withdraw', 'withdrawn']):
                            if k in ['title', 'decision', 'comment']:
                                retracted = True
                                
                    if 'review' in inv_str or 'decision' in inv_str:
                        is_peer_reviewed = True
                        
            if any(x in inv_str for x in ['retracted', 'withdrawn', 'withdraw']):
                retracted = True
                
            content = n.get('content', {})
            venue = str(content.get('venue', {}).get('value', '')).lower()
            if 'withdrawn' in venue or 'retracted' in venue:
                retracted = True
                
        result['is_peer_reviewed'] = is_peer_reviewed
        result['retracted'] = retracted
        result['comments_count'] = comments_count
        time.sleep(1.0)
    else:
        time.sleep(0.5)
        
    cache[paperhash] = result
    save_openreview_cache(cache)
    return result

def slugify(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

# --- Advanced DOI-Based API Fetcher ---
def fetch_advanced_citation_data(doi):
    default_metrics = {
        'FWCI': 'N/A',
        'Citation percentile (by year/subfield)': 'N/A',
        'Cites': 'N/A',
        'Cited by': 'N/A',
        'Related to': 'N/A',
        'Retracted': 'No',           
        'PubPeer Comments': '0',
        'Type': 'preprint'
    }
    
    metrics = default_metrics.copy()
    citations = 0
    importance = "New/Niche"
    
    try:
        if not doi or not str(doi).strip():
            return default_metrics.copy(), "No DOI", 0, None
            
        clean_doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '').strip()
        if not clean_doi.startswith('10.'):
            return default_metrics.copy(), "No DOI", 0, None
            
        url = f"https://api.openalex.org/works/doi:{clean_doi}"
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:user@user.com'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
            if 'cited_by_count' in data and data['cited_by_count'] is not None:
                citations = data['cited_by_count']
                metrics['Cited by'] = str(citations)
                
            if 'fwci' in data and data['fwci'] is not None:
                metrics['FWCI'] = str(round(data['fwci'], 2))
                
            if 'citation_normalized_percentile' in data and data['citation_normalized_percentile'] is not None:
                if 'value' in data['citation_normalized_percentile']:
                    metrics['Citation percentile (by year/subfield)'] = str(round(data['citation_normalized_percentile']['value'], 2))
                    
            if 'referenced_works_count' in data and data['referenced_works_count'] is not None:
                metrics['Cites'] = str(data['referenced_works_count'])
                
            if 'related_works' in data and data['related_works'] is not None:
                metrics['Related to'] = str(len(data['related_works']))
                
            if data.get('is_retracted'):
                metrics['Retracted'] = '\\textbf{\\textcolor{red}{YES (RETRACTED)}}'
                
            pubpeer_count = fetch_pubpeer_data(clean_doi)
            if pubpeer_count != '0':
                metrics['PubPeer Comments'] = f"\\textbf{{\\textcolor{{orange}}{{{pubpeer_count} Comments}}}}"
                
            if 'type' in data:
                metrics['Type'] = data['type']
                
            if citations >= 100:
                importance = "High"
            elif citations >= 10:
                importance = "Medium"
            else:
                importance = "New/Niche"
                
        return metrics, importance, citations, data.get('authorships', [])
                
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return default_metrics.copy(), "New/Niche", 0, None
    except Exception:
        pass 
        
    return default_metrics.copy(), "New/Niche", 0, None

# --- Author h-index Cache & Fetcher ---
def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = name.lower()
    if ',' in name:
        parts = name.split(',', 1)
        last = parts[0].strip()
        first_mid = parts[1].strip()
        name = f"{first_mid} {last}"
    name = re.sub(r'[^\w\s]', ' ', name)
    return " ".join(name.split())

def load_excel_names(excel_path=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not excel_path:
        xlsx_files = [f for f in glob.glob(os.path.join(os.getcwd(), '*.xlsx')) if not os.path.basename(f).startswith('~$')]
        if not xlsx_files:
            xlsx_files = [f for f in glob.glob(os.path.join(script_dir, '*.xlsx')) if not os.path.basename(f).startswith('~$')]
        if not xlsx_files:
            print("No .xlsx file found in current working directory or script directory.")
            return {}
        xlsx_path = xlsx_files[0]
    else:
        xlsx_path = excel_path

    if not os.path.exists(xlsx_path):
        print(f"Error: Excel file does not exist at '{xlsx_path}'")
        return {}

    xlsx_name = os.path.basename(xlsx_path)
    print(f"Using Excel file: {xlsx_path}")
    
    xlsx_dir = os.path.dirname(os.path.abspath(xlsx_path))
    cache_path = os.path.join(xlsx_dir, 'xlsx_names_cache.txt')
    
    if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(xlsx_path):
        print("Loading author names from cache...")
        excel_data = {}
        with open(cache_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip('\n').split('\t')
                if len(parts) == 4:
                    excel_data[parts[0]] = (parts[1], parts[2], parts[3])
                elif len(parts) == 1 and parts[0]:
                    excel_data[parts[0]] = ('N/A', 'N/A', 'N/A')
        return excel_data
            
    print("Cache invalid or missing. Parsing Excel file (this might take a while on the first run)...")
    t0 = time.time()
    excel_data = {}
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    row_tag = f'{{{ns}}}row'
    
    try:
        with zipfile.ZipFile(xlsx_path, 'r') as z:
            with z.open('xl/worksheets/sheet2.xml', 'r') as f:
                for event, elem in ET.iterparse(f, events=('end',)):
                    if elem.tag == row_tag:
                        cells = elem.findall(f'{{{ns}}}c')
                        cell_dict = {}
                        for cell in cells:
                            r = cell.get('r')
                            if r:
                                col = ''.join([char for char in r if char.isalpha()])
                                cell_dict[col] = cell
                                
                        if 'A' in cell_dict:
                            a_cell = cell_dict['A']
                            t_elem = a_cell.find(f'.//{{{ns}}}t')
                            if t_elem is not None and t_elem.text:
                                raw_name = t_elem.text
                                norm = normalize_name(raw_name)
                                if norm and norm != 'authfull':
                                    works = 'N/A'
                                    citations = 'N/A'
                                    h_index = 'N/A'
                                    
                                    if 'D' in cell_dict:
                                        v_elem = cell_dict['D'].find(f'{{{ns}}}v')
                                        if v_elem is not None and v_elem.text:
                                            works = v_elem.text
                                    if 'W' in cell_dict:
                                        v_elem = cell_dict['W'].find(f'{{{ns}}}v')
                                        if v_elem is not None and v_elem.text:
                                            citations = v_elem.text
                                    if 'X' in cell_dict:
                                        v_elem = cell_dict['X'].find(f'{{{ns}}}v')
                                        if v_elem is not None and v_elem.text:
                                            h_index = v_elem.text
                                            
                                    excel_data[norm] = (works, citations, h_index)
                        elem.clear()
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            for name, stats in sorted(excel_data.items()):
                f.write(f"{name}\t{stats[0]}\t{stats[1]}\t{stats[2]}\n")
                
        print(f"Excel parsing completed in {time.time() - t0:.2f}s. Cache saved.")
        return excel_data
    except Exception as e:
        print(f"Error parsing Excel file: {e}")
        return {}

def fetch_author_hindexes(authorships):
    if not authorships:
        return []
    
    author_ids = []
    author_display_order = []
    
    for authorship in authorships:
        author_info = authorship.get('author', {})
        display_name = author_info.get('display_name', '')
        author_id = author_info.get('id')
        if display_name:
            if author_id:
                clean_id = author_id.split('/')[-1]
                author_ids.append((clean_id, display_name))
                author_display_order.append((clean_id, display_name))
            else:
                author_display_order.append((None, display_name))
                
    ids_to_query = []
    for aid, name in author_ids:
        if normalize_name(name) in excel_author_data:
            continue
        if aid not in author_hindex_cache:
            ids_to_query.append(aid)
            
    if ids_to_query:
        for i in range(0, len(ids_to_query), 50):
            chunk = ids_to_query[i:i+50]
            filter_str = "|".join(chunk)
            url = f"https://api.openalex.org/authors?filter=openalex:{filter_str}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'mailto:zotero_parser@example.com'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode())
                    for author_obj in res_data.get('results', []):
                        aid = author_obj.get('id', '').split('/')[-1]
                        summary_stats = author_obj.get('summary_stats', {})
                        h_idx = summary_stats.get('h_index')
                        if h_idx is None:
                            h_idx = author_obj.get('h_index')
                        
                        works = author_obj.get('works_count')
                        cits = author_obj.get('cited_by_count')
                        
                        author_hindex_cache[aid] = {
                            'works_count': str(works) if works is not None else 'N/A',
                            'citations_count': str(cits) if cits is not None else 'N/A',
                            'h_index': str(h_idx) if h_idx is not None else 'N/A'
                        }
            except Exception:
                pass
                
        for aid in ids_to_query:
            if aid not in author_hindex_cache:
                author_hindex_cache[aid] = {
                    'works_count': 'N/A',
                    'citations_count': 'N/A',
                    'h_index': 'N/A'
                }
                
    result = []
    for aid, name in author_display_order:
        norm_name = normalize_name(name)
        if norm_name in excel_author_data:
            works_count, citations_count, h_index = excel_author_data[norm_name]
            result.append((name, f" (Works count: {works_count}, Citations count: {citations_count}, H-index: {h_index})"))
        elif aid:
            info = author_hindex_cache.get(aid, {'works_count': 'N/A', 'citations_count': 'N/A', 'h_index': 'N/A'})
            works_count = info.get('works_count', 'N/A')
            citations_count = info.get('citations_count', 'N/A')
            h_index = info.get('h_index', 'N/A')
            result.append((name, f" (Works count: {works_count}, Citations count: {citations_count}, H-index: {h_index})"))
        else:
            result.append((name, ""))
    return result

def extract_date(item):
    for th in item.find_all('th'):
        if th.text.strip() == 'Date':
            try:
                parsed = parser.parse(th.find_next_sibling('td').text.strip(), default=datetime.datetime(1900, 1, 1))
                return parsed.replace(tzinfo=None)
            except: pass
    return datetime.datetime(1900, 1, 1)


# Main Execution Function
def analyze_papers(input_filename='bibliography.html', output_filename='bibliography.tex', excel_path=None, report_template_path=None, paper_item_template_path=None):
    global excel_author_data
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Resolve paths
    if not report_template_path:
        cwd_template = os.path.join(os.getcwd(), 'report_template.tex')
        if os.path.exists(cwd_template):
            report_template_path = cwd_template
        else:
            report_template_path = os.path.join(script_dir, 'report_template.tex')
            
    if not paper_item_template_path:
        cwd_item_template = os.path.join(os.getcwd(), 'paper_item_template.tex')
        if os.path.exists(cwd_item_template):
            paper_item_template_path = cwd_item_template
        else:
            paper_item_template_path = os.path.join(script_dir, 'paper_item_template.tex')
        
    print(f"Loading template files:\n - {report_template_path}\n - {paper_item_template_path}")
    
    try:
        with open(report_template_path, 'r', encoding='utf-8') as f:
            latex_template = f.read()
        with open(paper_item_template_path, 'r', encoding='utf-8') as f:
            item_template = f.read()
    except FileNotFoundError as e:
        print(f"Error loading LaTeX template: {e}")
        return False

    # Load Excel author list
    excel_author_data = load_excel_names(excel_path)
    
    # Load HTML report
    print(f"Reading HTML library from {input_filename}...")
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
    except FileNotFoundError:
        print(f"Error: Could not find HTML file '{input_filename}'")
        return False
        
    report_list = soup.find('ul', class_='report')
    if not report_list:
        print("Error: Could not find paper list in the HTML.")
        return False
        
    items = report_list.find_all('li', class_='item')
    sorted_items = sorted(items, key=extract_date, reverse=True)
    
    # Extract all valid DOIs to pre-fetch PubPeer data
    all_dois = []
    for item in sorted_items:
        for tr in item.find_all('tr'):
            th, td = tr.find('th'), tr.find('td')
            if th and td and th.get_text(strip=True) == 'DOI':
                doi = td.get_text(strip=True).replace('https://doi.org/', '').replace('http://doi.org/', '').strip()
                if doi.startswith('10.'):
                    all_dois.append(doi)
                    
    print(f"Pre-fetching PubPeer comments for {len(all_dois)} DOIs...")
    pubpeer_cache.update(batch_fetch_pubpeer_data(all_dois))
    
    openreview_cache = load_openreview_cache()
    
    # Parse items and generate LaTeX code
    latex_items = []
    categorized_articles = {
        'High': [],
        'Medium': [],
        'New/Niche': [],
        'No DOI': []
    }
    newest_articles = []
    suspicious_retracted = [] 
    suspicious_pubpeer = []    
    openreview_matched_list = []
    peer_reviewed_list = []
    
    print(f"Processing {len(sorted_items)} items. Simulating strict metrics...")
    
    for item in sorted_items:
        title_element = item.find('h2')
        raw_title = title_element.get_text(strip=True) if title_element else "Untitled"
        title = escape_latex(raw_title)
        
        slug = slugify(raw_title)
        item_id = item.get('id', f'item_{slug[:8]}') 
        
        authors = []
        metadata = []
        is_github = False
        raw_doi = None 
        date_str = "Unknown Date"
        
        for tr in item.find_all('tr'):
            th, td = tr.find('th'), tr.find('td')
            if not th or not td: continue
                
            key = th.get_text(strip=True)
            if key not in ALLOWED_FIELDS: continue
            
            if key == 'DOI':
                raw_doi = td.get_text(strip=True)
                
            if key == 'Date':
                try:
                    parsed_date = parser.parse(td.get_text(strip=True))
                    val_escaped = escape_latex(parsed_date.strftime('%Y-%m-%d'))
                except:
                    val_escaped = escape_latex(td.get_text(separator='\n', strip=True))
                date_str = val_escaped
                metadata.append((key, val_escaped))
                continue
                
            if key == 'Author':
                authors.append(td.get_text(strip=True))
            else:
                val = td.get_text(separator='\n', strip=True)
                if "github.com" in val.lower(): is_github = True
                
                a_tag = td.find('a')
                if a_tag and a_tag.get('href'):
                    raw_url = a_tag['href']
                    if "doi.org" not in raw_url:
                        val_escaped = f"\\url{{{raw_url}}}"
                    else:
                        val_escaped = f"\\href{{{raw_url}}}{{{escape_latex(val)}}}"
                else:
                    val_escaped = escape_latex(val).replace('\n', ' ')
                metadata.append((key, val_escaped))
                
        author_display_list = []
        peer_reviewed_str = "No"
        or_comments_str = "0"
        
        if not is_github: 
            if len(newest_articles) < 5:
                newest_articles.append((title, slug, date_str))
                
            # Get OpenReview data
            openreview_res = fetch_openreview_data(authors, raw_title, openreview_cache)
            is_or_retracted = openreview_res.get('retracted', False)
            is_or_peer_reviewed = openreview_res.get('is_peer_reviewed', False)
            or_comments_count = openreview_res.get('comments_count', 0)
            if or_comments_count > 0:
                or_comments_str = f"\\textbf{{\\textcolor{{orange}}{{{or_comments_count} Comments}}}}"
                
            if raw_doi:
                metrics, importance, citations, authorship_data = fetch_advanced_citation_data(raw_doi)
                if authorship_data:
                    author_display_list = fetch_author_hindexes(authorship_data)
                else:
                    author_display_list = [(a, "") for a in authors]
                    
                is_oa_retracted = 'YES' in metrics.get('Retracted', '')
                is_retracted = is_oa_retracted or is_or_retracted
                if is_retracted:
                    metrics['Retracted'] = '\\textbf{\\textcolor{red}{YES (RETRACTED)}}'
                    if (title, slug) not in suspicious_retracted:
                        suspicious_retracted.append((title, slug))
                        
                if metrics.get('PubPeer Comments', '0') not in ['0', 'N/A']:
                    suspicious_pubpeer.append((title, slug, is_retracted))
                    
                openalex_type = metrics.get('Type', 'preprint')
                is_peer_reviewed_bool = openalex_type in ['article', 'book-chapter', 'book', 'standard', 'reference-entry'] or is_or_peer_reviewed
                peer_reviewed_str = "Yes" if is_peer_reviewed_bool else "No"
                time.sleep(0.5)
            else:
                importance = "No DOI"
                citations = 0
                is_retracted = is_or_retracted
                metrics = {
                    'FWCI': 'N/A',
                    'Citation percentile (by year/subfield)': 'N/A',
                    'Cites': 'N/A',
                    'Cited by': 'N/A',
                    'Related to': 'N/A',
                    'Retracted': '\\textbf{\\textcolor{red}{YES (RETRACTED)}}' if is_retracted else 'No',       
                    'PubPeer Comments': '0'  
                }
                if is_retracted:
                    if (title, slug) not in suspicious_retracted:
                        suspicious_retracted.append((title, slug))
                author_display_list = [(a, "") for a in authors]
                is_peer_reviewed_bool = is_or_peer_reviewed
                peer_reviewed_str = "Yes" if is_peer_reviewed_bool else "No"
                
            if importance in categorized_articles:
                categorized_articles[importance].append((title, slug, citations))
            else:
                categorized_articles['New/Niche'].append((title, slug, citations))
                
            if importance == "High":
                importance_display = "\\textbf{\\textcolor{purple}{High (100+ citations)}}"
            elif importance == "Medium":
                importance_display = "\\textbf{\\textcolor{blue}{Medium (10+ citations)}}"
            elif importance == "No DOI":
                importance_display = "No DOI (Unindexed)"
            else:
                importance_display = "New / Niche (<10 citations)"
                
            metadata.append(('Importance', importance_display))
            metadata.append(('FWCI', metrics.get('FWCI', 'N/A')))
            metadata.append(('Citation percentile', metrics.get('Citation percentile (by year/subfield)', 'N/A')))
            metadata.append(('Cites', metrics.get('Cites', 'N/A')))
            metadata.append(('Cited by', metrics.get('Cited by', 'N/A')))
            metadata.append(('Related to', metrics.get('Related to', 'N/A')))
            metadata.append(('Retracted', metrics.get('Retracted', 'No')))
            metadata.append(('PubPeer Alerts', metrics.get('PubPeer Comments', '0')))
            metadata.append(('OpenReview Alerts', or_comments_str))
        else:
            author_display_list = [(a, "") for a in authors]
            
        metadata.append(('Peer Reviewed', peer_reviewed_str))
        
        if not is_github:
            if openreview_res.get('found'):
                openreview_matched_list.append((title, slug))
            if peer_reviewed_str == "Yes":
                peer_reviewed_list.append((title, slug))
                
        if author_display_list:
            formatted_authors = []
            for name, stats in author_display_list:
                escaped_name = escape_latex(name)
                norm_name = normalize_name(name)
                if norm_name in excel_author_data:
                    escaped_name = f"\\textcolor{{red}}{{{escaped_name}}}"
                    if not stats:
                        works, citations, h_index = excel_author_data[norm_name]
                        stats = f" (Works count: {works}, Citations count: {citations}, H-index: {h_index})"
                escaped_stats = escape_latex(stats) if stats else ""
                formatted_authors.append(escaped_name + escaped_stats)
                
            metadata.insert(0, ('Author(s)', ", ".join(formatted_authors)))
            
        table_rows = [f"{escape_latex(k)} & {v} \\\\" for k, v in metadata]
        
        item_tex = item_template.replace("ITEM_ID", item_id).replace("SLUG", slug).replace("TITLE", title).replace("TABLE_CONTENT", "\n".join(table_rows))
        latex_items.append(item_tex)
        
    # Build the Report Summary Block
    summary_tex = "\\section*{Report Summary}\n\n"
    important_count = len(categorized_articles['High']) + len(categorized_articles['Medium'])
    summary_tex += f"\\textbf{{Total Important Articles (10+ Citations):}} {important_count}\n\n"
    
    summary_tex += "\\subsection*{Newest Additions}\n\\begin{itemize}\n"
    for t, s, d in newest_articles:
        summary_tex += f"  \\item \\textbf{{{d}}}: \\hyperref[{s}]{{{t}}} (Page \\pageref{{{s}}})\n"
    summary_tex += "\\end{itemize}\n\n"
    
    summary_tex += "\\subsection*{Articles by Importance}\n\\begin{itemize}\n"
    for cat in ['High', 'Medium', 'New/Niche', 'No DOI']:
        items_in_cat = categorized_articles[cat]
        items_in_cat.sort(key=lambda x: x[2], reverse=True)
        
        cat_title = cat
        if cat == 'High': cat_title = "High Importance (100+ Citations)"
        elif cat == 'Medium': cat_title = "Medium Importance (10 - 99 Citations)"
        elif cat == 'New/Niche': cat_title = "New / Niche (<10 Citations)"
        elif cat == 'No DOI': cat_title = "No DOI"
        
        articles_tex_list = []
        for t, s, c in items_in_cat:
            articles_tex_list.append(f"\\ref{{{s}}} (Page \\pageref{{{s}}})")
            
        articles_str = ", ".join(articles_tex_list)
        summary_tex += f"  \\item \\textbf{{{cat_title}}}: {articles_str}\n"
        
    summary_tex += "\\end{itemize}\n"
    
    if suspicious_retracted or suspicious_pubpeer:
        summary_tex += "\n\\subsection*{Suspicious Papers (Action Required)}\n\\begin{itemize}\n"
        if suspicious_retracted:
            retracted_refs = ", ".join([f"\\ref{{{s}}} (Page \\pageref{{{s}}})" for t, s in suspicious_retracted])
            summary_tex += f"  \\item \\textbf{{\\textcolor{{red}}{{Retracted}}}}: {retracted_refs}\n"
            
        if suspicious_pubpeer:
            pubpeer_refs_list = []
            pubpeer_retracted_list = []
            for t, s, r in suspicious_pubpeer:
                ret_val = "\\textcolor{red}{Yes}" if r else "No"
                pubpeer_refs_list.append(f"\\ref{{{s}}} (Page \\pageref{{{s}}}) (Retracted: {ret_val})")
                if r:
                    pubpeer_retracted_list.append(f"\\ref{{{s}}} (Page \\pageref{{{s}}})")
                    
            pubpeer_refs = ", ".join(pubpeer_refs_list)
            summary_tex += f"  \\item \\textbf{{\\textcolor{{orange}}{{PubPeer Alerts}}}}: {pubpeer_refs}\n"
            
            if pubpeer_retracted_list:
                retracted_sub_refs = ", ".join(pubpeer_retracted_list)
                summary_tex += f"    \\begin{{itemize}}\n      \\item \\textbf{{\\textcolor{{red}}{{Retracted PubPeer Articles}}}}: {retracted_sub_refs}\n    \\end{{itemize}}\n"
                
        summary_tex += "\\end{itemize}\n"
        
    if openreview_matched_list or peer_reviewed_list:
        summary_tex += "\n\\subsection*{Reviewed Papers}\n\\begin{itemize}\n"
        if openreview_matched_list:
            or_refs = ", ".join([f"\\ref{{{s}}} (Page \\pageref{{{s}}})" for t, s in openreview_matched_list])
            summary_tex += f"  \\item \\textbf{{OpenReview Submissions}}: {or_refs}\n"
        if peer_reviewed_list:
            pr_refs = ", ".join([f"\\ref{{{s}}} (Page \\pageref{{{s}}})" for t, s in peer_reviewed_list])
            summary_tex += f"  \\item \\textbf{{Peer Reviewed Articles}}: {pr_refs}\n"
        summary_tex += "\\end{itemize}\n"
        
    summary_tex += "\n\\vspace{1cm}\\hrule\\vspace{1cm}\n" 
    
    # Write LaTeX file
    with open(output_filename, 'w', encoding='utf-8') as f:
        final_latex = latex_template.replace("[REPORT_SUMMARY]", summary_tex).replace("[LATEX_ITEMS]", "\n".join(latex_items))
        f.write(final_latex)
        
    print("Data parsed! Compiling to PDF using pdflatex...")
    subprocess.run(['pdflatex', '-interaction=nonstopmode', output_filename], stdout=subprocess.DEVNULL)
    subprocess.run(['pdflatex', '-interaction=nonstopmode', output_filename], stdout=subprocess.DEVNULL)
    
    pdf_filename = os.path.splitext(output_filename)[0] + ".pdf"
    if os.path.exists(pdf_filename):
        print("Success! Your PDF with the Executive Summary is ready.")
    else:
        print("Error: PDF was not generated. Check LaTeX warnings/errors.")
        return False
        
    # Cleanup auxiliary files
    base, _ = os.path.splitext(output_filename)
    for ext in ['.aux', '.log', '.out']:
        temp_file = base + ext
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception as e:
                print(f"Error removing auxiliary file {temp_file}: {e}")
                
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Query paper metrics and compile LaTeX report to PDF")
    parser.add_argument("--html", default="bibliography.html", help="Path to input HTML file")
    parser.add_argument("--tex", default="bibliography.tex", help="Path to output TeX file")
    parser.add_argument("--excel", default=None, help="Path to top scientists Excel file")
    parser.add_argument("--template", default=None, help="Path to main LaTeX report template")
    parser.add_argument("--item-template", default=None, help="Path to LaTeX item template")
    args = parser.parse_args()
    
    analyze_papers(args.html, args.tex, args.excel, args.template, args.item_template)