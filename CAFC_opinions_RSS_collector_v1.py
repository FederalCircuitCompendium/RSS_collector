# CAFC RSS Feed parser
# Purpose: This file  parses the CAFC Opinions & Orders RSS file and extracts the key information. In addition, it downloads a copy of the document. It also checks against the existing set of data to make sure that it has not previously collected that record (so that it only collects new entries on the RSS feed). It is designed to be run as a cron job.
# Date initially created: October 18, 2022
# Author: Jason Rantanen


# Psuedocode
# Download most recent RSS file from CAFC
# Turn the current set of guid in the dataset into a list
# Run through each item in the RSS file to determine whether it is already in the dataset
# If it is not in the dataset, extract the information and download the file
# Assign a uniqueID to each new record
# Generate a newFileName for the associated document
# Write the date & time the job is being run to RSS_log.log
# Write the information to the dataset
# Make a copy of the document with the NewFileName
# Upon completion, delete the RSS file

# Relevant files:
# CAFC_documents.csv: this is the dataset of documents collected from the Federal Circuit's website
# CAFC_RSS.rss: this is the most recent rss file downloaded from the Federal Circuit's RSS feed. It is deleted on the conclusion of the script.
# RSS_log.log: logs each time the job is run. 

import feedparser
import os
import csv
import wget
import shutil
import re

#This script uses the pdfminer package to extract text from PDF files.  You will need to install PDF miner if it is not already installed.  To do this, 
#Open terminal and type "pip3 install pdfminer.six --user"  This should install pdfminer.

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import BytesIO

os.chdir("/Users/jrantanen/Documents/GitHub/RSS_collector") 

# Timestamp the log file when the cron job is run. (If not running a cron job it will just write the date/time this file is run to the log file.)
from datetime import datetime

def print_datetime():   
    """ Creates a function that will turn the current date and time into a string. """
    now = datetime.now()
    current_date = now.strftime("%d:%b:%Y")
    current_time = now.strftime("%H:%M:%S")
    data = "\n\nCurrent Date: " + current_date + "\n" + "Current Time = " + current_time
    return data


print(print_datetime())

# Create a new CAFC_documents.csv file if necessary

try: # This will check to see if the CAFC_documents.csv file exists
    with open("CAFC_documents.csv", 'r') as f:
        check = 1

except: # This will generate a new CAFC_documents.csv file if one doesn't exist
    fields = ['caseName','appealNumber', 'origin', 'PrecedentialStatus', 'CAFC_URL', 'FileName', 'guid', 'docDate', 'uniqueID', 'NewFileName', 'CloudLink', 'Appeal_Dockets'] 
    
    with open('CAFC_documents.csv', 'a', newline='') as f:
        # create the csv writer
        writer = csv.writer(f)
        writer.writerow(fields)


# Check to see whether there are new entries in the rss feed. 
url_RSS_opinions = "https://cafc.uscourts.gov/category/opinion-order/feed/" # This points to the CAFC's RSS feed

filename = wget.download(url_RSS_opinions, "CAFC_RSS.rss")

with open("CAFC_documents.csv", 'r') as f: #this extracts the existing guid into a list.
    # pass the file object to reader() to get the reader object
    reader = csv.reader(f)
    data = list(reader)
    # Pass reader object to list() to get a list of lists. 

guid_collected = []
uniqueID_collected = []
NewFileName_collected = []
    
for s in data: #This loops through the elements in the list of lists to extract the appeal numbers.
    guid = s[6] #defines the variable guid as the text in the 7th column of the .csv 
    guid_collected.append(guid)
    
    uniqueID = s[8]
    if uniqueID=="": uniqueID=0
    uniqueID_collected.append(uniqueID)
    
    NewFileName = s[9]
    NewFileName = NewFileName.split("CAFC")[0]
    if NewFileName=="": NewFileName=0        
    NewFileName_collected.append(NewFileName)
            
guid_collected.pop(0)
uniqueID_collected.pop(0)
NewFileName_collected.pop(0)


uniqueID_collected = list(map(int, uniqueID_collected))
NewFileName_collected = list(map(int, NewFileName_collected))

uniqueID = max(uniqueID_collected)
NewFileName = max(NewFileName_collected)

print("\nPrevious uniqueID: " + str(uniqueID))
print("Previous NewFileName number: " + str(NewFileName))


f.close()

d = feedparser.parse('CAFC_RSS.rss') # This is the RSS file that is being parsed. 

def extractText(path):
    manager = PDFResourceManager()
    retstr = BytesIO()
    layout = LAParams(all_texts=True)
    device = TextConverter(manager, retstr, laparams=layout)
    filepath = open(path, 'rb')
    interpreter = PDFPageInterpreter(manager, device)

    for page in PDFPage.get_pages(filepath, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()
    text = str(text[:3000])

    filepath.close()
    device.close()
    retstr.close()
    return text 

 
def extract_appeal_number(inputText):

    yearStart = 2001 #This is when we'll start running this text analysis.  It is very unlikely that pre-2000 appeal numbers will be searchable using this technique
    yearEnd = 2030 #This is a year five years from now.  The code will need to be updated if we ever get there. 

    Appeal_Dockets = [] #creates empty list for the appeal numbers to go in
    

    for year in range(yearStart, yearEnd): #This for loop runs a search for appeal numbers for each year between 2000 and 2025, adding to the appealNumbers list.  It uses several different search strings.
        appealPrefix  = str(year)+"-" #leading search string that will be used (example: "2012-"
   
        
        searchString1 = str(year)+'-'+"(\d\d\d\d)" #Searchstring to look for entries in the exact format of YYYY-####
        searchString2 = str(year)+'-'+"(\d\d\d\\b)" #Searchstring to look for entries in the exact format of YYYY-###
        
                
        appealSubstring1 = re.findall(searchString1, inputText) # captures the text that matches our the exact format YYYY-XXXX.
        appealSubstring2 = re.findall(searchString2, inputText) # captures the text that matches our exact format YYYY-XXX.
                      
        #Next we need to remove duplicates, which might happen because the docket number is repeated more than once in the document.
        tempList = [] 
        [tempList.append(x) for x in appealSubstring1 if x not in tempList]
        appealSubstring1=tempList
        
        tempList = [] 
        [tempList.append(x) for x in appealSubstring2 if x not in tempList]
        appealSubstring2=tempList        

        formattedAppealNumber1 = [appealPrefix + "0" + sub for sub in appealSubstring1] #This takes the extracted text (the last four digits of the appeal number) and add the prefix and a zero (example: 2012-01012)
        
        formattedAppealNumber2 = [appealPrefix + "00" + sub for sub in appealSubstring2]
        
        Appeal_Dockets = Appeal_Dockets + formattedAppealNumber1  #adds the new appeal numbers to the list of appeal numbers
        Appeal_Dockets = Appeal_Dockets + formattedAppealNumber2
        

    return(Appeal_Dockets) #Returns the final list of appeal numbers
 
def extractItem(item):
    
    guid = d.entries[item].guid
    item_guid = guid.split('=')[1]
   
    global uniqueID
    global NewFileName   
   
    if item_guid in guid_collected:

        return()
        
    else:
       
        #increment our uniqueID and NewFileName counters      
      
        uniqueID = uniqueID + 1
        NewFileName = NewFileName + 1
        
        # extract the date    
      
        pubDate = d.entries[item].published
        
        item_date = pubDate.split(' ')
    
        item_day = item_date[1]
        item_month = item_date[2]
        item_year = item_date[3]
        item_date = item_day + '-' + item_month + '-' + item_year
        
        print(item_date)       
       
        content = d.entries[item].content # This will take the content field of the item and output it as a list with a single item that is a dictionary. 
        
        item_text = content[0]["value"] # This will extract the text from the content list-dictionary. item_text is a string contains several components that then need to be parsed. 
        
        item_url = item_text.split('<p><a href="')[1] # parses the item_text string to start at the beginning of the file path
        item_url = item_url.split('"')[0] # parses the item_url string to remove the text after the file path
        
        title_parse = item_url + '">' # creates the text that will be used to parse the text for the title. 
        
        item_url = "https://cafc.uscourts.gov" + item_url # appends the site location to the file path
        
        item_filename = item_url.split('/')[-1] # parses the item_url to obtain only the last portion of the path (i.e.; the filename)
        
        item_title = item_text.split(title_parse)[1] # extracts the case name title
        item_title = item_title.split('<')[0]
        
        item_appeal_number = item_text.split('Appeal Number: ')[1] # extracts the CAFC website single appeal number
        item_appeal_number = item_appeal_number.split(' ')[0]
        
        item_origin = item_text.split('Origin: ')[1] # Cuts the string at the beginning of the origin
        item_prec_status = item_origin.split('>')[1] # Extracts the precedential status
        
        item_origin = item_origin.split(' ')[0] # truncates the end off the origin
        
        item_prec_status = item_prec_status.split(' ')[0] # truncates the end off the precedential status
        
        item_uniqueID = uniqueID
        item_NewFileName = str(NewFileName) + "CAFCDocument.pdf"     
        
        item_CloudLink = "https://storage.googleapis.com/cafc_compendium_repository/" + item_NewFileName       
        
        print(item_title) 
                 
        os.chdir("/Users/jrantanen/Documents/GitHub/RSS_collector/documents/") # this is where the files are going to be saved. I'm sure there is a more elegant solution.
        response = wget.download(item_url, item_filename)
        os.chdir("/Users/jrantanen/Documents/GitHub/RSS_collector/")
        
        shutil.copy("Documents/"+item_filename,"NewFileName/"+item_NewFileName)
        
        path = "NewFileName/" + item_NewFileName
        
        item_Appeal_Dockets = ""
        
        try: #I added the try - except clause in order to skip any files that aren't pdfs or that have another error message
            first3000 = extractText(path) #runs the pdf_to_text function on the file and returns the first 3000 characters
            inputText = first3000   
            item_Appeal_Dockets = extract_appeal_number(inputText) # returns a list of appeal numbers
            item_Appeal_Dockets = ";".join(item_Appeal_Dockets) # Converts list to a string               
    
        except:
            outputText="error" #returns an error message if the text miner fails.        
        
        input_variable = [item_title, item_appeal_number, item_origin, item_prec_status, item_url, item_filename, item_guid, item_date, item_uniqueID, item_NewFileName, item_CloudLink, item_Appeal_Dockets]
    
        with open('CAFC_documents.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow(input_variable)            
         
        return()
        
d = feedparser.parse('CAFC_RSS.rss')

for n in range(0,100):
    extractItem(n)

    

os.remove('CAFC_RSS.rss')

print("\nNew highest uniqueID is: " + str(uniqueID))
print("New highest NewFileName number is: " + str(NewFileName))
    
print("done")
        
# Additional components to add
# Sometimes the title is being output with quotation marks and sometimes it isn't.
# Additional automated collections of information based on text parsing



