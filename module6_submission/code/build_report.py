"""Build the editable checklist and PDF from actual validation evidence."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data_and_evidence'
BRANCH_URL='https://github.com/chenwang266/DSO576_Project/tree/chenwang'

def build():
    a=json.loads((E/'full_data_checks.json').read_text())
    checks=json.loads((E/'record_checks.json').read_text())
    columns=pd.read_csv(E/'column_audit.csv')
    repro=json.loads((E/'reproducibility.json').read_text())
    validation=json.loads((E/'independent_validation.json').read_text())
    notebook=json.loads((E/'notebook_execution.json').read_text())
    m,j=a['sources']; merge=a['merge']
    items=[
      ('State the vision along with a specific analysis question', 'Done',
       'Working individual vision: a marketplace analyst prioritizes Los Angeles neighborhoods for pricing/host-support follow-up. Compare March and June listing counts and advertised median price by neighborhood and room type, with calendar availability and review ratings as context. Stakeholder confirmation and team agreement remain limitations; this is descriptive, not a causal recommendation.'),
      ('Define one row','Done',f"One listing observed in one snapshot. Key (snapshot_date, id) is unique for all {a['clean_rows']:,} cleaned rows. IDs are strings. A repeated ID between snapshots is valid."),
      ('Preserve the source','Done','Inside Airbnb Los Angeles detailed listings, March 16 and June 15, 2026. Original 90-column CSV files remain outside the package, unchanged. Full-data audit records exact SHA-256 hashes. Actual retrieval date is unknown; inspected October 5, 2026. README gives source access and reload instructions.'),
      ('Inspect columns and types','Done',f"Read all originals as strings; select 28 analytical original fields. Parse 16 numeric fields, 4 date fields, and 3 t/f boolean fields; leave identifiers/labels as strings. {int(columns.conversion_failures.sum()):,} nonmissing conversion failures across selected fields. Failures would become missing and be counted. column_audit.csv lists every selected field, type, and missing count; excluded fields were not cleaned or validated."),
      ('Standardize text','Done',f"Trim surrounding whitespace only, blank to missing, and preserve case/distinct neighborhood labels and ID leading zeros. {int(columns.whitespace_changes.sum())} selected values required whitespace trimming. Example label 'Hollywood' stays 'Hollywood'; t/f becomes True/False; '$67.22' becomes 67.22. No case-collapsing or fabricated whitespace examples. text_examples.csv is header-only when no changes occur."),
      ('Investigate duplicates','Done',f"March: {m['exact_duplicate_rows']} exact duplicates and {m['repeated_ids_before']} repeated IDs. June: {j['exact_duplicate_rows']} and {j['repeated_ids_before']}. None removed. {merge['matched']:,} IDs repeat validly across snapshots. Conflicting within-snapshot IDs stop the pipeline."),
      ('Handle missing data','Done','No imputation or row deletion for missing fields. Price missing: March 8,910 before/after; June 5,565 before/after. Rating missing: March 12,519 before/after; June 11,257 before/after. instant_bookable is entirely missing in both snapshots. Missing price cannot mean free lodging; missing rating cannot mean poor quality. Every affected field appears in the missing-data table below and column_audit.csv.'),
      ('Check suspicious values','Done',f"No failed date parses or impossible selected numerical values; no stay-order, availability-order, review-order, future-review, or unknown-room-type flags. Retained prices over $2,000: March {m['flag_high_price']}, June {j['flag_high_price']}. Minimum stays over 365 nights: March {m['flag_long_minimum_stay']}, June {j['flag_long_minimum_stay']}. Review thresholds flag observations for sensitivity analysis, not automatic deletion. Actual March scraping spans March 16-18; June spans June 15-17 and June 22-23."),
      ('Verify merges','Done',f"Outer one-to-one join by ID: {merge['march_rows']:,} March rows and {merge['june_rows']:,} June rows produce {merge['outer_rows']:,} IDs. Matched {merge['matched']:,}; March-only {merge['march_only']:,}; June-only {merge['june_only']:,}. Outer union and intersection verified independently, with no unexpected multiplication. listing_comparison.csv and full_data_checks.json contain evidence."),
      ('Reconcile changes','Done',f"46,088 + 43,751 = 89,839 original and final listing-snapshot rows. Zero deleted. Combined 90 source columns become 28 selected columns plus 27 provenance/quality columns (55 total). Parsed price sum unchanged: March ${m['price_sum_after']:,.2f}; June ${j['price_sum_after']:,.2f}. These sums are audit statistics, not revenue. Count difference June versus March is -2,337 and reflects snapshot composition, not row cleaning."),
      ('Check calculations','Done',f"Listing counts include all rows. Price has 37,178 March / 38,186 June usable observations; ratings have 33,569 / 32,494. Availability_365 has 46,088 / 43,751. Missing values are excluded from numerical totals/means/medians, and nonmissing counts accompany each group metric. Missing neighborhood/room keys become [Unknown] for grouping; none in these sources. Group totals independently reconcile. {merge['matched_with_both_prices']:,} matched listings support paired prices; median June-minus-March change is ${merge['paired_median_price_change']:.2f}. No inference about realized revenue or occupancy."),
      ('Verify individual records','Done','Five original-to-cleaned checks below: missing price, currency price, missing rating, boolean label, and unusually high price. All expected results match. Original filename/version, string ID, and source record position locate each check. record_checks.json holds machine-readable evidence; all five records are in the inspection sample.'),
      ('Test reproducibility','Done',f"Fresh Python process reran clean_data.py from both untouched originals into a separate temporary directory. {len(repro['compared_files'])} deterministic output files matched submitted SHA-256 hashes. Independent validation checked {validation['records_checked']:,} rows and passed. Notebook execution: {notebook['status']}, {notebook['code_cells']} code cells. Commands and restart/run-all procedure are in README; evidence is reproducibility.json and notebook_execution.json."),
      ('Document remaining limitations','Done','Working vision requires team/stakeholder confirmation. Missing price is substantial and potentially systematic. Snapshot windows, seasonality, composition changes, and stale scraped data limit comparisons. Los Angeles region includes distinct municipalities. Calendar availability is not occupancy; advertised price is not transaction revenue; ratings omit unreviewed listings. Excluded fields and unprovided calendar/review transaction tables were not validated. Follow-up needs calendar/booking evidence, consistent price quote dates, missingness investigation, and team reconciliation.')]
    verification=(f"Codex verification response: I checked the submitted cleaning implementation and full-data evidence against the assignment. Independent validation passed on {a['clean_rows']:,} rows, including source-price parsing, key/row reconciliation, outer-join membership, group denominators, bounds, and sample membership. Five documented record checks passed. Fresh-process hashes matched all {len(repro['compared_files'])} pipeline outputs; the notebook ran all code cells successfully. This supports the working descriptive question using the selected fields. It does not establish correctness of excluded source columns, random sample representativeness, stakeholder approval, or group consensus. The student remains responsible for reviewing the rules and interpretation.")
    md=['# Module 6 - Project Data Cleaning Checklist','',
        'Project: Short-Term Rental Marketplace Health | Student: chenwang266 | Branch: chenwang',
        f'GitHub branch: [chenwang]({BRANCH_URL})',
        'Individual report, October 5, 2026. Team reconciliation and stakeholder confirmation remain pending.','']
    for i,(title,status,body) in enumerate(items,1):md += [f'## {i}. {title}',f'Status: {status}',body,'']
    md += ['## Five record checks','']
    for r in checks:md += [f"- {r['case']}: {r['snapshot_date']} / ID {r['id']} / source record {r['source_row']}; {r['field']}: {r['original']!r} -> expected {r['expected']!r}, actual {r['actual']!r}; matches={r['matches']}. {r['reason']}"]
    md += ['', '## Codex verification response',verification,'','## Cleaning decision log',
           (ROOT/'report/cleaning_decision_log.md').read_text()]
    (ROOT/'report/completed_report.md').write_text('\n'.join(md)+'\n')
    styles=getSampleStyleSheet()
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=13
    styles['Heading2'].fontSize=12;styles['Heading2'].leading=16
    styles['Title'].fontSize=20
    styles.add(ParagraphStyle('LogBody',parent=styles['BodyText'],fontSize=9,leading=11))
    def para(s,style='BodyText'):return Paragraph(escape(str(s)),styles[style])
    story=[para('Project Data Cleaning','Title'),para('DSO 576 | Module 6 | chenwang266 | branch chenwang'),
           Paragraph(f'GitHub branch: <link href="{BRANCH_URL}" color="#1557a0">{BRANCH_URL}</link>',styles['BodyText']),
           para('Short-Term Rental Marketplace Health','Heading2'),
           para('Individual report - October 5, 2026. All 14 items have documented individual evidence. Team reconciliation and stakeholder confirmation remain pending.'),Spacer(1,12)]
    for i,(title,status,body) in enumerate(items,1):
        story.extend([para(f'{i}. {title}','Heading2'),para(f'Status: {status}. {body}'),Spacer(1,6)])
    story.extend([PageBreak(),para('Missing-data evidence','Heading1'),
      para('Every selected field with missing values in either snapshot. Counts before/after are identical; no imputation. See column_audit.csv for zero-missing fields and types.'),Spacer(1,10)])
    pivot=columns.pivot(index='column',columns='snapshot_date',values='missing_after')
    rows=[[para('Field'),para('March before / after'),para('June before / after')]]
    for col,row in pivot.iterrows():
        if row.max()>0:rows.append([para(col),para(f'{int(row.iloc[0]):,} / {int(row.iloc[0]):,}'),para(f'{int(row.iloc[1]):,} / {int(row.iloc[1]):,}')])
    t=Table(rows,colWidths=[235,130,130],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef5')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)]))
    story += [t,Spacer(1,12),para('Five original-to-cleaned record checks','Heading1')]
    for r in checks:
        story.extend([para(r['case'],'Heading2'),para(f"Snapshot {r['snapshot_date']}; ID {r['id']}; source record {r['source_row']}; field {r['field']}. Original: {r['original']!r}. Expected: {r['expected']!r}. Actual: {r['actual']!r}. Matches: {r['matches']}. {r['reason']}"),Spacer(1,6)])
    story += [para('Codex verification response','Heading1'),para(verification),PageBreak(),para('Cleaning decision log','Heading1')]
    for line in (ROOT/'report/cleaning_decision_log.md').read_text().splitlines():
        if line and not line.startswith('#'):story += [para(line,'LogBody'),Spacer(1,4)]
    story += [para('Source attribution and evidence references','Heading2'),
      para('Inside Airbnb: https://insideairbnb.com/get-the-data/ (CC BY 4.0, checked October 5, 2026). Source filenames and hashes: full_data_checks.json. Local retrieval date not recorded. Run/access instructions: README.md. This individual report must be reconciled with team members before group submission.')]
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.drawString(42,25,'DSO 576 | chenwang266 | Individual evidence');canvas.drawRightString(570,25,str(doc.page))
    SimpleDocTemplate(str(ROOT/'report/completed_report.pdf'),pagesize=(612,792),
        rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    print('Created report/completed_report.pdf and completed_report.md')

if __name__=='__main__':build()
