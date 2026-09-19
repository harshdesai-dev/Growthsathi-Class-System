import csv

from django.http import HttpResponse


def csv_report(name, columns, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    response["Cache-Control"] = "private, no-store"
    writer = csv.writer(response)
    writer.writerow(columns)
    for row in rows:
        safe = []
        for value in row:
            value = str(value if value is not None else "")
            if value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe.append(value)
        writer.writerow(safe)
    return response
