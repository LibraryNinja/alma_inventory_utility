# Alma Inventory Date Updater
Utility program with TKinter/CustomTKinter interface to update inventory dates by barcode in Alma on scan. Instant feedback for errors/issues.

*Note: Previous version of this tool was built using PySimpleGUI version 4, which is no longer available. I moved the files for that version to the PSG_version subfolder of this repository.*

<img src=https://github.com/LibraryNinja/alma_inventory_utility/blob/main/inventory_updater_screenshot_v2_ctk.png width="300">

# How it works
- Makes initial call to Alma API to check for existence of barcode in system (Note: The barcode-based call is an alias, but it will return the full item record with proper identifiers)
  - If no match is found in Alma, will alert user to set item aside
- Provided the item is found on lookup, updates the Inventory Date field in the item record's retreived XML and sends it back to Alma in as PUT request
  - Inventory date field is updated based on computer's current date
  - Will alert the user if there was an error in updating the record
- If the barcode is found in Alma, looks for existence of existing process statuses and also checks if the item is currently in a temporary location
  - If the item is in process (currently still on loan, marked as missing or lost, etc), it will alert the user to set aside for remediation
  - If item is listed as being in a temporary location, and that location isn't where the user is, they should probably also set it aside for remediation
- Displays current item information on screen so users know the item went through (and to help them keep track as they work their way through a row or shelf).

# Requirements
## Non-default Python Libraries
- CustomTKinter (https://customtkinter.tomschimansky.com/)
  - Extension of TKinter library that makes things look nice and modern
- BeautifulSoup (and its XML parser) (Used to parse and edit the XML for the item record)

## Other Requirements
- Alma API key for Bibs with Read/Write Permissions
- Check your PROCESSTYPE code table to ensure it matches the existing code (I believe my library only has default ones but your mileage may vary)

# Notes
Inspired by [Jeremy Hobb's LazyLists](https://github.com/MrJeremyHobbs/LazyLists/tree/master) but written by me from scratch because it was easier for me to do that than learn someone else's code vernacular.

To make it easy to have library staff run this, I used auto-py-to-exe (that's built off of PyInstaller) to generate a portable .exe package to use. As the generated .exe is environment depenedent feel free to do something similar.
