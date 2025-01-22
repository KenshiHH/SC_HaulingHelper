from PIL import ImageGrab
import pytesseract
import tkinter as tk
from flask import Flask
from flask_scss import Scss
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


class SortedMissionClass:
    def __init__(self):
        self.dropOfLocation = ""
        self.cargo = []

    def printInfo(self):
        print(f"Drop of Location: {self.dropOfLocation}")
        for i in self.cargo:
            print(f"Cargo: {i}")


class MainSortedMissionClass:

    def __init__(self):
        self.SortedMissions: SortedMissionClass = []

    def addSortedMissions(self,DropLocation:str, SCU:int, Item:str, MissionID:int):
        bDropLocationFound = False

        for i in self.SortedMissions:
                if DropLocation == i.dropOfLocation:
                    bDropLocationFound = True
                    i.cargo.append([SCU,Item,MissionID])

        if not bDropLocationFound:
            newSortedMissions = SortedMissionClass()
            newSortedMissions.dropOfLocation = DropLocation
            newSortedMissions.cargo.append([SCU,Item,MissionID])
            self.SortedMissions.append(newSortedMissions)

    def CheckForMissions(self):
        global MissionList
        self.SortedMissions.clear()

        for i in MissionList.MainMissions:
            for j in i.subMissions:
                for k in j.DropLocations:
                    self.addSortedMissions(k['DropLocation'], k['SCU'], j.Item,i.MissionID)

        self.SortedMissions.sort(key=lambda x: x.dropOfLocation) # Sort by Drop Location Name

    def printSortedMissions(self):
        for i in self.SortedMissions:
            print(f"{i.dropOfLocation}:")
            for j in i.cargo:
                print(f"   - SCU: {j[0]} \t {j[1]}\t\t\tMission# {str(j[2])}")

class SubMissionClass:
    def __init__(self):
        self.Item = ""
        self.PickupLocation = ""
        self.DropLocations = []
        self.PickupInfo = {
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
    
    def getMissionText(self):
        return f"{self.Item} from {self.PickupLocation}"


class MainMissionClass:
    def __init__(self):
        self.subMissions: SubMissionClass = []
        self.MissionID = 0

    def addSubMission(self, subMission: SubMissionClass):
        self.subMissions.append(subMission)

    def printSubMissions(self):
        for i in self.subMissions:
                i.getMissionDetails()
    
    def getID(self):
        return str(self.MissionID)
    


class MissionClass:
    def __init__(self):
        self.MainMissions: MainMissionClass = []
        self.cargoSCU = 0
        self.SortedMissions = MainSortedMissionClass()

    def addMainMission(self, mainMission: MainMissionClass):
        self.MainMissions.append(mainMission)
        self.updateMissionIDs()
        self.updateCargoSCU()

    def updateMissionIDs(self):
        for i in self.MainMissions:
            i.MissionID = self.MainMissions.index(i)+1

    def updateCargoSCU(self):
        self.cargoSCU = 0
        for i in self.MainMissions:
            for j in i.subMissions:
                for k in j.DropLocations:
                    self.cargoSCU += k['SCU']

    def getCargoSCU(self):
        return self.cargoSCU

    def reomveMainMissions(self,int):
        try:
            del self.MainMissions[int-1]
        except:
            print("error deleting Mission"+str(int))
        self.updateMissionIDs()
        self.updateCargoSCU()                       


MissionList = MissionClass()


def getMissionDetails():

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
                    for k in stringFixes:
                        i = i.replace(k,stringFixes[k]) # fix commong ocr errors

                    scu = i.split("Deliver 0/")[1].split(" SCU")[0]
                    target = i.split("to ")[1].replace('\n'," ")
                    newSubMission.addDropLocation(cargo,int(scu), target)
                
            newMission.addSubMission(newSubMission)
        if bFoundPickup:
            MissionList.addMainMission(newMission)

    except Exception as error:
        print("An exception occurred:", error)

if bDebug: # creates test missions
    newMission = MainMissionClass()
    newSubMission = SubMissionClass()
    newSubMission.addPickupInfo("Stims", "Everus Harbor")
    newSubMission.addDropLocation("Stims", 1, "Port Tresser")
    newSubMission.addDropLocation("Stims", 12, "Pyro")
    newMission.addSubMission(newSubMission)
    newMission.MissionID = 1
    MissionList.addMainMission(newMission)


@app.route('/')
def index():
    global bShowSorted
    if bShowSorted:
        return render_template('index2.html', sortedMissionList=MissionList.SortedMissions)
    else:
        return render_template('index.html', missionList=MissionList)

@app.route('/delete/<id>')
def delete(id):
    MissionList.reomveMainMissions(int(id))
    MissionList.SortedMissions.CheckForMissions()
    return redirect("/")

@app.route('/add/')
def AddMission():
    getMissionDetails()
    MissionList.SortedMissions.CheckForMissions()
    return redirect("/")

@app.route('/toggle/')
def ToggleView():
    global bShowSorted
    bShowSorted = not bShowSorted
    return redirect("/")


if __name__ == '__main__':
    app.run(debug=False)