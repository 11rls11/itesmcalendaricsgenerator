﻿import os
import re
from datetime import datetime, timedelta

import fitz  # PyMuPDF para leer PDFs
import pytz
from icalendar import Calendar, Event, vText


def parse_pdf(file_path):
    """Analiza el PDF y extrae los datos del horario."""
    pdf_document = fitz.open(file_path)
    text = ""

    # Leer todo el texto del PDF
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        page_text = page.get_text("text")
        text += page_text

    pdf_document.close()

    # Procesar el texto completo
    lines = text.split('\n')
    schedule_data = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detectar el inicio de una Unidad de Formación (UF's)
        if line.lower().startswith('unidad de formación:'):
            # Inicializar variables
            subject_code = line[len('Unidad de formación:'):].strip()
            i += 1

            # Obtener UF's
            while i < len(lines) and lines[i].strip() == '':
                i += 1
            subject = lines[i].strip() if i < len(lines) else ''
            i += 1

            # Obtener profesores
            professor_lines = []
            while (
                i < len(lines) and not re.match(
                    r'^(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)',
                    lines[i].strip(),
                    re.IGNORECASE
                )
            ):
                professor_lines.append(lines[i].strip())
                i += 1
            professor = ' '.join(professor_lines).strip()

            # Obtener días y horas
            days_times_line = ''
            while i < len(lines):
                line = lines[i].strip()
                if re.match(
                    r'^(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)',
                    line,
                    re.IGNORECASE
                ):
                    days_times_line = line
                    i += 1
                    break
                else:
                    i += 1

            # Extraer días y horas
            days_pattern = r'(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)'
            days = re.findall(days_pattern, days_times_line, re.IGNORECASE)
            times_pattern = r'(\d{1,2}:\d{2})'
            times = re.findall(times_pattern, days_times_line)
            if len(times) >= 2:
                start_time = times[0]
                end_time = times[1]
            else:
                start_time = end_time = ''

            # Obtener fechas de inicio y fin
            dates_line = ''
            while i < len(lines):
                line = lines[i].strip()
                if re.match(
                    r'^\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}\.\d{2}\.\d{4}',
                    line
                ):
                    dates_line = line
                    i += 1
                    break
                else:
                    i += 1

            start_date = end_date = None
            if dates_line:
                start_date_str, end_date_str = dates_line.split(' - ')
                start_date = datetime.strptime(
                    start_date_str.strip(),
                    '%d.%m.%Y'
                )
                end_date = datetime.strptime(
                    end_date_str.strip(),
                    '%d.%m.%Y'
                )
            else:
                print(
                    f"Fechas no reconocidas para la clase '{subject}'. "
                    f"Línea de fecha: '{dates_line}'"
                )
                continue  # Saltar esta clase si no se pueden obtener las fechas

            # Obtener ubicación (puede tener varias líneas)
            location_lines = []
            while (
                i < len(lines)
                and not lines[i].strip().lower().startswith('sub-período')
                and lines[i].strip() != ''
            ):
                location_lines.append(lines[i].strip())
                i += 1
            location = (
                ' '.join(location_lines).strip() if location_lines else 'Sin sala'
            )

            # Obtener sub-período y CRN
            subperiodo = ''
            crn = ''
            if i < len(lines) and 'Sub-período' in lines[i]:
                match = re.search(
                    r'Sub-período\s*(.*?)\s*\|\s*CRN\s*(\S+)',
                    lines[i]
                )
                if match:
                    subperiodo = match.group(1).strip()
                    crn = match.group(2).strip()
                i += 1

            # Obtener formato (Presencial/Remoto)
            formato = ''
            if (
                i < len(lines)
                and ('Presencial' in lines[i] or 'Remoto' in lines[i])
            ):
                formato = lines[i].strip()
                i += 1

            # Determinar si es una clase especial (Semana TEC o símilar)
            is_special_class = False
            special_keywords = [
                'ST -', '18 -', 'Semana 18', 'Semana Tec',
                'Evaluación Etapa Inicial'
            ]
            for keyword in special_keywords:
                if keyword.lower() in subject.lower():
                    is_special_class = True
                    break

            # Otras condición para identificar clases especiales
            # Por ejemplo, clases que duran una semana o menos
            class_duration = (end_date - start_date).days + 1
            if class_duration <= 7:
                is_special_class = True

            # Imprimir datos de la clase para depuración
            print("--- Clase detectada ---")
            print(f"Código de la materia: {subject_code}")
            print(f"Materia: {subject}")
            print(f"Profesor(es): {professor}")
            print(f"Sub-período: {subperiodo}")
            print(f"CRN: {crn}")
            print(f"Días: {days}")
            print(f"Horario: {start_time} - {end_time}")
            print(f"Fechas: {start_date} - {end_date}")
            print(f"Formato: {formato}")
            print(f"Ubicación: {location}")
            print(f"Clase especial: {'Sí' if is_special_class else 'No'}")
            print("---------------------------\n")

            # Agregar clase al horario
            schedule_data.append({
                'subject_code': subject_code,
                'subject': subject,
                'professor': professor,
                'subperiodo': subperiodo,
                'crn': crn,
                'days': days,
                'start_time': start_time,
                'end_time': end_time,
                'start_date': start_date,
                'end_date': end_date,
                'format': formato,
                'location': location,
                'is_special_class': is_special_class
            })
        else:
            i += 1

    return schedule_data


def generate_exclude_dates(semester_start_date, weeks):
    """Genera fechas a excluir para las semanas indicadas (especiales)."""
    exclude_dates = []
    for week in weeks:
        week_start = semester_start_date + timedelta(weeks=week)
        week_dates = [week_start + timedelta(days=n) for n in range(7)]
        exclude_dates.extend(week_dates)
    return [d.date() for d in exclude_dates]


def create_ics_files(schedule_data, current_date, semester_start_date):
    """Crea archivos ICS a partir de los datos del horario."""
    # Crear la carpeta en Descargas
    output_dir = os.path.expanduser("~/Downloads/Horarios")
    os.makedirs(output_dir, exist_ok=True)

    day_mapping = {
        "Lun": "MO",
        "Mar": "TU",
        "Mié": "WE",
        "Jue": "TH",
        "Vie": "FR",
        "Sáb": "SA",
        "Dom": "SU"
    }

    # Definir la zona horaria
    tz = pytz.timezone('America/Mexico_City')

    # Semanas a excluir (semana 6, 12, 18)
    weeks_to_exclude = [5, 11, 17]
    exclude_dates = generate_exclude_dates(semester_start_date, weeks_to_exclude)

    for item in schedule_data:
        # Validaciones previas
        if item["start_date"] is None or item["end_date"] is None:
            print(f"Fechas inválidas para la clase '{item['subject']}'. Omitiendo...")
            continue

        if item["end_date"] < current_date:
            print(f"Clase '{item['subject']}' finalizada. Omitiendo...")
            continue

        if not item["start_time"] or not item["end_time"]:
            print(f"Horario no definido correctamente para la clase '{item['subject']}'. Omitiendo...")
            continue

        if not item["days"]:
            print(f"Días no definidos correctamente para la clase '{item['subject']}'. Omitiendo...")
            continue

        cal = Calendar()
        cal.add('prodid', '-//Mi Horario//mx')
        cal.add('version', '2.0')

        # Establecer la hora de inicio y fin del evento
        try:
            start_time_obj = datetime.strptime(
                item["start_time"], "%H:%M"
            ).time()
            end_time_obj = datetime.strptime(
                item["end_time"], "%H:%M"
            ).time()
        except ValueError:
            print(f"Formato de hora incorrecto en la clase '{item['subject']}'. Omitiendo...")
            continue

        # Obtener la fecha de la primera ocurrencia
        first_day_date = None
        for day in item["days"]:
            day_name = day.capitalize()
            day_index = (
                list(day_mapping.keys()).index(day_name)
                - item["start_date"].weekday()
            ) % 7
            potential_date = item["start_date"] + timedelta(days=day_index)
            if potential_date >= current_date:
                first_day_date = potential_date
                break
        if not first_day_date:
            first_day_date = item["start_date"]

        event = Event()
        event.add('summary', item["subject"])
        event.add(
            'dtstart',
            tz.localize(datetime.combine(first_day_date, start_time_obj))
        )
        event.add(
            'dtend',
            tz.localize(datetime.combine(first_day_date, end_time_obj))
        )

        # Configurar RRULE para recurrencia
        days_of_week = [
            day_mapping[day.capitalize()] for day in item["days"]
        ]
        until_date = tz.localize(
            datetime.combine(
                item["end_date"] + timedelta(days=1),
                datetime.min.time()
            )
        )

        rrule = {
            'freq': 'weekly',
            'byday': days_of_week,
            'until': until_date
        }

        event.add('rrule', rrule)

        # Añadir excepciones para semanas 6, 12 y 18 si no es clase especial
        if not item['is_special_class']:
            exdates = []
            for exclude_date in exclude_dates:
                for day in item["days"]:
                    day_name = day.capitalize()
                    if exclude_date.weekday() == list(
                        day_mapping.keys()
                    ).index(day_name):
                        exdate = tz.localize(
                            datetime.combine(exclude_date, start_time_obj)
                        )
                        exdates.append(exdate)

            if exdates:
                event.add('exdate', exdates)
                print(
                    f"Fechas de exclusión para la clase '{item['subject']}': "
                    f"{[dt.strftime('%Y-%m-%d') for dt in exdates]}"
                )
        else:
            print(
                f"La clase '{item['subject']}' es especial y se programará "
                f"en la semana 6, 12 u 18."
            )

        # Ubicación y descripción del evento
        description = (
            f"Profesor(es): {item['professor']}\n"
            f"Sub-período: {item['subperiodo']}\n"
            f"CRN: {item['crn']}\n"
            f"Formato: {item['format']}\n"
            f"Ubicación: {item['location']}\n"
            f"Días: {', '.join(item['days'])}\n"
            f"Horario: {item['start_time']} - {item['end_time']}\n"
            f"Periodo: {item['start_date'].strftime('%d/%m/%Y')} - "
            f"{item['end_date'].strftime('%d/%m/%Y')}"
        )
        event.add('location', vText(item["location"]))
        event.add('description', vText(description))

        # Añadir información de zona horaria al calendario
        cal.add('X-WR-TIMEZONE', tz.zone)
        cal.add_component(event)

        # Guardar archivo ICS para la clase
        safe_subject = item['subject'].replace(' ', '_')
        file_name = os.path.join(output_dir, f"{safe_subject}.ics")
        with open(file_name, 'wb') as f:
            f.write(cal.to_ical())
        print(f"Archivo ICS guardado en {file_name}")

    print("Proceso completado.")


def main():
    """Función principal para ejecutar el script."""
    # Preguntar al usuario el nombre del archivo
    file_name = input("Ingresa el nombre del archivo PDF (sin extensión): ")
    file_path = os.path.expanduser(f"~/Downloads/{file_name}.pdf")
    if not os.path.isfile(file_path):
        print(
            f"El archivo {file_path} no existe. "
            "Verifica el nombre y la ubicación."
        )
        return
    current_date_str = input("Ingresa la fecha actual (YYYY-MM-DD): ")
    try:
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    except ValueError:
        print("Formato de fecha incorrecto. Usa el formato YYYY-MM-DD.")
        return

    # Preguntar la fecha de inicio del semestre
    semester_start_str = input(
        "Ingresa la fecha de inicio del semestre (YYYY-MM-DD): "
    )
    try:
        semester_start_date = datetime.strptime(
            semester_start_str,
            "%Y-%m-%d"
        )
    except ValueError:
        print("Formato de fecha incorrecto. Usa el formato YYYY-MM-DD.")
        return

    schedule_data = parse_pdf(file_path)
    create_ics_files(schedule_data, current_date, semester_start_date)

# Correr el programa
if __name__ == "__main__":
    main()
