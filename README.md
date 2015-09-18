Overview
========

ioc2splunk.py takes a CSV result from [ioc-parser] and appends de-duped results to
a CSV file that can be processed by Splunk as a lookup table. 
ioc-parser results must be saved in the following format for it to work as-coded:

[YYYYMMDD].[ticket_number].[report_name].csv

ex: 20150918.1234567.ioc_report.csv

python ioc2splunk.py "./path/to/20150918.1234567.ioc_report.csv"

Requirements
============

- backup folder is defined by backup_folder (default: "./backup") and must be created before execution
- master_splunk_file is where the resulting Splunk lookup table will be created, and
    the directory must exist before execution
- [report_name] must match the following regex: **((?![a-zA-Z0-9_\-\[\]]).)+**

( i.e. alpha-numeric characters and _-[] )

Process Flow
============

- Adds the following data/columns to csv after parsed
    - date_added
    - ticket_number
    - report title
    - status
    - notes

- Parse out resulting IOC CSV from iocp.py into Splunk Lookup Table format
- Check backup folder for backup files older than 30 days and delete them
- Checks current Splunk table for IOCs older than 30 days and removes them
- Checks current Splunk table w/ new IOC results to de-dup
- Appends non-duplicates to Splunk table (with dates for future removal)
- Saves final Splunk table backup

[//]:#
  [ioc-parser]: <https://github.com/armbues/ioc_parser>
