from tkinter import *
import customtkinter as ctk
from datetime import datetime
import logging
from bs4 import BeautifulSoup
import requests
from requests.exceptions import ConnectionError
import json
from CustomTkinterMessagebox import CTkMessagebox


#Sets up logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, filename="inventory_update.log", datefmt='%Y-%m-%d %H:%M:%S')

#Brings in a config file with settings (including API key, base URL, and information on item process types and labels)
with open('settings.json') as config_file:
    settings = json.load(config_file)

#R/W Bibs API Key for Alma instance
bibapi = settings['bibapi']
#Base Alma server URL
alma_base = settings['alma_base']
#headers = settings['headers']
#Taken from the PROCESSTYPE code table (https://developers.exlibrisgroup.com/blog/Working-with-the-code-tables-API/)
statuslist = settings['statuslist']
#Gives that list user-friendly labels:
processlabel = settings['processlabel']
#Default message when launching program:
default_message = settings['default_message']

#Takes note of current date
rawdate=datetime.now().strftime("%Y-%m-%d")
scandate = (f"{rawdate}Z")

#Back-end functions (The functions that do the API requests and data parsing):

#Look up item by barcode, if found get item record XML
def scan_barcode (barcode, alma_base, bibapi):
    headers = settings['headers']
    #Set up default things for base URL and bib API key
    try: 
        r = requests.get(f"{alma_base}/items?view=label&item_barcode={barcode}&apikey={bibapi}",  headers=headers)
        
        #If status code is returned and isn't =200, that means it was able to connect to the server but the record wasn't returned (item likely not found)
        if r.status_code != 200:
            founditem = False
            connectFail = False
        
        #Otherwise, status code assumed to be 200, connection made and record found
        else:
            founditem = True
            connectFail = False

        return(founditem, connectFail, r, headers)
    
    #Adds timeout exception if unable to connect to server to check for item
    except ConnectionError:
        connectFail = True
        founditem = False
        r = ""
        return(founditem, connectFail, r, headers)


#Parses item data XML to find elements for display and eventual record update
def retreive_item_data (r, scandate):
    soup = BeautifulSoup(r.content, "xml")

    #Locate identifiers in data (used for update request)
    mmsid = soup.mms_id.string
    holdid = soup.holding_id.string
    itemid = soup.pid.string

    #Check for process status
    try:
        processstatus = soup.process_type.string
    except AttributeError:
        processstatus = "None"
    if processstatus in statuslist:
        inprocess = True
        {"syslabel": processstatus}.get("readlabel")

        for syslabel, readlabel in processlabel.items():  
            if syslabel == processstatus:
                 processtype = readlabel
            else:
                pass
    else:
        inprocess = False
        processtype = ""

    #Look for metadata elements for display
    try:
        title = soup.title.string
    except AttributeError:
        title = ""
    
    try:
        author = soup.author.string
    except AttributeError:
        author = ""

    #Checks to see if item is in a temporary location
    try:
        intemp_check = soup.in_temp_location.string
    except AttributeError:
        intemp_check = ""

    if intemp_check == 'true':
        intemp = True
        templocation_raw = soup.temp_location['desc']
        location = f"{templocation_raw} (Temporary Location)"
    else:
        intemp = False
        location = soup.location['desc']       

    #Gets call number
    try:    
        callnumber = soup.call_number.string
    except AttributeError:
        callnumber = ""
    
    #Gets item description
    try:
        desc = soup.description.string
    except AttributeError:
        desc = ""

    #Looks for existing inventory date field, adds it if missing, and updates value to current date
    try:
        inventorydate = soup.inventory_date
        inventorydate.string = scandate
    except AttributeError:
        addeddate = soup.new_tag("inventory_date")
        addeddate.string = scandate

        #Find inventory number field to use as placement reference
        inventorynumber = soup.inventory_number
        soup.item.item_data.inventory_number.insert_after(addeddate)

    #Updated item record XML to send back to Alma
    itemdata = soup.item
    return(itemdata, mmsid, holdid, itemid, processtype, inprocess, title, author, location, callnumber, desc, intemp)


#Update Alma item record 
def update_inventory_date(itemdata, mmsid, holdid, itemid, bibapi, headers, alma_base):
    #This should be the XML body data to send back in as a PUT 
    updatepush = requests.put(f"{alma_base}/bibs/{mmsid}/holdings/{holdid}/items/{itemid}?generate_description=false&apikey={bibapi}", data=itemdata.encode('utf-8'),headers=headers)

    #Code 200 is "success", anything else is a failure and will display an error
    if updatepush.status_code != 200:
        updatestatus = False
    
    else:
        updatestatus = True

    return(updatestatus, updatepush)


#Actual GUI and associated GUI functions to make things work
class Widget:
    def __init__(self, gui):
        #Basic winow properties
        gui.title("Alma Inventory Date Updater")
        gui.bind('<Return>', lambda e: self.inventoryUpdate() )
        gui.resizable(False, False)
        gui.wm_iconbitmap("inventory_icon.ico")

        #Top label text
        ctk.CTkLabel(gui, text="Scan barcode below:", font=('Roboto', 16)).grid(row=0, columnspan=2, pady=10)

        #Entry field and Enter button
        self.barcodeEntry = ctk.CTkEntry(gui, width=200)
        self.barcodeEntry.grid(row=1, column=0, padx=10, pady=20)
        ctk.CTkButton(gui, text="Enter", command=lambda: self.inventoryUpdate()).grid(row=1, column=1, padx=10, pady=20 )

        #Center frame to show data, background color is grey by the default but changes with status
        self.infoframe = ctk.CTkFrame(gui, width=400, height=250)
        self.frameReset()
        self.infoframe.grid(row=2, columnspan=2, pady=10, sticky='nsew')

        #Information at top of frame (updates to show current status)
        self.statustext = ctk.CTkLabel(self.infoframe, text=default_message, fg_color="transparent")
        self.statustext.pack()

        #Central item information display
        self.infoDisplay = ctk.CTkTextbox(self.infoframe, width=300, height=175, wrap="word")
        self.infoDisplay.configure(state="disabled")
        self.infoDisplay.pack()

        #Blank spacer at bottom of frame so it's symmetrical
        ctk.CTkLabel(self.infoframe, text=" ").pack()
        
        #Frame to keep the clear and exit buttons separate from the main grid because that grid's asymmetrical
        self.controlframe = ctk.CTkFrame(gui, fg_color="transparent")
        self.controlframe.grid(row=3, columnspan=2)

        #Clear screen button
        ctk.CTkButton(self.controlframe, text="Clear Screen", command=lambda: self.clearEntry()).grid(row=0, column=0, pady=10, padx=10)

        #Exit button
        ctk.CTkButton(self.controlframe, text="Exit", command=lambda: gui.destroy()).grid(row=0, column=1, pady=10, padx=10)

    #Function to clear the barcode entry field
    def clearBarcode(self):
        self.barcodeEntry.delete(0, 'end')

    #Returns information frame to default grey
    def frameReset (self):
        self.infoframe.configure(fg_color="#ced4da")

    #Turns information frame green
    def frameSuccess (self):
        self.infoframe.configure(fg_color="#79dfc1")
    
    #Turns information frame yellow
    def frameWarning (self):
        self.infoframe.configure(fg_color="#ffe69c")
    
    #Turns information frame red
    def frameError (self):
        self.infoframe.configure(fg_color="#f1aeb5")

    #Turns information frame blue for a note
    def frameNote (self):
        self.infoframe.configure(fg_color="#a4ddf1")

    #Popup box for connection error
    def connectError (self):
        CTkMessagebox.messagebox(title="Check Connection", text="Unable to connect to Alma, please check internet connection.", size="400x150")

    #Clears central item information display (Text widget must be set to normal state for editing, disables it again after so text can't be added by user)
    def displayClear (self):
        self.infoDisplay.configure(state="normal")
        self.infoDisplay.delete("1.0", END)
        self.infoDisplay.configure(state="disabled")

    #Returns to all defaults
    def clearEntry(self):        
        self.frameReset()
        self.displayClear()
        self.statustext.configure(text=default_message)        
        self.clearBarcode()

    #Sets a progress bar to display while task is running
    def runProgressBar(self):
        self.progresstext = ctk.CTkLabel(self.infoframe, text="Working...")
        self.progressbar = ctk.CTkProgressBar(self.infoframe, orientation="horizontal", height=10, mode="indeterminate")
        self.progresstext.pack()
        self.progressbar.pack()
        self.progressbar.start()

    #Stops the progress bar when task is finished
    def killProgressBar(self):
        self.progressbar.stop()
        self.progresstext.pack_forget()
        self.progressbar.pack_forget()


    def finalupdate (self, updatestatus, updatepush):
        if updatestatus == False:
            self.killProgressBar()
            self.frameError()
            self.statustext.configure(text= "Item information was not updated. Please try again")

        else:
            self.killProgressBar()


    #The function that handles everything when "Enter" or <Return> are pressed
    def inventoryUpdate (self):
        self.frameReset()
        self.displayClear()
        barcode = self.barcodeEntry.get()
        self.clearBarcode()
        self.statustext.configure(text= "Working...")
        self.runProgressBar()

        #Checks Alma for barcode
        founditem, connectFail, r, headers = scan_barcode (barcode, alma_base, bibapi)
        

        #If item isn't found in Alma by barcode, give user an error message and change frame color to error color
        if (connectFail == True):
            self.frameError()
            self.killProgressBar()
            self.connectError()
            self.statustext.configure(text="Please resolve connection issue before continuing.")
            #Logs that the item was scanned while not connected (for troubleshooting from log if needed later)
            logging.error(f"Barcode {barcode} scanned. Connection attempt timed out.")

        #If connection was made but item wasn't found, prompt user to set item aside (cannot update record)
        elif (connectFail == False) & (founditem == False):
            self.frameError()
            self.killProgressBar()
            self.statustext.configure(text="Item not found! Please set aside.")
            logging.error(f"Barcode {barcode} scanned. Item not found in Alma.")


        #If found, retreives and parses item data    
        else:            
            itemdata, mmsid, holdid, itemid, processtype, inprocess, title, author, location, callnumber, desc, intemp = retreive_item_data (r, scandate)
            
            #Checks if item is currently in a process status or a temp location (to affect display and messages)
            pathcheck = inprocess or intemp

            if pathcheck == True:
                if inprocess == True:
                    screenpath = "withprocess"
                if intemp == True:
                    screenpath = "withtemp"
            else:
                screenpath = "clearstatus"

            #Update basic display information about item
            self.update_item_display(barcode, title, author, location, callnumber, desc)

            #Attempt to update item data in Alma via API
            updatestatus, updatepush = update_inventory_date(itemdata, mmsid, holdid, itemid, bibapi, headers, alma_base)

            #Final display update options for item (dependent on item status and if update was successful):
            #If item is in process, alert the user
            if screenpath == "withprocess":                
                self.statustext.configure(text= f"Item has process status: {processtype}, \nPlease set aside!")
                self.frameWarning()
                self.finalupdate(updatestatus, updatepush)
                logging.info(f"Barcode {barcode} scanned. Had process status {processtype}. Updated?: {updatestatus}")

            #If it's not in process but it is in temp location, also let the user know
            elif screenpath == "withtemp":                
                self.statustext.configure(text= f"Scan next barcode to continue \nNote: This item is in a temporary location")
                self.frameNote()
                self.finalupdate(updatestatus, updatepush)
                logging.info(f"Barcode {barcode} scanned. Item currently has a temporary location. Updated?: {updatestatus}")

            #If item isn't in process or in a temp location, show all clear status (unless there was an error updating the record)
            elif screenpath == "clearstatus":                
                self.statustext.configure(text= "Scan next barcode to continue")
                self.frameSuccess()
                self.finalupdate(updatestatus, updatepush)
                logging.info(f"Barcode {barcode} scanned. Updated?: {updatestatus}")


    #Updates the central item information display with the parsed information from the item scanned
    def update_item_display(self, barcode, title, author, location, callnumber, desc):        
        #Allows text to be written to the display
        self.infoDisplay.configure(state="normal")
        self.infoDisplay.insert("1.0", f"You just scanned: \nBarcode: {barcode} \nTitle: {title} \nAuthor: {author} \n\nLocation: {location} \nCall number: {callnumber} \nDescription: {desc}")
        #Makes display text read-only                
        self.infoDisplay.configure(state="disabled")
    

def main():
    ctk.set_appearance_mode("System")  # Modes: system (default), light, dark
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    interface = Widget(root)
    root.mainloop()

if __name__ == "__main__":
    main()