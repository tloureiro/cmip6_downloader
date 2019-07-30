__Requirements:__
- Python 3

__How to run it:__

1) If you do not have python, you can download it here: https://www.python.org/downloads/
2) Create a folder and place the cmip6_downloader.py file inside of it
3) Open a terminal window and change directories to the new folder
4) Type: python3 cmip6_downloader.py
5) When prompted, give it a variable name (i.e. type “siarean” for Arctic sea ice area), time frequency (i.e. type “mon” for monthly data), experiment id and it’s off to the races. See https://esgf-node.llnl.gov/search/cmip6/ for list of variable names, time frequencies, and experiments.

The script will create a folder for each group of downloaded files following the following standard:
<variable_id>\_\<frequency>\_<experiment_id>

Also, a file list is generated and placed in the root folder. Inside this .txt file you have a list of files to be download.

Note: Some files might not be downloaded when you run this script (the script will even retry downloading them), if this happens, you can run the script again, provide the same search parameters and only new or previously failed files will be downloaded.

I'm still improving the code so please be patient and I'm sorry if it breaks for you somehow. Code contributions are very welcome.

Bugs, questions or request for new features: thiago@tloureiro.com

