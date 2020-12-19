import argparse
import sys

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

    options = parser.parse_args(sys.argv[1:])

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

url_params_dictionary = search_params_dictionary.copy()
url_params_dictionary.update(config_params_dictionary)

print(url_params_dictionary)