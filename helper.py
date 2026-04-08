from PIL import ImageGrab, ImageOps, ImageFilter
import pytesseract
from flask import Flask
from flask import render_template, request
from flask import redirect
import uuid
import ctypes
import os
import re
from rapidfuzz import process, fuzz
import cv2
import numpy as np

####config
bDebug = False
bTestMissions = False
bLocalTest = False
currentLocalScreenshot = 0

#get screen resolution
user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)

#load json for ocr string fixes
import requests
import json
ocr_string_fixes = json.loads(requests.get("https://github.com/KenshiHH/SC_HaulingHelper/raw/refs/heads/ocrfixes/ocrfixes.json").text)
known_locations = json.loads(requests.get("https://github.com/KenshiHH/SC_HaulingHelper/raw/refs/heads/main/known_locations.json").text)

# Moving the space between letters and numbers
blacklist_chars = '!@#$%^&*()_+-=[]{}|;\'"<>?~`\\¬¦'

# If the game uses those diamond bullet points, add them too:
game_icons = '◇◆□■○●'

custom_config = f'--oem 3 --psm 6 -c tessedit_char_blacklist={blacklist_chars}{game_icons}'

def fix_location(raw: str, threshold: int = 90) -> str:
    if raw in known_locations:
        for k in ocr_string_fixes:
            if k in raw:
                raw = raw.replace(k, ocr_string_fixes[k])
        return raw
    result = process.extractOne(raw, known_locations, scorer=fuzz.WRatio)
    if result and result[1] >= threshold:
        return result[0]
    return raw  # no confident match → keep original

def getLocationGroups():
    global missionDatabase

    return

# Set the path to tesseract.exe in the same folder as the script
script_dir = os.path.dirname(os.path.abspath(__file__))+"\\Tesseract-OCR"

pytesseract.pytesseract.tesseract_cmd = os.path.join(script_dir, 'tesseract.exe')
if not os.path.exists(os.path.join(script_dir, 'tesseract.exe')):
    raise Exception("tesseract.exe not found in path: "+script_dir)

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
    
    if bLocalTest:
        global currentLocalScreenshot
        y1 = int(screen_height * 0.01)
        y2 = int(screen_height * 0.26)
        x1 = int(screen_width * 0.66)
        x2 = int(screen_width * 0.95)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, '4_7', f'test_{currentLocalScreenshot}.png')
        screenshot_auec = cv2.imread(image_path)
        screenshot_auec = screenshot_auec[y1:y2, x1:x2]
    else:
        auec_coords = (screen_width*0.66, screen_height*0.1, screen_width*0.95, screen_height*0.26)
        screenshot_auec = ImageGrab.grab(auec_coords)
        screenshot_auec = np.array(screenshot_auec)
    screenshot_auec = cv2.resize(screenshot_auec, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    screenshot_auec = cv2.cvtColor(screenshot_auec, cv2.COLOR_RGB2GRAY)
    screenshot_auec = cv2.bitwise_not(screenshot_auec)

    text = pytesseract.image_to_string(screenshot_auec,config=custom_config)
    print(text)
    text = text.split('\n')
    

    try:
        for i in text:
            if "reward" in i.lower():
                rew = i.rsplit(' ', 1)[-1]
                rew = rew.replace(",", "")
                reward = int(rew)
    except:
        print("reward not found")
        pass

    return reward

def ExtractMissionInfo():
    global missionDatabase
    global ocr_string_fixes

    if bLocalTest:
        global currentLocalScreenshot
        y1 = int(screen_height * 0.25)
        y2 = int(screen_height * 0.7)
        x1 = int(screen_width * 0.62)
        x2 = int(screen_width * 0.9)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, '4_7', f'test_{currentLocalScreenshot}.png')
        screenshot = cv2.imread(image_path)
        screenshot = screenshot[y1:y2, x1:x2]
    else:
        mission_coords = (screen_width*0.62, screen_height*0.25, screen_width*0.9, screen_height*0.70)
        screenshot = ImageGrab.grab(mission_coords)
        screenshot = np.array(screenshot)
    screenshot = cv2.resize(screenshot, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
    screenshot = cv2.bitwise_not(screenshot)
    text = pytesseract.image_to_string(screenshot,config=custom_config)
    print(text)

    text = text.replace('© ', '') #cleanup
    
    missionText = []
    if bDebug:
        print("OCR Text:")
        print(text)
        print("---END---")

    text = re.sub(r'PRIMARY OBJECTIVES\s*\n', '', text)
    text = re.sub(r'[^\w\s\n./\-]+\s*(?=Deliver)', '', text)
    text = re.sub(r'[\|\s]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!\.)(\n)(?=[A-Z][a-z])', ' ', text)
    ocrArray = re.split(r'(?=Deliver)', text)
    ocrArray = [p.strip() for p in ocrArray if p.strip()]



    #del ocrArray[len(ocrArray)-1] #remove last array index, it is empty

    #ocrArray = missionText
    newMission = MainMission()

    try:
        print("ocr: "+str(len(ocrArray)))
        for i in ocrArray:
            newSubMission = SubMission()
            print("pattern test string: "+i)
            PATTERN = re.compile(
                r'Deliver \d+/(?P<scu>\d+) SCU of (?P<cargo>[\w\s]+?) to (?P<deliver_target>.+?)\.'
                r'.*?'
                r'Collect \w+ from (?P<collect_from>.+?)(?:\.|$)',
                re.DOTALL
            )
            m = PATTERN.search(i)
            if m:
                scu    = int(m.group('scu'))            # 3
                cargo    = m.group('cargo')                 # "Corundum"
                target = m.group('deliver_target')      # "Teasa Spaceport in Lorville"
                pickup = m.group('collect_from')        # "Everus Harbor"
            
            target = fix_location(target)
            pickup = fix_location(pickup)
            for k in ocr_string_fixes:
                if k in target:
                    target = target.replace(k, ocr_string_fixes[k])
                if k in pickup:
                    pickup = pickup.replace(k, ocr_string_fixes[k])

            print(f"Extracted: \n{scu} SCU \n{cargo} \nto {target}\ncollect from {pickup}")
            newSubMission.scu += int(scu)
            newSubMission.AddPickupInfo(cargo, pickup)
            newSubMission.AddDropLocation(cargo,int(scu), target)
            newMission.AddSubMission(newSubMission)
            newMission.auec = ExtractReward()
        missionDatabase.AddMainMission(newMission)
            
    except Exception as error:
        print("Error extracting mission info")
        print("An exception occurred:", error)



if bDebug and bTestMissions: # creates test missions
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
    global currentLocalScreenshot
    if bLocalTest:
        currentLocalScreenshot += 1
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