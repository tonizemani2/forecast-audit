"""Extract one well pair's monthly record from the Nevada Division of Minerals workbook.

Source: "Geothermal Production And Well Data" (XLSX, inline strings), sheets
GeothermalProduction and GeothermalInjection. Operator-reported regulator data;
values are copied verbatim, never smoothed or filled.
"""
import csv
import datetime
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKBOOK = HERE / 'data/source/ndom-geothermal-production-and-well-data-2026-09-29.xlsx'
OUTPUT = HERE / 'data/project-red-ndom-monthly.csv'
PRODUCTION_SHEET = 'xl/worksheets/sheet2.xml'
INJECTION_SHEET = 'xl/worksheets/sheet3.xml'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
FIELDS = ['month_end', 'production_gal', 'production_temp_f', 'injection_gal', 'injection_temp_f']


def rows(workbook, sheet):
    with zipfile.ZipFile(workbook) as archive, archive.open(sheet) as handle:
        for _, element in ET.iterparse(handle):
            if element.tag != NS + 'row':
                continue
            row = {}
            for cell in element:
                column = re.match(r'[A-Z]+', cell.attrib['r']).group(0)
                if cell.attrib.get('t') == 'inlineStr':
                    row[column] = ''.join(node.text or '' for node in cell.iter(NS + 't'))
                else:
                    value = cell.find(NS + 'v')
                    row[column] = None if value is None else value.text
            yield row
            element.clear()


def excel_date(serial):
    return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(serial)))).isoformat()


def well_pair(workbook=WORKBOOK, production_permit='1506', injection_permit='1505'):
    """Monthly rows joined on month end; a month missing from either sheet is an error."""
    header = next(rows(workbook, PRODUCTION_SHEET))
    if [header.get(c) for c in 'ABCDEF'] != ['PermitNumber', 'WellName', 'Field', 'Date', 'ProductionGal', 'TempF']:
        raise ValueError('unexpected production sheet layout')
    header = next(rows(workbook, INJECTION_SHEET))
    if [header.get(c) for c in 'ABCDEFG'] != ['PermitNumber', 'WellName', 'Field', 'Date', 'InjGalPerDay', 'InjGalPerMo', 'TempF']:
        raise ValueError('unexpected injection sheet layout')
    production = {excel_date(r['D']): r for r in rows(workbook, PRODUCTION_SHEET) if r.get('A') == production_permit}
    injection = {excel_date(r['D']): r for r in rows(workbook, INJECTION_SHEET) if r.get('A') == injection_permit}
    if not production or set(production) != set(injection):
        raise ValueError('production and injection months do not match')
    return [dict(month_end=month,
                 production_gal=float(production[month]['E']),
                 production_temp_f=float(production[month]['F']),
                 injection_gal=float(injection[month]['F']),
                 injection_temp_f=float(injection[month]['G']))
            for month in sorted(production)]


def write_csv(records, path=OUTPUT):
    with open(path, 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({k: (record[k] if k == 'month_end' else repr(record[k])) for k in FIELDS})


def read_csv(path=OUTPUT):
    with open(path, newline='') as handle:
        return [{k: (v if k == 'month_end' else float(v)) for k, v in row.items()} for row in csv.DictReader(handle)]


if __name__ == '__main__':
    write_csv(well_pair())
    print(f'wrote {OUTPUT.relative_to(HERE)}', file=sys.stderr)
