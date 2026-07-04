import json
import webbrowser
import os

FIELD_MAPPING = {
    'title-short': 'Short Title',
    'language': 'Language',
    'publisher': 'Publisher',
    'source': 'Library Catalog',
    'abstract': 'Abstract',
    'license': 'License',
    'ISSN': 'ISSN',
    'event-title': 'Conference Name',
    'publisher-place': 'Place',
    'container-title-short': 'Journal Abbr',
    'container-title': 'Publication',
    'page': 'Pages',
    'citation-key': 'Citation Key',
    'URL': 'URL',
    'ISBN': 'ISBN',
    'issue': 'Issue',
    'genre': 'Type',
    'volume': 'Volume',
    'version': 'Version',
    'DOI': 'DOI',
    'PMID': 'PMID',
    'number': 'Number',
}

TYPE_MAPPING = {
    'article-journal': 'Journal Article',
    'paper-conference': 'Conference Paper',
    'preprint': 'Preprint',
    'document': 'Document',
    'report': 'Report',
    'book': 'Book',
    'chapter': 'Book Section',
    'article': 'Article'
}

CLASS_MAPPING = {
    'article-journal': 'journalArticle',
    'paper-conference': 'conferencePaper',
    'preprint': 'preprint',
    'document': 'document',
    'report': 'report',
    'book': 'book',
    'chapter': 'bookSection',
    'article': 'article'
}

def format_date(date_obj):
    try:
        parts = date_obj.get('date-parts', [[]])[0]
        return "-".join(str(p) for p in parts)
    except:
        return ""

def generate_html(json_filepath="bibliography.json", output_filename="bibliography.html"):
    print(f"Reading local library data from {json_filepath}...")
    
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            items = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find '{json_filepath}'. Did you export it from Zotero?")
        return False

    html_content = """<!DOCTYPE html>
<html><head>
		<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
		<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline' data:">
		<title>Zotero Report</title>
		<link rel="stylesheet" type="text/css" href="data:text/css;base64,Ym9keSB7Cgljb2xvci1zY2hlbWU6IGxpZ2h0IGRhcms7CgkvKiBUaGVzZSBzaG91bGQgYmUgdGhlIGRlZmF1bHRzLCBidXQganVzdCBpbiBjYXNlOiAqLwoJYmFja2dyb3VuZDogQ2FudmFzOwoJY29sb3I6IENhbnZhc1RleHQ7Cn0KCmEgewoJdGV4dC1kZWNvcmF0aW9uOiB1bmRlcmxpbmU7Cn0KCmJvZHkgewoJcGFkZGluZzogMDsKfQoKdWwucmVwb3J0IGxpLml0ZW0gewoJYm9yZGVyLXRvcDogNHB4IHNvbGlkICM1NTU7CglwYWRkaW5nLXRvcDogMWVtOwoJcGFkZGluZy1sZWZ0OiAxZW07CglwYWRkaW5nLXJpZ2h0OiAxZW07CgltYXJnaW4tYm90dG9tOiAyZW07Cn0KCmgxLCBoMiwgaDMsIGg0LCBoNSwgaDYgewoJZm9udC13ZWlnaHQ6IG5vcm1hbDsKfQoKaDIgewoJbWFyZ2luOiAwIDAgLjVlbTsKfQoKaDIucGFyZW50SXRlbSB7Cglmb250LXdlaWdodDogNjAwOwoJZm9udC1zaXplOiAxZW07CglwYWRkaW5nOiAwIDAgLjVlbTsKCWJvcmRlci1ib3R0b206IDFweCBzb2xpZCAjY2NjOwp9CgovKiBJZiBjb21iaW5pbmcgY2hpbGRyZW4sIGRpc3BsYXkgcGFyZW50IHNsaWdodGx5IGxhcmdlciAqLwp1bC5yZXBvcnQuY29tYmluZUNoaWxkSXRlbXMgaDIucGFyZW50SXRlbSB7Cglmb250LXNpemU6IDEuMWVtOwoJcGFkZGluZy1ib3R0b206IC43NWVtOwoJbWFyZ2luLWJvdHRvbTogLjRlbTsKfQoKaDIucGFyZW50SXRlbSAudGl0bGUgewoJZm9udC13ZWlnaHQ6IG5vcm1hbDsKfQoKaDMgewoJbWFyZ2luLWJvdHRvbTogLjZlbTsKCWZvbnQtd2VpZ2h0OiA2MDAgIWltcG9ydGFudDsKCWZvbnQtc2l6ZTogMWVtOwoJZGlzcGxheTogYmxvY2s7Cn0KCi8qIE1ldGFkYXRhIHRhYmxlICovCnRoIHsKCXZlcnRpY2FsLWFsaWduOiB0b3A7Cgl0ZXh0LWFsaWduOiByaWdodDsKCXdpZHRoOiAxNSU7Cgl3aGl0ZS1zcGFjZTogbm93cmFwOwp9Cgp0ZCB7CglwYWRkaW5nLWxlZnQ6IC41ZW07Cn0KCgp1bC5yZXBvcnQsIHVsLm5vdGVzLCB1bC50YWdzIHsKCWxpc3Qtc3R5bGU6IG5vbmU7CgltYXJnaW4tbGVmdDogMDsKCXBhZGRpbmctbGVmdDogMDsKfQoKLyogVGFncyAqLwpoMy50YWdzIHsKCWZvbnQtc2l6ZTogMS4xZW07Cn0KCnVsLnRhZ3MgewoJbGluZS1oZWlnaHQ6IDEuNzVlbTsKCWxpc3Qtc3R5bGU6IG5vbmU7Cn0KCnVsLnRhZ3MgbGkgewoJZGlzcGxheTogaW5saW5lOwp9Cgp1bC50YWdzIGxpOm5vdCg6bGFzdC1jaGlsZCk6YWZ0ZXIgewoJY29udGVudDogJywgJzsKfQoKCi8qIENoaWxkIG5vdGVzICovCmgzLm5vdGVzIHsKCWZvbnQtc2l6ZTogMS4xZW07Cn0KCnVsLm5vdGVzIHsKCW1hcmdpbi1ib3R0b206IDEuMmVtOwp9Cgp1bC5ub3RlcyA+IGxpOmZpcnN0LWNoaWxkIHAgewoJbWFyZ2luLXRvcDogMDsKfQoKdWwubm90ZXMgPiBsaSB7CglwYWRkaW5nOiAuN2VtIDA7Cn0KCnVsLm5vdGVzID4gbGk6bm90KDpsYXN0LWNoaWxkKSB7Cglib3JkZXItYm90dG9tOiAxcHggI2NjYyBzb2xpZDsKfQoKCnVsLm5vdGVzID4gbGkgcDpmaXJzdC1jaGlsZCB7CgltYXJnaW4tdG9wOiAwOwp9Cgp1bC5ub3RlcyA+IGxpIHA6bGFzdC1jaGlsZCB7CgltYXJnaW4tYm90dG9tOiAwOwp9CgovKiBBZGQgcXVvdGF0aW9uIG1hcmtzIGFyb3VuZCBibG9ja3F1b3RlICovCnVsLm5vdGVzID4gbGkgYmxvY2txdW90ZSBwOm5vdCg6ZW1wdHkpOmJlZm9yZSwKbGkubm90ZSBibG9ja3F1b3RlIHA6bm90KDplbXB0eSk6YmVmb3JlIHsKCWNvbnRlbnQ6ICfigJwnOwp9Cgp1bC5ub3RlcyA+IGxpIGJsb2NrcXVvdGUgcDpub3QoOmVtcHR5KTpsYXN0LWNoaWxkOmFmdGVyLApsaS5ub3RlIGJsb2NrcXVvdGUgcDpub3QoOmVtcHR5KTpsYXN0LWNoaWxkOmFmdGVyIHsKCWNvbnRlbnQ6ICfigJ0nOwp9CgovKiBQcmVzZXJ2ZSB3aGl0ZXNwYWNlIG9uIHBsYWludGV4dCBub3RlcyAqLwp1bC5ub3RlcyBsaSBwLnBsYWludGV4dCwgbGkubm90ZSBwLnBsYWludGV4dCwgZGl2Lm5vdGUgcC5wbGFpbnRleHQgewoJd2hpdGUtc3BhY2U6IHByZS13cmFwOwp9CgovKiBEaXNwbGF5IHRhZ3Mgd2l0aGluIGNoaWxkIG5vdGVzIGlubGluZSAqLwp1bC5ub3RlcyBoMy50YWdzIHsKCWRpc3BsYXk6IGlubGluZTsKCWZvbnQtc2l6ZTogMWVtOwp9Cgp1bC5ub3RlcyBoMy50YWdzOmFmdGVyIHsKCWNvbnRlbnQ6ICcgJzsKfQoKdWwubm90ZXMgdWwudGFncyB7CglkaXNwbGF5OiBpbmxpbmU7Cn0KCnVsLm5vdGVzIHVsLnRhZ3MgbGk6bm90KDpsYXN0LWNoaWxkKTphZnRlciB7Cgljb250ZW50OiAnLCAnOwp9CgoKLyogQ2hpbGQgYXR0YWNobWVudHMgKi8KaDMuYXR0YWNobWVudHMgewoJZm9udC1zaXplOiAxLjFlbTsKfQoKdWwuYXR0YWNobWVudHMgbGkgewoJcGFkZGluZy10b3A6IC41ZW07Cn0KCnVsLmF0dGFjaG1lbnRzIGRpdi5ub3RlIHsKCW1hcmdpbi1sZWZ0OiAyZW07Cn0KCnVsLmF0dGFjaG1lbnRzIGRpdi5ub3RlIHA6Zmlyc3QtY2hpbGQgewoJbWFyZ2luLXRvcDogLjc1ZW07Cn0KCmRpdiB0YWJsZSB7Cglib3JkZXItY29sbGFwc2U6IGNvbGxhcHNlOwp9CgpkaXYgdGFibGUgdGQsIGRpdiB0YWJsZSB0aCB7Cglib3JkZXI6IDFweCAjY2NjIHNvbGlkOwoJYm9yZGVyLWNvbGxhcHNlOiBjb2xsYXBzZTsKCXdvcmQtYnJlYWs6IGJyZWFrLWFsbDsKfQoKZGl2IHRhYmxlIHRkIHA6ZW1wdHk6OmFmdGVyLCBkaXYgdGFibGUgdGggcDplbXB0eTo6YWZ0ZXIgewoJY29udGVudDogIlwwMGEwIjsKfQoKZGl2IHRhYmxlIHRkICo6Zmlyc3QtY2hpbGQsIGRpdiB0YWJsZSB0aCAqOmZpcnN0LWNoaWxkIHsKCW1hcmdpbi10b3A6IDA7Cn0KCmRpdiB0YWJsZSB0ZCAqOmxhc3QtY2hpbGQsIGRpdiB0YWJsZSB0aCAqOmxhc3QtY2hpbGQgewoJbWFyZ2luLWJvdHRvbTogMDsKfQo=">
		<link rel="stylesheet" type="text/css" media="screen,projection" href="data:text/css;base64,LyogR2VuZXJpYyBzdHlsZXMgKi8KYm9keSB7Cglmb250OiA2Mi41JSBHZW9yZ2lhLCBUaW1lcywgc2VyaWY7Cgl3aWR0aDogNzgwcHg7CgltYXJnaW46IDAgYXV0bzsKfQoKaDIgewoJZm9udC1zaXplOiAxLjVlbTsKCWxpbmUtaGVpZ2h0OiAxLjVlbTsKCWZvbnQtZmFtaWx5OiBHZW9yZ2lhLCBUaW1lcywgc2VyaWY7Cn0KCnAgewoJbGluZS1oZWlnaHQ6IDEuNWVtOwp9CgphOmFueS1saW5rIHsKCWNvbG9yOiAjOTAwOwp9CgphOmhvdmVyLCBhOmFjdGl2ZSB7Cgljb2xvcjogIzc3NzsKfQoKQG1lZGlhIChwcmVmZXJzLWNvbG9yLXNjaGVtZTogZGFyaykgewoJYTphbnktbGluayB7CgkJY29sb3I6ICNmMDA7Cgl9CgoJYTpob3ZlciwgYTphY3RpdmUgewoJCWNvbG9yOiAjOTk5OwoJfQp9CgoKdWwucmVwb3J0IHsKCWZvbnQtc2l6ZTogMS40ZW07Cgl3aWR0aDogNjgwcHg7CgltYXJnaW46IDAgYXV0bzsKCXBhZGRpbmc6IDIwcHggMjBweDsKfQoKLyogTWV0YWRhdGEgdGFibGUgKi8KdGFibGUgewoJYm9yZGVyOiAxcHggI2NjYyBzb2xpZDsKCW92ZXJmbG93OiBhdXRvOwoJd2lkdGg6IDEwMCU7CgltYXJnaW46IC4xZW0gYXV0byAuNzVlbTsKCXBhZGRpbmc6IDAuNWVtOwp9Cg==">
		<link rel="stylesheet" type="text/css" media="print" href="data:text/css;base64,Ym9keSB7Cglmb250OiAxMnB0ICJUaW1lcyBOZXcgUm9tYW4iLCBUaW1lcywgR2VvcmdpYSwgc2VyaWY7CgltYXJnaW46IDA7Cgl3aWR0aDogYXV0bzsKfQoKLyogUGFnZSBCcmVha3MgKHBhZ2UtYnJlYWstaW5zaWRlIG9ubHkgcmVjb2duaXplZCBieSBPcGVyYSkgKi8KaDEsIGgyLCBoMywgaDQsIGg1LCBoNiB7CglwYWdlLWJyZWFrLWFmdGVyOiBhdm9pZDsKCXBhZ2UtYnJlYWstaW5zaWRlOiBhdm9pZDsKfQoKdWwsIG9sLCBkbCB7CglwYWdlLWJyZWFrLWluc2lkZTogYXZvaWQ7Cgljb2xvci1hZGp1c3Q6IGV4YWN0Owp9CgpoMiB7Cglmb250LXNpemU6IDEuM2VtOwoJbGluZS1oZWlnaHQ6IDEuM2VtOwp9CgphIHsKCWNvbG9yOiBpbmhlcml0OwoJdGV4dC1kZWNvcmF0aW9uOiBub25lOwp9Cg==">
	</head>
	<body>
		<ul class="report combineChildItems">
"""

    for item in items:
        # Use id from json if available, else a generated one
        item_id = item.get('id', 'unknown')
        raw_type = item.get('type', 'document')
        display_type = TYPE_MAPPING.get(raw_type, raw_type.title())
        class_type = CLASS_MAPPING.get(raw_type, 'document')
        title = item.get('title', 'Untitled Document')
        
        html_content += f'\t\t\t<li id="item_{item_id}" class="item {class_type}">\n'
        html_content += f'\t\t\t<h2>{title}</h2>\n'
        html_content += '\t\t\t\t<table>\n\t\t\t\t\t<tbody>\n'
        
        # 1. Item Type
        html_content += f'\t\t\t\t\t<tr>\n\t\t\t\t\t\t<th>Item Type</th>\n\t\t\t\t\t\t<td>{display_type}</td>\n\t\t\t\t\t</tr>\n'
        
        # 2. Authors
        for author in item.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            author_name = f"{given} {family}".strip()
            if author_name:
                html_content += f'\t\t\t\t\t<tr>\n\t\t\t\t\t\t<th class="author">Author</th>\n\t\t\t\t\t\t<td>{author_name}</td>\n\t\t\t\t\t</tr>\n'
                
        # 3. Abstract
        if 'abstract' in item and item['abstract']:
            html_content += f'\t\t\t\t\t<tr>\n\t\t\t\t\t<th>Abstract</th>\n\t\t\t\t\t\t<td>{item["abstract"]}</td>\n\t\t\t\t\t</tr>\n'

        # 4. Date (issued)
        if 'issued' in item:
            date_str = format_date(item['issued'])
            if date_str:
                html_content += f'\t\t\t\t\t<tr>\n\t\t\t\t\t<th>Date</th>\n\t\t\t\t\t\t<td>{date_str}</td>\n\t\t\t\t\t</tr>\n'
                
        # 5. Rest of the fields
        skip_keys = {'id', 'type', 'title', 'author', 'abstract', 'issued'}
        for key, val in item.items():
            if key in skip_keys: continue
            
            display_key = FIELD_MAPPING.get(key, key.replace('-', ' ').title())
            
            if key == 'accessed':
                val = format_date(val)
            elif key == 'URL':
                val = f'<a href="{val}">{val}</a>'
            elif key == 'DOI':
                val = f'<a href="http://doi.org/{val}">{val}</a>'
                
            html_content += f'\t\t\t\t\t<tr>\n\t\t\t\t\t<th>{display_key}</th>\n\t\t\t\t\t\t<td>{val}</td>\n\t\t\t\t\t</tr>\n'
            
        html_content += '\t\t\t\t</tbody></table>\n'
        html_content += '\t\t\t</li>\n\n'

    html_content += """\t\t</ul>\n\t</body>\n</html>\n"""

    output_filepath = os.path.abspath(output_filename)
    
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\nSuccess! Found {len(items)} papers.")
    print(f"Report generated: {output_filename}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert Zotero JSON export to HTML report")
    parser.add_argument("--json", default="bibliography.json", help="Path to input JSON file")
    parser.add_argument("--html", default="bibliography.html", help="Path to output HTML file")
    args = parser.parse_args()
    generate_html(args.json, args.html)
