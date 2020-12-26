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

# rev_multidict = {}
# for key, value in search_params_to_abbreviations.items():
#     rev_multidict.setdefault(value, set()).add(key)
#
# print(rev_multidict)

test = { 'experiment_id': 'ssp126', 'variable_id': 'siflswdtop' }

file_name_parts = []
for key, value in test.items():
    file_name_parts.append(search_params_to_abbreviations[key] + '_' + value)

file_name = '_'.join(file_name_parts)

print(file_name)