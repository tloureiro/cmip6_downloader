import solr

# create a connection to a solr server
s = solr.SolrConnection('https://esgf-node.llnl.gov/esg-search/search/')



# offset=0&limit=9999&type=Dataset&replica=false&latest=true&project=CMIP6&' + variable + frequency + experiment + '&facets=mip_era%2Cactivity_id%2Cmodel_cohort%2Cproduct%2Csource_id%2Cinstitution_id%2Csource_type%2Cnominal_resolution%2Cexperiment_id%2Csub_experiment_id%2Cvariant_label%2Cgrid_label%2Ctable_id%2Cfrequency%2Crealm%2Cvariable_id%2Ccf_standard_name%2Cdata_node&format=application%2Fsolr%2Bjson
# do a search
response = s.query(project='CMIP6', facets=['mip_era'], type=['Dataset'], limit=100, variable_id='rsu', format='application/solr+json')
for hit in response.results:
    print(hit)