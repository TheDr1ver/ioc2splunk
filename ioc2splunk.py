#!/usr/local/bin/python2.7
__author__ = 'Nick Driver - https://github.com/TheDr1ver'

'''
#### Overview ####

ioc2splunk.py takes a CSV result from ioc-parser and appends de-duped results to
a CSV file that can be processed by Splunk as a lookup table. ioc-parser results must be
saved in the following format for it to work as-coded:

<YYYYMMDD>.<ticket_number>.<report_name>.csv
ex: 20150918.1234567.ioc_report.csv

python ioc2splunk.py "./path/to/<report_name>.csv"

#### Requirements ####

- backup folder is defined by backup_folder (default: "./backup") and must be created before execution
- master_splunk_file is where the resulting Splunk lookup table will be created, and
    the directory must exist before execution
- <report_name> must match the following regex: "((?![a-zA-Z0-9_\-\[\]]).)+"
    ( i.e. alpha-numeric characters and _-[] )

#### Flow ####

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

'''


#### Imports ####
import os
import csv
from datetime import datetime, date, time
import shutil
import sys

#### Vars ####

test_ioc_csv = sys.argv[1]
temp_splunk_csv = "./new_splunk_iocs2.csv"
backup_folder = "./backup"
master_splunk_file = "./master_splunk_table/master.splunk_table.csv"



#### Filename Parser ####
def parseFilename(test_ioc_csv):
    # This gets the important info from the filename being fed
    parsed_results = {}
    #Split for Linux
    filename = test_ioc_csv.rsplit("/",1)[-1]
    #Split for Windows
    filename = filename.rsplit("\\",1)[-1]
    #Split on periods
    filename_split = filename.split(".")

    if len(filename_split)!=4:
        #Quit
        print "Something went wrong - filename should only have 4 parts (three periods)"+str(filename_split)
    else:
        parsed_results["date_added"] = filename_split[0]
        parsed_results["ticket_number"] = filename_split[1]
        parsed_results["report_title"] = filename_split[2]

    return parsed_results


#### Get the data from the IOCP.py output csv and add it to a stop-gap file (temp_splunk_f) ####
def tempCSV(temp_splunk_csv, test_ioc_csv):
    headers = ["date_added", "ticket_number", "report_title", "ioc_type", "ioc", "status", "notes"]

    with open(temp_splunk_csv, "wb") as temp_splunk_f:
        writer = csv.writer(temp_splunk_f)

        #Write the headers to the first row of the CSV file
        writer.writerows([headers])

        #Parse out the important info from the filename
        parsed_filename = parseFilename(test_ioc_csv)

        date_added = parsed_filename["date_added"]
        ticket_number = parsed_filename["ticket_number"]
        report_title = parsed_filename["report_title"]

        #### Read IOCP Results CSV ####
        with open(test_ioc_csv, 'rb') as iocpf:
            try:
                reader = csv.reader(iocpf, delimiter="\t")
                for row in reader:
                    #For each row in the IOCP results csv
                    #Build the new row that's about to be written
                    row_list = []
                    row_list.append(date_added)
                    row_list.append(ticket_number)
                    row_list.append(report_title)

                    colnum = 0
                    for col in row:
                        #Do something with the column
                        #iocp.py outputs these values: file_path, page_no, ioc_type, ioc
                        #print col
                        if colnum==2:
                            #This is the IOC type
                            #print col
                            row_list.append(col)
                        if colnum==3:
                            #This is the IOC
                            #print col
                            row_list.append(col)
                        colnum+=1
                    #resulting row_list should contain date_added,ticket_number,report_title,ioc_type,ioc
                    #status and notes headers are for manual addition by the analyst
                    writer.writerows([row_list])
            finally:
                iocpf.close()

        temp_splunk_f.close()



'''
- Check backup folder for backup files older than 30(?) days and delete them
'''


def purgeBackups(backup_folder):
    #Walk through backup directory and delete anything with a dated filename older than 30 days from today
    backup_files=os.listdir(backup_folder)
    today_date = datetime.today()
    #today_date = int(d.strftime("%Y%m%d"))
    for f in backup_files:
        parsed_filename=parseFilename(f)
        date_added=parsed_filename["date_added"]
        date_added = datetime.strptime(date_added, "%Y%m%d")
        td = today_date-date_added

        if td.days > 30:
            file_path = backup_folder+"/"+f
            os.remove(file_path)



'''
- Checks current Splunk table for IOCs older than 30 days and removes them
'''

def purgeIOCs(master_splunk_file):
    #Check that master_splunk_file exists
    if os.path.isfile(master_splunk_file):
        #Check each IOC to see if it's older than 30 days. If so, remove it.
        with open(master_splunk_file, 'rb') as splunk_master:
            try:
                reader = csv.reader(splunk_master)
                splunk_master_list=[]

                today_date = datetime.today()
                #today_date = int(d.strftime("%Y%m%d"))

                rowcount=0
                for row in reader:
                    if rowcount==0:
                        #add the header
                        splunk_master_list.append(row)
                        #move onto the next


                    colnum=0
                    if rowcount!=0:
                        for col in row:
                            if colnum==0:
                                date_added = datetime.strptime(col, "%Y%m%d")
                                td = today_date-date_added
                                if td.days <= 30:
                                    splunk_master_list.append(row)
                            colnum+=1

                    rowcount+=1
            finally:
                splunk_master.close()
        #print splunk_master_list
        with open(master_splunk_file, 'wb') as splunk_master:
            try:
                writer = csv.writer(splunk_master)
                for row in splunk_master_list:
                    writer.writerows([row])
            finally:
                splunk_master.close()



'''
- Checks current Splunk table w/ new IOC results to de-dup
- Appends non-duplicates to Splunk table (with dates for future removal)
'''


def addIOCs(master_splunk_file, temp_splunk_csv):
    #Check if master_splunk_file exists
    if os.path.isfile(master_splunk_file):
        #Open master_splunk_file and read line-by-line
        with open(master_splunk_file, 'rb') as splunk_master:
                try:
                    reader = csv.reader(splunk_master)
                    splunk_master_iocs = []
                    rowcount = 0
                    for row in reader:
                        if rowcount == 0:
                            #Skip the header
                            pass
                        colnum = 0
                        for col in row:
                            if colnum==4:
                                #Add each IOC to a list
                                splunk_master_iocs.append(col)
                            colnum+=1
                        rowcount += 1
                finally:
                    #Close master_splunk_file
                    splunk_master.close()
                    #print splunk_master_iocs
    else:
        splunk_master_iocs = []


    #Open temp_splunk_csv and read line by line
    with open(temp_splunk_csv) as temp_splunk:
        try:
            reader = csv.reader(temp_splunk)
            rowcount = 0
            for row in reader:
                if rowcount == 0 and os.path.isfile(master_splunk_file):
                    #Skip the header if the file exists
                    pass
                colnum = 0
                for col in row:
                    if colnum==4:
                        #Check if the IOC is in the master splunk list - if not, add the whole row
                        #print col
                        if col not in splunk_master_iocs:
                            #print col
                            #print row
                            fd = open(master_splunk_file, 'ab')
                            writer = csv.writer(fd)
                            writer.writerows([row])
                            fd.close()
                    colnum+=1
                rowcount +=1
        finally:
            #Close temp_splunk_csv and then delete it
            temp_splunk.close()
            #os.remove(temp_splunk_csv) #### Put this back in later





'''
- Saves final Splunk table backup
'''

def saveCopies(backup_folder, master_splunk_file):
    #Copy the newly created master_splunk_file with this naming convention to the backup folder:
    #<date_added>.master.splunk_table.csv

    d = datetime.today()
    today_date = str(d.strftime("%Y%m%d"))

    backup_master_splunk = today_date+".master.splunk_table.csv"
    dest_file=backup_folder+"/"+backup_master_splunk

    shutil.copy(master_splunk_file, dest_file)




#### Execute all Functions ####

#### Get the data from the IOCP.py output csv (test_ioc_csv) and add it to a stop-gap file (temp_splunk_csv) ####
tempCSV(temp_splunk_csv, test_ioc_csv)

#### Walk through backup directory and delete anything with a dated filename older than 30 days from today ####
purgeBackups(backup_folder)

#### Check each IOC to see if it's older than 30 days. If so, remove it. ####
purgeIOCs(master_splunk_file)

#### De-dup and add new IOCs to master Splunk file ####
addIOCs(master_splunk_file, temp_splunk_csv)

#### Copy the newly created master_splunk_file with this naming convention to the backup folder:
#### <date_added>.master.splunk_table.csv
saveCopies(backup_folder, master_splunk_file)
