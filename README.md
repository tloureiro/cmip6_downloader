__Requirements:__
- Python 3

__How to run it:__

1) If you do not have python, you can download it here: https://www.python.org/downloads/
2) Create a folder and place the cmip6_downloader.py file inside of it
3) Open a terminal window and change directories to the new folder
4) Type: python3 cmip6_downloader.py (you can run it in interactive mode or provide search params)

__What's new in version 2:__
- You can now run the downloader in pure command line mode using any of the search params available in the website: --mip_era, --activity_id, --model_cohort, --product, --source_id, --institution_id, --source_type, --nominal_resolution, --experiment_id, --sub_experiment_id, --variant_label, --grid_label, --table_id, --frequency, --realm, --variable_id, --cf_standard_name, --data_node. Example:

``python3 cmip6_downloader.py --variable_id siflswdtop --experiment_id ssp126``

``python3 cmip6_downloader.py --variable_id siconc --frequency mon --experiment_id ssp126``

(if you don't provide any params you will be prompted for variable name, frequency, experiment ID and source ID)

- New folder structure for downloaded files
- Better downloading process feedback

Also, a file list is generated and placed in the root folder. Inside this .txt file you have a list of files to be download.

Note: Some files might not be downloaded when you run this script (the script will even downloading them again on the first run), if this happens, you can run the script again, provide the same search parameters and only new or previously failed files will be downloaded.

I'm still improving the code so please be patient and I'm sorry if it breaks for you somehow. Code contributions are very welcome.

Bugs, questions or request for new features: thiago@tloureiro.com

[![DOI](https://zenodo.org/badge/183989782.svg)](https://zenodo.org/badge/latestdoi/183989782)
