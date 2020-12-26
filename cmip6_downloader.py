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
    with url_open_retry(url_files_search, 5, 10) as result:
        data = json.loads(result.read().decode())
        file_urls_to_download = data['response']['docs']

        for file_url_to_download in file_urls_to_download:

            for file_dataset_to_download in file_url_to_download['url']:

                if file_dataset_to_download.split('|')[2] == 'HTTPServer':
                    files_to_download.append(file_dataset_to_download.split('|')[0])


def download_file(url_to_download, folder_path, index):

    print_and_log('\t Downloading file [' + str(index) + '/' + str(len(files_to_download)) +'] ' + url_to_download)

    for currentRun in range(0, int(number_of_processes / 10)):
        result_code = os.system('wget -nc -c --retry-connrefused --waitretry=10 --quiet -o /dev/null -P ' + folder_path + ' ' + url_to_download)
        if result_code == 0:
            break
        else:
            print_and_log('There was a problem downloading ' + url_to_download + '. Retrying...')

    if result_code != 0:
        print_and_log('Failed to download ' + url_to_download)
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
    log_file.write(str(text))
    log_file.write('\n')


def url_open_retry(url, retries=0, retry_interval=10):
    result = None
    for i in range(0, retries):
        try:
            result = urllib.request.urlopen(url)
            break
        except:

            if i == (retries - 1):
                print_and_log('failed to fetch ' + url)
            else:
                print_and_log('retrying ' + str((i + 1)) + '/' + str((retries - 1)) + ' ' + url)
                time.sleep(retry_interval)

            continue
        break
    return result


def get_folder_path(search_params_dictionary):
    search_params_to_abbreviations = {
        'mip_era': 'me',
        'activity_id': 'a',
        'model_cohort': 'mc',
        'product': 'p',
        'source_id': 's',
        'institution_id': 'i',
        'source_type': 'st',
        'nominal_resolution': 'nr',
        'experiment_id': 'e',
        'sub_experiment_id': 'se',
        'variant_label': 'vl',
        'grid_label': 'g',
        'table_id': 't',
        'frequency': 'f',
        'realm': 'r',
        'variable_id': 'v',
        'cf_standard_name': 'cf',
        'data_node': 'd'
    }

    folder_name_parts = []
    for key, value in search_params_dictionary.items():
        folder_name_parts.append(search_params_to_abbreviations[key] + '_' + value)

    folder_name = '_'.join(folder_name_parts)
    return 'data' + os.path.sep + folder_name, folder_name


def get_number_of_previously_downloaded_files(folder_path):
    if os.path.exists(folder_path):
        return len([name for name in os.listdir(folder_path) if os.path.isfile(folder_path + os.path.sep + name)])
    else:
        return 0


if __name__ == '__main__':

    config_params_dictionary, search_params_dictionary = get_params()

    if search_params_dictionary:

        url_params_dictionary = search_params_dictionary.copy()
        url_params_dictionary.update(config_params_dictionary)

        folder_path, folder_name = get_folder_path(search_params_dictionary)

        records_search_url = 'https://esgf-node.llnl.gov/esg-search/search/?' + urlencode(url_params_dictionary)

        print_and_log('1- Searching for records: ' + records_search_url)
        records_content = url_open_retry(records_search_url, 3, 10)

        if records_content:
            records = json.loads(records_content.read().decode())
            total_number_of_records = len(records['response']['docs'])
            if total_number_of_records > 0:
                total_number_of_files = 0
                for record in records['response']['docs']:
                    total_number_of_files += int(record['number_of_files'])

                if total_number_of_files > 0:
                    number_of_previously_downloaded_files = get_number_of_previously_downloaded_files(folder_path)
                    print_and_log('2- ' + str(total_number_of_files) + ' files found in ' + str(total_number_of_records) + ' records. ' + str(number_of_previously_downloaded_files) + ' of these files were already downloaded.')

                    if (number_of_previously_downloaded_files == 0) or (0 < number_of_previously_downloaded_files < total_number_of_files):

                        if number_of_previously_downloaded_files == 0:
                            print_and_log('3- No previously downloaded files found')
                        elif 0 < number_of_previously_downloaded_files < total_number_of_files:
                            print_and_log('3- ' + str(number_of_previously_downloaded_files) + '/' + str(total_number_of_files) + ' files were previously downloaded. Attempting to download missing ones...')

                        pool_search = multiprocessing.Pool(number_of_processes)

                        print_and_log('4- Fetching list of files to be downloaded...')
                        for record in records['response']['docs']:
                            url_files_search = 'https://esgf-node.llnl.gov/search_files/' + record['id'] + '/' + record['index_node'] + '/?limit=9999&rnd=' + str(random.randint(100000, 999999))
                            pool_search.apply_async(get_files_to_download, args=[url_files_search])

                        pool_search.close()
                        pool_search.join()

                        print_and_log('5- ' + str(len(files_to_download)) + '/' + str(total_number_of_files) + ' files added to download list')

                        if len(files_to_download) < total_number_of_files:
                            print_and_log('Not all files were found and added to the download list. Try running the downloader again with the same params and hopefully the servers will behave next time')

                        print_and_log('6- Writing list of files ' + folder_name + '_files_url_list.txt')
                        with open(folder_name + '_files_url_list.txt', 'w') as file:
                            for file_to_download in files_to_download:
                                file.write(file_to_download + '\n')
                            file.close()

                            print_and_log('7- Downloading files...FINALLY')
                            pool_download = multiprocessing.Pool(int(number_of_processes / 5))
                            index = 1
                            for file_to_download in files_to_download:
                                pool_download.apply_async(download_file, args=[file_to_download, folder_path, index])
                                index += 1
                            pool_download.close()
                            pool_download.join()

                            number_of_previously_downloaded_files = get_number_of_previously_downloaded_files(folder_path)
                            if number_of_previously_downloaded_files == total_number_of_files:
                                print_and_log('It looks like all ' + str(total_number_of_files) + ' files were downloaded successfully')
                            else:
                                print_and_log('Not all files (' + str(number_of_previously_downloaded_files) + '/' + str(total_number_of_files) + ') were downloaded. You can try running the script again')
                                if len(failed_files) > 0:
                                    print_and_log('These files were not downloaded:')
                                    for failed_file in failed_files:
                                        print_and_log(failed_file)

                            print_and_log('Done. Check the ' + folder_path + ' folder :)')

                    else:
                        print_and_log('All files were previously downloaded. Check ' + folder_path + ' folder')
                else:
                    print_and_log('No files found inside the records')
            else:
                print_and_log('No records found :(')
        else:
            print_and_log('There was a problem searching for the records')
    else:
        print_and_log('No search params provided :(')
