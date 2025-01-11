from PIL import ImageGrab
import pytesseract
import tkinter as tk
import time
import os



####config
bDebug = True

root = tk.Tk()

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

bShowSorted = True


class SortedMissionClass:
    def __init__(self):
        self.dropOfLocation = ""
        self.cargo = []

    #dropOfLocation = ""
    #cargo = []

    def printInfo(self):
        print(f"Drop of Location: {self.dropOfLocation}")
        for i in self.cargo:
            print(f"Cargo: {i}")


class MainSortedMissionClass:

    SortedMissions: SortedMissionClass = []
    def __init__(self):
        self.SortedMissions = []

    def addSortedMissions(self,DropLocation:str, SCU:int, Item:str):
        bDropLocationFound = False


        for i in self.SortedMissions:
                if DropLocation == i.dropOfLocation:
                    bDropLocationFound = True
                    i.cargo.append([SCU,Item])

        if not bDropLocationFound:
            newSortedMissions = SortedMissionClass()
            newSortedMissions.dropOfLocation = DropLocation
            newSortedMissions.cargo.append([SCU,Item])
            self.SortedMissions.append(newSortedMissions)


    def CheckForMissions(self):
        global MissionList
        self.SortedMissions.clear()

        for i in MissionList.MainMissions:
            for j in i.subMissions:
                for k in j.DropLocations:
                    self.addSortedMissions(k['DropLocation'], k['SCU'], j.Item)

        self.SortedMissions.sort(key=lambda x: x.dropOfLocation) # Sort by Drop Location Name
        self.printSortedMissions()

        

    def printSortedMissions(self):
        for i in self.SortedMissions:
            print(f"{i.dropOfLocation}:")
            for j in i.cargo:
                print(f"   - SCU: {j[0]} Item: {j[1]}")

class SubMissionClass:
    def __init__(self):
        self.Item = ""
        self.PickupLocation = ""
        self.DropLocations = []
        self.PickupInfo = {
            "Item": "",
            "PickupLocation": ""
        }

    Item = ""
    PickupLocation = ""

    DropLocations = []

    PickupInfo = {
        "Item": "",
        "PickupLocation": ""
        }
    
    def addPickupInfo(self, Item:str, PickupLocation:str):
        self.Item = Item
        self.PickupLocation = PickupLocation

    def addDropLocation(self,Item:str, SCU:int, DropLocation:str):
        subMissionDetails = {
        "Item" : Item,
        "SCU" : SCU,
        "DropLocation": DropLocation}
        self.DropLocations.append(subMissionDetails)

    def getMissionDetails(self):
        print(f"    Collect {self.Item} from {self.PickupLocation}")
        for i in self.DropLocations:
            print(f"      - Deliver {i['SCU']} SCU to {i['DropLocation']}")


  
class MainMissionClass:
    def __init__(self):
        self.subMissions = []

    subMissions: SubMissionClass = []

    def addSubMission(self, subMission: SubMissionClass):
        self.subMissions.append(subMission)

    def printSubMissions(self):
        for i in self.subMissions:
                i.getMissionDetails()


class MissionClass:
    def __init__(self):
        self.MainMissions = []

    MainMissions: MainMissionClass = []

    def addMainMission(self, mainMission: MainMissionClass):
        self.MainMissions.append(mainMission)

    def printMainMissions(self):
        for index, i in enumerate(self.MainMissions):
            print(f"Mission: {index+1}")
            i.printSubMissions()
    def reomveMainMissions(self,int):
        try:
            del self.MainMissions[int-1]
        except:
            print("error deleting Mission"+str(int))
                 
    def createSortedMissions(self):
        global SortedMissions
        SortedMissions = []
        


MissionList = MissionClass()
SortedMissions = MainSortedMissionClass()


def getScreenShot():

    bbox = (screen_width*0.62, screen_height*0.25, screen_width*0.9, screen_height*0.70)
    screenshot = ImageGrab.grab(bbox)

    text = pytesseract.image_to_string(screenshot,config='--psm 6')

    getMissionDetails(text)

def getMissionDetails(text):

    text =text.replace('© ', '') #cleanup
    missionText = []

    ocrArray = text.split(r"Collect")
    del ocrArray[0] #remove "primary objectives element"
    for i in ocrArray:
        missionText.append("Collect"+i)

    ocrArray = missionText
    global MissionList
     
    newMission = MainMissionClass()
      
    try:
        for i in ocrArray:
            bFoundPickup = False
            details = i.split(".")
            del details[len(details)-1] # remove last array index, it is empty
            newSubMission = SubMissionClass()
            for i in details:

                if "from" in i:
                    cargo = i.split("Collect ")[1]
                    cargo = cargo.split("from ")[0]
                    cargo = cargo.replace(' ',"")
                    pickup = i.split("from ")[1]
                    newSubMission.addPickupInfo(cargo, pickup)
                    bFoundPickup = True

                if "Deliver" in i:
                    i = i.replace('$',"S").replace('  ',' ').replace('S1DC06','S1DCO6')

                    scu = i.split("Deliver 0/")[1].split(" SCU")[0]
                    target = i.split("to ")[1].replace('\n'," ")
                    newSubMission.addDropLocation(cargo,int(scu), target)
                
            newMission.addSubMission(newSubMission)
        if bFoundPickup:
            MissionList.addMainMission(newMission)
                

    
    except Exception as error:
        print("An exception occurred:", error)

def ShowMissions():
    global bShowSorted

    if bShowSorted:
        os.system('cls')
        SortedMissions.CheckForMissions()
    else:
        os.system('cls')
        MissionList.printMainMissions()

    bShowSorted = not bShowSorted      


def checkForInput():
    global SortedMissions
    while True:
        print("\n\n        NO MISSIONS AVAILABLE\n\n      press 'a' to add missions\n\n")
        key = input(f"\n\n|  'a' add mission  |  '1-{len(MissionList.MainMissions)}' remove mission  |  't' toggle Mission Listing  |  'q' quit  |\nselect: ").lower().replace(" ","")
        
        if key == "t":
            ShowMissions()
        
        elif key == "a":
            getScreenShot()
            os.system('cls')
            MissionList.printMainMissions()
        elif key == "q":
            break
        else:
            try:
                removeIndex = int(key)
                if removeIndex <= len(MissionList.MainMissions):
                    MissionList.reomveMainMissions(removeIndex)

            except ValueError:
                print("not a valid mission number input")
        time.sleep(0.2)
    print("Goodbye")




checkForInput()

