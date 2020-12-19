import urllib.request
import json
import time

# def fetch_record_info(record_url):
#     with urllib.request.urlopen(record_url) as result:
#
#
# records_url = 'https://esgf-node.llnl.gov/esg-search/search/?experiment_id=ssp126&variable_id=siflswdtop&offset=0&limit=9999&type=Dataset&replica=false&latest=true&project=CMIP6&format=application%2Fsolr%2Bjson'
#
# with urllib.request.urlopen(records_url) as result_search:
#     data = json.loads(result_search.read().decode())
#     file_urls_to_download = data['response']['docs']
#
#     for file_url_to_download in file_urls_to_download:
#         fetch_record_info(file_url_to_download)

def url_open_retry(url, retries = 0, retry_interval = 10):
    result = None
    for i in range(0, retries):
        try:
            result = urllib.request.urlopen(url)
        except:
            print('retrying')
            time.sleep(retry_interval)
            continue
        break
    return result

print(url_open_retry('https://httpstat.us/500/cors', retries= 3, retry_interval= 2))