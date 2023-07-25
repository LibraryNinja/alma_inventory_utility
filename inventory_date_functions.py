def loading_animation ():
    import PySimpleGUI as sg
    #Loading animation while the function runs
    sg.popup_animated(sg.DEFAULT_BASE64_LOADING_GIF, text_color="black", background_color='white', transparent_color='white', keep_on_top=True, message="Waiting...")

def stop_animation ():
    import PySimpleGUI as sg
    #Stops progress animation popup 
    sg.popup_animated(None)
  
#Look up item by barcode, if found get item record XML
def scan_barcode (barcode, alma_base, bibapi):
    import requests

    loading_animation()

    #Set up default things for base URL and bib API key

    headers = {"Accept": "application/xml", "Content-Type": "application/xml"}

    r = requests.get(f"{alma_base}/items?view=label&item_barcode={barcode}&apikey={bibapi}", headers=headers)

    if r.status_code != 200:
        founditem = False
    else:
        founditem = True
      
    stop_animation()

    return(founditem, r, headers)


def check_item_status (r):
    from bs4 import BeautifulSoup
    loading_animation()

    #List of statuses to flag, taken from the PROCESSTYPE code table (https://developers.exlibrisgroup.com/blog/Working-with-the-code-tables-API/)
    statuslist = ["ACQ", "CLAIM_RETURNED_LOAN", "HOLDSHELF", "ILL", "LOAN", "LOST_ILL", "LOST_LOAN", "LOST_LOAN_AND_PAID", "MISSING", "REQUESTED", "TECHNICAL", "TRANSIT", "TRANSIT_TO_REMOTE_STORAGE", "WORK_ORDER_DEPARTMENT"]

    soup = BeautifulSoup(r.content, "xml")

    try:
        processstatus = soup.process_type.string
    except AttributeError:
        processstatus = "None"

    if processstatus in statuslist:
        inprocess = True
    else:
        inprocess = False

    stop_animation()

    return(processstatus, inprocess, soup)

#Parses item data XML to find elements for display and eventual record update
def retreive_item_data (soup, scandate):
    from bs4 import BeautifulSoup
    
    loading_animation()

    #Locate identifiers in data (used for update request)
    mmsid = soup.mms_id.string
    holdid = soup.holding_id.string
    itemid = soup.pid.string

    #Look for metadata elements for display
    try:
        title = soup.title.string
    except AttributeError:
        title = ""
    
    try:
        author = soup.author.string
    except AttributeError:
        author = ""

    try:    
        callnumber = soup.call_number.string
    except AttributeError:
        callnumber = ""

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

    stop_animation()

    return(itemdata, mmsid, holdid, itemid, title, author, callnumber)


#Update Alma item record 
def update_inventory_date(itemdata, mmsid, holdid, itemid, bibapi, headers, alma_base):
    import requests

    loading_animation()


    #This should be the XML body data to send back in as a PUT 
    updatepush = requests.put(f"{alma_base}/bibs/{mmsid}/holdings/{holdid}/items/{itemid}?generate_description=false&apikey={bibapi}", data=itemdata.encode('utf-8'),headers=headers)

    if updatepush.status_code != 200:
        updatestatus = False
    else:
        updatestatus = True

    stop_animation()

    return(updatestatus, updatepush)