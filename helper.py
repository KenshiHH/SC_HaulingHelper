from PIL import ImageGrab
import pytesseract
import tkinter as tk
from flask import Flask
from flask import render_template
from flask import redirect


####config
bDebug = False

root = tk.Tk()

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

root.destroy() # destroys initial window

bShowSorted = False

app = Flask(__name__)


class SortedMission:
    def __init__(self):
        self.dropOfLocation = ""
        self.cargo = []

class SortedMissionManager:

    def __init__(self):
        self.sortedMissions: SortedMission = []

    def AddSortedMissions(self,DropLocation:str, SCU:int, Item:str, MissionID:int):
        bDropLocationFound = False

        for i in self.sortedMissions:
                if DropLocation == i.dropOfLocation:
                    bDropLocationFound = True
                    i.cargo.append([SCU,Item,MissionID])

        if not bDropLocationFound:
            newSortedMissions = SortedMission()
            newSortedMissions.dropOfLocation = DropLocation
            newSortedMissions.cargo.append([SCU,Item,MissionID])
            self.sortedMissions.append(newSortedMissions)

    def CheckForMissions(self):
        global missionDatabase
        self.sortedMissions.clear()

        for i in missionDatabase.mainMissions:
            for j in i.subMissions:
                for k in j.DropLocations:
                    self.AddSortedMissions(k['DropLocation'], k['SCU'], j.Item,i.MissionID)

        self.sortedMissions.sort(key=lambda x: x.dropOfLocation) # Sort by Drop Location Name

class SubMission:
    def __init__(self):
        self.item = ""
        self.pickupLocation = ""
        self.dropLocations = []
        self.pickupInfo = {
            "Item": "",
            "PickupLocation": ""
        }

    def AddPickupInfo(self, Item:str, PickupLocation:str):
        self.item = Item
        self.pickupLocation = PickupLocation

    def AddDropLocation(self,Item:str, SCU:int, DropLocation:str):
        subMissionDetails = {
        "Item" : Item,
        "SCU" : SCU,
        "DropLocation": DropLocation}
        self.dropLocations.append(subMissionDetails)

    def GetMissionText(self):
        return f"{self.item} from {self.pickupLocation}"


class MainMission:
    def __init__(self):
        self.subMissions: SubMission = []
        self.missionID = 0

    def AddSubMission(self, subMission: SubMission):
        self.subMissions.append(subMission)

    def GetID(self):
        return str(self.missionID)


class MissionDatabase:
    def __init__(self):
        self.mainMissions: MainMission = []
        self.cargoSCU = 0
        self.SortedMissions = SortedMissionManager()

    def AddMainMission(self, mainMission: MainMission):
        self.mainMissions.append(mainMission)
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()

    def UpdateMissionIDs(self):
        for i in self.mainMissions:
            i.MissionID = self.mainMissions.index(i)+1

    def UpdateCargoSCU(self):
        self.cargoSCU = 0
        for i in self.mainMissions:
            for j in i.subMissions:
                for k in j.DropLocations:
                    self.cargoSCU += k['SCU']

    def GetCargoSCU(self):
        return self.cargoSCU

    def RemoveMainMission(self,int):
        try:
            del self.mainMissions[int-1]
        except:
            print("error deleting Mission"+str(int))
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()                       


missionDatabase = MissionDatabase()


def ExtractMissionInfo():
    global missionDatabase

    bbox = (screen_width*0.62, screen_height*0.25, screen_width*0.9, screen_height*0.70)
    screenshot = ImageGrab.grab(bbox)

    text = pytesseract.image_to_string(screenshot,config='--psm 6 --oem 1')

    stringFixes = {
        '$':"S",
        'S1DC06':'S1DCO6',
        'HUR-LS':'HUR-L5',
        'S1DCO06':'S1DCO6',
        'HUR-L55':'HUR-L5'
    }

    text =text.replace('© ', '') #cleanup
    missionText = []

    ocrArray = text.split(r"Collect")
    del ocrArray[0] #remove "primary objectives element"
    for i in ocrArray:
        missionText.append("Collect"+i)

    ocrArray = missionText
    newMission = MainMission()

    try:
        for i in ocrArray:
            bFoundPickup = False
            details = i.split(".")
            del details[len(details)-1] # remove last array index, it is empty
            newSubMission = SubMission()
            for i in details:

                if "from" in i:
                    cargo = i.split("Collect ")[1]
                    cargo = cargo.split("from ")[0]
                    cargo = cargo.replace(' ',"")
                    pickup = i.split("from ")[1]
                    newSubMission.AddPickupInfo(cargo, pickup)
                    bFoundPickup = True

                if "Deliver" in i:
                    for k in stringFixes:
                        i = i.replace(k,stringFixes[k]) # fix commong ocr errors

                    scu = i.split("Deliver 0/")[1].split(" SCU")[0]
                    target = i.split("to ")[1].replace('\n'," ")
                    newSubMission.AddDropLocation(cargo,int(scu), target)

            newMission.AddSubMission(newSubMission)
        if bFoundPickup:
            missionDatabase.AddMainMission(newMission)

    except Exception as error:
        print("An exception occurred:", error)

if bDebug: # creates test missions
    newMission = MainMission()
    newSubMission = SubMission()
    newSubMission.AddPickupInfo("Stims", "Everus Harbor")
    newSubMission.AddDropLocation("Stims", 1, "Port Tresser")
    newSubMission.AddDropLocation("Stims", 12, "Pyro")
    newMission.AddSubMission(newSubMission)
    newMission.missionID = 1
    missionDatabase.AddMainMission(newMission)


@app.route('/')
def index():
    global bShowSorted
    if bShowSorted:
        return render_template('index2.html', sortedMissionList=missionDatabase.SortedMissions)
    else:
        return render_template('index.html', missionList=missionDatabase)

@app.route('/delete/<id>')
def delete(id):
    missionDatabase.RemoveMainMission(int(id))
    missionDatabase.SortedMissions.CheckForMissions()
    return redirect("/")

@app.route('/add/')
def AddMission():
    ExtractMissionInfo()
    missionDatabase.SortedMissions.CheckForMissions()
    return redirect("/")

@app.route('/toggle/')
def ToggleView():
    global bShowSorted
    bShowSorted = not bShowSorted
    return redirect("/")


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')