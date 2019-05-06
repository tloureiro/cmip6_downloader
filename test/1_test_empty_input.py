variable_name = input('what\n')
frequency_value = input('frequency\n')
experiment_id = input("enter the experiment ID\n")

variable = ''
if variable_name:
   variable = '&variable_id=' + variable_name

frequency = ''
if frequency_value:
    frequency = '&frequency=' + frequency_value

experiment = ''
if experiment_id:
    experiment = '&experiment_id=' + experiment_id





url = 'https://esgf-node.llnl.gov/esg-search/search/?offset=0&limit=10000&type=Dataset&replica=false&latest=true&project=CMIP6&' + variable + frequency + experiment + '&facets=mip_era%2Cactivity_id%2Cmodel_cohort%2Cproduct%2Csource_id%2Cinstitution_id%2Csource_type%2Cnominal_resolution%2Cexperiment_id%2Csub_experiment_id%2Cvariant_label%2Cgrid_label%2Ctable_id%2Cfrequency%2Crealm%2Cvariable_id%2Ccf_standard_name%2Cdata_node&format=application%2Fsolr%2Bjson'

print(url)