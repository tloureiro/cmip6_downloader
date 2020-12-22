import urllib.request
import json
import random
import multiprocessing
import os
import sys
import argparse
from urllib.parse import urlencode
import time

number_of_processes = 50
files_to_download = multiprocessing.Manager().list()
failed_files = multiprocessing.Manager().list()
log_file = open('logs.txt', 'w')


def get_files_to_download(url_files_search):
    with urllib.request.urlopen(url_files_search) as result:
        data = json.loads(result.read().decode())
        print(len(data['response']['docs']))
        file_urls_to_download = data['response']['docs']

        for file_url_to_download in file_urls_to_download:

            for file_dataset_to_download in file_url_to_download['url']:

                if file_dataset_to_download.split('|')[2] == 'HTTPServer':
                    print(file_dataset_to_download)
                    files_to_download.append(file_dataset_to_download.split('|')[0])


def download_file(url_to_download, variable_name, index):

    print('\t Downloading file [' + str(index) + '/' + str(len(files_to_download)) +'] ' + url_to_download)

    for currentRun in range(0, 6):
        result_code = os.system('wget -nc -c --retry-connrefused --waitretry=10 --quiet -o /dev/null -P ' + variable_name + ' ' + url_to_download )
        if result_code == 0:
            break

    if result_code != 0:
        print('Failed to download ' + url_to_download)
        failed_files.append(url_to_download)


def get_params():
    parser = argparse.ArgumentParser(description='CMIP 6 Downloader. Version 2.0.0')

    if len(sys.argv) > 1:
        parser.add_argument('--mip_era', metavar='', help='MIP Era')
        parser.add_argument('--activity_id', metavar='', help='Activity')
        parser.add_argument('--model_cohort', metavar='', help='Model Cohort')
        parser.add_argument('--product', metavar='', help='Product')

        parser.add_argument('--source_id', metavar='', help='Source ID', )
        parser.add_argument('--institution_id', metavar='', help='Institution ID')
        parser.add_argument('--source_type', metavar='', help='Source Type')
        parser.add_argument('--nominal_resolution', metavar='', help='Nominal Resolution')

        parser.add_argument('--experiment_id', metavar='', help='Experiment ID')
        parser.add_argument('--sub_experiment_id', metavar='', help='Sub-Experiment')
        parser.add_argument('--variant_label', metavar='', help='Variant Label')
        parser.add_argument('--grid_label', metavar='', help='Grid Label')

        parser.add_argument('--table_id', metavar='', help='Table ID')
        parser.add_argument('--frequency', metavar='', help='Frequency')
        parser.add_argument('--realm', metavar='', help='Realm')
        parser.add_argument('--variable_id', metavar='', help='Variable')
        parser.add_argument('--cf_standard_name', metavar='', help='CF Standard Name')

        parser.add_argument('--data_node', metavar='', help='Data Node')

        args = parser.parse_args()
        search_params_dictionary = vars(args)

    else:  # interactive mode
        search_params_dictionary = {
            'variable_id': input("enter the variable name\n"),
            'frequency': input("enter the frequency\n"),
            'experiment_id': input("enter the experiment ID\n"),
            'source_id': input("enter the source ID\n"),
        }

    # clean keys that are empty
    search_params_dictionary = {k: v for k, v in search_params_dictionary.items() if v}

    config_params_dictionary = {
        'offset': 0,
        'limit': 9999,
        'type': 'Dataset',
        'replica': 'false',
        'latest': 'true',
        'project': 'CMIP6',
        'format': 'application/solr+json'
    }

    return config_params_dictionary, search_params_dictionary


def print_and_log(text):
    print(text)
    log_file.write(text)
    log_file.write('\n')


def url_open_retry(url, retries=0, retry_interval=10):
    result = None
    for i in range(0, retries):
        try:
            result = urllib.request.urlopen(url)
            break
        except:
            print_and_log('retrying ' + url)
            time.sleep(retry_interval)
            continue
        print_and_log('failed to fetch ' + url)
        break
    return result

# def get_url():

# url = 'https://esgf-node.llnl.gov/esg-search/search/?offset=0&limit=9999&type=Dataset&replica=false&latest=true&project=CMIP6&' + variable + frequency + experiment + '&facets=mip_era%2Cactivity_id%2Cmodel_cohort%2Cproduct%2Csource_id%2Cinstitution_id%2Csource_type%2Cnominal_resolution%2Cexperiment_id%2Csub_experiment_id%2Cvariant_label%2Cgrid_label%2Ctable_id%2Cfrequency%2Crealm%2Cvariable_id%2Ccf_standard_name%2Cdata_node&format=application%2Fsolr%2Bjson'

if __name__ == '__main__':

    pool_search = multiprocessing.Pool(number_of_processes)

    config_params_dictionary, search_params_dictionary = get_params()

    url_params_dictionary = search_params_dictionary.copy()
    url_params_dictionary.update(config_params_dictionary)

    records_search_url = 'https://esgf-node.llnl.gov/esg-search/search/?' + urlencode(url_params_dictionary)

    print_and_log('1- Searching for records: ' + records_search_url)
    records_content = url_open_retry(records_search_url, 3, 10)

    if records_content:
        records = json.loads(records_content.read().decode())
        print_and_log(records)
    else:
        print_and_log('There was a problem searching for the records')


    print_and_log('2- ' + str(len(records['response']['docs'])) + ' records found. Searching for files to download inside each record...')
#         for doc in data['response']['docs']:
#             url_files_search = 'https://esgf-node.llnl.gov/search_files/' + doc['id'] + '/' + doc['index_node'] + '/?limit=9999&rnd=' + str(random.randint(100000, 999999))
#
#             pool_search.apply_async(get_files_to_download, args=[url_files_search])
#
#         pool_search.close()
#         pool_search.join()
#
#
#
#         print('3- Writing list of files ' + variable_name + '_' + frequency_value + '_' + experiment_id + '_files_url_list.txt')
#         with open(variable_name + '_' + frequency_value + '_' + experiment_id + '_files_url_list.txt', 'w') as file:
#             for file_to_download in files_to_download:
#                 file.write(file_to_download + '\n')
#             file.close()
#
#         print('4- Downloading files...')
#         pool_download = multiprocessing.Pool(int(number_of_processes / 5))
#         index = 1
#         for file_to_download in files_to_download:
#             pool_download.apply_async(download_file, args=[file_to_download, variable_name + '_' + frequency_value + '_' + experiment_id, index])
#             index += 1
#         pool_download.close()
#         pool_download.join()
#
#         print('Done :)')
#
#         if len(failed_files) > 0:
#             print('The script was not able to download some files (you can try running the script again):')
#             for failed_file in failed_files:
#                 print(failed_file)
#
# #TODO retry
# #TODO printandlog function
#
# # what's new
# # pure command line or interactive mode
# # new folder structure
# # retries
# # better user feedback / file logging