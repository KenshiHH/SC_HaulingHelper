from PIL import ImageGrab
import pytesseract
from flask import Flask
from flask import render_template, request
from flask import redirect
import uuid
import ctypes


####config
bDebug = False

#get screen resolution
user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)


app = Flask(__name__)

class LocationDatabase:
    class Cargo:
        def __init__(self):
            self.itemName = ""
            self.SCUs = 0
            self.missionUUID = 0
            self.pickedUp = False
            self.droppedOff = False
    class DropLocation:
        def __init__(self):
            self.name = ""
            self.cargo = []
    class PickupLocation:
        def __init__(self):
            self.name = ""
            self.cargo = []

    def __init__(self):
        self.dropLocations = []
        self.pickupLocations = []
        self.locationList = []

    def AddPickupLocation(self, PickupLocation:str, Cargo: Cargo):
        bPickupLocationFound = False

        for i in self.pickupLocations:
            if PickupLocation == i.name:
                bPickupLocationFound = True
                i.cargo.append(Cargo)

        if not bPickupLocationFound:
            newPickupLocation = self.PickupLocation()
            newPickupLocation.name = PickupLocation
            newPickupLocation.cargo.append(Cargo)
            self.pickupLocations.append(newPickupLocation)

    def AddDropLocation(self, Drop :str, Cargo: Cargo):
        bDropLocationFound = False

        for i in self.dropLocations:
            if Drop == i.name:
                bDropLocationFound = True
                i.cargo.append(Cargo)

        if not bDropLocationFound:
            newDropLocation = self.DropLocation()
            newDropLocation.name = Drop
            newDropLocation.cargo.append(Cargo)
            self.dropLocations.append(newDropLocation)

    def GetPickupLocations(self):
        return self.pickupLocations
    
    def GetDropLocations(self):
        return self.dropLocations
    
    def GenerateLocationList(self,location: str):
        bfound = False
        locationDetail = {}
        locationDetail["name"] = location
        locationDetail["order"] = len(self.locationList)+1
        locationDetail["done"] = False


        for i in self.locationList:
            if i["name"] == location:
                bfound = True
        if not bfound:
            self.locationList.append(locationDetail)

    def ReorderLocationList(self,new_order):
        newOrder = []
        for i in new_order:
            newOrder.append(self.locationList[int(i)-1])
        self.locationList = newOrder
        for i in self.locationList:
            i["order"] = self.locationList.index(i)+1

    def GenerateDropPickupList(self, missionDatabase, bGenerate:bool = False):
        if not bGenerate:
            if missionDatabase.locationDatabase.locationList:
                return
        self.locationList.clear()
        self.pickupLocations.clear()
        self.dropLocations.clear()
        for i in missionDatabase.mainMissions:
            for j in i.subMissions:
                pickupCargo = LocationDatabase.Cargo()
                pickupCargo.itemName = j.item
                pickupCargo.SCUs = j.scu
                pickupCargo.missionUUID = i.uuid
                missionDatabase.locationDatabase.AddPickupLocation(j.pickupLocation, pickupCargo)
                self.GenerateLocationList(j.pickupLocation)
                for k in j.dropLocations:
                    cargo = LocationDatabase.Cargo()
                    cargo.itemName = j.item
                    cargo.SCUs = k['SCU']
                    cargo.missionUUID = i.uuid
                    missionDatabase.locationDatabase.AddDropLocation(k['DropLocation'], cargo)
                    self.GenerateLocationList(k['DropLocation'])

    def GetPickupList(self,location:str):
        for i in self.pickupLocations:
            if i.name == location:
                return i.cargo
            
    def GetDropList(self,location:str):
        for i in self.dropLocations:
            if i.name == location:
                return i.cargo

    def GetCargoTab3(self,location:str):
        pickupCargo = self.GetPickupList(location)
        dropCargo = self.GetDropList(location)
        template = ["","","",""]
        listenarray :list = []

        pickupCargoLength = len(pickupCargo) if pickupCargo else 0
        dropCargoLength = len(dropCargo) if dropCargo else 0
        maxLength = max(pickupCargoLength, dropCargoLength)

        for i in range(maxLength):
            try:
                if i < pickupCargoLength:
                    template[0] = f"{pickupCargo[i].SCUs}x" 
                    template[1] = f"{pickupCargo[i].itemName}" 
                else:
                    template[0] = ""
                    template[1] = ""
            except:
                ...
            try:
                if i < dropCargoLength:
                    template[2] = f"{dropCargo[i].SCUs}x"  
                    template[3] = f"{dropCargo[i].itemName}"
                else:
                    template[2] = ""
                    template[3] = ""
            except:
                ...
            listenarray.append(template)
            template = ["","","",""]
            
        return listenarray
    
    def ToggleLocationStatus(self,location: str):
        for i in self.locationList:
            if i["name"] == location:
                i["done"] = not i["done"]


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
                for k in j.dropLocations:
                    self.AddSortedMissions(k['DropLocation'], k['SCU'], j.item,i.missionID)

        self.sortedMissions.sort(key=lambda x: x.dropOfLocation) # Sort by Drop Location Name

class SubMission:
    def __init__(self):
        self.item = ""
        self.scu = 0
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
        self.sortedID = 0
        self.auec = 0
        self.uuid = uuid.uuid4()

    def AddSubMission(self, subMission: SubMission):
        self.subMissions.append(subMission)

    def GetID(self):
        return str(self.missionID)
    
    def GetUEC(self):
        return self.auec


class MissionDatabase:
    def __init__(self):
        self.mainMissions: MainMission = []
        self.cargoSCU = 0
        self.sortedMissionManager = SortedMissionManager()
        self.dropOffLocations = {}
        self.pickupLocations = {}
        self.auec = 0
        self.locationDatabase = LocationDatabase()

    def AddMainMission(self, mainMission: MainMission):
        self.mainMissions.append(mainMission)
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()
        self.UpdateAUEC()

    def UpdateMissionIDs(self):
        for i in self.mainMissions:
            i.missionID = self.mainMissions.index(i)+1
            
    def UpdateCargoSCU(self):
        self.cargoSCU = 0
        for i in self.mainMissions:
            for j in i.subMissions:
                for k in j.dropLocations:
                    self.cargoSCU += k['SCU']

    def UpdateAUEC(self):
        self.auec = 0
        for i in self.mainMissions:
            self.auec += i.auec

    def GetAuec(self):
        auec = self.auec
        auec = "{:,}".format(auec).replace(",", ".")
        return auec

    def GetCargoSCU(self):
        return self.cargoSCU

    def EditMissionReward(self,missionID:int,reward:int):
        self.mainMissions[int(missionID)-1].auec = reward
        self.UpdateAUEC()

    def RemoveMainMission(self,int):
        try:
            del self.mainMissions[int-1]
        except:
            print("error deleting Mission"+str(int))
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()
        self.UpdateAUEC()

    def newMissionOrder(self,new_order):
        newOrder: MainMission = []
        newOrder.clear()
        for i in new_order:
            newOrder.append(self.mainMissions[int(i)-1])
        self.mainMissions.clear()
        self.mainMissions = newOrder 
        self.UpdateMissionIDs()

    def GeneratePickupLocations(self):
        self.pickupLocations.clear()
        for i in self.mainMissions:
            for j in i.subMissions:
                self.pickupLocations[j.pickupLocation] = 0                     


missionDatabase = MissionDatabase()

def ExtractReward():
    reward = 0
    auec_coords = (screen_width*0.66, screen_height*0.1, screen_width*0.95, screen_height*0.26)
    screenshot_auec = ImageGrab.grab(auec_coords)
    text = pytesseract.image_to_string(screenshot_auec,config='--psm 6 --oem 3' )
    print(text)
    text = text.split('\n')
    try:
        for i in text:
            if "reward" in i.lower():
                rew = i
                rew = rew[9:]
                rew = rew.replace(" ", "").replace(",", "")
                reward = int(rew)
    except:
        print("reward not found")
        pass

    return reward

def ExtractMissionInfo():
    global missionDatabase

    mission_coords = (screen_width*0.62, screen_height*0.25, screen_width*0.9, screen_height*0.70)
    screenshot = ImageGrab.grab(mission_coords)

    text = pytesseract.image_to_string(screenshot,config='--psm 6 --oem 3')

    stringFixes = {
        '$':"S",
        'Teasa Spaceport':'Teasa Spaceport (Lorville)',
        'HUR-LS':'HUR-L5',
        'S1DCO06':'S1DC06',
        'HUR-L55':'HUR-L5',
        'HUR-LS5':'HUR-L5',
        'HDMS-Periman':'HDMS-Perlman',
        'S1DCO6':'S1DC06',
        'NB Int': 'NB Int. Spaceport (New Babbage)',
        'S4LDO1':'S4LD01',
        'SMCa':'SMCA',
        'Depot SS4LD':'Depot S4LD'
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
                    for k in stringFixes:
                        pickup = pickup.replace(k,stringFixes[k])
                    newSubMission.AddPickupInfo(cargo, pickup)
                    bFoundPickup = True

                if "Deliver" in i:
                    for k in stringFixes:
                        i = i.replace(k,stringFixes[k]) # fix commong ocr errors

                    scu = i.split("Deliver 0/")[1].split(" SCU")[0]
                    newSubMission.scu += int(scu)
                    target = i.split("to ")[1].replace('\n'," ")
                    newSubMission.AddDropLocation(cargo,int(scu), target)

            newMission.AddSubMission(newSubMission)
        if bFoundPickup:
            newMission.auec = ExtractReward()
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

    newMission = MainMission()
    newSubMission = SubMission()
    newSubMission.AddPickupInfo("Iron Ore", "Earth")
    newSubMission.AddDropLocation("Iron Ore", 1, "Port Tresser")
    newSubMission.AddDropLocation("Iron Ore", 12, "Pyro")
    newMission.AddSubMission(newSubMission)
    newMission.missionID = 2
    missionDatabase.AddMainMission(newMission)

    newMission = MainMission()
    newSubMission = SubMission()
    newSubMission.AddPickupInfo("Copper", "Pyro")
    newSubMission.AddDropLocation("Copper", 1, "Mars")
    newSubMission.AddDropLocation("Copper", 12, "Jupiter")
    newSubMission.AddDropLocation("Copper", 12, "Pyro")
    newMission.AddSubMission(newSubMission)
    newMission.missionID = 3
    missionDatabase.AddMainMission(newMission)


@app.route('/')
def index():
    return render_template('index.html', missionDatabase=missionDatabase)

@app.route('/edit/<id>/<auec>', methods=['PUT'])
def editReward(id,auec):
    print("editreward",id,auec)
    missionDatabase.EditMissionReward(int(id),int(auec))
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/delete/<id>', methods=['DELETE'])
def delete(id):
    missionDatabase.RemoveMainMission(int(id))
    missionDatabase.sortedMissionManager.CheckForMissions()
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase,True)
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/add/', methods=['POST'])
def AddMission():
    ExtractMissionInfo()
    missionDatabase.sortedMissionManager.CheckForMissions()
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase,True)
    return redirect("/")

@app.route('/toggle/<location>', methods=['POST'])
def ToggleLocation(location):
    missionDatabase.locationDatabase.ToggleLocationStatus(location)
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/update-order', methods=['POST'])
def update_order():
    new_order = request.json.get('order', [])
    if bDebug:
        print("Neue Sortierung:", new_order)
    missionDatabase.locationDatabase.ReorderLocationList(new_order)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/route', methods=['GET'])
def route():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/stations', methods=['POST'])
def stations():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('stations.html', missionDatabase=missionDatabase)

@app.route('/tab1', methods=['GET'])
def tab1():
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/tab2', methods=['GET'])
def tab2():
    missionDatabase.sortedMissionManager.CheckForMissions()
    return render_template('tab2.html', missionDatabase=missionDatabase)

@app.route('/tab3', methods=['GET'])
def tab3():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('tab3.html', missionDatabase=missionDatabase)



if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')