import PySimpleGUI as sg
from datetime import datetime
import logging
from inventory_date_functions import scan_barcode, retreive_item_data, update_inventory_date, check_item_status, loading_animation, stop_animation
import configparser

default_message = "Please scan barcode to continue"

#Sets up logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, filename="inventory_update.log", datefmt='%Y-%m-%d %H:%M:%S')

#Pulls in config file
config = configparser.ConfigParser()
config.read("inventory_settings.ini")

#Parameters!
bibapi = config.get("main", "bibapi")
alma_base = config.get("main", "alma_base")
#headers = config.get("main", "headers")
theme = config.get("style", "theme")
font_size = config.get("style", "font_size")
font_family = config.get("style", "font_family")


#Takes note of current date
rawdate=datetime.now().strftime("%Y-%m-%d")
scandate = (f"{rawdate}Z")

#Function to take Alma internal status and display a user-friendly label
#Probably a better way to do this, but this will suffice for now
#Taken from the PROCESSTYPE code table (https://developers.exlibrisgroup.com/blog/Working-with-the-code-tables-API/)
def status_display(processstatus):
    if processstatus == "ACQ":
        processtype = "Acquisitions"
    if processstatus == "CLAIM_RETURNED_LOAN":
        processtype = "Claimed Returned"
    if processstatus == "HOLDSHELF":
        processtype = "On Hold Shelf"
    if processstatus == "ILL":
        processtype = "Resource Sharing Request"
    if processstatus == "LOAN":
        processtype = "On Loan"
    if processstatus == "LOST_ILL":
        processtype = "Lost Resource Sharing Request"
    if processstatus == "LOST_LOAN":
        processtype = "Lost"
    if processstatus == "LOST_LOAN_AND_PAID":
        processtype = "Lost and Paid"
    if processstatus == "MISSING":
        processtype = "Missing"
    if processstatus == "REQUESTED":
        processtype = "Requested"
    if processstatus == "TECHNICAL":
        processtype = "Technical Migration"
    if processstatus == "TRANSIT":
        processtype = "In Transit"
    if processstatus == "TRANSIT_TO_REMOTE_STORAGE":
        processtype = "In Transit to Remote Storage"
    if processstatus == "WORK_ORDER_DEPARTMENT":
        processtype = "In Work Order Status"
    return(processtype)

#The window layout
def main_window():
    layout = [
        [sg.T('Scan Barcode Below:', font="bold")],
        
        #Barcode input and optional enter button
        [sg.Input(default_text='', do_not_clear=False, s=26, key='-ITEM_BARCODE-', background_color="white"), sg.B("Enter", key="-ENTER-", button_color=("white", "green4"), font="bold")],

        #Info display in a nice frame
        [sg.Frame('', [[sg.T("Please Scan Barcode to begin", key='-STATUS-', font="bold", pad=5)],
        [sg.T("", key='-SCANNED-')],
        [sg.T("", key='-TITLE-', expand_y=True, auto_size_text=True, size=(45, 1))],
        [sg.T("", key='-AUTHOR-')],
        [sg.T("", key='-CALLNO-')]])],

        [sg.T("", pad=5, key='-TONEXT-')],

        #Function buttons
        [sg.B('Clear Screen', key= "-CLEAR-", s=12, button_color=("black", "yellow"), font="bold"), sg.B('Exit', s=10, button_color=("black", "tomato"), font="bold")]]


    #Window details
    window_title = "Alma Inventory Date Updater"
    window = sg.Window(window_title, layout, icon="inventory_icon.ico", grab_anywhere=True, finalize=True)

    window['-ITEM_BARCODE-'].bind("<Return>", "_Enter")

    #Actually runs the thing
    while True:
        event, values = window.read()
        #print(event,values)
        if event in (sg.WINDOW_CLOSED, 'Exit'):
            break
        
        #Take input and clear display if anything's there
        if event in (('-ITEM_BARCODE-' + "_Enter"), ("-ENTER-")):
            barcode = values['-ITEM_BARCODE-']
            
            logging.info(f"Barcode {barcode} scanned")
            window['-STATUS-'].update("", background_color=None)
            window['-SCANNED-'].update("")
            window['-TITLE-'].update("")
            window['-AUTHOR-'].update("")
            window['-CALLNO-'].update("") 
            window['-TONEXT-'].update("", background_color=None)  

            #Search for barcode
            founditem, r, headers = scan_barcode(barcode, alma_base, bibapi)

            #If it finds the barcode display success message, find metadata to use to update display, and attempt to update inventory date in Alma
            if founditem == True:
                window['-STATUS-'].update("Item found!", text_color="green4", background_color="azure1", font="bold")

                #Retreive item information from returned XML

                #First just check for status
                processstatus, inprocess, soup = check_item_status(r)

                #Then look for rest of data
                itemdata, mmsid, holdid, itemid, title, author, callnumber= retreive_item_data(soup, scandate)

                #Update display to show current item
                window['-STATUS-'].update("You just scanned: ")
                window['-SCANNED-'].update(f"Barcode: {barcode}")
                window['-TITLE-'].update(f"Title: {title}")
                window['-AUTHOR-'].update(f"Author: {author}")
                window['-CALLNO-'].update(f"Call Number: {callnumber}")


                #If item has a process status, display message and don't update record at this time                               
                if inprocess == True:
                    processtype = status_display(processstatus)
                    window['-STATUS-'].update(f"Item has status {processtype}, please set aside!", background_color="tomato", text_color="black", font="bold")
                    logging.error(f"Barcode {barcode} has process type {processstatus}")
                    window['-TONEXT-'].update("Scan next barcode to continue", text_color="green4", background_color="azure1", font="bold")

                #If not in process, update record
                if inprocess == False:                
                    window['-TONEXT-'].update("Please wait...Updating Record", text_color="black", background_color=None)

                    #Run function to update inventory date in Alma
                    updatestatus, updatepush = update_inventory_date(itemdata, mmsid, holdid, itemid, bibapi, headers, alma_base)
                    logging.info(f"Update data response: {updatepush}")

                    #If date was updated show success message, if it wasn't for whever reason display error message and log status
                    if updatestatus == True:
                        window['-TONEXT-'].update("Scan next barcode to continue", text_color="green4", background_color="azure1", font="bold")
                        logging.info("Inventory date updated!")
                    if updatestatus == False:
                        window['-TONEXT-'].update("Item information was not updated. Please try again", background_color="tomato", text_color="black", font="bold")
                        logging.error(f"Inventory date not updated? Barcode {barcode}")

                
            #If item wasn't found by barcode, prompt user to set aside and scan next item to continue
            if founditem == False:
                #sg.popup("Item not found. Please set aside!", background_color="tomato", no_titlebar=True)
                window['-STATUS-'].update("Item not found, please set aside", background_color="tomato", text_color="black", font="bold")
                logging.error(f"Barcode {barcode} not found")
                window['-TONEXT-'].update("Scan next barcode to continue", text_color="green4", background_color="azure1", font="bold")
        
        #Function to clear display
        if event == '-CLEAR-':
            window['-STATUS-'].update(default_message, background_color=None)
            window['-TITLE-'].update("")
            window['-AUTHOR-'].update("")
            window['-CALLNO-'].update("")
            window['-SCANNED-'].update("")
            window['-TONEXT-'].update("", background_color=None)

        #Exit button
        if event == sg.WIN_CLOSED or event == 'Exit':
            break

    window.close()



if __name__ == '__main__':
    sg.theme(theme)
    sg.set_options(font=(font_family, font_size))
    main_window()
    