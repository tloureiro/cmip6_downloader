import re
from datetime import datetime


def parse_datetime(datetime_str):
    formats = ['%Y%m%d%H%M%S', '%Y%m%d%H%M', '%Y%m%d%H', '%Y%m%d', '%Y%m', '%Y']
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid date format")


def filter_filenames_by_date_interval(filenames, start_datetime, end_datetime):
    def is_within_interval(file_start, file_end, start, end):
        return start <= file_start <= end and start <= file_end <= end


    def extract_dates(filename):
        date_pattern = r'(\d{6,14})-(\d{6,14})\.nc$'
        match = re.search(date_pattern, filename)
        if match:
            return match.groups()
        else:
            return None, None


    filtered_filenames = []
    start = parse_datetime(start_datetime)
    end = parse_datetime(end_datetime)


    for filename in filenames:
        file_start_str, file_end_str = extract_dates(filename)
        if file_start_str and file_end_str:
            file_start = parse_datetime(file_start_str)
            file_end = parse_datetime(file_end_str)
            if is_within_interval(file_start, file_end, start, end):
                filtered_filenames.append(filename)


    return filtered_filenames


# Example usage
filenames = [
    # Add your filenames here
]
start_datetime = "2003"
end_datetime = "2005"


filtered_files = filter_filenames_by_date_interval(filenames, start_datetime, end_datetime)
print("Filtered Filenames:", filtered_files)