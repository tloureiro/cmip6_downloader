import urllib.request
import json
import random
import multiprocessing
import os

# todo: check if wget completed,  

number_of_processes = 50
manager = multiprocessing.Manager()
files_to_download = manager.list()

def get_files_to_download(url_files_search):
    with urllib.request.urlopen(url_files_search) as result:
        data = json.loads(result.read().decode())
        file_urls_to_download = data['response']['docs'][0]['url']
        for file_url_to_download in file_urls_to_download:
            if file_url_to_download.split('|')[2] == 'HTTPServer':
                files_to_download.append(file_url_to_download.split('|')[0])

def download_file(url_to_download, variable_name):
    os.system('wget -nc -c -P ' + variable_name + ' ' + url_to_download)



if __name__ == '__main__':

    variable_name = input("enter the variable name\n")
    frequency = input("enter the frequency\n")

    url = 'https://esgf-node.llnl.gov/esg-search/search/?offset=0&limit=10000&type=Dataset&replica=false&latest=true&project=CMIP6&variable_id=' + variable_name + '&frequency=' + frequency + '&facets=mip_era%2Cactivity_id%2Cmodel_cohort%2Cproduct%2Csource_id%2Cinstitution_id%2Csource_type%2Cnominal_resolution%2Cexperiment_id%2Csub_experiment_id%2Cvariant_label%2Cgrid_label%2Ctable_id%2Cfrequency%2Crealm%2Cvariable_id%2Ccf_standard_name%2Cdata_node&format=application%2Fsolr%2Bjson'

    pool_search = multiprocessing.Pool(number_of_processes)

    print('1- Searching for records that contains variable and frequency...')
    with urllib.request.urlopen(url) as result_search:
        data = json.loads(result_search.read().decode())
        print('2- ' + str(len(data['response']['docs'])) + ' records found. Searching for files to download inside each record...')
        for doc in data['response']['docs']:
            url_files_search = 'https://esgf-node.llnl.gov/search_files/' + doc['id'] + '/' + doc['index_node'] + '/?limit=10&rnd=' + str(random.randint(100000, 999999))
            pool_search.apply_async(get_files_to_download, args=[url_files_search])

        pool_search.close()
        pool_search.join()

        print('3- Writing list of files ' + variable_name + '_' + frequency + '_files_url_list.txt')
        with open(variable_name + '_' + frequency + '_files_url_list.txt', 'w') as file:
            for file_to_download in files_to_download:
                file.write(file_to_download + '\n')
            file.close()
        print(files_to_download)

        pool_download = multiprocessing.Pool(number_of_processes / 5)
        for file_to_download in files_to_download:
            pool_download.apply_async(download_file, args=[file_to_download, variable_name + '_' + frequency])
        pool_download.close()
        pool_download.join()