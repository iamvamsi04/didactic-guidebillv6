"""Validate small, declarative charts made only from executed query rows."""
import math


def numeric(value):
    if value is None or isinstance(value, bool):
        raise ValueError('Chart measures must be finite numbers, without null values.')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Chart measures must be numeric.') from None
    if not math.isfinite(number):
        raise ValueError('Chart measures must be finite.')
    return number


def prepare_chart(columns, rows, spec, truncated=False):
    if not isinstance(spec, dict) or set(spec) - {'type','title','x','y'}:
        raise ValueError('Chart accepts only type, title, x and y fields.')
    kind, x, ys = spec.get('type'), spec.get('x'), spec.get('y')
    if kind not in ('bar','line','area','pie','scatter'):
        raise ValueError('Chart type must be bar, line, area, pie or scatter.')
    if len(columns) != len(set(columns)):
        raise ValueError('Give every selected SQL column a unique alias.')
    if not isinstance(x, str) or x not in columns or not isinstance(ys, list) or not 1 <= len(ys) <= 4:
        raise ValueError('Chart x must name a returned column; y must list 1-4 returned numeric columns.')
    if any(not isinstance(y,str) or y not in columns or y == x for y in ys) or len(set(ys)) != len(ys):
        raise ValueError('Chart y columns must exist, be distinct, and differ from x.')
    if kind in ('pie','scatter') and len(ys) != 1:
        raise ValueError('Pie and scatter charts require one y column.')
    if truncated:
        raise ValueError('Query results were truncated. Aggregate or narrow the query before charting.')
    if not rows or len(rows) > 200:
        raise ValueError('Charts require 1-200 rows. Aggregate or narrow the query.')
    if kind == 'pie' and len(rows) > 12:
        raise ValueError('Pie charts support at most 12 categories; group smaller categories or use bars.')
    title = spec.get('title') or 'Query results'
    if not isinstance(title,str) or len(title) > 160:
        raise ValueError('Chart title must be text of at most 160 characters.')
    currencies = {r[columns.index('currency')] for r in rows} if 'currency' in columns else set()
    if currencies and (len(currencies) != 1 or None in currencies or '' in currencies):
        raise ValueError('Chart one currency at a time. Filter currency and return it as currency.')
    records, seen = [], set()
    for row in rows:
        label = row[columns.index(x)]
        if label is None:
            raise ValueError('Chart x values cannot be null.')
        label = numeric(label) if kind == 'scatter' else str(label)
        if kind != 'scatter' and label in seen:
            raise ValueError('Group duplicate x values in SQL before charting.')
        seen.add(label)
        values = {y:numeric(row[columns.index(y)]) for y in ys}
        if kind == 'pie' and any(v < 0 for v in values.values()):
            raise ValueError('Pie charts cannot contain negative values.')
        records.append({x:label, **values})
    if kind == 'pie' and sum(r[ys[0]] for r in records) <= 0:
        raise ValueError('A pie chart needs a positive total.')
    return {'type':kind,'title':title,'x':x,'y':ys,'currency':next(iter(currencies),None),'data':records}


def chart_from_result(result):
    metadata = result['chart']
    return prepare_chart(result['columns'], result['rows'],
                         {k:metadata[k] for k in ('type','title','x','y')}, result.get('truncated',False))
